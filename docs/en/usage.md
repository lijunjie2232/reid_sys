# Usage

## 1. Setup

Prerequisites: [uv](https://docs.astral.sh/uv/) and a CUDA-capable GPU (falls back to CPU otherwise).

```bash
uv sync                 # install dependencies (incl. torch cu126)
uv run reid-init        # unzip data/*.zip and verify/build the Milvus index
uv run python serve.py  # start the Smart Gateway → http://127.0.0.1:8000
```

Key `reid-init` flags:

| Flag | Effect |
| :---- | :---- |
| `--check` | Verify only, no writes; exit code 1 if incomplete (for CI) |
| `--only data1` | Process only the named dataset (repeatable) |
| `--force` | Ignore existing index and rebuild everything |
| `--no-unzip` | Skip the unzip step |

Open `http://127.0.0.1:8000` for the frontend; `/docs` for the API spec.

## 2. Frontend (9 tabs)

The header shows runtime chips (`backbone R50 · 2048d` / `device` / `milvus count` / `probe count`)
plus **dataset switch**, **language switch (ja-JP / zh-TW / en-US)** and **refresh status**.

### Search by Image

Pick a capture from the left Probe list or upload an image to trigger Milvus k-NN retrieval.
Results are ordered by cosine similarity, one unique ID per gallery image; matches get a
"ground-truth" badge and similarity is shown as a score bar.

![Search (initial)](../fig/screenshots/search-empty.png)
![Results with score bars](../fig/screenshots/search-results.png)

### Gallery

Paged browsing of the gallery, used to confirm where retrieval candidates come from.

### Detection & Dedup

- **Single-frame person detection**: upload a street/entrance image; the endpoint crops person boxes
  only (no feature computation).
- **Tracking dedup (synthetic video)**: synthesize a multi-target sequence from gallery crops and run
  YOLO26n + ByteTrack + dedup, viewing the emits that fire only on enter/pose-change/exit.

![Detection & dedup](../fig/screenshots/detection-dedup.png)

### Architecture

Visualizes the upstream design from `SYSTEM.md` (three-tier collaboration, system scale, dual data
centers, Mamba, watchlist, Smart Gateway routing). Like the tabs below, a banner always notes the
**figures are design values, not implemented in this demo**.

### Cameras / Edge Nodes / Location Map

Monitoring views for endpoint IPCs, street edge nodes and GIS points. Because the **device platform /
K3s / GIS are not connected**, metrics are blank and only a "not connected" badge plus a placeholder
ledger are shown.

![Cameras](../fig/screenshots/cameras.png)
![Edge nodes](../fig/screenshots/edge-nodes.png)
![Location map](../fig/screenshots/location-map.png)

### K8s Orchestration

The containerization/orchestration picture from design principle #5 (edge=K3s / cloud=K8s workload
list, canary release, elastic scaling). **No real cluster**, so `Ready`/aggregate metrics are blank.

![K8s orchestration](../fig/screenshots/k8s-orchestration.png)

### System & Eval

Shows runtime info from `/api/status` and retrieval evaluation from `/api/eval` (Rank-1 / mAP-style
metrics).

## 3. Switching datasets

Use the header dataset menu to switch `data1` / `data2`. Switching only moves the "current pointer";
if the matching collection is not indexed, rebuild it with `reid-init` or `POST /api/index`.

## 4. Building this documentation

```bash
uv run zensical serve   # local preview
uv run zensical build   # emit the static site to site/
```
