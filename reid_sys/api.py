"""Smart Gateway：对外暴露 HTTP 接口，并托管 React 前端构建产物（web/dist）。

对齐 docs/SYSTEM.md §7 —— 上层业务只需要「传图/传向量 + 时间范围」，不感知底层
检测、特征、向量库的细节。

.. note::
   **当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。**
   本模块的接口形状、字段命名、错误码均可能随验证结论调整，请勿作为对外契约使用。
"""

from __future__ import annotations

import base64
import random
import threading
from pathlib import Path

import cv2
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import ROOT
from . import datasets as ds_registry
from .detect import PersonTracker, detect_persons, make_demo_sequence
from .engine import (
    GALLERY_DIR,
    IMAGE_SUFFIXES,
    PROBE_DIR,
    ReIDEngine,
    imdecode,
    imread,
    list_images,
    parse_name,
)
from .schemas import (
    Camera,
    CameraNetwork,
    CameraStatus,
    DatasetList,
    DatasetSelect,
    EdgeStatus,
    K8sOverview,
    MapTrack,
    ProbeResult,
    RolloutRequest,
    RolloutResponse,
    WatchlistAlerts,
)
from .services import get_provider

WEB_DIST = ROOT / "web" / "dist"

app = FastAPI(
    title="跨镜头 Re-ID 系统（可行性验证）",
    version="0.1.0",
    description=(
        "当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。\n\n"
        "**未接入能力的接口契约**：摄像头监控 / 边缘节点 / K8s 编排 / 布控告警等能力"
        "当前尚未接入真实服务，但接口与数据结构已定义（见 `/openapi.json` 与 `reid_sys/schemas.py`）；"
        "调用时响应会带 `connected: false` 并返回模拟或空数据，接入真实服务后无需改动前端。"
    ),
)

_lock = threading.Lock()
_backbone = None
_engines: dict[str, ReIDEngine] = {}
_current: str | None = None


def get_backbone():
    """懒加载 backbone（全数据集共用同一份权重与显存）。"""
    global _backbone
    if _backbone is None:
        with _lock:
            if _backbone is None:
                from .backbone import FastReIDBackbone

                _backbone = FastReIDBackbone()
    return _backbone


def _available() -> list[ds_registry.Dataset]:
    return ds_registry.discover()


def _resolve_current() -> str | None:
    """当前数据集：显式选择过就用它，否则回退到第一个可用的。"""
    global _current
    avail = {d.name for d in _available()}
    if _current in avail:
        return _current
    _current = next(iter(sorted(avail)), None)
    return _current


def get_dataset(name: str | None = None) -> ds_registry.Dataset:
    """取数据集元信息；name 为空则取当前数据集。"""
    target = name or _resolve_current()
    if target is None:
        raise HTTPException(503, "data/ 下没有符合 query/gallery/meta.json 结构的 demo 数据集")
    found = ds_registry.get(target)
    if found is None:
        raise HTTPException(404, f"未找到数据集 {target}")
    return found


def get_engine(name: str | None = None) -> ReIDEngine:
    """取某个数据集对应的引擎（含各自的 Milvus collection），按需懒加载并缓存。

    首次请求时才载入权重、建库，避免 import 期就吃满显存。
    """
    target = (name or _resolve_current())
    if target is None:
        raise HTTPException(503, "data/ 下没有可用的 demo 数据集")
    if target not in _engines:
        with _lock:
            if target not in _engines:
                from .store import MilvusStore

                dataset = get_dataset(target)
                backbone = get_backbone()
                store = MilvusStore(dim=backbone.dim, collection=dataset.collection)
                _engines[target] = ReIDEngine.for_dataset(backbone, dataset, store=store)
    return _engines[target]


def to_data_url(image) -> str:
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise HTTPException(500, "图片编码失败")
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def _entry(name: str, split: str, dataset: str | None = None) -> dict:
    """构造一条图片条目。split 为 query/gallery；url 带上数据集以便切换后仍能取图。"""
    ds = dataset or _resolve_current()
    q = f"?dataset={ds}" if ds else ""
    return {
        **parse_name(name),
        "split": split,
        "dataset": ds,
        "url": f"/api/image/{split}/{name}{q}",
    }


# ---------------------------------------------------------------- 状态 / 数据

#: 本机演示态的部署画像。docs/SYSTEM.md 设计原则 #5 要求全量单元以标准 Docker 镜像
#: 封装、由 K3s（边侧）/ K8s（云侧）统一编排；当前单进程直跑只是「本地调试形态」，
#: 因此这里显式标注 mode=local-process、containerized=False，前端据此打「未接入」标。
DEPLOYMENT = {
    "principle": "计算容器化封装与 K8s 统一编排",
    "mode": "local-process",
    "orchestrator": "none",
    "containerized": False,
    "edge_runtime": "K3s (设计)",
    "cloud_runtime": "K8s (设计)",
    "registry": "registry.reid.local (设计)",
    "note": "当前为单进程本地调试形态，未接入容器编排",
}


@app.get("/api/status")
def status(dataset: str | None = Query(default=None, description="数据集名；缺省用当前数据集")):
    engine = get_engine(dataset)
    dataset_meta = get_dataset(dataset)
    return {
        **engine.status(),
        "dataset": dataset_meta.name,
        "dataset_title": dataset_meta.title,
        "detector": "yolo26n.pt + ByteTrack",
        "tracker_interval": 30,
        "milvus_uri": engine.store.uri,
        "image_suffixes": list(IMAGE_SUFFIXES),
        "deployment": DEPLOYMENT,
    }


# ---------------------------------------------------------------- 数据集注册

def _dataset_info(d: ds_registry.Dataset) -> dict:
    """给数据集补上「已索引条数」，用于判断是否 ready。"""
    indexed = None
    try:
        from .store import MilvusStore

        store = MilvusStore(dim=get_backbone().dim, collection=d.collection)
        indexed = store.count()
        store.close()
    except Exception:  # noqa: BLE001 —— 集合不存在/库未建时按「未索引」处理
        indexed = None
    total = d.gallery_total
    return {
        **d.summary(),
        "indexed": indexed,
        "ready": indexed == total and total > 0,
    }


@app.get("/api/datasets", response_model=DatasetList)
def datasets_list():
    """列出 `data/` 下所有符合 query/gallery/meta.json 结构的 demo 数据集。

    .. note:: 每个数据集对应一个独立的 Milvus collection（`reid_<目录名>`）。
    """
    items = [_dataset_info(d) for d in _available()]
    return {"current": _resolve_current(), "items": items}


@app.post("/api/datasets/select", response_model=DatasetList)
def datasets_select(req: DatasetSelect):
    """切换当前数据集 —— 后续 `search/detect/eval` 等默认用它。

    只是切「当前指针」，不触发重建；集合缺索引时用 `scripts/init_data.py` 或
    `POST /api/index` 补建。
    """
    target = ds_registry.get(req.name)
    if target is None:
        raise HTTPException(404, f"未找到数据集 {req.name}")
    global _current
    _current = target.name
    # 预热引擎，避免切换后第一次检索还要等建库
    get_engine(target.name)
    items = [_dataset_info(d) for d in _available()]
    return {"current": _current, "items": items}


@app.get("/api/probe")
def probe_list(dataset: str | None = Query(default=None)):
    engine = get_engine(dataset)
    names = list_images(engine.probe_dir)
    return {"total": len(names), "items": [_entry(n, "query", dataset) for n in names]}


@app.get("/api/gallery")
def gallery_list(
    offset: int = 0,
    limit: int = 60,
    q: str = "",
    dataset: str | None = Query(default=None),
):
    engine = get_engine(dataset)
    names = list_images(engine.gallery_dir)
    if q:
        names = [n for n in names if q in n]
    page = names[offset : offset + limit]
    return {
        "total": len(names),
        "offset": offset,
        "limit": limit,
        "items": [_entry(n, "gallery", dataset) for n in page],
    }


# ---------------------------------------------------- 摄像头 / 边缘节点台账
# 这些能力当前**尚未接入**真实设备管理平台，但接口契约已定义；调用返回模拟数据并标
# connected=False。接入真实平台时替换 services.PROVIDERS['device'] 即可。

@app.get("/api/cameras", response_model=CameraNetwork)
def cameras():
    """摄像头与边缘节点台账。

    .. note:: 数据来自 `web/src/config/cameras.json`，是**模拟组态**，
       尚未接入真实设备管理平台。当前项目仅仅作为前期可行性验证使用，
       部分代码沿用但并不代表最终系统。
    """
    return get_provider("device").cameras()


@app.get("/api/cameras/{camera_id}", response_model=Camera)
def camera_detail(camera_id: str):
    """单个摄像头/边缘节点详情。字段 `status`、`stream_url` 在未接入态恒为空。"""
    hit = get_provider("device").camera_detail(camera_id)
    if hit is None:
        raise HTTPException(404, f"未找到设备 {camera_id}")
    return hit


@app.post("/api/cameras/ping", response_model=list[ProbeResult])
def camera_ping(ids: list[str] | None = Query(default=None, description="可选，仅探测这些设备 id")):
    """批量存活探测 —— 尚未接入真实设备，返回全量 offline。"""
    return get_provider("device").ping(ids)


@app.get("/api/map/track", response_model=MapTrack)
def map_track(person: str = Query("P-0001")):
    """跨镜头轨迹 —— 未接入态只回放配置里的示例轨迹，不含真实时空数据。"""
    hit = get_provider("track").track(person)
    if hit is None:
        raise HTTPException(404, f"未找到轨迹 {person}")
    return hit


# ---------------------------------------------------------- 实时监控（未接入）
# 以下接口对应前端「摄像头监控 / 边缘节点」页：**契约已定义、服务尚未接入**。
# 当前返回表格骨架与留空的实时指标，接入采集服务后替换 provider 即可。

@app.get("/api/monitor/cameras", response_model=CameraStatus)
def monitor_cameras():
    """摄像头实时监控指标（ping / fps / NPU 负载 / 视频流状态）。

    .. note:: 尚未接入真实设备管理平台，实时指标为空、`connected=false`。
    """
    return get_provider("monitor").camera_status()


@app.get("/api/monitor/edges", response_model=EdgeStatus)
def monitor_edges():
    """边缘节点实时监控指标（节点健康度 / 算力负载 / K3s Pod）。

    .. note:: 尚未接入 Kubernetes（K3s）API 与节点 Exporter，指标为空、`connected=false`。
    """
    return get_provider("monitor").edge_status()


# ------------------------------------------------------------ K8s 编排（未接入）

@app.get("/api/k8s/workloads", response_model=K8sOverview)
def k8s_workloads():
    """编排工作负载清单（设计原则 #5）。

    .. note:: 尚未接入 K3s/K8s 集群，`ready`/`status` 与集群聚合指标为空、`connected=false`。
    """
    return get_provider("orchestrator").workloads()


@app.post("/api/k8s/rollout", response_model=RolloutResponse)
def k8s_rollout(req: RolloutRequest):
    """灰度/滚动升级 —— 未接入集群时只回显计划，不真正执行。"""
    return get_provider("orchestrator").rollout(req.model_dump())


# ------------------------------------------------------------ 布控告警（未接入）

@app.get("/api/watchlist/alerts", response_model=WatchlistAlerts)
def watchlist_alerts(limit: int = Query(50, ge=1, le=500)):
    """布控告警流水 —— 尚未接入告警通道（MQTT / Pulsar），返回空列表、`connected=false`。"""
    return get_provider("watchlist").alerts(limit=limit)


@app.get("/api/image/{split}/{name}")
def image(split: str, name: str, dataset: str | None = Query(default=None)):
    engine = get_engine(dataset)
    directory = {"query": engine.probe_dir, "probe": engine.probe_dir, "gallery": engine.gallery_dir}.get(split)
    if directory is None or Path(name).name != name:
        raise HTTPException(404, "非法路径")
    path = directory / name
    if not path.is_file():
        raise HTTPException(404, "图片不存在")
    return FileResponse(path, media_type="image/jpeg")


# ---------------------------------------------------------------- 特征录入

@app.post("/api/index")
def index_gallery(dataset: str | None = Query(default=None)):
    """重建某个数据集的底库索引。"""
    ds = get_dataset(dataset)
    engine = get_engine(ds.name)
    return {**engine.index_gallery(), "dataset": ds.name}


# ---------------------------------------------------------------- 检索

@app.post("/api/search/probe")
def search_probe(
    name: str = Query(...),
    topk: int = Query(10, ge=1, le=50),
    dataset: str | None = Query(default=None),
):
    engine = get_engine(dataset)
    hits = engine.search_by_name(name, topk=topk)
    return {
        "query": _entry(name, "query", dataset),
        "truth": parse_name(name)["person_id"],
        "hits": [
            _entry(h["id"], "gallery", dataset) | {"score": h["score"], "person_id": h["person_id"]}
            for h in hits
        ],
    }


@app.post("/api/search/upload")
def search_upload(
    file: UploadFile = File(...),
    topk: int = Query(10, ge=1, le=50),
    dataset: str | None = Query(default=None),
):
    image = imdecode(file.file.read())
    engine = get_engine(dataset)
    hits = engine.search([image], topk=topk)[0]
    return {
        "query_image": to_data_url(image),
        "hits": [
            _entry(h["id"], "gallery", dataset) | {"score": h["score"], "person_id": h["person_id"]}
            for h in hits
        ],
    }


@app.get("/api/eval")
def evaluate(topk: int = Query(10, ge=5, le=50), dataset: str | None = Query(default=None)):
    return get_engine(dataset).evaluate(topk=topk)


# ---------------------------------------------------------------- 端侧检测 / 去重

@app.post("/api/detect")
def detect(file: UploadFile = File(...)):
    image = imdecode(file.file.read())
    persons = detect_persons(image)
    height, width = image.shape[:2]
    return {
        "image": to_data_url(image),
        "width": width,
        "height": height,
        "count": len(persons),
        "persons": [
            {"box": list(p["box"]), "score": round(p["score"], 4), "crop": to_data_url(p["crop"])}
            for p in persons
        ],
    }


@app.post("/api/detect/track-demo")
def track_demo(
    persons: int = Query(3, ge=1, le=6),
    frames: int = Query(90, ge=30, le=300),
    interval: int = Query(30, ge=5, le=120),
    dataset: str | None = Query(default=None),
):
    """用数据集裁图合成一段多目标移动序列，跑真实的 yolo26n + ByteTrack + 去重。"""
    engine = get_engine(dataset)
    names = random.sample(list_images(engine.gallery_dir), persons)
    crops = [imread(engine.gallery_dir / n) for n in names]
    tracker = PersonTracker(interval=interval)
    tracker.reset()
    emits = list(tracker.stream(make_demo_sequence(crops, frames=frames)))
    return {
        "sources": [_entry(n, "gallery", dataset) for n in names],
        "interval": interval,
        "stats": tracker.stats(),
        "timeline": [{"frame": e.frame, "track_id": e.track_id, "reason": e.reason} for e in emits],
        "samples": [{"frame": e.frame, "track_id": e.track_id, "reason": e.reason, "crop": to_data_url(e.crop)} for e in emits if e.crop is not None][:12],
    }


# ---------------------------------------------------------------- 前端静态资源

if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
