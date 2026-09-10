---
hide:
  - navigation
  - toc
---

# カメラ間 Re-ID 目標追跡システム · ドキュメント

!!! warning "検証用 demo"
    本プロジェクトは**前期フィージビリティ検証**専用です。一部コードは流用ですが、最終システムを
    表すものではありません。規模・構築コスト・ハードウェア一覧・アルゴリズムパラメータはいずれも
    **設計値**であり、実運用での検証は未実施です。

本ドキュメントは 3 言語で提供しています / 本文件提供三種語言 / This documentation is available in three languages:

<div class="grid cards" markdown>

-   :material-translate:{ .lg .middle } __日本語__

    ---

    システム概要・API・使い方・システム設計

    [:octicons-arrow-right-24: ドキュメントへ](ja/index.md)

-   :material-format-text:{ .lg .middle } __繁體中文__

    ---

    系統索引、API 文件、使用方式、系統設計

    [:octicons-arrow-right-24: 前往文件](zh-TW/index.md)

-   :material-web:{ .lg .middle } __English__

    ---

    Project index, API reference, usage and system design

    [:octicons-arrow-right-24: Go to docs](en/index.md)

</div>

---

**クイックリンク / Quick links**

| セクション | 説明 |
| :---- | :---- |
| [プロジェクト概要](ja/index.md) | システムの位置づけ・リポジトリ構成・依存スタック |
| [API リファレンス](ja/api.md) | Smart Gateway（FastAPI）の全エンドポイント |
| [使い方](ja/usage.md) | 初期化から起動、フロント 9 タブのデモ |
| [システム設計](ja/system.md) | 三層協同・2 データセンター・Mamba・ウォッチリストの設計目標 |
