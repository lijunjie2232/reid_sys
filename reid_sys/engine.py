"""Smart Gateway 背后的 ReID 引擎：把 backbone（特征）与 store（检索）组合起来。

backbone 与 store 互不知情，组合只发生在这里 —— 换 backbone 或换向量库都不影响对方。

.. note::
   当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from . import ROOT

DATASET = ROOT / "data" / "underground_reid"
GALLERY_DIR = DATASET / "gallery"
PROBE_DIR = DATASET / "probe"

# GRID 用 .jpeg，MSMT17 用 .jpg，两套数据集共用同一套解析逻辑
IMAGE_SUFFIXES = (".jpeg", ".jpg")


def imread(path) -> np.ndarray:
    """cv2.imread 在 Windows 上遇到非 ASCII 路径会返回 None，统一走 imdecode。"""
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


def imdecode(data: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("无法解码图片")
    return image


def parse_name(name: str) -> dict:
    """文件名约定 `personID_cameraID_frame_x_y_w_h.jpeg`（QMUL GRID / underground_reid）。

    底库里的 775 张干扰图 personID 统一是 0000，不属于任何 probe。
    """
    parts = Path(name).stem.split("_")
    return {
        "id": name,
        "person_id": parts[0],
        "camera": parts[1] if len(parts) > 1 else "0",
        "frame": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0,
    }


def list_images(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)


class ReIDEngine:
    def __init__(self, backbone, store, gallery_dir=GALLERY_DIR, probe_dir=PROBE_DIR):
        self.backbone = backbone
        self.store = store
        self.gallery_dir = Path(gallery_dir)
        self.probe_dir = Path(probe_dir)

    @classmethod
    def for_dataset(cls, backbone, dataset, store=None):
        """按一个 `datasets.Dataset` 构造引擎 —— 目录名统一为 query/ 与 gallery/。"""
        from .store import MilvusStore

        store = store or MilvusStore(dim=backbone.dim, collection=dataset.collection)
        return cls(
            backbone,
            store,
            gallery_dir=dataset.gallery_dir,
            probe_dir=dataset.query_dir,
        )

    # ---------- 特征录入 ----------

    def index_gallery(self, batch_size=64, progress=None) -> dict:
        """把 gallery 全部特征写入向量库（等价于边侧节点批量上报）。

        progress: 可选 `fn(done, total)`，每批录入后回调一次。
        """
        names = list_images(self.gallery_dir)
        total = len(names)
        self.store.reset()
        for i in range(0, total, batch_size):
            chunk = names[i : i + batch_size]
            images = [imread(self.gallery_dir / n) for n in chunk]
            vectors = self.backbone.embed(images)
            self.store.upsert(
                [{**parse_name(n), "vector": v.tolist()} for n, v in zip(chunk, vectors)]
            )
            if progress:
                progress(min(i + batch_size, total), total)
        return {"indexed": total, "dim": self.backbone.dim, "count": self.store.count()}

    # ---------- 检索 ----------

    def search(self, images, topk=10):
        """images: BGR ndarray 列表 -> 每个 query 的 topk 命中（按相似度降序）。"""
        vectors = self.backbone.embed(list(images))
        return self.store.search(vectors, topk=topk)

    def search_by_name(self, name: str, topk=10, split="probe"):
        directory = self.probe_dir if split == "probe" else self.gallery_dir
        image = imread(directory / name)
        if image is None:
            raise FileNotFoundError(f"{split}/{name} 不存在")
        return self.search([image], topk=topk)[0]

    # ---------- 评估 ----------

    def evaluate(self, topk=10, progress=None) -> dict:
        """用 probe 集跑一次 rank-1 / rank-5 / mAP（每张 probe 在底库里有唯一真值）。

        progress: 可选 `fn(done, total)`，每批查询后回调一次。
        """
        names = list_images(self.probe_dir)
        total = len(names)
        hits, step = [], 64
        for i in range(0, total, step):
            chunk = names[i : i + step]
            vectors = self.backbone.embed([imread(self.probe_dir / n) for n in chunk])
            # rank-5 需要看前 5，但也有命中落在更后面，所以统一按 topk 取
            hits.extend(self.store.search(vectors, topk=topk))
            if progress:
                progress(min(i + step, total), total)
        ranks, rows = [], []
        for name, row in zip(names, hits):
            truth = parse_name(name)["person_id"]
            rank = next((i + 1 for i, h in enumerate(row) if h["person_id"] == truth), None)
            ranks.append(rank)
            rows.append(
                {
                    "probe": name,
                    "truth": truth,
                    "rank": rank,
                    "top1": row[0]["person_id"] if row else None,
                    "top1_score": row[0]["score"] if row else 0.0,
                }
            )
        n = len(ranks)
        matched = [r for r in ranks if r]
        return {
            "queries": n,
            "rank1": round(sum(1 for r in ranks if r == 1) / n, 4),
            "rank5": round(sum(1 for r in ranks if r and r <= 5) / n, 4),
            "mAP": round(sum(1 / r for r in matched) / n, 4),
            "miss": sum(1 for r in ranks if r is None),
            "samples": rows[:24],
        }

    # ---------- 状态 ----------

    def status(self) -> dict:
        return {
            "backbone": type(self.backbone).__name__,
            "device": getattr(self.backbone, "device", "?"),
            "dim": self.backbone.dim,
            "collection": self.store.collection,
            "indexed": self.store.count(),
            "gallery_total": len(list_images(self.gallery_dir)),
            "probe_total": len(list_images(self.probe_dir)),
        }
