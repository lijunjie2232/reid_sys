"""为 MSMT17_V1/test 手工构建一个 demo 用的 query/gallery 划分。

MSMT17_V1/test 只有 `personID/*.jpg` 一层结构，没有 query/gallery 目录。
本脚本按官方 `list_query.txt` / `list_gallery.txt` 的划分思路，用「能否召回」来筛选：

  1. 每个候选人的 gallery 图片建索引，用他的 query 图片去检索；
  2. 能召回的（rank<=K）人才进 demo 集，query 进 demo 的 query/，对应 gallery 进 gallery/；
  3. 召不回的人整体丢弃 —— 这就是 GRID 那边 `filter_probe.py` 的同款思路。

与 GRID 的区别：MSMT17 官方划分里 95.7% 的 query 和 gallery 来自**同一台相机的同一段视频**
（相隔几帧，cosine 0.97-0.99，近似重复帧），所以零样本召回率天然很高，能被剔掉的很少。
这里额外提供 `--require-cross-camera`，只保留 query 与 gallery **不在同一相机**的人，
让 demo 演示真正的跨镜头 Re-ID，而不是「拿相邻帧搜自己」。

产物（默认 `data/MSMT17_demo/`）：
    query/    每人 --queries 张
    gallery/  每人 --galleries 张
    meta.json 划分明细（每个人选了哪些文件、哪个相机、benchmark 排名）

文件名保持原名（`personID_...jpg`），personID 仍在第 1 个下划线字段，
所以 `reid_sys.engine.parse_name` 不用改。

    python scripts/build_msmt17_demo.py                      # dry-run，只报告
    python scripts/build_msmt17_demo.py --apply              # 真正复制文件
    python scripts/build_msmt17_demo.py --people 400 --apply
    python scripts/build_msmt17_demo.py --require-cross-camera --apply

.. note::
   当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。
"""

import argparse
import json
import random
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reid_sys import ROOT  # noqa: E402
from reid_sys.backbone import FastReIDBackbone  # noqa: E402
from reid_sys.engine import imread  # noqa: E402
from reid_sys.store import MilvusStore  # noqa: E402

DEFAULT_SRC = ROOT / "data" / "MSMT17_V1"
DEFAULT_OUT = ROOT / "data" / "MSMT17_demo"
# 不要在 demo 集里直接用 2048 维的正式集合名，避免和 GRID 的索引互相覆盖
DEMO_COLLECTION = "msmt17_bench"


def camera_of(rel: str) -> str:
    """`0000/0000_008_01_0303morning_0019_2.jpg` -> 相机号 `01`。"""
    return rel.split("/")[1].split("_")[2]


def person_of(rel: str) -> str:
    return rel.split("/")[0]


def read_list(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"缺少官方划分文件 {path}")
    return [line.split()[0] for line in path.read_text().splitlines() if line.split()]


def batch_embed(backbone, paths, batch=32):
    """分批读图 + 提特征，返回 (N, dim) 与成功读入的下标。"""
    import numpy as np

    vecs, ok = [], []
    for i in range(0, len(paths), batch):
        chunk = paths[i : i + batch]
        imgs = [imread(p) for p in chunk]
        good = [j for j, im in enumerate(imgs) if im is not None]
        if not good:
            continue
        v = backbone.embed([imgs[j] for j in good])
        vecs.append(v)
        ok.extend(i + j for j in good)
    if not vecs:
        return np.zeros((0, backbone.dim), dtype="float32"), []
    return np.concatenate(vecs), ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--people", type=int, default=400, help="保留多少人")
    ap.add_argument("--queries", type=int, default=1, help="每人取几张做 query")
    ap.add_argument("--galleries", type=int, default=3, help="每人取几张做 gallery")
    ap.add_argument("-k", "--threshold", type=int, default=5, help="rank<=K 视为可召回")
    ap.add_argument(
        "--require-cross-camera",
        action="store_true",
        help="只保留 query 与 gallery 跨相机的人（真正跨镜头，但通过率低）",
    )
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--max-candidates", type=int, default=0, help="只试前 N 个人（0=全部），调试用"
    )
    ap.add_argument("--apply", action="store_true", help="真正复制文件（默认只报告）")
    args = ap.parse_args()

    random.seed(args.seed)
    test_dir = args.src / "test"
    if not test_dir.is_dir():
        sys.exit(f"找不到 {test_dir}")

    queries = read_list(args.src / "list_query.txt")
    galleries = read_list(args.src / "list_gallery.txt")
    by_person_q = defaultdict(list)
    by_person_g = defaultdict(list)
    for r in queries:
        by_person_q[person_of(r)].append(r)
    for r in galleries:
        by_person_g[person_of(r)].append(r)

    people = sorted(set(by_person_q) & set(by_person_g))
    # 图太少的人直接跳过（没法凑够 query+gallery）
    people = [
        p
        for p in people
        if len(by_person_q[p]) >= args.queries and len(by_person_g[p]) >= args.galleries
    ]
    random.shuffle(people)
    if args.max_candidates:
        people = people[: args.max_candidates]
    print(f"候选 {len(people)} 人（官方 query/gallery 都有、且图量够）")

    # ---------- 建一个独立的候选 gallery 索引 ----------
    # 每个候选人先挑定本 demo 要用的 query/gallery，再只索引这些 gallery
    plan = []
    for p in people:
        qs = sorted(by_person_q[p])[: args.queries]
        gs = sorted(by_person_g[p])[: args.galleries]
        if args.require_cross_camera:
            qcams = {camera_of(r) for r in qs}
            if qcams & {camera_of(r) for r in gs}:
                continue  # 同相机，跳过
        plan.append({"person": p, "query": qs, "gallery": gs})

    print(f"满足约束 {len(plan)} 人，开始建临时索引并跑召回测试 ...")

    backbone = FastReIDBackbone()
    print(f"backbone={type(backbone).__name__} dim={backbone.dim} device={backbone.device}")
    store = MilvusStore(dim=backbone.dim, collection=DEMO_COLLECTION)
    store.reset()

    # 索引阶段：把计划中所有人的 gallery 都灌进去，这样召不召回是真实竞争结果
    t0 = time.time()
    records = []
    for i, item in enumerate(plan):
        paths = [test_dir / r for r in item["gallery"]]
        vecs, ok = batch_embed(backbone, paths)
        for j, idx in enumerate(ok):
            rel = item["gallery"][idx]
            records.append(
                {
                    "id": rel,
                    "person_id": item["person"],
                    "camera": camera_of(rel),
                    "frame": 0,
                    "vector": vecs[j].tolist(),
                }
            )
        if (i + 1) % 100 == 0:
            print(f"  索引 {i + 1}/{len(plan)} 人, {len(records)} 张, {time.time() - t0:.0f}s")
    store.upsert(records)
    print(f"索引完成 {len(records)} 张，{time.time() - t0:.1f}s")

    # 检索阶段：一次性把所有 query 提完特征再批量搜索
    # （逐个 query 调 search() 会走 N 次 gRPC 往返，实测占了总耗时的 95%）
    t0 = time.time()
    q_vecs, q_owner = [], []
    for k, item in enumerate(plan):
        vecs, ok = batch_embed(backbone, [test_dir / r for r in item["query"]])
        for j in range(len(ok)):
            q_vecs.append(vecs[j])
            q_owner.append(k)
    print(f"query 提特征 {len(q_vecs)} 张，{time.time() - t0:.1f}s")

    import numpy as np

    t0 = time.time()
    all_hits = []
    for i in range(0, len(q_vecs), 256):
        chunk = np.stack(q_vecs[i : i + 256])
        all_hits.extend(store.search(chunk, topk=max(args.threshold, 5)))
    print(f"批量检索 {len(q_vecs)} 次，{time.time() - t0:.1f}s")

    # 把命中按人归拢：一个人可能有多张 query，取其中最好的 rank
    best_rank: dict[int, int | None] = {}
    for owner, row in zip(q_owner, all_hits):
        pid = plan[owner]["person"]
        r = next((i + 1 for i, h in enumerate(row) if h["person_id"] == pid), None)
        if r is not None:
            prev = best_rank.get(owner)
            best_rank[owner] = r if prev is None else min(prev, r)
        else:
            best_rank.setdefault(owner, None)

    kept, dropped = [], []
    for k, item in enumerate(plan):
        best = best_rank.get(k)
        rec = {
            "person": item["person"],
            "query": item["query"],
            "gallery": item["gallery"],
            "rank": best,
            "q_cam": sorted({camera_of(r) for r in item["query"]}),
            "g_cam": sorted({camera_of(r) for r in item["gallery"]}),
        }
        (kept if (best is not None and best <= args.threshold) else dropped).append(rec)
    total = len(plan)
    print(f"\n召回结果：可召回 {len(kept)}/{total} ({len(kept) / total:.1%})，"
          f"剔除 {len(dropped)} ({len(dropped) / total:.1%})")
    print("rank 分布:", dict(sorted(Counter(r["rank"] for r in kept).items())))
    if args.require_cross_camera:
        print("（已启用跨相机约束）")

    final = kept[: args.people]
    print(f"最终写入 {len(final)} 人（--people={args.people}）")

    if not args.apply:
        print(f"\n[dry-run] 未复制任何文件。产物会写到 {args.out}")
        print("确认后加 --apply 执行。")
        store.close()
        return

    # ---------- 复制 ----------
    out_q = args.out / "query"
    out_g = args.out / "gallery"
    if args.out.exists():
        print(f"清空已存在的 {args.out}")
        shutil.rmtree(args.out)
    out_q.mkdir(parents=True)
    out_g.mkdir(parents=True)

    n_q = n_g = 0
    for item in final:
        for rel in item["query"]:
            shutil.copy2(test_dir / rel, out_q / Path(rel).name)
            n_q += 1
        for rel in item["gallery"]:
            shutil.copy2(test_dir / rel, out_g / Path(rel).name)
            n_g += 1

    meta = {
        "source": str(args.src),
        "threshold": args.threshold,
        "require_cross_camera": args.require_cross_camera,
        "people": len(final),
        "query_images": n_q,
        "gallery_images": n_g,
        "candidates": total,
        "kept": len(kept),
        "dropped": len(dropped),
        "items": final,
        "dropped_items": [{"person": d["person"], "rank": d["rank"]} for d in dropped],
    }
    (args.out / "meta.json").write_text(
        json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n写入完成：{args.out}")
    print(f"  query   {n_q} 张")
    print(f"  gallery {n_g} 张")
    print(f"  meta    {args.out / 'meta.json'}")
    store.close()


if __name__ == "__main__":
    main()
