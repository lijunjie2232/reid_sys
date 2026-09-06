"""按「能否召回」筛选 demo 用的 probe 测试例。

跑一次全量 gallery 录入 + probe 检索，把 rank > K 的 probe 移到 `probe_excluded/`，
只留下能在 top-K 内命中真值的样例，让 demo 每次都稳定出结果。

    python scripts/filter_probe.py            # 只报告，不动文件（默认）
    python scripts/filter_probe.py --apply    # 真正移动文件
    python scripts/filter_probe.py --restore  # 把 probe_excluded 全部移回
    python scripts/filter_probe.py -k 5 --apply

注意：这是演示口径，不是评测口径。被移走的样例模型确实召不回，
剔除它们之后的 rank-1 数字**不能再当作模型指标引用**。

.. note::
   当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reid_sys.backbone import FastReIDBackbone  # noqa: E402
from reid_sys.engine import ReIDEngine, imread, list_images, parse_name  # noqa: E402
from reid_sys.store import MilvusStore  # noqa: E402

EXCLUDED_DIRNAME = "probe_excluded"
REPORT_PATH = Path(__file__).resolve().parent.parent / "data" / "probe_recall_report.json"


def recall_table(rows, threshold):
    """按 rank 分桶打印召回曲线，阈值那一档高亮。"""
    print(f"\n召回曲线（{len(rows)} 张 probe，threshold=rank<={threshold}）")
    print(f"  {'rank<=':<8}{'命中':>6}{'占比':>9}")
    for k in [1, 2, 3, 5, 10, 20, 50, 100, 200]:
        n = sum(1 for r in rows if r["rank"] and r["rank"] <= k)
        mark = "  <-- 阈值" if k == threshold else ""
        print(f"  {k:<8}{n:>6}{n / len(rows):>9.1%}{mark}")
    never = sum(1 for r in rows if not r["rank"] or r["rank"] > 200)
    print(f"  {'召不回':<8}{never:>6}{never / len(rows):>9.1%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", "--threshold", type=int, default=5, help="rank<=K 视为可召回")
    ap.add_argument("--apply", action="store_true", help="真正移动文件（默认只报告）")
    ap.add_argument("--restore", action="store_true", help="把 probe_excluded 全部移回 probe")
    ap.add_argument("--batch", type=int, default=64)
    args = ap.parse_args()

    probe_dir = ReIDEngine(  # 只是为了拿默认路径，不需要模型
        None, None
    ).probe_dir
    excluded_dir = probe_dir.parent / EXCLUDED_DIRNAME

    # ---------- restore 分支 ----------
    if args.restore:
        if not excluded_dir.is_dir():
            print(f"没有 {excluded_dir}，无需恢复")
            return
        names = list_images(excluded_dir)
        print(f"恢复 {len(names)} 张 -> {probe_dir.name}/")
        for n in names:
            shutil.move(str(excluded_dir / n), str(probe_dir / n))
        print(f"恢复完成，probe 现在 {len(list_images(probe_dir))} 张")
        print("提示：需要重跑 scripts/build_index.py 保持索引一致。")
        return

    # ---------- 正常分支 ----------
    backbone = FastReIDBackbone()
    print(f"backbone={type(backbone).__name__} dim={backbone.dim} device={backbone.device}")
    engine = ReIDEngine(backbone, MilvusStore(dim=backbone.dim))

    t0 = time.time()
    print(f"录入 gallery: {engine.index_gallery(batch_size=args.batch)} ({time.time() - t0:.1f}s)")

    names = list_images(engine.probe_dir)
    vectors = backbone.embed([imread(engine.probe_dir / n) for n in names])
    # 阈值可能很大，检索深度取 max(K, 200) 才能算出「召不回」那一档
    hits = engine.store.search(vectors, topk=max(args.threshold, 200))

    rows = []
    for name, row in zip(names, hits):
        truth = parse_name(name)["person_id"]
        rank = next((i + 1 for i, h in enumerate(row) if h["person_id"] == truth), None)
        rows.append(
            {
                "probe": name,
                "truth": truth,
                "rank": rank,
                "top1": row[0]["person_id"] if row else None,
                "top1_score": round(row[0]["score"], 6) if row else 0.0,
            }
        )

    keep = [r for r in rows if r["rank"] and r["rank"] <= args.threshold]
    drop = [r for r in rows if not (r["rank"] and r["rank"] <= args.threshold)]

    recall_table(rows, args.threshold)
    print(f"\n保留 {len(keep)} 张（可在 top-{args.threshold} 内召回）")
    print(f"剔除 {len(drop)} 张（其中 {sum(1 for r in drop if not r['rank'])} 张完全召不回）")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "threshold": args.threshold,
                "total": len(rows),
                "kept": [r["probe"] for r in keep],
                "dropped": [
                    {"probe": r["probe"], "rank": r["rank"], "top1": r["top1"]} for r in drop
                ],
            },
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"报告已写入 {REPORT_PATH}")

    if not args.apply:
        print("\n[dry-run] 未移动任何文件。确认无误后加 --apply 执行。")
        return

    # 真正移动：先列清单再动手
    excluded_dir.mkdir(exist_ok=True)
    print(f"\n移动 {len(drop)} 张 -> {excluded_dir.name}/")
    for r in drop:
        shutil.move(str(engine.probe_dir / r["probe"]), str(excluded_dir / r["probe"]))
    remaining = list_images(engine.probe_dir)
    print(f"probe 剩余 {len(remaining)} 张，{excluded_dir.name} 内 {len(list_images(excluded_dir))} 张")
    print("提示：需要重跑 scripts/build_index.py（或重启服务）让索引与目录一致。")


if __name__ == "__main__":
    main()
