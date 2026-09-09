# Cross-Camera Re-ID Tracking System

[![日本語](https://img.shields.io/badge/日本語-lightgrey)](README.md) [![繁體中文](https://img.shields.io/badge/繁體中文-lightgrey)](README.zh-TW.md) [![English](https://img.shields.io/badge/English-blue)](README.en-US.md)

> **Feasibility-study demo**: this project is a **preliminary feasibility study** only. Some code is
> carried over and does not represent the final system. All scale, cost, hardware lists and algorithm
> parameters are **design values** that have not been validated in production.

The **city-scale cross-camera Re-ID tracking system (10,000-camera scale)** validates a three-tier
architecture: dedup at the endpoint, feature extraction at the edge, and vector retrieval in the cloud.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and a CUDA-capable GPU (falls back to CPU automatically).

```bash
uv sync                 # install dependencies (incl. torch cu126)
uv run reid-init        # unzip data/*.zip, verify/build the Milvus index
uv run python serve.py  # start the Smart Gateway → http://127.0.0.1:8000
```

`http://127.0.0.1:8000` serves the frontend (9 tabs, ja-JP / zh-TW / en-US built in); `/docs` is the API reference.

## Documentation

| Section | Link |
| :---- | :---- |
| Project index (scope, repository layout, tech stack) | [docs/en/index.md](docs/en/index.md) |
| Usage (init through launch, all 9 frontend tabs) | [docs/en/usage.md](docs/en/usage.md) |
| API reference (every Smart Gateway endpoint) | [docs/en/api.md](docs/en/api.md) |
| System design (three-tier, dual data center, Mamba, watchlist) | [docs/en/system.md](docs/en/system.md) |
| High-level design spec (original) | [SYSTEM.md](SYSTEM.md) |

Build this docs site: `uv run zensical serve` (preview) / `uv run zensical build` (static output to `site/`).
