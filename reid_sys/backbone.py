"""边侧（街区边缘节点）：ReID backbone —— 抓拍小图 -> 特征向量。

本模块**只**负责「图像 -> 向量」，不知道 Milvus 的存在，也不知道向量会被谁检索。
任何提供 `dim: int` 和 `embed(list[ndarray]) -> ndarray` 的对象都可以替换进来
（换成 MobileNetV3 / OSNet / TensorRT 量化模型时只动这一个文件）。

.. note::
   当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
FASTREID_ROOT = ROOT / "third_part" / "fast-reid"
DEFAULT_CONFIG = FASTREID_ROOT / "configs" / "MSMT17" / "sbs_R50-ibn.yml"
DEFAULT_WEIGHTS = ROOT / "models" / "msmt_sbs_R50-ibn.pth"
DEFAULT_WEIGHT_URL = (
    "https://github.com/JDAI-CV/fast-reid/releases/download/v0.1.1/msmt_sbs_R50-ibn.pth"
)


class FastReIDBackbone:
    """fast-reid SBS-R50-ibn（MSMT17 预训练），输出 L2 归一化的 2048 维向量。

    预处理与 fast-reid 官方 demo 一致：BGR -> RGB，cubic 缩放到 INPUT.SIZE_TEST
    （本 config 为 384x128），转 float32 tensor 后由模型内部做 mean/std 归一化。
    """

    def __init__(self, config=DEFAULT_CONFIG, weights=DEFAULT_WEIGHTS, device=None, batch_size=32):
        weights = Path(weights)
        if not weights.exists():
            raise FileNotFoundError(
                f"缺少 fast-reid 权重 {weights}\n"
                f"下载: curl -L -o {weights} {DEFAULT_WEIGHT_URL}"
            )
        # fast-reid 仓库没有 setup.py，官方用法就是把它挂到 sys.path 后 import fastreid。
        if str(FASTREID_ROOT) not in sys.path:
            sys.path.insert(0, str(FASTREID_ROOT))
        # 不走 fastreid.engine.DefaultPredictor：那会连带 import 训练/评测模块，
        # 而 fastreid/evaluation/testing.py 在 Python 3.10 上 `from collections import Mapping`
        # 已经失效。推理只需要 build_model + Checkpointer。
        from fastreid.config import get_cfg
        from fastreid.modeling.meta_arch import build_model
        from fastreid.utils.checkpoint import Checkpointer

        cfg = get_cfg()
        cfg.merge_from_file(str(config))
        cfg.MODEL.WEIGHTS = str(weights)
        cfg.MODEL.BACKBONE.PRETRAIN = False  # 权重由 Checkpointer 加载，不再拉 ImageNet
        cfg.MODEL.DEVICE = device or ("cuda" if torch.cuda.is_available() else "cpu")
        cfg.freeze()

        self.cfg = cfg
        self.device = cfg.MODEL.DEVICE
        self.dim = cfg.MODEL.BACKBONE.FEAT_DIM
        self.batch_size = batch_size
        self._size = tuple(cfg.INPUT.SIZE_TEST[::-1])  # (W, H)
        self.model = build_model(cfg)
        Checkpointer(self.model).load(str(weights))
        self.model.eval()

    def embed(self, images) -> np.ndarray:
        """images: BGR uint8 ndarray 列表 -> (N, dim) float32，已 L2 归一化。"""
        if len(images) == 0:
            return np.zeros((0, self.dim), dtype=np.float32)
        out = []
        for i in range(0, len(images), self.batch_size):
            chunk = images[i : i + self.batch_size]
            rgb = [cv2.resize(im[:, :, ::-1], self._size, interpolation=cv2.INTER_CUBIC) for im in chunk]
            tensor = torch.as_tensor(np.stack(rgb).astype("float32").transpose(0, 3, 1, 2))
            with torch.no_grad():
                feats = self.model(tensor.to(self.model.device))
            out.append(torch.nn.functional.normalize(feats.float(), dim=1).cpu().numpy())
        return np.concatenate(out).astype(np.float32)

    def embed_one(self, image) -> np.ndarray:
        return self.embed([image])[0]
