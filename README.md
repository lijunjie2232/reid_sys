# カメラ間 Re-ID 目標追跡システム

_正式名称（中国語）：跨镜头 Re-ID 目标追踪系统_

[![日本語](https://img.shields.io/badge/日本語-blue)](README.md) [![繁體中文](https://img.shields.io/badge/繁體中文-lightgrey)](README.zh-TW.md) [![English](https://img.shields.io/badge/English-lightgrey)](README.en-US.md)

> **検証用 demo**：本プロジェクトは**前期フィージビリティ検証**専用です。一部コードは流用ですが、
> 最終システムを表すものではありません。規模・構築コスト・ハードウェア一覧・アルゴリズムパラメータは
> いずれも**設計値**であり、実運用での検証は未実施です。

**都市規模（万級カメラ）のカメラ間 Re-ID 目標追跡システム** —— カメラ側で重複排除、エッジ側で
特徴抽出、クラウド側でベクトル検索を行う三層協同アーキテクチャの検証 demo です。

## クイックスタート

前提：[uv](https://docs.astral.sh/uv/) と CUDA 対応 GPU（無い場合は CPU に自動フォールバック）

```bash
uv sync                 # 依存をインストール（torch cu126 を含む）
uv run reid-init        # data/*.zip を展開し、Milvus インデックスを検証／補完構築
uv run python serve.py  # Smart Gateway を起動 → http://127.0.0.1:8000
```

`http://127.0.0.1:8000` にフロントエンド（9 タブ、ja-JP / zh-TW / en-US を内蔵）、`/docs` に API 仕様。

## ドキュメント

| 内容 | リンク |
| :---- | :---- |
| プロジェクト概要（実装範囲・リポジトリ構成・技術スタック） | [docs/ja/index.md](docs/ja/index.md) |
| 使い方（初期化〜起動・フロント 9 タブの詳細） | [docs/ja/usage.md](docs/ja/usage.md) |
| API リファレンス（Smart Gateway の全エンドポイント） | [docs/ja/api.md](docs/ja/api.md) |
| システム設計（三層協同・2 データセンター・Mamba・ウォッチリスト） | [docs/ja/system.md](docs/ja/system.md) |
| 上流設計説明書（中国語原文） | [SYSTEM.md](SYSTEM.md) |

本ドキュメントサイトのビルド：`uv run zensical serve`（プレビュー）/ `uv run zensical build`（`site/` に静的出力）。
