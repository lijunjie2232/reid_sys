# API 文件

Smart Gateway（`reid_sys/api.py`）對外暴露的 HTTP 介面。因採 FastAPI 實作，啟動後可用
**`/docs`（Swagger UI）** 與 **`/openapi.json`** 自動檢視最新 schema。

!!! tip "介面的即時契約"
    執行 `uv run python serve.py` 後開啟 `http://127.0.0.1:8000/docs`，即可看到含請求/回應
    模型（`reid_sys/schemas.py`）的互動式文件。

!!! warning "契約會變動"
    可行性驗證 demo，介面形狀、欄位命名、錯誤碼均可能隨驗證結論調整，請勿作為對外契約使用。

## 狀態／資料集

| Method | Path | 接入 | 說明 |
| :---- | :---- | :---- | :---- |
| `GET` | `/api/status` | ✅ | 回傳 backbone 維度、device、Milvus 計數、probe 計數、deployment 畫像 |
| `GET` | `/api/datasets` | ✅ | 列出 `data/` 下 demo 資料集（`current` + `items`，各含 `indexed`/`ready`） |
| `POST` | `/api/datasets/select` | ✅ | 以 `{name}` 切換目前資料集（並預熱引擎） |
| `POST` | `/api/index` | ✅ | 重建指定資料集的底庫索引 |

## 檢索（Re-ID）

| Method | Path | 接入 | 說明 |
| :---- | :---- | :---- | :---- |
| `POST` | `/api/search/probe` | ✅ | `?name=<probe圖名>&topk=10` 以既有 probe 檢索，附 `truth`（真值 ID） |
| `POST` | `/api/search/upload` | ✅ | 上傳圖（multipart `file`）檢索，回 `query_image`(data URL) + `hits` |
| `GET` | `/api/gallery` | ✅ | 底庫清單（`offset`/`limit`/`q` 分頁與篩選） |
| `GET` | `/api/probe` | ✅ | probe（query）清單 |
| `GET` | `/api/image/{split}/{name}` | ✅ | 圖片直出（`split` ∈ query/probe/gallery，防路徑穿越） |
| `GET` | `/api/eval` | ✅ | 對底庫做檢索評測（`topk` 5〜50） |

檢索回應的 `hits[]` 對每個候選回傳 `person_id`、`score`（餘弦相似度）與 `url`（gallery 圖）。
UI 對命中候選顯示「真值」徽章，並以分數條呈現相似度。

## 端側 檢測／去重

| Method | Path | 接入 | 說明 |
| :---- | :---- | :---- | :---- |
| `POST` | `/api/detect` | ✅ | 從單幀圖檢測 person，`persons[]` 含 `box`/`score`/`crop`(data URL) |
| `POST` | `/api/detect/track-demo` | ✅ | 用底庫裁圖合成多目標移動序列，實跑 YOLO26n + ByteTrack + 去重，回 `stats`/`timeline`/`samples` |

## 未接入（僅契約・`connected: false`）

以下**回應結構已定義但尚未接入真實服務**，回傳模擬或空資料。接入時只需替換 `services.py`
的 provider，前端無需改動。

| Method | Path | 未接入原因 |
| :---- | :---- | :---- |
| `GET` | `/api/cameras` | 未接入設備管理平台（台帳為 `cameras.json` 模擬組態） |
| `GET` | `/api/cameras/{id}` | 單機詳情，`status`/`stream_url` 恆為空 |
| `POST` | `/api/cameras/ping` | 未接入存活探測，回傳全量 offline |
| `GET` | `/api/monitor/cameras` | 未接入 ping/fps/NPU 負載/視頻流採集 |
| `GET` | `/api/monitor/edges` | 未接入 K3s API / 節點 Exporter |
| `GET` | `/api/k8s/workloads` | 未接入 K3s/K8s 叢集，`ready`/聚合指標為空 |
| `POST` | `/api/k8s/rollout` | 未接入叢集時僅回顯計畫（不真正執行） |
| `GET` | `/api/watchlist/alerts` | 未接入告警通道（MQTT / Pulsar），回空清單 |
| `GET` | `/api/map/track` | 未接入 GIS，僅回放設定內範例軌跡 |

## 通用規約（`reid_sys/schemas.py`）

- 未接入類回應頂層必帶 `connected: bool`；`false` 表示模擬/空，前端據此打「未接入」標。
- 分頁統一為 `{total, offset, limit, items}`。
- 時間一律 UTC ISO-8601 字串（無真實資料者為 `null`）。
- 欄位命名 snake_case。
