# API リファレンス

Smart Gateway（`reid_sys/api.py`）が公開する HTTP インターフェース。
FastAPI 実装のため、起動後に **`/docs`（Swagger UI）** と **`/openapi.json`** で最新の
スキーマを自動参照できます。

!!! tip "生きている契約"
    `uv run python serve.py` 起動後、`http://127.0.0.1:8000/docs` にアクセスすると、
    リクエスト／レスポンスモデル（`reid_sys/schemas.py`）を含む対話的な仕様が表示されます。

!!! warning "契約は変動します"
    検証用 demo のため、インターフェース形状・フィールド名・エラーコードは検証結論により変動します。
    対外契約として使わないでください。

## 状態・データセット

| Method | Path | 接続 | 説明 |
| :---- | :---- | :---- | :---- |
| `GET` | `/api/status` | ✅ | バックボーンの次元・device・Milvus 件数・probe 件数・deployment 情報を返す |
| `GET` | `/api/datasets` | ✅ | `data/` 配下の demo データセット一覧（`current` + `items`、各 `indexed`／`ready`） |
| `POST` | `/api/datasets/select` | ✅ | `{name}` で現在のデータセットを切り替え（エンジンをウォームアップ） |
| `POST` | `/api/index` | ✅ | 指定データセットのギャラリー索引を再構築 |

## 検索（Re-ID）

| Method | Path | 接続 | 説明 |
| :---- | :---- | :---- | :---- |
| `POST` | `/api/search/probe` | ✅ | `?name=<probe 画像名>&topk=10` で既存 probe から検索。`truth`（真値 ID）付き |
| `POST` | `/api/search/upload` | ✅ | アップロード画像（multipart `file`）で検索。`query_image`（data URL）+ `hits` |
| `GET` | `/api/gallery` | ✅ | ギャラリー一覧（`offset`／`limit`／`q` でページング・絞り込み） |
| `GET` | `/api/probe` | ✅ | probe（query）一覧 |
| `GET` | `/api/image/{split}/{name}` | ✅ | 画像の生配信（`split` ∈ query/probe/gallery、パストラバーサルを防止） |
| `GET` | `/api/eval` | ✅ | ギャラリーに対する検索評価（`topk` 5〜50） |

検索レスポンスの `hits[]` は各候補について `person_id`・`score`（コサイン類似度）と
`url`（ギャラリー画像）を返します。UI では一致候補に「真値」バッジとスコアバーを表示します。

## カメラ側 検出・重複排除

| Method | Path | 接続 | 説明 |
| :---- | :---- | :---- | :---- |
| `POST` | `/api/detect` | ✅ | 1 フレームの画像から person を検出。`persons[]` に `box`／`score`／`crop`（data URL） |
| `POST` | `/api/detect/track-demo` | ✅ | ギャラリーの切り出し画像で複数ターゲットの移動系列を合成し、YOLO26n + ByteTrack + 重複排除を実行。`stats`／`timeline`／`samples` |

## 未接続（契約のみ・`connected: false`）

以下は**レスポンス構造は定義済みですが実サービスは未接続**です。モックまたは空データを返します。
実接続時は `services.py` の provider を差し替えるだけで、フロントエンドは変更不要です。

| Method | Path | 未接続の理由 |
| :---- | :---- | :---- |
| `GET` | `/api/cameras` | デバイス管理プラットフォーム未接続（台帳は `cameras.json` のモック設定） |
| `GET` | `/api/cameras/{id}` | 単体の詳細。`status`／`stream_url` は常に空 |
| `POST` | `/api/cameras/ping` | ライブネス確認未接続。全件 offline を返す |
| `GET` | `/api/monitor/cameras` | ping/fps/NPU 負荷/映像ストリームの収集サービス未接続 |
| `GET` | `/api/monitor/edges` | K3s API / ノード Exporter 未接続 |
| `GET` | `/api/k8s/workloads` | K3s/K8s クラスタ未接続。`ready`／集約指標は空 |
| `POST` | `/api/k8s/rollout` | クラスタ未接続のため計画をエコーするのみ（実行しない） |
| `GET` | `/api/watchlist/alerts` | アラートチャネル（MQTT / Pulsar）未接続。空リスト |
| `GET` | `/api/map/track` | GIS 未接続。設定内のサンプル軌跡を再生するのみ |

## 共通規約（`reid_sys/schemas.py`）

- 未接続系のレスポンス最上位には必ず `connected: bool`。`false` は「モック/空」を意味し、
  フロントエンドは「未接続」バッジを表示します。
- ページングは統一で `{total, offset, limit, items}`。
- 時刻は UTC ISO-8601 文字列（実データが無いものは `null`）。
- フィールド名は snake_case。
