# API Reference

HTTP endpoints exposed by the Smart Gateway (`reid_sys/api.py`). Because it is a FastAPI app, the
live schema is auto-published at **`/docs` (Swagger UI)** and **`/openapi.json`** once running.

!!! tip "Living contract"
    After `uv run python serve.py`, open `http://127.0.0.1:8000/docs` to see the interactive spec
    including request/response models (`reid_sys/schemas.py`).

!!! warning "The contract may change"
    This is a feasibility-study demo — endpoint shapes, field names and error codes may change with
    validation conclusions. Do not treat them as an external contract.

## Status / datasets

| Method | Path | Connected | Description |
| :---- | :---- | :---- | :---- |
| `GET` | `/api/status` | ✅ | Backbone dim, device, Milvus count, probe count, deployment profile |
| `GET` | `/api/datasets` | ✅ | Lists demo datasets under `data/` (`current` + `items`, each with `indexed`/`ready`) |
| `POST` | `/api/datasets/select` | ✅ | Switch current dataset via `{name}` (warms the engine) |
| `POST` | `/api/index` | ✅ | Rebuild the gallery index for a dataset |

## Retrieval (Re-ID)

| Method | Path | Connected | Description |
| :---- | :---- | :---- | :---- |
| `POST` | `/api/search/probe` | ✅ | Search by existing probe: `?name=<probe>&topk=10`; includes `truth` (ground-truth ID) |
| `POST` | `/api/search/upload` | ✅ | Search by uploaded image (multipart `file`); returns `query_image` (data URL) + `hits` |
| `GET` | `/api/gallery` | ✅ | Gallery list (paged/filtered via `offset`/`limit`/`q`) |
| `GET` | `/api/probe` | ✅ | Probe (query) list |
| `GET` | `/api/image/{split}/{name}` | ✅ | Raw image serving (`split` ∈ query/probe/gallery; path-traversal guarded) |
| `GET` | `/api/eval` | ✅ | Retrieval evaluation against the gallery (`topk` 5–50) |

Each `hits[]` entry returns `person_id`, `score` (cosine similarity) and `url` (gallery image). The
UI shows a "ground-truth" badge on matches and a score bar for similarity.

## Endpoint detection / dedup

| Method | Path | Connected | Description |
| :---- | :---- | :---- | :---- |
| `POST` | `/api/detect` | ✅ | Detect persons in a single frame; `persons[]` with `box`/`score`/`crop` (data URL) |
| `POST` | `/api/detect/track-demo` | ✅ | Synthesize a multi-target sequence from gallery crops and run YOLO26n + ByteTrack + dedup; returns `stats`/`timeline`/`samples` |

## Not connected (contract only, `connected: false`)

These have a **defined response structure but no real service**; they return mock or empty data.
Wiring a real service only requires swapping the provider in `services.py` — no frontend change.

| Method | Path | Why not connected |
| :---- | :---- | :---- |
| `GET` | `/api/cameras` | No device-management platform (ledger is mock `cameras.json`) |
| `GET` | `/api/cameras/{id}` | Single-device detail; `status`/`stream_url` always empty |
| `POST` | `/api/cameras/ping` | No liveness probe; returns all offline |
| `GET` | `/api/monitor/cameras` | No ping/fps/NPU-load/stream collector |
| `GET` | `/api/monitor/edges` | No K3s API / node exporters |
| `GET` | `/api/k8s/workloads` | No K3s/K8s cluster; `ready`/aggregate metrics empty |
| `POST` | `/api/k8s/rollout` | Echoes the plan only when no cluster is connected (does not execute) |
| `GET` | `/api/watchlist/alerts` | No alert channel (MQTT / Pulsar); returns empty list |
| `GET` | `/api/map/track` | No GIS; replays a sample track from config only |

## Conventions (`reid_sys/schemas.py`)

- Every not-connected response carries a top-level `connected: bool`; `false` means mock/empty and
  the frontend renders a "not connected" badge.
- Pagination is uniformly `{total, offset, limit, items}`.
- Timestamps are UTC ISO-8601 strings (`null` when no real data).
- Field names are snake_case.
