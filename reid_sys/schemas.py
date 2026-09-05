"""未接入能力的接口数据结构（Pydantic v2）。

本模块只定义 **契约**，不含任何实现：为「仅展示、尚未接入真实服务」的功能
（摄像头监控 / 边缘节点 / K8s 编排 / 地图轨迹 / 布控告警）描述请求与响应形状。
真实服务接入后，只需替换 `services.py` 里的 provider 实现，schema 与前端无需改动。

设计约定
--------
* 所有面向「尚未接入」能力的响应，顶层都带 `connected: bool`；
  `connected=False` 表示当前返回的是模拟/空数据，前端据此打「未接入」标。
* 分页统一 `{total, offset, limit, items}`。
* 时间字段一律为 UTC ISO-8601 字符串（可空，表示该字段当前无真实数据）。
* 命名用 snake_case，与既有 `/api/status` 等接口保持一致。

.. note::
   **当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。**
   这些 schema 描述的是**接入后**的契约，当前由 stub provider 返回模拟值。
"""

from __future__ import annotations

from enum import Enum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


# --------------------------------------------------------------------- 通用

class DatasetInfo(BaseModel):
    """一个 demo 数据集的摘要（`data/` 下含 query/gallery/meta.json 的目录）。"""

    name: str = Field(description="目录名，如 data1")
    title: str = Field(description="显示名，来自 meta.json")
    description: str | None = None
    collection: str = Field(description="对应的 Milvus collection 名")
    query_total: int
    gallery_total: int
    metric_note: str | None = None
    indexed: int | None = Field(default=None, description="该集合已索引条数；未建库时为空")
    ready: bool = Field(default=False, description="是否已完整索引（indexed == gallery_total）")


class DatasetList(BaseModel):
    """`GET /api/datasets` 响应。"""

    current: str | None = Field(default=None, description="当前选中的数据集名")
    items: list[DatasetInfo] = Field(default_factory=list)


class DatasetSelect(BaseModel):
    """`POST /api/datasets/select` 请求体。"""

    name: str = Field(description="目标数据集名")


class ZoneId(str, Enum):
    """片区编码 —— A/B/C 对应 cameras.json 里的 zones。"""

    A = "A"
    B = "B"
    C = "C"


class ConnState(str, Enum):
    """设备/服务连通态。"""

    online = "online"
    offline = "offline"
    unknown = "unknown"


class Page(BaseModel, Generic[T]):
    """统一分页包装。"""

    total: int = Field(description="过滤后的总条数")
    offset: int = 0
    limit: int = 50
    items: list[T] = Field(default_factory=list)


class ProbeResult(BaseModel):
    """单设备存活探测结果。"""

    id: str
    reachable: bool = False
    rtt_ms: float | None = Field(default=None, description="往返延迟；未接入时为空")
    reason: str | None = Field(default=None, description="不可达原因（如 device-platform not connected）")


# ----------------------------------------------------- 摄像头 / 边缘节点台账

class Camera(BaseModel):
    """一台端侧 IPC 的台账条目。"""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    road: str | None = None
    zone: ZoneId | None = None
    zone_name: str | None = None
    type: str = "IPC"
    model: str | None = None
    lat: float | None = None
    lng: float | None = None
    mount: str | None = None
    resolution: str | None = None
    npu_tops: float | None = None
    edge_node: str | None = None
    status: ConnState = ConnState.offline
    stream_url: str | None = Field(default=None, description="实时流地址；未接入时为空")
    rtsp: str | None = None


class EdgeNode(BaseModel):
    """一个边侧街区节点。"""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str | None = None
    zone: str | None = Field(default=None, description="片区编码 A/B/C…")
    lat: float | None = None
    lng: float | None = None
    tops: float | None = None
    chip: str | None = None
    manages: int | None = Field(default=None, description="纳管的 IPC 数量")
    disk_buffer_gb: int | None = None
    orchestrator: str | None = Field(default=None, description="设计编排形态，如 K3s")
    status: ConnState = ConnState.offline


class CameraNetwork(BaseModel):
    """摄像头 + 边缘节点的整体组态（地图页与台账页共用）。"""

    source: str = Field(description="数据来源，如 web/src/config/cameras.json")
    simulated: bool = Field(default=True, description="是否为模拟组态")
    connected: bool = Field(default=False, description="是否已接入真实设备管理平台")
    city: str | None = None
    district: str | None = None
    coordinate_system: str | None = Field(default=None, description="坐标系，如 GCJ-02")
    center: dict[str, float] | None = None
    zoom: float | None = None
    zones: list[dict] = Field(default_factory=list)
    cameras: list[Camera] = Field(default_factory=list)
    edge_nodes: list[EdgeNode] = Field(default_factory=list)
    demo_tracks: list[dict] = Field(default_factory=list)


# ------------------------------------------------------------ 实时监控指标

class CameraMetrics(BaseModel):
    """摄像头监控页的汇总指标。接入前各项为 None。"""

    connected: bool = False
    online: int | None = None
    total: int | None = None
    avg_rtt_ms: float | None = None
    capture_rate_fps: float | None = None
    avg_npu_load: float | None = None


class CameraStatusRow(BaseModel):
    """摄像头监控页表格行。"""

    id: str
    zone: ZoneId | None = None
    ping_ms: float | None = None
    fps: float | None = None
    npu_load: float | None = None
    emit_qps: float | None = None
    stream: Literal["connecting", "live", "offline"] = "offline"


class CameraStatus(BaseModel):
    """`GET /api/monitor/cameras` 响应。"""

    connected: bool = False
    simulated: bool = True
    metrics: CameraMetrics = Field(default_factory=CameraMetrics)
    rows: list[CameraStatusRow] = Field(default_factory=list)
    note: str | None = None


class EdgeMetrics(BaseModel):
    """边缘节点页的汇总指标。接入前各项为 None。"""

    connected: bool = False
    online: int | None = None
    total: int | None = None
    avg_rtt_ms: float | None = None
    embedding_qps: float | None = None
    watchlist_hits: int | None = None


class EdgeStatusRow(BaseModel):
    """边缘节点页表格行。"""

    id: str
    zone: ZoneId | None = None
    ipcs_managed: int | None = None
    ping_ms: float | None = None
    qps: float | None = None
    load_pct: float | None = None
    pod: str | None = Field(default=None, description="K3s Pod 名；未接入时为空")
    status: ConnState = ConnState.offline


class EdgeStatus(BaseModel):
    """`GET /api/monitor/edges` 响应。"""

    connected: bool = False
    simulated: bool = True
    metrics: EdgeMetrics = Field(default_factory=EdgeMetrics)
    rows: list[EdgeStatusRow] = Field(default_factory=list)
    note: str | None = None


# ---------------------------------------------------------------- K8s 编排

class WorkloadKind(str, Enum):
    Deployment = "Deployment"
    DaemonSet = "DaemonSet"
    StatefulSet = "StatefulSet"
    CronJob = "CronJob"


class Workload(BaseModel):
    """一条编排工作负载（K3s 边侧 / K8s 云侧）。"""

    cluster: Literal["edge", "cloud"]
    namespace: str
    name: str
    kind: WorkloadKind
    image: str
    role_key: str = Field(description="前端 i18n key，如 roleBackbone")
    replicas: str | None = Field(default=None, description="设计副本数，如 33")
    schedule: str | None = Field(default=None, description="CronJob 的 cron 表达式")
    ready: str | None = Field(default=None, description="就绪副本，如 3/3；未接入时为空")
    status: ConnState = ConnState.offline


class ClusterSummary(BaseModel):
    """集群聚合指标。"""

    connected: bool = False
    edge_cluster: int | None = None
    cloud_cluster: int | None = None
    running_pods: int | None = None
    image_consistency: float | None = None


class K8sOverview(BaseModel):
    """`GET /api/k8s/workloads` 响应。"""

    connected: bool = False
    simulated: bool = True
    summary: ClusterSummary = Field(default_factory=ClusterSummary)
    workloads: list[Workload] = Field(default_factory=list)
    note: str | None = None


class RolloutRequest(BaseModel):
    """灰度/滚动升级请求。接入后可真正触发。"""

    workload: str = Field(description="目标工作负载名，如 reid-backbone")
    image: str = Field(description="目标镜像，如 reid/backbone:1.4.0-cu126")
    strategy: Literal["maxSurge", "maxUnavailable"] = "maxSurge"
    max_surge: str = "1"
    max_unavailable: str = "0"


class RolloutResponse(BaseModel):
    """灰度/滚动升级响应。未接入时只回显计划，不真正执行。"""

    connected: bool = False
    accepted: bool = False
    simulated: bool = True
    plan: RolloutRequest
    message: str


# ------------------------------------------------------------ 地图轨迹 / 布控

class TrackPoint(BaseModel):
    """轨迹上的一个点位。"""

    camera: str
    lat: float | None = None
    lng: float | None = None
    timestamp: str | None = Field(default=None, description="UTC ISO-8601；未接入时为空")


class MapTrack(BaseModel):
    """`GET /api/map/track` 响应。"""

    person: str
    label: str | None = None
    simulated: bool = True
    connected: bool = False
    points: list[TrackPoint] = Field(default_factory=list)


class WatchlistEntry(BaseModel):
    """布控名单条目。"""

    person: str
    alias: str | None = None
    added_at: str | None = None
    priority: Literal["low", "normal", "high"] = "normal"


class WatchlistAlert(BaseModel):
    """布控命中告警。"""

    id: str
    person: str
    camera: str
    score: float | None = None
    ts: str | None = Field(default=None, description="UTC ISO-8601")
    latency_ms: float | None = Field(default=None, description="命中到推送的端到端时延")


class WatchlistAlerts(BaseModel):
    """`GET /api/watchlist/alerts` 响应。"""

    connected: bool = False
    simulated: bool = True
    channel: str | None = Field(default=None, description="告警通道，如 MQTT / Pulsar")
    items: list[WatchlistAlert] = Field(default_factory=list)
