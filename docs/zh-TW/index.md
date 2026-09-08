# 項目索引

!!! warning "可行性驗證 demo"
    本專案僅作為**前期可行性驗證**使用，部分程式碼沿用但並不代表最終系統。文中出現的規模、
    造價、硬體清單、演算法參數均為**設計取值**，尚未經過落地驗證。

**萬級城市級跨鏡頭 Re-ID 目標追蹤系統** —— 端側去重、邊側提特徵、雲側檢索的三級協同架構驗證
demo。上流設計目標見[系統設計](system.md)，實際操作見[使用方式](usage.md)。

## 本 demo 已實作的部分

| 層 | 實作 | 對應程式碼 |
| :---- | :---- | :---- |
| 端側（檢測・去重） | YOLO26n 檢測 + ByteTrack 偽追蹤，僅在入幀/姿態顯著變化/出幀裁 256×128 | `reid_sys/detect.py` |
| 邊側（特徵抽取） | FastReID（ResNet-50，2048 維）產生嵌入向量 | `reid_sys/backbone.py` |
| 雲側（檢索） | 寫入 Milvus（milvus-lite 進程內）並做向量近鄰檢索（KNN） | `reid_sys/store.py`、`reid_sys/engine.py` |
| 閘道 | Smart Gateway（FastAPI）同時託管前端構建產物 | `reid_sys/api.py` |

!!! info "尚未接入的能力"
    攝像頭監控 / 邊緣節點 / K8s 編排 / 地圖軌跡 / 布控告警，**介面契約（schema）已定義但
    尚未接入真實服務**。對應 API 回傳 `connected: false` 及模擬或空資料（詳見 [API 文件](api.md)）。

## 倉庫結構

```tree
reid_sys/
├── reid_sys/            # 庫本體
│   ├── api.py           # Smart Gateway（FastAPI）+ 前端託管
│   ├── backbone.py      # FastReID 特徵抽取（R50・2048d）
│   ├── detect.py        # 端側：YOLO26n 檢測 + ByteTrack 去重
│   ├── engine.py        # 檢索與評測編排
│   ├── store.py         # Milvus 向量庫
│   ├── datasets.py      # demo 資料集自動發現
│   └── schemas.py       # 未接入能力的回應契約
├── scripts/
│   └── init_data.py     # reid-init：解壓 zip + 校驗/補建索引
├── web/                 # React + MUI 前端（內建 ja-JP / zh-TW / en-US）
├── data/                # demo 資料集（data1 / data2）與 Milvus DB
├── models/              # 權重（msmt_sbs_R50-ibn.pth、yolo26n.pt 等）
├── docs/                # 本文件（Zensical）
└── SYSTEM.md            # 上流設計說明書
```

## 技術堆疊

- **推理**：PyTorch 2.7.0（cu126，最後一批支援 Pascal 的官方輪子）
- **檢測/追蹤**：ultralytics YOLO26n + ByteTrack（editable 引用 `third_part/ultralytics`）
- **特徵**：fast-reid（以 sys.path 引用 `third_part/fast-reid`）
- **向量庫**：pymilvus + milvus-lite（進程內 Milvus）
- **API**：FastAPI + Uvicorn
- **前端**：React + MUI（Vite 構建 → `web/dist`）

## 資料集

`data/` 下凡同時含 `query/` + `gallery/` + `meta.json` 的目錄即被視為 demo 資料集自動發現。
目前為 **data1 / data2**（登記於 `data/datasets.json`）。每個資料集對應一個獨立 Milvus
collection（`reid_<目錄名>`）。

## 下一步

- 啟動操作 → [使用方式](usage.md)
- 查詢介面 → [API 文件](api.md)
- 閱讀設計 → [系統設計](system.md)
