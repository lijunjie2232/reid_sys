"""云侧（AI 算力机房）：Milvus 向量库 —— 入库 + KNN 检索。

本模块**只**接受向量，不关心向量由哪个 backbone 产生，也不 import torch。
换成 GPU CAGRA / 分布式 Milvus 集群时，只需把 uri 指向服务端即可。

.. note::
   当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。
"""

from __future__ import annotations

from pathlib import Path

from pymilvus import DataType, MilvusClient

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_URI = ROOT / "data" / "milvus_reid.db"  # 本地文件 = milvus-lite 嵌入式实例


class MilvusStore:
    def __init__(self, uri=DEFAULT_URI, collection="reid_gallery", dim=2048):
        Path(uri).parent.mkdir(parents=True, exist_ok=True)
        self.uri = str(uri)
        self.client = MilvusClient(uri=self.uri)
        self.collection = collection
        self.dim = dim
        self._ensure_collection()
        # 重开进程时集合处于 released 状态，search/query 前必须 load
        self.client.load_collection(self.collection)

    def _ensure_collection(self):
        if self.client.has_collection(self.collection):
            # 换了 backbone 导致维度变化时，旧索引已经无效，直接重建
            fields = {f["name"]: f for f in self.client.describe_collection(self.collection)["fields"]}
            if fields["vector"].get("params", {}).get("dim") == self.dim:
                return
            self.client.drop_collection(self.collection)
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=128)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=self.dim)
        schema.add_field("person_id", DataType.VARCHAR, max_length=32)
        schema.add_field("camera", DataType.VARCHAR, max_length=16)
        schema.add_field("frame", DataType.INT64)

        index = self.client.prepare_index_params()
        # AUTOINDEX 让服务端自选（lite 走 FLAT，集群走 HNSW/CAGRA），无需按部署形态改代码
        index.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")

        self.client.create_collection(self.collection, schema=schema, index_params=index)

    def reset(self):
        self.client.drop_collection(self.collection)
        self._ensure_collection()
        self.client.load_collection(self.collection)

    def upsert(self, records):
        """records: [{id, vector, person_id, camera, frame}, ...]"""
        if records:
            self.client.upsert(collection_name=self.collection, data=records)

    def search(self, vectors, topk=10):
        """vectors: (N, dim) -> 每行一个按相似度降序的命中列表。"""
        hits = self.client.search(
            collection_name=self.collection,
            data=list(vectors),
            limit=topk,
            output_fields=["person_id", "camera", "frame"],
        )
        return [
            [{**h["entity"], "id": h["id"], "score": float(h["distance"])} for h in row]
            for row in hits
        ]

    def count(self) -> int:
        rows = self.client.query(collection_name=self.collection, output_fields=["count(*)"])
        return int(rows[0]["count(*)"])

    def close(self):
        self.client.close()
