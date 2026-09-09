# 跨鏡頭 Re-ID 目標追蹤系統

[![日本語](https://img.shields.io/badge/日本語-lightgrey)](README.md) [![繁體中文](https://img.shields.io/badge/繁體中文-blue)](README.zh-TW.md) [![English](https://img.shields.io/badge/English-lightgrey)](README.en-US.md)

> **可行性驗證 demo**：本專案僅作為**前期可行性驗證**使用，部分程式碼沿用但並不代表最終系統。
> 規模、造價、硬體清單、演算法參數均為**設計取值**，尚未經過落地驗證。

**萬級城市級跨鏡頭 Re-ID 目標追蹤系統** —— 端側去重、邊側提特徵、雲側檢索的三級協同架構驗證 demo。

## 快速開始

前提：[uv](https://docs.astral.sh/uv/) 與支援 CUDA 的 GPU（若無則自動退回 CPU）。

```bash
uv sync                 # 安裝相依套件（含 torch cu126）
uv run reid-init        # 解壓 data/*.zip 並校驗/補建 Milvus 索引
uv run python serve.py  # 啟動 Smart Gateway → http://127.0.0.1:8000
```

`http://127.0.0.1:8000` 為前端（9 個分頁，內建 ja-JP / zh-TW / en-US），`/docs` 為 API 文件。

## 文件

| 內容 | 連結 |
| :---- | :---- |
| 項目索引（實作範圍、倉庫結構、技術堆疊） | [docs/zh-TW/index.md](docs/zh-TW/index.md) |
| 使用方式（初始化至啟動、前端 9 個分頁詳解） | [docs/zh-TW/usage.md](docs/zh-TW/usage.md) |
| API 文件（Smart Gateway 全部端點） | [docs/zh-TW/api.md](docs/zh-TW/api.md) |
| 系統設計（三級協同、雙機房、Mamba、布控） | [docs/zh-TW/system.md](docs/zh-TW/system.md) |
| 上流設計說明書（原文） | [SYSTEM.md](SYSTEM.md) |

本文件站的建置：`uv run zensical serve`（本地預覽）/ `uv run zensical build`（靜態輸出至 `site/`）。
