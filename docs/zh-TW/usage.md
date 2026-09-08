# 使用方式

## 1. 環境準備

前提：[uv](https://docs.astral.sh/uv/) 與 CUDA 相容 GPU（若無則自動退回 CPU）。

```bash
uv sync                 # 安裝依賴（含 torch cu126）
uv run reid-init        # 解壓 data/*.zip 並校驗/補建 Milvus 索引
uv run python serve.py  # 啟動 Smart Gateway → http://127.0.0.1:8000
```

`reid-init` 常用旗標：

| 旗標 | 效果 |
| :---- | :---- |
| `--check` | 只檢查不寫庫，有缺則結束碼 1（CI 用） |
| `--only data1` | 只處理指定資料集（可重複） |
| `--force` | 無視既有索引，全部重建 |
| `--no-unzip` | 跳過解壓步驟 |

瀏覽器開啟 `http://127.0.0.1:8000` 即為前端，`/docs` 為 API 文件。

## 2. 前端畫面（9 個頁籤）

頁首有運行狀態晶片（`backbone R50 · 2048d` / `device` / `milvus 計數` / `probe 計數`），
以及**資料集切換**、**語言切換（ja-JP / zh-TW / en-US）**、**重新整理狀態**。

### 以圖搜人（Search by Image）

從左側 Probe 清單選抓拍圖或上傳圖片，即觸發 Milvus 向量近鄰檢索。結果按餘弦相似度降序、
每張底庫圖唯一 ID；命中候選顯示「真值」徽章，相似度以分數條呈現。

![檢索（初始）](../fig/screenshots/search-empty.png)
![檢索結果與分數條](../fig/screenshots/search-results.png)

### 底庫瀏覽（Gallery）

分頁瀏覽底庫圖，用於核對檢索候選出處。

### 檢測與去重（Detection & Dedup）

- **單幀 person 檢測**：上傳街景/卡口圖，端側僅裁出 person 框（不做特徵計算）。
- **追蹤去重（合成影片）**：用底庫裁圖合成多目標移動序列，實跑 YOLO26n + ByteTrack + 去重，
  可在時間軸查看僅在入幀/姿態變化/出幀觸發的 Emit。

![檢測與去重](../fig/screenshots/detection-dedup.png)

### 系統構成（Architecture）

將 `SYSTEM.md` 的上流設計視覺化（三級協同、系統規模、雙機房、Mamba、布控、Smart Gateway 路由）。
與下層頁籤一樣，常駐橫幅標明**數值為設計值、本 demo 未實裝**。

### 攝像頭監控 / 邊緣節點 / 設置點地圖

端側 IPC、街區邊緣、GIS 點位的監控畫面。因**設備管理基礎 / K3s / GIS 未接入**，指標為空，
僅顯示 `未接入` 徽章與佔位台帳。

![攝像頭監控](../fig/screenshots/cameras.png)
![邊緣節點](../fig/screenshots/edge-nodes.png)
![設置點地圖](../fig/screenshots/location-map.png)

### K8s 編排

設計原則 #5 的容器化／編成像（edge=K3s / cloud=K8s 的工作負載清單、灰度發布、彈性擴縮）。
**未接入真實叢集**，`Ready`/聚合指標為空。

![K8s 編排](../fig/screenshots/k8s-orchestration.png)

### 系統與評測（System & Eval）

顯示 `/api/status` 運行資訊與 `/api/eval` 檢索評測（Rank-1 / mAP 類指標）。

## 3. 切換資料集

頁首資料集選單可切 `data1` / `data2`。切換僅移動「目前指標」，若對應 collection 未建索引，
請用 `reid-init` 或 `POST /api/index` 補建。

## 4. 建置本文件

```bash
uv run zensical serve   # 本地預覽
uv run zensical build   # 輸出靜態站到 site/
```
