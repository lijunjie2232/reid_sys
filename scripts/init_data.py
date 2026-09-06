"""一键初始化 demo 数据：解压数据集 + 校验/补建 Milvus 索引。

流程
----
1. **解压**：扫描 `data/*.zip`，若对应的目录还不存在就就地解压（已存在则跳过）。
2. **发现**：任何含 `query/` + `gallery/` + `meta.json` 的目录都被认作 demo 数据集
   （见 `reid_sys/datasets.py`）。
3. **校验**：比对「集合里已索引条数」与「gallery 目录实际张数」。
4. **补建**：不一致（未建 / 残缺 / 多出）就重建该集合，使两者一致。

常用：
    uv run reid-init                 # 解压 + 缺啥补啥（默认，安全可重复跑）
    uv run reid-init --check         # 只检查不写库；有缺就非零退出（CI 用）
    uv run reid-init --only data1    # 只处理指定数据集
    uv run reid-init --force         # 无视已有索引，全部重建

.. note::
   当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。
"""

from __future__ import annotations

import argparse
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reid_sys import ROOT  # noqa: E402
from reid_sys import datasets as ds_registry  # noqa: E402
from reid_sys.engine import ReIDEngine  # noqa: E402

DATA_DIR = ROOT / "data"

MANIFEST = DATA_DIR / "datasets.json"


def ensure_manifest(data_dir: Path) -> None:
    """若 `data/datasets.json` 不存在，则按当前扫到的目录生成一份。

    清单决定「哪些目录算 demo 数据集、以什么顺序出现在前端下拉框」。
    仓库里已带一份（data1/data2），这里只是给「clone 后只有 zip」的场景兜底。
    """
    path = data_dir / "datasets.json"
    if path.exists():
        return
    names = []
    for child in sorted(data_dir.iterdir()) if data_dir.is_dir() else []:
        if child.name.startswith("."):
            continue
        if all((child / e).exists() for e in ds_registry.REQUIRED_ENTRIES):
            names.append(child.name)
    if not names:
        return
    import json

    path.write_text(json.dumps({"datasets": names}, indent=2) + "\n", encoding="utf-8")
    print(f"  [生成] {path.name} -> {names}")


# ------------------------------------------------------------------ 解压

def is_demo_zip(zpath: Path) -> bool:
    """判断一个 zip 里装的是不是一个 demo 数据集。

    只认「顶层就是 `<zip名>/query/ + <zip名>/gallery/ + <zip名>/meta.json`」的 zip。
    这样 `data/` 里那些**原始数据集**压缩包（msmt17.zip 有 2.5GB、underground_reid.zip）
    就不会被顺手解开 —— 它们不是 demo 数据集，解了纯属浪费时间和磁盘。
    """
    stem = zpath.stem
    try:
        with zipfile.ZipFile(zpath) as zf:
            names = zf.namelist()
    except (zipfile.BadZipFile, OSError):
        return False

    has_query = has_gallery = has_meta = False
    for n in names:
        if n == f"{stem}/meta.json":
            has_meta = True
        elif n.startswith(f"{stem}/query/"):
            has_query = True
        elif n.startswith(f"{stem}/gallery/"):
            has_gallery = True
        if has_query and has_gallery and has_meta:
            return True
    return False


def unzip_datasets(data_dir: Path, force: bool = False) -> list[str]:
    """把 `data/*.zip` 里**符合 demo 数据集结构**的解压到同名目录。

    已存在同名目录则跳过（`force=True` 时重解）。
    不是 demo 数据集的 zip（原始数据集压缩包）会明确报告并跳过。

    返回本次实际解压的 zip 名列表。
    """
    done = []
    if not data_dir.is_dir():
        return done
    for zpath in sorted(data_dir.glob("*.zip")):
        target = data_dir / zpath.stem
        if target.exists() and not force:
            print(f"  [跳过] {zpath.name} -> {target.name}/ 已存在")
            continue
        if not is_demo_zip(zpath):
            print(f"  [忽略] {zpath.name} 不是 demo 数据集 zip"
                  f"（需内含 {zpath.stem}/query/ + gallery/ + meta.json）")
            continue
        print(f"  [解压] {zpath.name} -> {target.name}/")
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(data_dir)
        done.append(zpath.name)
    return done



# ------------------------------------------------------------------ 校验 / 建索引

def ensure_index(backbone, dataset, force: bool = False, check_only: bool = False) -> dict:
    """保证某个数据集的集合与 gallery 一致。

    返回 {name, collection, gallery_total, indexed, action}，
    action ∈ {ok, would-index, indexed, built}（check 模式下只报告 would-index）。
    """
    from reid_sys.store import MilvusStore

    total = dataset.gallery_total
    store = MilvusStore(dim=backbone.dim, collection=dataset.collection)
    indexed = store.count()

    if not force and indexed == total and total > 0:
        store.close()
        return {"name": dataset.name, "collection": dataset.collection,
                "gallery_total": total, "indexed": indexed, "action": "ok"}

    if check_only:
        store.close()
        return {"name": dataset.name, "collection": dataset.collection,
                "gallery_total": total, "indexed": indexed, "action": "would-index"}

    engine = ReIDEngine.for_dataset(backbone, dataset, store=store)
    t0 = time.time()
    result = engine.index_gallery()
    store.close()
    return {"name": dataset.name, "collection": dataset.collection,
            "gallery_total": total, "indexed": result["indexed"],
            "action": "built" if indexed != total else "indexed",
            "elapsed": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser(description="解压 demo 数据集并校验/补建 Milvus 索引")
    ap.add_argument("--check", action="store_true",
                    help="只检查索引是否完整，不写库；有缺则退出码 1（CI 用）")
    ap.add_argument("--force", action="store_true", help="无视已有索引，全部重建")
    ap.add_argument("--only", action="append", default=None,
                    help="只处理指定数据集（可重复，如 --only data1 --only data2）")
    ap.add_argument("--no-unzip", action="store_true", help="跳过解压步骤")
    args = ap.parse_args()

    print("== 1/3 解压数据集 ==")
    if args.no_unzip:
        print("  （已跳过 --no-unzip）")
    else:
        extracted = unzip_datasets(DATA_DIR, force=args.force)
        if not extracted:
            print("  （无待解压的 zip）")

    print("\n== 2/3 发现数据集 ==")
    ensure_manifest(DATA_DIR)
    found = ds_registry.discover(DATA_DIR)
    if args.only:
        found = [d for d in found if d.name in set(args.only)]
    if not found:
        print("  未发现符合 query/gallery/meta.json 结构的目录。")
        print(f"  请确认 {DATA_DIR} 下有 data1/data2 之类的目录，或放一个 .zip 让本脚本解压。")
        sys.exit(1 if args.check else 0)
    for d in found:
        print(f"  - {d.name:8} collection={d.collection:18} "
              f"query={d.query_total:5} gallery={d.gallery_total:5}")

    # --check 也需载入 backbone（要拿 dim 去查集合），但不会建库
    print("\n== 3/3 校验索引 ==")
    from reid_sys.backbone import FastReIDBackbone

    backbone = FastReIDBackbone()
    print(f"  backbone={type(backbone).__name__} dim={backbone.dim} device={backbone.device}")

    results = [ensure_index(backbone, d, force=args.force, check_only=args.check) for d in found]

    print("\n结果：")
    need = 0
    for r in results:
        line = (f"  {r['name']:8} {r['collection']:18} "
                f"indexed={r['indexed']}/{r['gallery_total']}  {r['action']}")
        if "elapsed" in r:
            line += f"  ({r['elapsed']}s)"
        print(line)
        if r["action"] in ("would-index", "indexed", "built"):
            need += 1

    if args.check:
        if need:
            print(f"\n[check] {need} 个数据集索引不完整 —— 请运行 `uv run reid-init` 补建。")
            sys.exit(1)
        print("\n[check] 全部数据集索引完整。")
        return

    print(f"\n完成：{len(results)} 个数据集，{need} 个已建/重建索引。")


if __name__ == "__main__":
    main()
