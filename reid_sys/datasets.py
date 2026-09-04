"""Demo 数据集的发现与注册 —— 全仓唯一的数据集真相来源。

约定：`data/` 下任何**同时含 `query/`、`gallery/`、`meta.json`** 的目录都算一个
demo 数据集。每个数据集对应一个 Milvus collection，名字由目录名派生：

    data/data1/{query,gallery,meta.json}  ->  collection "reid_data1"
    data/data2/{query,gallery,meta.json}  ->  collection "reid_data2"

这样「加一个数据集」只需往 `data/` 里放一个符合结构的目录，前后端与 init 脚本
都不用改。凭 `meta.json` 里的字段可以覆盖显示名 / collection 名。

.. note::
   当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import ROOT
from .engine import IMAGE_SUFFIXES, list_images

DATA_DIR = ROOT / "data"

#: collection 名前缀。collection 名只允许字母/数字/下划线，所以目录名会做净化。
COLLECTION_PREFIX = "reid_"

#: 进入 registry 必需的子项
REQUIRED_ENTRIES = ("query", "gallery", "meta.json")


def sanitize_collection(name: str) -> str:
    """把目录名转成合法的 collection 名（只留字母/数字/下划线）。"""
    cleaned = "".join(c if (c.isalnum() or c == "_") else "_" for c in name)
    return f"{COLLECTION_PREFIX}{cleaned}"


def is_dataset_dir(path: Path) -> bool:
    """判断目录是否符合 demo 数据集结构。"""
    return path.is_dir() and all((path / e).exists() for e in REQUIRED_ENTRIES)


@dataclass
class Dataset:
    """一个 demo 数据集的元信息。"""

    name: str
    path: Path
    collection: str
    query_dir: Path
    gallery_dir: Path
    meta_path: Path
    title: str = ""
    description: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def query_total(self) -> int:
        return len(list_images(self.query_dir))

    @property
    def gallery_total(self) -> int:
        return len(list_images(self.gallery_dir))

    def summary(self) -> dict:
        """给 API/前端的轻量摘要。"""
        return {
            "name": self.name,
            "title": self.title or self.name,
            "description": self.description,
            "collection": self.collection,
            "query_total": self.query_total,
            "gallery_total": self.gallery_total,
            "suffixes": list(IMAGE_SUFFIXES),
            "metric_note": self.meta.get("metric_note"),
        }


def load_dataset(path: Path) -> Dataset | None:
    """读一个目录，符合结构则返回 Dataset，否则 None。"""
    if not is_dataset_dir(path):
        return None
    meta_path = path / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        meta = {}
    return Dataset(
        name=path.name,
        path=path,
        collection=meta.get("collection") or sanitize_collection(path.name),
        query_dir=path / "query",
        gallery_dir=path / "gallery",
        meta_path=meta_path,
        title=meta.get("title") or path.name,
        description=meta.get("description") or "",
        meta=meta,
    )


#: 可选的清单文件：`data/datasets.json`，形如 `{"datasets": ["data1", "data2"]}`。
#: 存在时按它给定的顺序与范围来注册 —— 用来把 demo 限定在指定的几个数据集上，
#: 避免 `data/` 下遗留的中间目录（如构建 demo 时的工作副本）混进来。
#: 不存在则退化成「扫全部符合结构的目录」。
MANIFEST = "datasets.json"


def _read_manifest(base: Path) -> list[str] | None:
    """读 `data/datasets.json`；没有/读不动就返回 None（表示走自动发现）。"""
    path = base / MANIFEST
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    names = data.get("datasets") if isinstance(data, dict) else data
    if not isinstance(names, list):
        return None
    return [str(n) for n in names]


def discover(root: Path | None = None) -> list[Dataset]:
    """返回所有 demo 数据集。

    有 `data/datasets.json` 就按清单的顺序与范围来；没有则扫描 `data/` 下
    所有符合 `query/ + gallery/ + meta.json` 结构的目录（按名字排序）。
    """
    base = Path(root) if root else DATA_DIR
    if not base.is_dir():
        return []

    manifest = _read_manifest(base)
    if manifest is not None:
        out = []
        for name in manifest:
            ds = load_dataset(base / name)
            if ds is not None:
                out.append(ds)
        return out

    found = []
    for child in sorted(base.iterdir()):
        if child.name.startswith("."):
            continue
        ds = load_dataset(child)
        if ds is not None:
            found.append(ds)
    return found


def get(name: str, root: Path | None = None) -> Dataset | None:
    """按数据集名取一个；找不到返回 None。"""
    return next((d for d in discover(root) if d.name == name), None)
