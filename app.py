"""Hugging Face Space 版前端：用 Gradio 复刻 `web/` 的 React 界面。

设计取舍
--------
* **界面**：不另起一套视觉，而是把 `web/src/` 的深色 geek 风格、9 个页签布局、三语
  i18n 逐条搬到 Gradio 上 —— CSS 变量与 `web/src/index.css` / `ui.jsx` 对齐，分数条沿用
  `ScoreBar` 的 `[threshold, 1]` 线性映射，文案直接读
  `web/src/i18n/locales/*.js` 导出的 JSON（见 `scripts/export_locales.mjs`），
  所以前端改文案这里自动跟着变，不存在两套翻译。
* **推理**：仍然复用 `reid_sys` 的三级协同（`detect` / `backbone` / `store`），
  torch + CUDA 不变。所有要吃 GPU 的调用都套 `@spaces.GPU` —— ZeroGPU 只在被装饰的函数
  内分配真卡，函数外是 CUDA 模拟态，因此模型按官方要求放在模块顶层加载。
* **数据**：仓库里只有 `data/*.zip`，启动时按 `scripts/init_data.py` 的规则解压；
  308MB 的 fast-reid 权重不塞进仓库，缺了就按 `backbone.py` 里记的官方地址拉一次。

.. note::
   当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。
"""

from __future__ import annotations

import base64
import functools
import html
import json
import os
import random
import sys
import threading
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------- ZeroGPU
# `spaces` 必须在 torch 之前 import：ZeroGPU 的 CUDA 模拟是在 import 时给 torch
# 打补丁，晚于 torch 可能不生效。`@spaces.GPU` 在非 ZeroGPU 环境是空操作
# （官方说明：effect-free）；本机没装 spaces 时退化成恒等装饰器，方便直接调试。
try:
    import spaces
except ImportError:  # pragma: no cover - 本地调试路径
    from types import SimpleNamespace

    spaces = SimpleNamespace(GPU=lambda *a, **kw: a[0] if a and callable(a[0]) else (lambda fn: fn))

import cv2
import gradio as gr
import torch

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reid_sys import datasets as ds_registry
from reid_sys.detect import PersonTracker, detect_persons, make_demo_sequence
from reid_sys.engine import ReIDEngine, imread, list_images, parse_name
from reid_sys.store import MilvusStore

# ---------------------------------------------------------------- 常量
DATA_DIR = ROOT / "data"
LOCALES = ("zh-TW", "en-US", "ja-JP")
LOCALE_LABELS = {"zh-TW": "繁體中文", "en-US": "English", "ja-JP": "日本語"}
#: 与 web/src/i18n/index.js 的 DEFAULT_LOCALE 一致（可用 REID_LOCALE 覆盖）
DEFAULT_LOCALE = os.environ.get("REID_LOCALE", "ja-JP")
#: None -> backbone 自己挑（cuda 可用就用 cuda）
DEVICE = os.environ.get("REID_DEVICE")
#: 检测模型的设备：ZeroGPU 下模块层已是模拟 cuda，进 @spaces.GPU 才是真卡
DETECT_DEVICE = DEVICE or ("cuda" if torch.cuda.is_available() else "cpu")

THRESHOLD = 0.95  # 与 Search.jsx / Detect.jsx 里的常量一致
PAGE_SIZE = 60  # 与 Gallery.jsx 一致
DETECT_CONF = 0.35  # 与 detect.py 默认值一致
EVAL_TOPK = 10

C_PRIMARY, C_SECONDARY, C_SUCCESS, C_WARN, C_ERROR = (
    "#4dabf7",
    "#a78bfa",
    "#37d67a",
    "#f59e0b",
    "#f4645f",
)
REASON_COLOR = {"enter": C_PRIMARY, "interval": C_SECONDARY, "exit": C_WARN}


# ---------------------------------------------------------------- i18n
def _load_locales() -> dict[str, dict[str, str]]:
    """读 `scripts/export_locales.mjs` 从 React 字典导出的扁平化 JSON。"""
    out: dict[str, dict[str, str]] = {}
    for loc in LOCALES:
        path = ROOT / "reid_sys" / "locales" / f"{loc}.json"
        if not path.is_file():
            raise FileNotFoundError(
                f"缺少 {path}；先运行 `node scripts/export_locales.mjs` 从 web/src/i18n/locales 生成"
            )
        out[loc] = json.loads(path.read_text(encoding="utf-8"))
    return out


I18N = _load_locales()


def tr(locale: str, key: str, **vars) -> str:
    """与前端 `t()` 同语义：点号取 key、`{name}` 插值、缺 key 原样回显。"""
    text = I18N.get(locale, I18N[DEFAULT_LOCALE]).get(key, key)
    for name, value in vars.items():
        text = text.replace("{" + name + "}", str(value))
    return text


# ---------------------------------------------------------------- 后端装配
_lock = threading.Lock()
_backbone = None
_engines: dict[str, ReIDEngine] = {}


def _bootstrap_data() -> None:
    """Space 仓库里只有 `data/*.zip`，按 `init_data.py` 的规则解压出 data1/data2。"""
    from scripts.init_data import unzip_datasets

    unzip_datasets(DATA_DIR)


def _ensure_weights() -> None:
    """308MB 权重不进仓库，缺了就按 `backbone.py` 里记的官方地址拉一次。"""
    from reid_sys.backbone import DEFAULT_WEIGHTS, DEFAULT_WEIGHT_URL

    if DEFAULT_WEIGHTS.exists():
        return
    DEFAULT_WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    print(f"[space] 下载 fast-reid 权重 -> {DEFAULT_WEIGHTS}", flush=True)
    urllib.request.urlretrieve(DEFAULT_WEIGHT_URL, DEFAULT_WEIGHTS)


def get_backbone():
    """懒加载 + 缓存 backbone（所有数据集共用同一份权重与显存）。"""
    global _backbone
    if _backbone is None:
        with _lock:
            if _backbone is None:
                from reid_sys.backbone import FastReIDBackbone

                _backbone = FastReIDBackbone(device=DEVICE)
    return _backbone


def available() -> list:
    return ds_registry.discover()


def get_dataset(name: str | None = None):
    """取数据集元信息；name 为空或失效则回退到第一个可用的。"""
    found = ds_registry.get(name) if name else None
    if found is not None:
        return found
    avail = available()
    return avail[0] if avail else None


def get_engine(name: str | None = None) -> ReIDEngine:
    """取某个数据集对应的引擎（各自一个 Milvus collection），懒加载并缓存。"""
    ds = get_dataset(name)
    if ds is None:
        raise RuntimeError("data/ 下没有符合 query/gallery/meta.json 结构的 demo 数据集")
    if ds.name not in _engines:
        with _lock:
            if ds.name not in _engines:
                store = MilvusStore(dim=get_backbone().dim, collection=ds.collection)
                _engines[ds.name] = ReIDEngine.for_dataset(get_backbone(), ds, store=store)
    return _engines[ds.name]


def _ensure_index(engine: ReIDEngine) -> None:
    """gallery 特征没录全就先录一遍 —— 必须在 GPU 窗口内调用（首次约 10~30 秒）。"""
    total = len(list_images(engine.gallery_dir))
    if total and engine.store.count() != total:
        engine.index_gallery()


# ---------------------------------------------------------------- GPU 入口
# 每个函数 = 一次「申请 GPU -> 跑完 -> 归还」。duration 是上限，越短排队优先级越高。


@spaces.GPU(duration=60)
def gpu_search_probe(ds_name: str, name: str, topk: int):
    engine = get_engine(ds_name)
    _ensure_index(engine)
    return engine.search_by_name(name, topk=topk)


@spaces.GPU(duration=60)
def gpu_search_image(ds_name: str, image, topk: int):
    engine = get_engine(ds_name)
    _ensure_index(engine)
    return engine.search([image], topk=topk)[0]


@spaces.GPU(duration=60)
def gpu_detect(image):
    return detect_persons(image, conf=DETECT_CONF, device=DETECT_DEVICE)


@spaces.GPU(duration=120)
def gpu_track(ds_name: str, persons: int, frames: int, interval: int):
    engine = get_engine(ds_name)
    names = list_images(engine.gallery_dir)
    picks = random.sample(names, min(int(persons), len(names)))
    crops = [imread(engine.gallery_dir / n) for n in picks]
    tracker = PersonTracker(device=DETECT_DEVICE, interval=int(interval))
    tracker.reset()
    emits = list(tracker.stream(make_demo_sequence(crops, frames=int(frames))))
    return {"names": picks, "stats": tracker.stats(), "emits": emits}


@spaces.GPU(duration=240)
def gpu_index(ds_name: str):
    return get_engine(ds_name).index_gallery()


@spaces.GPU(duration=240)
def gpu_evaluate(ds_name: str, topk: int):
    engine = get_engine(ds_name)
    _ensure_index(engine)
    return engine.evaluate(topk=topk)


# ---------------------------------------------------------------- HTML 片段
def esc(text) -> str:
    return html.escape(str(text), quote=True)


def data_url(image, width: int | None = None, quality: int = 85) -> str:
    """BGR ndarray -> data URL。Gradio 没有可复用的图片路由，直接内联最省事。"""
    if image is None:
        return ""
    if width and image.shape[1] > width:
        scale = width / image.shape[1]
        image = cv2.resize(image, (width, max(1, int(image.shape[0] * scale))))
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def panel(title: str = "", subtitle: str = "", body: str = "", action: str = "", cls: str = "") -> str:
    head = ""
    if title or action:
        sub = f'<div class="pn-sub">{esc(subtitle)}</div>' if subtitle else ""
        head = (
            '<div class="pn-head"><div>'
            f'<div class="pn-title">{esc(title)}</div>{sub}</div>'
            f'<div class="pn-action">{action}</div></div>'
        )
    return f'<section class="pn {cls}">{head}<div class="pn-body">{body}</div></section>'


def head_html(title: str, subtitle: str = "", action: str = "") -> str:
    """只渲染面板头 —— 给「面板里还要放原生 Gradio 组件」的场景用。"""
    sub = f'<div class="pn-sub">{esc(subtitle)}</div>' if subtitle else ""
    return (
        f'<div class="pn-head"><div><div class="pn-title">{esc(title)}</div>{sub}</div>'
        f'<div class="pn-action">{action}</div></div>'
    )


def chip(text: str, tone: str = "default") -> str:
    return f'<span class="chip chip-{tone}">{text}</span>'


def stat_chip(label: str, value, tone: str = "default") -> str:
    return (
        f'<span class="chip chip-{tone}"><span class="ck">{esc(label)}</span>'
        f'<b class="cv">{esc(value)}</b></span>'
    )


def metric(label: str, value, hint_text: str = "") -> str:
    tail = f'<div class="m-hint">{esc(hint_text)}</div>' if hint_text else ""
    return (
        f'<div class="metric"><div class="m-label">{esc(label)}</div>'
        f'<div class="m-value">{esc(value)}</div>{tail}</div>'
    )


def notice(detail: str, locale: str) -> str:
    return (
        f'<div class="notice"><div class="n-title">{esc(tr(locale, "common.demo"))}</div>'
        f'<div class="n-detail">{esc(detail)}</div></div>'
    )


def hint(text: str) -> str:
    return f'<p class="hint">{esc(text)}</p>'


def score_bar(value, threshold: float = THRESHOLD, label: str | None = None) -> str:
    """复刻 ui.jsx 的 ScoreBar：按 [threshold, 1] 线性映射，三档配色。

    cosine 全挤在 0.95~0.99，从 0 起算没有区分度，所以阈值以下钳到 0%、1.0 才满格。
    """
    raw = max(0.0, min(1.0, float(value or 0.0)))
    lo = max(0.0, min(0.999, threshold))
    rel = 0.0 if raw <= lo else (raw - lo) / (1 - lo)
    pct = round(rel * 100)
    color = C_SUCCESS if rel >= 0.66 else C_WARN if rel >= 0.33 else C_ERROR
    caption = f"{label} · cosine {raw:.4f}" if label else f"cosine {raw:.4f}"
    return (
        f'<div class="sb"><div class="sb-row"><span class="sb-lo">{lo:.2f}</span>'
        f'<div class="sb-track"><div class="sb-fill" style="width:{pct}%;background:{color}"></div></div>'
        f'<span class="sb-pct" style="color:{color}">{pct}%</span></div>'
        f'<div class="sb-cap">{esc(caption)}</div></div>'
    )


def tile(url: str, caption: str = "", width: int = 84, height: int = 108) -> str:
    cap = f'<div class="t-cap">{esc(caption)}</div>' if caption else ""
    return (
        f'<div class="tile" style="width:{width}px"><div class="t-img" style="height:{height}px">'
        f'<img src="{url}" loading="lazy" alt=""/></div>{cap}</div>'
    )


def tier_cards(locale: str) -> str:
    """三级协同（对应 docs/SYSTEM.md）：端去重 -> 边提特征 -> 云检索。"""
    tiers = (
        ("system.tierEnd", "detect", C_PRIMARY, ("sysTierEnd1", "sysTierEnd2", "sysTierEnd3", "sysTierEnd4")),
        ("system.tierEdge", "backbone", C_SECONDARY, ("sysTierEdge1", "sysTierEdge2", "sysTierEdge3", "sysTierEdge4")),
        ("system.tierCloud", "store", C_SUCCESS, ("sysTierCloud1", "sysTierCloud2", "sysTierCloud3", "sysTierCloud4")),
    )
    cards = []
    for title_key, module, tone, points in tiers:
        items = "".join(
            f'<li><i style="background:{tone}"></i>{esc(tr(locale, "system." + p))}</li>' for p in points
        )
        cards.append(
            f'<div class="tier"><div class="tier-h" style="color:{tone}">'
            f'<span class="dot" style="background:{tone}"></span>{esc(tr(locale, title_key))}</div>'
            f'<span class="chip tier-mod" style="color:{tone};border-color:{tone}55">{esc(module)}</span>'
            f'<ul class="tier-list">{items}</ul></div>'
        )
    return f'<div class="tier-grid">{"".join(cards)}</div>'


# ---------------------------------------------------------------- 状态
def new_state() -> dict:
    first = available()
    return {
        "locale": DEFAULT_LOCALE,
        "dataset": first[0].name if first else "",
        "probe": [],
        "probe_total": 0,
        "probe_q": "",
        "probe_index": None,
        "search": None,
        "page": 1,
        "q": "",
        "gallery": [],
        "gallery_total": 0,
        "gallery_pages": 1,
        "detect": None,
        "detect_image": None,
        "crop_search": None,
        "track": None,
        "index": None,
        "eval": None,
        "error": "",
    }


def _status(ds) -> dict | None:
    if ds is None:
        return None
    engine = get_engine(ds.name)
    return {
        **engine.status(),
        "dataset": ds.name,
        "dataset_title": ds.title,
        "detector": "yolo26n.pt + ByteTrack",
        "milvus_uri": engine.store.uri,
    }


def _load_probe(s: dict) -> dict:
    ds = get_dataset(s["dataset"])
    names = list_images(ds.query_dir) if ds else []
    s["probe_total"] = len(names)
    q = s.get("probe_q", "")
    s["probe"] = [n for n in names if q in n] if q else names
    return s


def _load_gallery(s: dict) -> dict:
    ds = get_dataset(s["dataset"])
    names = list_images(ds.gallery_dir) if ds else []
    q = s.get("q", "")
    if q:
        names = [n for n in names if q in n]
    pages = max(1, -(-len(names) // PAGE_SIZE))
    s["gallery_total"] = len(names)
    s["gallery_pages"] = pages
    s["page"] = max(1, min(s.get("page", 1), pages))
    start = (s["page"] - 1) * PAGE_SIZE
    s["gallery"] = names[start : start + PAGE_SIZE]
    return s


# ---------------------------------------------------------------- 面板内容
def _hits_html(hits, locale: str, truth: str | None, ds) -> str:
    """检索结果列表 —— 复刻 Search.jsx 的行布局（排名 / 缩略图 / 元信息 / 分数条）。"""
    if not hits:
        return hint(tr(locale, "search.empty"))
    rows = []
    for i, h in enumerate(hits):
        is_truth = bool(truth) and h["person_id"] == truth
        url = data_url(imread(ds.gallery_dir / h["id"]), width=120)
        marks = chip("cam " + str(h["camera"]), "ghost") + chip("frame " + str(h["frame"]), "ghost")
        if is_truth:
            marks += chip(tr(locale, "search.truth"), "success")
        person = esc(h["person_id"])
        rows.append(
            f'<div class="hit{" hit-truth" if is_truth else ""}">'
            f'<div class="hit-rank">{i + 1}</div>'
            f'<div class="hit-img"><img src="{url}" loading="lazy" alt=""/></div>'
            f'<div class="hit-main"><div class="hit-meta">'
            f'<span class="mono">person {person}</span>{marks}</div>'
            f'<div class="hit-id">{esc(h["id"])}</div>'
            f"{score_bar(h['score'])}</div></div>"
        )
    return "".join(rows)


def _query_html(s: dict, locale: str) -> str:
    if s.get("error"):
        return f'<div class="alert">{esc(s["error"])}</div>'
    res = s.get("search")
    if not res:
        return hint(tr(locale, "search.pickHint"))
    chips = [chip(tr(locale, "search.returned", n=len(res["hits"])), "primary")]
    truth = res.get("truth")
    if truth:
        rank = next((i + 1 for i, h in enumerate(res["hits"]) if h["person_id"] == truth), 0)
        if rank == 1:
            chips.append(chip(tr(locale, "search.rank1Hit", p=truth), "success"))
        else:
            shown = rank or tr(locale, "search.truthNotRecalled")
            chips.append(chip(tr(locale, "search.truthRank", p=truth, r=shown), "warn"))
    top1 = res["hits"][0]["score"] if res["hits"] else None
    chips.append(chip(tr(locale, "search.top1Score", s="-" if top1 is None else f"{top1:.4f}"), "ghost"))
    return (
        f'<div class="query"><div class="query-img"><img src="{res["url"]}" alt=""/></div>'
        f'<div class="query-side"><div class="row-wrap">{"".join(chips)}</div>'
        f'<div class="query-name">{esc(res["name"])}</div></div></div>'
    )


def _crops_html(det, locale: str) -> str:
    if not det or not det["persons"]:
        return hint(tr(locale, "detect.noCrop"))
    rows = []
    for p in det["persons"]:
        box = ", ".join(str(v) for v in p["box"])
        rows.append(
            f'<div class="crop-row">'
            f'<div class="crop-img"><img src="{data_url(p["crop"], width=110)}" loading="lazy" alt=""/></div>'
            f'<div class="crop-meta"><div class="mono">box {esc(box)}</div>'
            f'<div class="dim">score {p["score"]:.4f}</div></div></div>'
        )
    return "".join(rows)


def _track_html(track, locale: str) -> str:
    if not track:
        return hint(tr(locale, "detect.runDemo"))
    stats = track["stats"]
    emits = track["emits"]
    marks: dict[int, dict[int, str]] = {}
    for e in emits:
        marks.setdefault(e.track_id, {})[e.frame] = e.reason

    enter = stats["by_reason"]["enter"]
    interval = stats["by_reason"]["interval"]
    exit_ = stats["by_reason"]["exit"]
    cards = "".join(
        [
            metric(
                tr(locale, "detect.statDetections"),
                stats["detections"],
                tr(locale, "detect.statDetectionsHint", n=stats["frames"]),
            ),
            metric(tr(locale, "detect.statEmits"), stats["emits"], f"enter {enter} / interval {interval} / exit {exit_}"),
            metric(tr(locale, "detect.statDedup"), f"{stats['dedup_rate'] * 100:.1f}%", tr(locale, "detect.statDedupHint")),
            metric(tr(locale, "detect.statTracks"), len(marks), tr(locale, "detect.statTracksHint")),
        ]
    )

    rows = []
    for tid, per_frame in marks.items():
        cells = "".join(
            '<i style="background:{};height:{}px"></i>'.format(
                REASON_COLOR[per_frame[f]] if f in per_frame else "rgba(255,255,255,0.10)",
                16 if f in per_frame else 4,
            )
            for f in range(stats["frames"])
        )
        rows.append(f'<div class="tl-row"><span class="tl-id">track {tid}</span><div class="tl-bar">{cells}</div></div>')

    legend_keys = {"enter": "detect.legendEnter", "interval": "detect.legendInterval", "exit": "detect.legendExit"}
    legend = "".join(
        '<span class="chip chip-ghost" style="color:{0};border-color:{0}66">{1}</span>'.format(
            color, esc(tr(locale, legend_keys[name]))
        )
        for name, color in REASON_COLOR.items()
    )

    samples = "".join(
        tile(data_url(e.crop, width=90), f"f{e.frame} {e.reason}", width=70, height=104)
        for e in [e for e in emits if e.crop is not None][:12]
    )

    return (
        f'<div class="metric-grid">{cards}</div>'
        f'<div class="sub">{esc(tr(locale, "detect.timeline"))}</div>'
        f'<div class="tl">{"".join(rows)}</div>'
        f'<div class="row-wrap">{legend}</div>'
        f'<div class="sub">{esc(tr(locale, "detect.emitSamples"))}</div>'
        f'<div class="row-wrap">{samples}</div>'
    )


def _eval_detail_html(res, locale: str) -> str:
    if not res:
        return hint(tr(locale, "system.evalHint"))
    rows = []
    for row in res["samples"]:
        rank = row["rank"]
        tone = "success" if rank == 1 else "warn" if rank else "error"
        rows.append(
            f'<tr><td class="mono dim">{esc(row["probe"])}</td><td class="mono">{esc(row["truth"])}</td>'
            f'<td class="mono">{esc(row["top1"])}</td>'
            f'<td class="mono" style="text-align:right">{row["top1_score"]:.4f}</td>'
            f'<td style="text-align:right">{chip(rank or "miss", tone)}</td></tr>'
        )
    head = "".join(
        f"<th>{esc(tr(locale, k))}</th>"
        for k in ("system.colProbe", "system.colTruth", "system.colTop1", "system.colScore", "system.colRank")
    )
    return f'<table class="tbl"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def _placeholder_panel(locale: str, tab_key: str, note: str) -> str:
    """未接入能力的占位页：形状像真面板，数值一律留空。"""
    cells = "".join(
        metric(tr(locale, k), "—")
        for k in ("space.metricDevice", "space.metricOnline", "space.metricRtt", "space.metricLoad")
    )
    return panel(
        tr(locale, "tabs." + tab_key),
        tr(locale, "common.notConnected"),
        notice(note, locale) + f'<div class="metric-grid">{cells}</div>',
        action=chip(tr(locale, "common.planned"), "ghost"),
        cls="pn-dashed",
    )


HTML_ORDER = (
    "topbar",
    "error",
    "probe_head",
    "probe_hint",
    "search_head",
    "search_query",
    "search_hits",
    "gallery_head",
    "gallery_foot",
    "detect_head",
    "detect_crop_head",
    "detect_crops",
    "crop_search",
    "track_head",
    "track_panel",
    "arch_head",
    "arch_panel",
    "cameras_panel",
    "edges_panel",
    "map_panel",
    "k8s_panel",
    "sys_status",
    "sys_tiers",
    "sys_index",
    "sys_eval",
    "sys_detail",
    "footer",
)


def render_html(s: dict) -> dict[str, str]:
    locale = s["locale"]
    ds = get_dataset(s["dataset"])
    st = _status(ds)
    out: dict[str, str] = {}

    brand = (
        '<div class="brand"><span class="logo">⬡</span><div>'
        f'<div class="brand-t">{esc(tr(locale, "app.title"))}</div>'
        f'<div class="brand-s">{esc(tr(locale, "app.subtitle"))}</div></div></div>'
    )
    if st:
        chips = "".join(
            [
                stat_chip(tr(locale, "status.backbone"), f"R50 · {st['dim']}d", "primary"),
                stat_chip(tr(locale, "status.device"), st["device"], "success" if st["device"] == "cuda" else "default"),
                stat_chip(tr(locale, "dataset.chip"), st["dataset"], "secondary"),
                stat_chip(tr(locale, "status.milvus"), f"{st['indexed']}/{st['gallery_total']}", "secondary"),
                stat_chip(tr(locale, "status.probe"), st["probe_total"]),
            ]
        )
    else:
        chips = chip(tr(locale, "dataset.empty"), "warn")
    out["topbar"] = f'<div class="topbar">{brand}<div class="chips">{chips}</div></div>'

    out["error"] = f'<div class="alert">{esc(s["error"])}</div>' if s["error"] else ""

    # ---- 以图搜人
    probe_n = len(s["probe"]) if s["probe_q"] else s["probe_total"]
    out["probe_head"] = head_html(
        tr(locale, "search.probeTitle"), tr(locale, "search.probeSubtitle", n=probe_n)
    )
    out["probe_hint"] = hint(tr(locale, "search.clickHint"))
    out["search_head"] = head_html(tr(locale, "search.params"), tr(locale, "search.paramsSubtitle"))
    out["search_query"] = _query_html(s, locale)
    hits_body = (
        _hits_html(s["search"]["hits"], locale, s["search"].get("truth"), ds)
        if s["search"]
        else hint(tr(locale, "search.empty"))
    )
    out["search_hits"] = panel(tr(locale, "search.results"), tr(locale, "search.resultsSubtitle"), hits_body)

    # ---- 底库浏览
    title = st["dataset_title"] if st else "—"
    total = st["gallery_total"] if st else 0
    out["gallery_head"] = head_html(tr(locale, "gallery.title"), tr(locale, "gallery.subtitleDs", ds=title, n=total))
    out["gallery_foot"] = (
        f'<div class="dim">{esc(tr(locale, "gallery.hitCount", n=s["gallery_total"]))}</div>'
        f'<div class="dim">{esc(tr(locale, "gallery.pageLabel", a=s["page"], b=s["gallery_pages"]))}</div>'
    )

    # ---- 检测与去重
    out["detect_head"] = head_html(tr(locale, "detect.singleTitle"), tr(locale, "detect.singleSubtitle"))
    out["detect_crop_head"] = head_html(tr(locale, "detect.cropTitle"), tr(locale, "detect.cropSubtitle"))
    out["detect_crops"] = _crops_html(s["detect"], locale)
    if s.get("crop_search"):
        out["crop_search"] = panel(
            tr(locale, "detect.cropSearchTitle", n=s["crop_search"]["index"] + 1),
            "",
            _hits_html(s["crop_search"]["hits"], locale, None, ds),
        )
    else:
        out["crop_search"] = ""
    out["track_head"] = head_html(tr(locale, "detect.trackTitle"), tr(locale, "detect.trackSubtitle"))
    out["track_panel"] = _track_html(s["track"], locale)

    # ---- 系统架构
    out["arch_head"] = head_html(tr(locale, "system.tiers"), tr(locale, "system.tiersSubtitle"))
    out["arch_panel"] = tier_cards(locale) + hint(tr(locale, "space.archDoc"))

    # ---- 未接入能力的占位页
    for slot, tab_key in (("cameras_panel", "cameras"), ("edges_panel", "edges"), ("k8s_panel", "k8s")):
        out[slot] = _placeholder_panel(locale, tab_key, tr(locale, "space.notConnectedNote", name=tr(locale, "tabs." + tab_key)))
    out["map_panel"] = _placeholder_panel(
        locale, "map", tr(locale, "space.notConnectedNote", name=tr(locale, "tabs.map"))
    ) + panel(
        tr(locale, "map.complianceTitle"),
        tr(locale, "map.complianceSubtitle"),
        hint(tr(locale, "space.mapNote")),
    )

    # ---- 系统与评估
    dim = f"R50 / {st['dim']}d" if st else "—"
    indexed = f"{st['indexed']} / {st['gallery_total']}" if st else "—"
    dev = st["device"] if st else "—"
    probe_total = st["probe_total"] if st else "—"
    out["sys_status"] = panel(
        tr(locale, "system.runStatus"),
        tr(locale, "system.runStatusSubtitle"),
        '<div class="metric-grid">'
        + metric(tr(locale, "system.backbone"), dim, st["backbone"] if st else "")
        + metric(tr(locale, "system.device"), dev, tr(locale, "system.deviceHint"))
        + metric(tr(locale, "system.indexed"), indexed, st["collection"] if st else "")
        + metric(tr(locale, "system.probeSet"), probe_total, tr(locale, "system.probeSetHint"))
        + "</div>"
        + f'<div class="dim mono">detector = {esc(st["detector"]) if st else "—"} · milvus = {esc(st["milvus_uri"]) if st else "—"}</div>',
    )
    out["sys_tiers"] = panel(
        tr(locale, "system.tiers"),
        tr(locale, "system.tiersSubtitle"),
        tier_cards(locale) + hint(tr(locale, "system.tiersFootnote")),
    )

    idx = s["index"]
    if idx:
        index_body = (
            '<div class="metric-grid">'
            + metric(tr(locale, "system.metricIndexed"), idx["indexed"])
            + metric(tr(locale, "system.metricDim"), idx["dim"])
            + metric(tr(locale, "system.metricCount"), idx["count"])
            + "</div>"
        )
    else:
        index_body = hint(tr(locale, "system.indexHint"))
    if st and st["indexed"] != st["gallery_total"]:
        index_body += f'<div class="alert alert-info">{esc(tr(locale, "space.firstIndex"))}</div>'
    out["sys_index"] = panel(tr(locale, "system.indexTitle"), tr(locale, "system.indexSubtitle"), index_body)

    ev = s["eval"]
    if ev:
        eval_body = (
            '<div class="metric-grid">'
            + metric(tr(locale, "system.rank1"), f"{ev['rank1'] * 100:.2f}%", tr(locale, "system.queriesHint", n=ev["queries"]))
            + metric(tr(locale, "system.rank5"), f"{ev['rank5'] * 100:.2f}%")
            + metric("mAP", f"{ev['mAP']:.4f}", tr(locale, "system.missHint", n=ev["miss"]))
            + "</div>"
        )
    else:
        eval_body = hint(tr(locale, "system.evalHint"))
    out["sys_eval"] = panel(
        tr(locale, "system.evalTitle"),
        tr(locale, "system.evalSubtitle", n=st["probe_total"] if st else 0),
        eval_body,
    )
    out["sys_detail"] = (
        panel(tr(locale, "system.detailTitle"), tr(locale, "system.detailSubtitle"), _eval_detail_html(ev, locale))
        if ev
        else ""
    )

    out["footer"] = (
        f'<div class="foot">{esc(tr(locale, "common.feasibility"))}<br/>{esc(tr(locale, "space.runtime"))}</div>'
    )
    return out


# ---------------------------------------------------------------- 事件
#: 需要跟着语言切换的组件：(组件, i18n key, 属性)
LABELS: list[tuple] = []


def L(comp, key: str, attr: str = "label"):
    LABELS.append((comp, key, attr))
    return comp


def html_values(s: dict) -> list:
    slots = render_html(s)
    return [slots[k] for k in HTML_ORDER]


def label_values(s: dict) -> list:
    return [gr.update(**{attr: tr(s["locale"], key)}) for _, key, attr in LABELS]


def render(s: dict) -> list:
    """输出顺序：state -> HTML 面板 -> 组件标签。"""
    return [s, *html_values(s), *label_values(s)]


def render_full(s: dict) -> list:
    """额外带上两个网格、检测图与语言下拉框的值。

    语言下拉框也在这组里：`?locale=en-US` 时界面会切成英文，下拉框自己也得跟着改，
    否则会出现「界面英文、选择器还停在 日本語」的错位。
    """
    return [*render(s), _probe_gallery_update(s), gallery_grid_value(s), s["detect_image"], s["locale"]]


def probe_gallery_value(s: dict) -> list:
    ds = get_dataset(s["dataset"])
    return [(str(ds.query_dir / n), parse_name(n)["person_id"]) for n in s["probe"]] if ds else []


def _probe_gallery_update(s: dict) -> dict:
    return gr.update(value=probe_gallery_value(s), selected_index=s["probe_index"])


def gallery_grid_value(s: dict) -> list:
    """底库网格：Gradio 要能直接读到的路径，所以拼绝对路径，顺带把 personID 当角标。"""
    ds = get_dataset(s["dataset"])
    return [(str(ds.gallery_dir / n), parse_name(n)["person_id"]) for n in s["gallery"]] if ds else []


def handler(full: bool = False):
    """统一收口异常：任何 handler 内部报错都落到 state['error']，页面照常渲染。"""

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(state, *args):
            try:
                state = fn(state, *args)
            except Exception as exc:  # noqa: BLE001
                state = {**state, "error": f"{type(exc).__name__}: {exc}"}
            return render_full(state) if full else render(state)

        return wrapper

    return deco


@handler(full=True)
def on_load(state, request: gr.Request):
    """首屏：按前端的优先级定语言（URL ?locale= > REID_LOCALE > ja-JP），再装数据。"""
    hit = None
    try:
        hit = request.query_params.get("locale") if request else None
    except Exception:  # noqa: BLE001 - 拿不到请求就退回默认语言
        hit = None
    state["locale"] = hit if hit in LOCALES else DEFAULT_LOCALE
    _load_probe(state)
    _load_gallery(state)
    return state


@handler(full=True)
def on_refresh(state, locale):
    state["locale"] = locale
    _load_probe(state)
    _load_gallery(state)
    return state


@handler(full=True)
def on_locale(state, locale):
    state["locale"] = locale
    return state


@handler(full=True)
def on_dataset(state, name, locale):
    state["locale"] = locale
    state["dataset"] = name or state["dataset"]
    state["probe_q"] = state["q"] = ""
    state["page"] = 1
    state["probe_index"] = None
    state["search"] = state["detect"] = state["crop_search"] = state["track"] = None
    state["detect_image"] = state["index"] = state["eval"] = None
    _load_probe(state)
    _load_gallery(state)
    return state


@handler(full=True)
def on_probe_filter(state, text, locale):
    state["locale"] = locale
    state["probe_q"] = text or ""
    state["probe_index"] = None
    return _load_probe(state)


@handler(full=True)
def on_probe_select(state, locale, topk, evt: gr.SelectData):
    state["locale"] = locale
    name = state["probe"][evt.index]
    ds = get_dataset(state["dataset"])
    hits = gpu_search_probe(ds.name, name, int(topk))
    state["probe_index"] = evt.index
    state["search"] = {
        "hits": hits,
        "name": name,
        "url": data_url(imread(ds.query_dir / name), width=220),
        "truth": parse_name(name)["person_id"],
    }
    return state


@handler(full=True)
def on_search_upload(state, locale, image, topk):
    state["locale"] = locale
    if image is None:
        return state
    ds = get_dataset(state["dataset"])
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    hits = gpu_search_image(ds.name, bgr, int(topk))
    state["probe_index"] = None
    state["search"] = {
        "hits": hits,
        "name": tr(locale, "search.localUpload"),
        "url": data_url(bgr, width=220),
        "truth": None,
    }
    return state


@handler(full=True)
def on_gallery_filter(state, text, locale):
    state["locale"] = locale
    state["q"] = text or ""
    state["page"] = 1
    return _load_gallery(state)


@handler(full=True)
def on_page(state, delta, locale):
    state["locale"] = locale
    state["page"] = max(1, min(state["page"] + delta, state["gallery_pages"]))
    return _load_gallery(state)


@handler(full=True)
def on_detect(state, locale, image):
    state["locale"] = locale
    if image is None:
        return state
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    persons = gpu_detect(bgr)
    canvas = bgr.copy()
    for i, p in enumerate(persons):
        x1, y1, x2, y2 = p["box"]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (247, 171, 77), 2)  # BGR 形式的 #4dabf7
        cv2.putText(canvas, f"#{i + 1} {p['score']:.2f}", (x1, max(14, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (247, 171, 77), 1)
    state["detect"] = {"persons": persons, "count": len(persons)}
    state["detect_image"] = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    state["crop_search"] = None
    return state


@handler(full=True)
def on_track(state, locale, persons, frames, interval):
    state["locale"] = locale
    state["track"] = gpu_track(state["dataset"], int(persons), int(frames), int(interval))
    return state


@handler(full=True)
def on_index(state, locale):
    state["locale"] = locale
    state["index"] = gpu_index(state["dataset"])
    return state


@handler(full=True)
def on_eval(state, locale):
    state["locale"] = locale
    state["eval"] = gpu_evaluate(state["dataset"], EVAL_TOPK)
    return state


# ---------------------------------------------------------------- 样式
CSS = """
:root, .dark {
  --pn-bg: #0d131f;
  --pn-bd: rgba(255,255,255,0.08);
  --tx: #e6edf7;
  --mut: rgba(230,237,247,0.60);
  --pri: #4dabf7;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
html, body { color-scheme: dark !important; }
body, .gradio-container {
  background:
    radial-gradient(1100px 520px at 12% -10%, rgba(77,171,247,0.16), transparent 60%),
    radial-gradient(900px 480px at 92% 0%, rgba(167,139,250,0.13), transparent 62%),
    #0a0e15 !important;
  color: #e6edf7 !important;
}
.gradio-container {
  max-width: 1600px !important;
  --body-background-fill: transparent;
  --background-fill-primary: #0d131f;
  --background-fill-secondary: rgba(255,255,255,0.03);
  --block-background-fill: #0d131f;
  --block-border-color: rgba(255,255,255,0.08);
  --block-label-text-color: rgba(230,237,247,0.60);
  --block-title-text-color: #e6edf7;
  --border-color-primary: rgba(255,255,255,0.08);
  --border-color-accent: rgba(77,171,247,0.55);
  --body-text-color: #e6edf7;
  --body-text-color-subdued: rgba(230,237,247,0.60);
  --color-accent: #4dabf7;
  --color-accent-soft: rgba(77,171,247,0.12);
  --input-background-fill: rgba(255,255,255,0.04);
  --input-border-color: rgba(255,255,255,0.12);
  --input-placeholder-color: rgba(230,237,247,0.38);
  --button-primary-background-fill: #4dabf7;
  --button-primary-text-color: #08111f;
  --button-secondary-background-fill: rgba(255,255,255,0.04);
  --button-secondary-text-color: #e6edf7;
  --button-secondary-border-color: rgba(255,255,255,0.14);
  --panel-background-fill: #0d131f;
  --slider-color: #4dabf7;
  --table-border-color: rgba(255,255,255,0.08);
  --table-even-background-fill: rgba(255,255,255,0.02);
}
footer, .built-with, .footer, .show-api { display: none !important; }

/* ---------- 面板 ---------- */
.pn {
  background: var(--pn-bg) !important;
  border: 1px solid var(--pn-bd) !important;
  border-radius: 12px !important;
  padding: 0 !important;
  gap: 10px !important;
  overflow: hidden;
  margin-bottom: 14px;
}
.pn.pn-dashed { border-style: dashed !important; background: rgba(255,255,255,0.015) !important; }
.pn .block, .pn .form, .pn .html-container {
  border: 0 !important; background: transparent !important;
  box-shadow: none !important; padding: 0 !important; margin: 0 !important;
}
.pn-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 10px 14px; border-bottom: 1px solid var(--pn-bd); width: 100%;
}
.pn-title { font-size: 15px; font-weight: 650; color: #e6edf7; }
.pn-sub { font-size: 12px; color: var(--mut); margin-top: 2px; }
.pn-body { padding: 12px 14px; display: flex; flex-direction: column; gap: 10px; }

/* ---------- 顶栏 ---------- */
.hd { flex-wrap: nowrap !important; align-items: center !important; gap: 10px !important; }
.hd > * { margin: 0 !important; }
.hd > .block {
  padding: 0 !important; border: 0 !important; background: transparent !important;
  box-shadow: none !important; min-width: 0 !important;
}
.hd > .form { flex: 0 0 auto !important; width: fit-content !important; }
.hd > .form > * { flex: 0 0 auto !important; }
.hd > button { flex: 0 0 auto !important; min-width: 118px !important; white-space: nowrap !important; }
.topbar { display: flex; align-items: center; gap: 14px; flex-wrap: nowrap; }
.topbar .chips { margin-left: auto; display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }
.hd label { font-size: 11px !important; margin-bottom: 2px !important; color: var(--mut) !important; }
.brand { display: flex; align-items: center; gap: 10px; }
.brand .logo { font-size: 22px; color: var(--pri); }
.brand-t { font-size: 17px; font-weight: 700; white-space: nowrap; }
.brand-s { font-size: 12px; color: var(--mut); white-space: nowrap; }

/* ---------- 通用件 ---------- */
.chip {
  display: inline-flex; align-items: center; gap: 6px; height: 24px; padding: 0 9px;
  border: 1px solid var(--pn-bd); border-radius: 999px; background: rgba(255,255,255,0.03);
  font-size: 12px; color: #e6edf7; white-space: nowrap;
}
.chip .ck { opacity: .62; }
.chip .cv { font-family: var(--mono); font-weight: 700; }
.chip-primary { border-color: rgba(77,171,247,.5); background: rgba(77,171,247,.10); }
.chip-secondary { border-color: rgba(167,139,250,.45); background: rgba(167,139,250,.10); }
.chip-success { border-color: rgba(55,214,122,.5); background: rgba(55,214,122,.10); color: #37d67a; }
.chip-warn { border-color: rgba(245,158,11,.5); background: rgba(245,158,11,.10); color: #f59e0b; }
.chip-error { border-color: rgba(244,100,95,.5); background: rgba(244,100,95,.10); color: #f4645f; }
.chip-ghost { opacity: .78; }
.row-wrap { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.mono { font-family: var(--mono); }
.dim { color: var(--mut); font-size: 12px; }
.hint { color: var(--mut); font-size: 13px; margin: 0; line-height: 1.6; }
.sub { font-size: 13px; font-weight: 650; margin: 6px 0 2px; }
.alert {
  border: 1px solid rgba(244,100,95,.45); background: rgba(244,100,95,.10);
  color: #ffd9d7; border-radius: 8px; padding: 8px 10px; font-size: 12px;
}
.alert-info { border-color: rgba(77,171,247,.45); background: rgba(77,171,247,.10); color: #d6ecff; }
.notice {
  border: 1px solid rgba(77,171,247,.45); background: rgba(77,171,247,.08);
  border-radius: 8px; padding: 9px 11px;
}
.notice .n-title { font-size: 13px; font-weight: 650; }
.notice .n-detail { font-size: 12px; color: var(--mut); margin-top: 3px; line-height: 1.55; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.metric { padding: 10px 12px; border-radius: 10px; background: rgba(255,255,255,0.03); border: 1px solid var(--pn-bd); }
.m-label { font-size: 12px; color: var(--mut); }
.m-value { font-family: var(--mono); font-size: 20px; line-height: 1.35; }
.m-hint { font-size: 11px; color: var(--mut); margin-top: 2px; }

/* ---------- 分数条 ---------- */
.sb { width: 100%; }
.sb-row { display: flex; align-items: center; gap: 8px; }
.sb-lo { font-family: var(--mono); font-size: 11px; opacity: .55; min-width: 34px; }
.sb-track { flex: 1; height: 6px; border-radius: 3px; background: rgba(255,255,255,0.07); overflow: hidden; }
.sb-fill { height: 100%; border-radius: 3px; }
.sb-pct { font-family: var(--mono); font-size: 11px; min-width: 34px; text-align: right; }
.sb-cap { font-family: var(--mono); font-size: 11px; color: var(--mut); margin-top: 2px; }

/* ---------- 缩略图 ---------- */
.t-img {
  position: relative; border-radius: 8px; overflow: hidden; background: #0b101a;
  border: 1px solid var(--pn-bd); display: flex; align-items: center; justify-content: center;
}
.t-img img { width: 100%; height: 100%; object-fit: contain; }
.t-cap { font-family: var(--mono); font-size: 11px; color: var(--mut); margin-top: 3px; word-break: break-all; }

/* ---------- 检索结果 ---------- */
.hit {
  display: grid; grid-template-columns: 40px 76px 1fr; gap: 14px; align-items: center;
  padding: 8px; border-radius: 10px; border: 1px solid var(--pn-bd);
  background: rgba(255,255,255,0.02); margin-bottom: 10px;
}
.hit-truth { border-color: rgba(55,214,122,.55); background: rgba(55,214,122,.08); }
.hit-rank { text-align: center; font-family: var(--mono); font-size: 20px; opacity: .75; }
.hit-img { height: 132px; border-radius: 8px; overflow: hidden; background: #0b101a; border: 1px solid var(--pn-bd); }
.hit-img img { width: 100%; height: 100%; object-fit: contain; }
.hit-main { min-width: 0; }
.hit-meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 4px; }
.hit-id { font-family: var(--mono); font-size: 11px; color: var(--mut); margin-bottom: 6px; word-break: break-all; }
.query { display: flex; gap: 16px; align-items: flex-start; }
.query-img { width: 132px; height: 200px; flex: 0 0 auto; border-radius: 8px; overflow: hidden; background: #0b101a; border: 1px solid var(--pn-bd); }
.query-img img { width: 100%; height: 100%; object-fit: contain; }
.query-side { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.query-name { font-family: var(--mono); font-size: 11px; color: var(--mut); word-break: break-all; }
.crop-row { display: grid; grid-template-columns: 64px 1fr; gap: 14px; align-items: center; margin-bottom: 10px; }
.crop-img { height: 112px; border-radius: 8px; overflow: hidden; background: #0b101a; border: 1px solid var(--pn-bd); }
.crop-img img { width: 100%; height: 100%; object-fit: contain; }
.crop-meta { font-size: 12px; }

/* ---------- 时间轴 ---------- */
.tl { display: flex; flex-direction: column; gap: 6px; }
.tl-row { display: flex; align-items: center; gap: 12px; }
.tl-id { width: 74px; font-family: var(--mono); font-size: 11px; color: var(--mut); flex: 0 0 auto; }
.tl-bar { flex: 1; display: flex; gap: 2px; align-items: center; height: 16px; }
.tl-bar i { flex: 1; border-radius: 2px; }

/* ---------- 三级协同 ---------- */
.tier-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; }
.tier { padding: 12px; border-radius: 10px; border: 1px solid var(--pn-bd); background: rgba(255,255,255,0.02); }
.tier-h { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 650; margin-bottom: 8px; }
.tier-h .dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.tier-mod { font-family: var(--mono); margin-bottom: 8px; }
.tier-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.tier-list li { display: flex; gap: 8px; align-items: flex-start; font-size: 12px; color: var(--mut); line-height: 1.5; }
.tier-list li i { width: 5px; height: 5px; border-radius: 50%; margin-top: 6px; flex: 0 0 auto; }

/* ---------- 表格 ---------- */
.tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.tbl th { text-align: left; color: var(--mut); font-weight: 600; padding: 6px 8px; border-bottom: 1px solid var(--pn-bd); }
.tbl td { padding: 6px 8px; border-bottom: 1px solid rgba(255,255,255,0.05); }

/* ---------- Gradio 原生件微调 ---------- */
.tabs { margin-top: 4px; }
.grid-wrap img, .gallery-item img { object-fit: contain !important; background: #0b101a; }
.gallery-item, .thumbnail-item { border: 1px solid var(--pn-bd) !important; border-radius: 8px !important; overflow: hidden; }
.foot { color: var(--mut); font-size: 12px; line-height: 1.7; padding: 18px 2px 8px; }
"""

HEAD = """
<script>
  (function () {
    var force = function () {
      document.documentElement.classList.add('dark');
      if (document.body) document.body.classList.add('dark');
    };
    force();
    document.addEventListener('DOMContentLoaded', force);
    setTimeout(force, 150);
    setTimeout(force, 700);
  })();
</script>
"""


def _html_components(demo: gr.Blocks) -> list:
    """按 HTML_ORDER 取出界面里那批 gr.HTML —— 输出顺序必须与 render_html 一致。"""
    by_id = {getattr(c, "elem_id", None): c for c in demo.blocks.values()}
    missing = [k for k in HTML_ORDER if k not in by_id]
    if missing:
        raise RuntimeError(f"HTML_ORDER 与界面不一致，缺少：{missing}")
    return [by_id[k] for k in HTML_ORDER]


def build() -> gr.Blocks:
    # 首屏由 Python 直接渲染好塞进组件：页面一出来就是成品，不用等 demo.load 跑一个来回
    # （那个事件期间整页会盖一层 loading 遮罩）。demo.load 只负责 ?locale= 与刷新。
    initial = _load_gallery(_load_probe(new_state()))
    slots = render_html(initial)

    def H(key: str, **kwargs) -> gr.HTML:
        return gr.HTML(value=slots[key], elem_id=key, **kwargs)

    def btn(key: str, **kwargs) -> gr.Button:
        """按默认语言预填文案的按钮（语言切换时由 label_values 覆盖）。"""
        return L(gr.Button(tr(DEFAULT_LOCALE, key), **kwargs), key, "value")

    def txt(key: str, **kwargs) -> gr.Textbox:
        return L(gr.Textbox(placeholder=tr(DEFAULT_LOCALE, key), show_label=False, **kwargs), key, "placeholder")

    with gr.Blocks(title="ReID Trajectory Search System", fill_width=True) as demo:
        state = gr.State(initial)

        with gr.Row(elem_classes="hd"):
            H("topbar", scale=1)
            dataset_dd = L(
                gr.Dropdown(
                    choices=[(d.title or d.name, d.name) for d in available()],
                    value=initial["dataset"] or None,
                    scale=0,
                    min_width=180,
                ),
                "dataset.title",
            )
            lang_dd = L(
                gr.Dropdown(
                    choices=[(LOCALE_LABELS[k], k) for k in LOCALES],
                    value=DEFAULT_LOCALE,
                    scale=0,
                    min_width=130,
                ),
                "common.language",
            )
            refresh_btn = btn("common.refreshStatus", size="sm", variant="secondary", scale=0, min_width=110)

        H("error")

        with gr.Tabs():
            # ------------------------------------------------ 以图搜人
            tab_search = L(gr.Tab(tr(DEFAULT_LOCALE, "tabs.search"), id="search"), "tabs.search")
            with tab_search:
                with gr.Row():
                    with gr.Column(scale=4, min_width=300, elem_classes="pn"):
                        H("probe_head")
                        probe_filter = txt("search.filterPlaceholder", container=False)
                        probe_gallery = gr.Gallery(
                            value=probe_gallery_value(initial),
                            columns=6,
                            height=520,
                            allow_preview=False,
                            object_fit="contain",
                            show_label=False,
                        )
                        H("probe_hint")
                    with gr.Column(scale=7):
                        with gr.Column(elem_classes="pn"):
                            H("search_head")
                            with gr.Row():
                                topk = gr.Slider(1, 30, value=10, step=1, label="Top-K", scale=2)
                                upload_img = L(
                                    gr.Image(type="numpy", sources=["upload"], height=120, scale=1, min_width=220),
                                    "search.upload",
                                )
                            search_btn = btn("search.run", variant="primary", size="sm")
                            H("search_query")
                        H("search_hits")

            # ------------------------------------------------ 底库浏览
            tab_gallery = L(gr.Tab(tr(DEFAULT_LOCALE, "tabs.gallery"), id="gallery"), "tabs.gallery")
            with tab_gallery:
                with gr.Column(elem_classes="pn"):
                    H("gallery_head")
                    with gr.Row():
                        gallery_filter = txt("gallery.filterPlaceholder", container=False, scale=4)
                        prev_btn = btn("common.prev", size="sm", variant="secondary", scale=0, min_width=90)
                        next_btn = btn("common.next", size="sm", variant="secondary", scale=0, min_width=90)
                    H("gallery_foot")
                    gallery_grid = gr.Gallery(
                        value=gallery_grid_value(initial),
                        columns=8,
                        height=560,
                        allow_preview=False,
                        object_fit="contain",
                        show_label=False,
                    )

            # ------------------------------------------------ 检测与去重
            tab_detect = L(gr.Tab(tr(DEFAULT_LOCALE, "tabs.detect"), id="detect"), "tabs.detect")
            with tab_detect:
                with gr.Row():
                    with gr.Column(scale=5, elem_classes="pn"):
                        H("detect_head")
                        detect_in = L(gr.Image(type="numpy", sources=["upload"], height=260), "detect.uploadImage")
                        detect_btn = btn("detect.uploadImage", variant="primary", size="sm")
                        detect_out = gr.Image(interactive=False, show_label=False, container=False, height=300)
                    with gr.Column(scale=4, elem_classes="pn"):
                        H("detect_crop_head")
                        H("detect_crops")
                H("crop_search")
                with gr.Column(elem_classes="pn"):
                    H("track_head")
                    with gr.Row():
                        s_persons = L(gr.Slider(1, 6, value=3, step=1, label=tr(DEFAULT_LOCALE, "detect.persons")), "detect.persons")
                        s_frames = L(gr.Slider(30, 300, value=90, step=30, label=tr(DEFAULT_LOCALE, "detect.frames")), "detect.frames")
                        s_interval = L(gr.Slider(5, 120, value=30, step=5, label=tr(DEFAULT_LOCALE, "detect.interval")), "detect.interval")
                    track_btn = btn("detect.runDemo", variant="primary", size="sm")
                    H("track_panel")

            # ------------------------------------------------ 系统架构
            tab_arch = L(gr.Tab(tr(DEFAULT_LOCALE, "tabs.architecture"), id="architecture"), "tabs.architecture")
            with tab_arch:
                with gr.Column(elem_classes="pn"):
                    H("arch_head")
                    H("arch_panel")

            # ------------------------------------------------ 未接入能力的占位页
            tab_cameras = L(gr.Tab(tr(DEFAULT_LOCALE, "tabs.cameras"), id="cameras"), "tabs.cameras")
            with tab_cameras:
                H("cameras_panel")
            tab_edges = L(gr.Tab(tr(DEFAULT_LOCALE, "tabs.edges"), id="edges"), "tabs.edges")
            with tab_edges:
                H("edges_panel")
            tab_map = L(gr.Tab(tr(DEFAULT_LOCALE, "tabs.map"), id="map"), "tabs.map")
            with tab_map:
                H("map_panel")
            tab_k8s = L(gr.Tab(tr(DEFAULT_LOCALE, "tabs.k8s"), id="k8s"), "tabs.k8s")
            with tab_k8s:
                H("k8s_panel")

            # ------------------------------------------------ 系统与评估
            tab_system = L(gr.Tab(tr(DEFAULT_LOCALE, "tabs.system"), id="system"), "tabs.system")
            with tab_system:
                H("sys_status")
                H("sys_tiers")
                with gr.Row():
                    with gr.Column(elem_classes="pn"):
                        H("sys_index")
                        index_btn = btn("system.indexBtn", variant="primary", size="sm")
                    with gr.Column(elem_classes="pn"):
                        H("sys_eval")
                        eval_btn = btn("system.evalBtn", variant="primary", size="sm")
                H("sys_detail")

        H("footer")

        # ---------------------------------------------------------- 事件接线
        OUT = [state, *_html_components(demo), *[c for c, _, _ in LABELS]]
        OUT_FULL = [*OUT, probe_gallery, gallery_grid, detect_out, lang_dd]

        demo.load(on_load, inputs=[state], outputs=OUT_FULL)
        refresh_btn.click(on_refresh, [state, lang_dd], OUT_FULL)
        lang_dd.change(on_locale, [state, lang_dd], OUT_FULL)
        dataset_dd.change(on_dataset, [state, dataset_dd, lang_dd], OUT_FULL)
        probe_filter.change(on_probe_filter, [state, probe_filter, lang_dd], OUT_FULL)
        probe_gallery.select(on_probe_select, [state, lang_dd, topk], OUT_FULL)
        search_btn.click(on_search_upload, [state, lang_dd, upload_img, topk], OUT_FULL)
        gallery_filter.change(on_gallery_filter, [state, gallery_filter, lang_dd], OUT_FULL)
        prev_btn.click(lambda s, l: on_page(s, -1, l), [state, lang_dd], OUT_FULL)
        next_btn.click(lambda s, l: on_page(s, 1, l), [state, lang_dd], OUT_FULL)
        detect_btn.click(on_detect, [state, lang_dd, detect_in], OUT_FULL)
        track_btn.click(on_track, [state, lang_dd, s_persons, s_frames, s_interval], OUT_FULL)
        index_btn.click(on_index, [state, lang_dd], OUT_FULL)
        eval_btn.click(on_eval, [state, lang_dd], OUT_FULL)

    return demo


def _selfcheck() -> None:
    """自检：分数条的映射 + 三语 key 完整（`python app.py --check`）。"""
    assert "width:0%" in score_bar(THRESHOLD), "阈值处应为 0%"
    assert "width:100%" in score_bar(1.0), "1.0 应为满格"
    assert "width:50%" in score_bar(THRESHOLD + (1 - THRESHOLD) / 2), "区间中点应为 50%"
    assert "width:0%" in score_bar(0.5), "低于阈值钳到 0%"
    for loc in LOCALES:
        for key in ("app.title", "tabs.search", "search.upload", "system.colRank", "space.firstIndex"):
            assert tr(loc, key) != key, f"{loc} 缺 key {key}"
    print("self-check OK")


_bootstrap_data()
_ensure_weights()
get_backbone()  # ZeroGPU 要求：模型在模块顶层就放到 cuda（外面是 CUDA 模拟态）
demo = build()
demo.queue()


if __name__ == "__main__":
    if "--check" in sys.argv:
        _selfcheck()
    else:
        # ssr_mode=False：Gradio 6 默认会用 Node 起一个 SSR 服务，Space 上没必要多这一层
        demo.launch(theme=gr.themes.Base(), css=CSS, head=HEAD, ssr_mode=False)
