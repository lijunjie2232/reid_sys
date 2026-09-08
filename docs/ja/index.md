# プロジェクト概要

!!! warning "検証用 demo"
    本プロジェクトは**前期フィージビリティ検証**専用です。一部コードは流用ですが、最終システムを
    表すものではありません。規模・構築コスト・ハードウェア一覧・アルゴリズムパラメータはいずれも
    **設計値**であり、実運用での検証は未実施です。

**都市規模（万級カメラ）のカメラ間 Re-ID 目標追跡システム** —— カメラ側で重複排除、エッジ側で
特徴抽出、クラウド側でベクトル検索を行う三層協同アーキテクチャの検証 demo です。上流設計目標は
[システム設計](system.md) に、実際の動作は [使い方](usage.md) に記載しています。

## この demo が実装しているもの

| 層 | 実装 | 対応コード |
| :---- | :---- | :---- |
| カメラ側（検出・重複排除） | YOLO26n 検出 + ByteTrack 擬似トラッキング。出現・姿勢変化・退出時のみ 256×128 を切り出し | `reid_sys/detect.py` |
| エッジ側（特徴抽出） | FastReID（ResNet-50、2048 次元）で埋め込みベクトルを生成 | `reid_sys/backbone.py` |
| クラウド側（検索） | Milvus（milvus-lite によるプロセス内インスタンス）への書き込みとベクトル近傍検索（k-NN） | `reid_sys/store.py`、`reid_sys/engine.py` |
| ゲートウェイ | Smart Gateway（FastAPI）がフロントエンドのビルド成果物も配信 | `reid_sys/api.py` |

!!! info "未接続の機能"
    カメラ監視 / エッジノード / K8s オーケストレーション / 地図上の軌跡 / ウォッチリストアラートは、
    **契約（スキーマ）は定義済みですが実サービスは未接続**です。対応 API は `connected: false` を返し、
    モックまたは空データを返します（詳細は [API リファレンス](api.md)）。

## リポジトリ構成

```tree
reid_sys/
├── reid_sys/            # ライブラリ本体
│   ├── api.py           # Smart Gateway（FastAPI）+ フロント配信
│   ├── backbone.py      # FastReID 特徴抽出（R50・2048 次元）
│   ├── detect.py        # カメラ側：YOLO26n 検出 + ByteTrack 重複排除
│   ├── engine.py        # 検索・評価のオーケストレーション
│   ├── store.py         # Milvus ベクトルストア
│   ├── datasets.py      # demo データセットの自動検出
│   └── schemas.py       # 未接続機能のレスポンス契約
├── scripts/
│   └── init_data.py     # reid-init：zip 展開 + 索引の検証／補完構築
├── web/                 # React + MUI フロントエンド（ja-JP / zh-TW / en-US を内蔵）
├── data/                # demo データセット（data1 / data2）と Milvus DB
├── models/              # 重み（msmt_sbs_R50-ibn.pth、yolo26n.pt など）
├── docs/                # 本ドキュメント（Zensical）
└── SYSTEM.md            # 上流設計説明書
```

## 技術スタック

- **推論**：PyTorch 2.7.0（cu126・Pascal に対応した最後の公式ホイール）
- **検出／トラッキング**：ultralytics YOLO26n + ByteTrack（`third_part/ultralytics` を editable で参照）
- **特徴**：fast-reid（`third_part/fast-reid` を sys.path 経由で参照）
- **ベクトル DB**：pymilvus + milvus-lite（プロセス内 Milvus）
- **API**：FastAPI + Uvicorn
- **フロントエンド**：React + MUI（Vite でビルド → `web/dist`）

## データセット

`data/` 配下で `query/` + `gallery/` + `meta.json` を持つディレクトリが demo データセットとして
自動検出されます。現状は **data1 / data2**（`data/datasets.json` に登録）。各データセットは
独立した Milvus collection（`reid_<ディレクトリ名>`）に対応します。

## 次のステップ

- 起動して触る → [使い方](usage.md)
- インターフェースを引く → [API リファレンス](api.md)
- 設計を読む → [システム設計](system.md)
