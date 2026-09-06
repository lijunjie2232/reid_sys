"""把本仓库的两套 demo 数据集整理成统一的 `query/ gallery/ meta.json` 结构。

约定（此后所有 demo 数据集都长这样，`scripts/init_data.py` 靠它识别）：

    data/data1/            # GRID / underground_reid（端侧抓拍演示）
      query/     *.jpeg    # 原 probe 目录
      gallery/   *.jpeg
      meta.json
    data/data2/            # MSMT17_demo（跨镜头演示）
      query/     *.jpg
      gallery/   *.jpg
      meta.json

    python scripts/package_datasets.py            # dry-run，只报告
    python scripts/package_datasets.py --apply    # 真正复制
    python scripts/package_datasets.py --apply --zip   # 复制并重新打包成 data/<name>.zip

    # 生成物：data/data1.zip / data/data2.zip 是入库的（见 .gitignore），
    # 解压与建索引交给 `scripts/init_data.py`（`uv run reid-init`）。

.. note::
   当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。
"""

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reid_sys import ROOT  # noqa: E402
from reid_sys.engine import IMAGE_SUFFIXES, list_images, parse_name  # noqa: E402

DATA = ROOT / "data"

#: 数据集定义：(目标目录名, 源 query 目录, 源 gallery 目录, 元信息)
DATASETS = [
    {
        "name": "data1",
        "title": "GRID / underground_reid",
        "query_src": DATA / "underground_reid" / "probe",
        "gallery_src": DATA / "underground_reid" / "gallery",
        "description": "QMUL GRID 地下通道抓拍；每人一张 query，gallery 里混 775 张干扰图。",
        "metric_note": "零样本 rank-1 15.2% / rank-5 26.4% / mAP 0.216（全量 250 probe）。",
    },
    {
        "name": "data2",
        "title": "MSMT17_demo",
        "query_src": DATA / "MSMT17_demo" / "query",
        "gallery_src": DATA / "MSMT17_demo" / "gallery",
        "description": "从 MSMT17 手工构建的 demo 划分；400 人 / 400 query / 1200 gallery。",
        "metric_note": "同域 demo，rank-1 96.0% / rank-5 100% / mAP 0.977。",
    },
]


def build_meta(ds: dict, query_names: list[str], gallery_names: list[str]) -> dict:
    """生成统一 meta.json。附带每张图的解析字段，便于前端展示与排障。"""
    def rows(names, split):
        out = []
        for n in names:
            parsed = parse_name(n)
            out.append({"name": n, "split": split, "person_id": parsed["person_id"],
                        "camera": parsed["camera"]})
        return out

    persons = sorted({parse_name(n)["person_id"] for n in query_names})
    return {
        "name": ds["name"],
        "title": ds["title"],
        "description": ds["description"],
        "metric_note": ds["metric_note"],
        "query_images": len(query_names),
        "gallery_images": len(gallery_names),
        "persons": len(persons),
        "suffixes": sorted({Path(n).suffix.lower() for n in query_names + gallery_names}),
        "query": rows(query_names, "query"),
        "gallery": rows(gallery_names, "gallery"),
    }


def make_zip(out: Path) -> tuple[int, float]:
    """把数据集目录打成 `data/<name>.zip`（zip 内路径以目录名为根）。

    只收 `query/` `gallery/` `meta.json` —— 目录里若混进别的东西不会被带走。
    返回 (文件数, MB)。
    """
    zpath = out.with_suffix(".zip")
    n = 0
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(out.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(out.parent))
                n += 1
    return n, zpath.stat().st_size / 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正复制（默认只报告）")
    ap.add_argument("--force", action="store_true", help="目标已存在时也重建")
    ap.add_argument("--zip", dest="make_zip", action="store_true",
                    help="复制完再打包成 data/<name>.zip（入库用）")
    args = ap.parse_args()

    for ds in DATASETS:
        out = DATA / ds["name"]
        print(f"\n=== {ds['name']}  <-  {ds['title']} ===")
        for key in ("query_src", "gallery_src"):
            if not ds[key].is_dir():
                sys.exit(f"  缺少源目录 {ds[key]}")
        query_names = list_images(ds["query_src"])
        gallery_names = list_images(ds["gallery_src"])
        if not query_names or not gallery_names:
            sys.exit(f"  源目录为空：{ds['query_src']} / {ds['gallery_src']}")
        print(f"  query   {len(query_names)} 张  ({ds['query_src']})")
        print(f"  gallery {len(gallery_names)} 张  ({ds['gallery_src']})")

        if not out.exists() or args.force:
            if not args.apply:
                continue

            if out.exists():
                shutil.rmtree(out)
            (out / "query").mkdir(parents=True)
            (out / "gallery").mkdir(parents=True)

            for split, src, names in (
                ("query", ds["query_src"], query_names),
                ("gallery", ds["gallery_src"], gallery_names),
            ):
                for n in names:
                    shutil.copy2(src / n, out / split / n)

            meta = build_meta(ds, query_names, gallery_names)
            (out / "meta.json").write_text(
                json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8"
            )
            print(f"  写入 {out}（query/gallery/meta.json）")
        else:
            print(f"  目标已存在，跳过（加 --force 重建）：{out}")

        if args.make_zip:
            if not args.apply:
                print("  [dry-run] 将打包为 data/%s.zip" % ds["name"])
            else:
                n, mb = make_zip(out)
                print(f"  打包 data/{ds['name']}.zip  {n} 个文件  {mb:.2f} MB")

    if not args.apply:
        print("\n[dry-run] 未复制任何文件。确认后加 --apply 执行。")


if __name__ == "__main__":
    main()
