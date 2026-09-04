"""跨镜头 Re-ID 目标追踪系统 —— 可扩展的最小实现（demo 级）。

模块划分与 docs/SYSTEM.md 的三级协同架构一一对应：

    端侧 IPC      detect.py    YOLO 检测 + 跟踪去重（只上报入帧/变化/出帧）
    边侧 街区节点  backbone.py  抓拍小图 -> 特征向量（fast-reid）
    云侧 算力机房  store.py     向量入库 + KNN 检索（Milvus）
    Smart Gateway engine.py    组合上面三者；api.py 对外暴露 HTTP

.. note::
   当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
