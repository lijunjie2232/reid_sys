# Project Index

!!! warning "Feasibility-study demo"
    This project is a **preliminary feasibility study** only. Some code is carried over and does
    not represent the final system. All scale, cost, hardware lists and algorithm parameters are
    **design values** that have not been validated in production.

The **city-scale cross-camera Re-ID tracking system (10,000-camera scale)** is a demo validating a
three-tier architecture: dedup at the endpoint, feature extraction at the edge, and vector retrieval
in the cloud. Upstream design goals are in [System Design](system.md); hands-on operation is in
[Usage](usage.md).

## What this demo implements

| Tier | Implementation | Code |
| :---- | :---- | :---- |
| Endpoint (detect・dedup) | YOLO26n detection + ByteTrack pseudo-tracking; crops 256×128 only on enter/pose-change/exit | `reid_sys/detect.py` |
| Edge (embedding) | FastReID (ResNet-50, 2048-d) produces embedding vectors | `reid_sys/backbone.py` |
| Cloud (retrieval) | Writes to Milvus (in-process milvus-lite) and runs k-NN vector retrieval | `reid_sys/store.py`, `reid_sys/engine.py` |
| Gateway | Smart Gateway (FastAPI) also hosts the built frontend | `reid_sys/api.py` |

!!! info "Not-yet-connected capabilities"
    Camera monitoring / edge nodes / K8s orchestration / map tracks / watchlist alerts have a
    **defined contract (schema) but no real service behind them**. Their APIs return
    `connected: false` with mock or empty data (see the [API reference](api.md)).

## Repository layout

```tree
reid_sys/
├── reid_sys/            # library
│   ├── api.py           # Smart Gateway (FastAPI) + frontend hosting
│   ├── backbone.py      # FastReID embedding (R50, 2048-d)
│   ├── detect.py        # endpoint: YOLO26n + ByteTrack dedup
│   ├── engine.py        # retrieval & evaluation orchestration
│   ├── store.py         # Milvus vector store
│   ├── datasets.py      # demo dataset discovery
│   └── schemas.py       # response contracts for unconnected features
├── scripts/
│   └── init_data.py     # reid-init: unzip + verify/build index
├── web/                 # React + MUI frontend (ja-JP / zh-TW / en-US built in)
├── data/                # demo datasets (data1 / data2) and the Milvus DB
├── models/              # weights (msmt_sbs_R50-ibn.pth, yolo26n.pt, ...)
├── docs/                # this documentation (Zensical)
└── SYSTEM.md            # high-level design spec
```

## Tech stack

- **Inference**: PyTorch 2.7.0 (cu126 — the last official wheels supporting Pascal)
- **Detection/tracking**: ultralytics YOLO26n + ByteTrack (editable path to `third_part/ultralytics`)
- **Embedding**: fast-reid (imported via sys.path from `third_part/fast-reid`)
- **Vector DB**: pymilvus + milvus-lite (in-process Milvus)
- **API**: FastAPI + Uvicorn
- **Frontend**: React + MUI (Vite build → `web/dist`)

## Datasets

Any directory under `data/` containing `query/` + `gallery/` + `meta.json` is auto-discovered as a
demo dataset. Currently **data1 / data2** (registered in `data/datasets.json`). Each dataset maps to
its own Milvus collection (`reid_<dirname>`).

## Next steps

- Run it → [Usage](usage.md)
- Look up endpoints → [API reference](api.md)
- Read the design → [System Design](system.md)
