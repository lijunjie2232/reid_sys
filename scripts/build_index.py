"""把 gallery 特征录入 Milvus，并可选跑一次 probe 评估。

    uv run python scripts/build_index.py            # 录入
    uv run python scripts/build_index.py --eval     # 录入 + rank-1/mAP

.. note::
   当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reid_sys.backbone import FastReIDBackbone  # noqa: E402
from reid_sys.engine import ReIDEngine, list_images  # noqa: E402
from reid_sys.store import MilvusStore  # noqa: E402


class Progress:
    """往 stderr 打单行进度条，非 TTY（重定向/CI）时自动降级成整十百分比打点。"""

    def __init__(self, label, tty=None):
        self.label = label
        self.tty = sys.stderr.isatty() if tty is None else tty
        self.t0 = time.time()
        self._last = -1.0
        self._next = 0.0
        self._width = len(label)

    def __call__(self, done, total):
        ratio = done / total if total else 1.0
        if self.tty:
            bar_w = 28
            filled = int(bar_w * ratio)
            elapsed = time.time() - self.t0
            speed = done / elapsed if elapsed > 0 else 0.0
            eta = (total - done) / speed if speed > 0 else 0.0
            bar = "#" * filled + "." * (bar_w - filled)
            sys.stderr.write(
                f"\r{self.label:<{self._width}} [{bar}] {done:>5}/{total} "
                f"{ratio:6.1%}  {speed:6.1f} img/s  eta {eta:4.0f}s"
            )
        elif ratio >= self._next:
            elapsed = time.time() - self.t0
            speed = done / elapsed if elapsed > 0 else 0.0
            sys.stderr.write(
                f"{self.label}: {done}/{total} ({ratio:.0%}) {elapsed:.1f}s {speed:.1f} img/s\n"
            )
            self._next += 0.1  # 每 10% 打一行
        sys.stderr.flush()
        self._last = ratio

    def done(self):
        elapsed = time.time() - self.t0
        sys.stderr.write(f"\r{self.label:<{self._width}} 完成 ({elapsed:.1f}s){' ' * 40}\n")
        sys.stderr.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", action="store_true", help="录入后跑一次 probe 评估")
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--batch", type=int, default=64, help="录入批大小")
    parser.add_argument(
        "--quiet", action="store_true", help="不打进度条，只在结束时输出汇总"
    )
    # 换数据集：默认是 GRID，指向 MSMT17_demo 就跑那一套
    parser.add_argument("--gallery-dir", type=Path, default=None, help="底库目录")
    parser.add_argument("--probe-dir", type=Path, default=None, help="查询目录")
    parser.add_argument("--collection", default=None, help="Milvus 集合名")
    args = parser.parse_args()

    print("加载 backbone ...", flush=True)
    t_load = time.time()
    backbone = FastReIDBackbone()
    print(
        f"backbone={type(backbone).__name__} dim={backbone.dim} "
        f"device={backbone.device} 载入 {time.time() - t_load:.1f}s"
    )

    print("连接向量库 ...", flush=True)
    store_kw = {"dim": backbone.dim}
    if args.collection:
        store_kw["collection"] = args.collection
    engine_kw = {}
    if args.gallery_dir:
        engine_kw["gallery_dir"] = args.gallery_dir
    if args.probe_dir:
        engine_kw["probe_dir"] = args.probe_dir
    engine = ReIDEngine(backbone, MilvusStore(**store_kw), **engine_kw)
    print(f"gallery={engine.gallery_dir}  probe={engine.probe_dir}")

    # ---- 录入 ----
    total_gallery = len(list_images(engine.gallery_dir))
    bar = Progress(f"录入 gallery ({total_gallery})", tty=False if args.quiet else None)
    t0 = time.time()
    result = engine.index_gallery(batch_size=args.batch, progress=None if args.quiet else bar)
    if not args.quiet:
        bar.done()
    elapsed = max(time.time() - t0, 1e-6)
    print(f"录入 gallery: {result} 耗时 {elapsed:.1f}s ({result['indexed'] / elapsed:.1f} img/s)")

    # ---- 评估 ----
    if args.eval:
        total_probe = len(list_images(engine.probe_dir))
        bar = Progress(f"检索 probe ({total_probe})", tty=False if args.quiet else None)
        t0 = time.time()
        result = engine.evaluate(topk=args.topk, progress=None if args.quiet else bar)
        if not args.quiet:
            bar.done()
        elapsed = time.time() - t0
        print(f"评估耗时 {elapsed:.1f}s")
        print({k: v for k, v in result.items() if k != "samples"})


if __name__ == "__main__":
    main()
