"""未接入能力的 provider 层 —— 只暴露接口，当前全部由 stub 实现。

设计思路
--------
每种「尚未接入真实服务」的能力对应一个 **provider 协议**（Protocol）。api 层只依赖协议，
不依赖具体实现；当前注册的是 `Stub*` 实现，返回 schema 定义的空/模拟数据并标
`connected=False`。接入真实服务时只要写一个新的 provider（如 `HttpDeviceManager`）
并替换 `PROVIDERS` 里的绑定，路由、schema、前端都不用动。

.. note::
   **当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。**
   本模块的 stub 只是占位实现，返回结果不可用于真实监控或告警。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from . import ROOT

CAMERA_CONFIG = ROOT / "web" / "src" / "config" / "cameras.json"

#: 统一提示文案：说明这些接口已定义、但尚未接入真实服务。
NOT_CONNECTED_NOTE = "接口已定义，尚未接入真实服务；当前返回模拟数据。"


def _load_camera_db() -> dict:
    if not CAMERA_CONFIG.is_file():
        raise FileNotFoundError(f"摄像头配置文件缺失：{CAMERA_CONFIG}")
    return json.loads(CAMERA_CONFIG.read_text(encoding="utf-8"))


# ============================================================ 设备管理平台

class DeviceManager(Protocol):
    """端侧设备管理平台（RTSP / GB28181 / ONVIF）接入协议。"""

    def cameras(self) -> dict: ...
    def camera_detail(self, camera_id: str) -> dict | None: ...
    def ping(self, ids: list[str] | None = None) -> list[dict]: ...


class StubDeviceManager:
    """当前实现：读本地组态文件，一律标记未接入。"""

    connected = False
    simulated = True

    def cameras(self) -> dict:
        data = _load_camera_db()
        return {
            "source": "web/src/config/cameras.json",
            "simulated": True,
            "connected": False,
            "city": data.get("city"),
            "district": data.get("district"),
            "coordinate_system": data.get("coordinate_system"),
            "center": data.get("center"),
            "zoom": data.get("zoom"),
            "zones": data.get("zones", []),
            "cameras": data.get("cameras", []),
            "edge_nodes": data.get("edge_nodes", []),
            "demo_tracks": data.get("demo_tracks", []),
        }

    def camera_detail(self, camera_id: str) -> dict | None:
        data = _load_camera_db()
        pool = [*data.get("cameras", []), *data.get("edge_nodes", [])]
        hit = next((d for d in pool if d.get("id") == camera_id), None)
        return None if hit is None else {**hit, "simulated": True, "connected": False}

    def ping(self, ids: list[str] | None = None) -> list[dict]:
        data = _load_camera_db()
        rows = data.get("cameras", [])
        if ids:
            rows = [r for r in rows if r.get("id") in ids]
        return [
            {"id": r.get("id"), "reachable": False, "rtt_ms": None,
             "reason": "device-platform not connected"}
            for r in rows
        ]


# ================================================================ 监控指标

class MonitorService(Protocol):
    """摄像头 / 边缘节点监控指标采集协议。"""

    def camera_status(self) -> dict: ...
    def edge_status(self) -> dict: ...


class StubMonitorService:
    """当前实现：给出表格骨架，所有实时指标留空（None -> 前端显示 `—`）。"""

    connected = False

    def camera_status(self) -> dict:
        data = _load_camera_db()
        rows = [
            {
                "id": c.get("id"),
                "zone": c.get("zone"),
                "ping_ms": None,
                "fps": None,
                "npu_load": None,
                "emit_qps": None,
                "stream": "offline",
            }
            for c in data.get("cameras", [])
        ]
        return {
            "connected": False,
            "simulated": True,
            "metrics": {
                "connected": False,
                "online": None,
                "total": len(rows),
                "avg_rtt_ms": None,
                "capture_rate_fps": None,
                "avg_npu_load": None,
            },
            "rows": rows,
            "note": NOT_CONNECTED_NOTE,
        }

    def edge_status(self) -> dict:
        data = _load_camera_db()
        rows = [
            {
                "id": e.get("id"),
                "zone": e.get("zone"),
                "ipcs_managed": e.get("manages"),
                "ping_ms": None,
                "qps": None,
                "load_pct": None,
                "pod": None,
                "status": "offline",
            }
            for e in data.get("edge_nodes", [])
        ]
        return {
            "connected": False,
            "simulated": True,
            "metrics": {
                "connected": False,
                "online": None,
                "total": len(rows),
                "avg_rtt_ms": None,
                "embedding_qps": None,
                "watchlist_hits": None,
            },
            "rows": rows,
            "note": NOT_CONNECTED_NOTE,
        }


# ============================================================== K8s 编排

#: 设计态工作负载清单（来自 docs/SYSTEM.md 设计原则 #5）。接入集群后可在线获取。
_DESIGN_WORKLOADS = [
    {"cluster": "edge", "namespace": "reid-edge", "name": "reid-backbone", "kind": "Deployment",
     "image": "reid/backbone:1.3.0-cu126", "role_key": "roleBackbone", "replicas": "33"},
    {"cluster": "edge", "namespace": "reid-edge", "name": "watchlist-agent", "kind": "DaemonSet",
     "image": "reid/watchlist:0.9.2", "role_key": "roleWatchlist", "replicas": "33"},
    {"cluster": "edge", "namespace": "reid-edge", "name": "edge-gateway", "kind": "Deployment",
     "image": "reid/edge-gw:0.7.1", "role_key": "roleGateway", "replicas": "66"},
    {"cluster": "cloud", "namespace": "reid-cloud", "name": "reid-gateway", "kind": "Deployment",
     "image": "reid/gateway:1.4.2", "role_key": "roleRoute", "replicas": "8"},
    {"cluster": "cloud", "namespace": "reid-cloud", "name": "milvus-proxy", "kind": "StatefulSet",
     "image": "milvusdb/milvus:v2.5.x", "role_key": "roleMilvus", "replicas": "4"},
    {"cluster": "cloud", "namespace": "reid-cloud", "name": "gpu-cluster-job", "kind": "CronJob",
     "image": "reid/cluster:2.1.0-cu126", "role_key": "roleCluster", "replicas": "—",
     "schedule": "15 2 * * *"},
    {"cluster": "cloud", "namespace": "reid-cloud", "name": "mamba-engine", "kind": "Deployment",
     "image": "reid/mamba:0.5.0-cu126", "role_key": "roleMamba", "replicas": "4"},
]


class OrchestratorService(Protocol):
    """K3s / K8s 编排接入协议。"""

    def workloads(self) -> dict: ...
    def rollout(self, req: dict) -> dict: ...


class StubOrchestratorService:
    """当前实现：回显设计态清单，不连集群。"""

    connected = False

    def workloads(self) -> dict:
        items = [{**w, "ready": None, "status": "offline"} for w in _DESIGN_WORKLOADS]
        return {
            "connected": False,
            "simulated": True,
            "summary": {
                "connected": False,
                "edge_cluster": None,
                "cloud_cluster": None,
                "running_pods": None,
                "image_consistency": None,
            },
            "workloads": items,
            "note": NOT_CONNECTED_NOTE,
        }

    def rollout(self, req: dict) -> dict:
        return {
            "connected": False,
            "accepted": False,
            "simulated": True,
            "plan": req,
            "message": "尚未接入 K8s/K3s 集群，灰度发布仅回显计划，未真正执行。",
        }


# ========================================================== 轨迹 / 布控告警

class TrackService(Protocol):
    """跨镜头轨迹回放协议。"""

    def track(self, person: str) -> dict | None: ...


class StubTrackService:
    """当前实现：回放 cameras.json 里的示例轨迹，不含真实时空数据。"""

    connected = False

    def track(self, person: str) -> dict | None:
        data = _load_camera_db()
        hit = next((x for x in data.get("demo_tracks", []) if x.get("person") == person), None)
        if hit is None:
            return None
        by_id = {d.get("id"): d for d in [*data.get("cameras", []), *data.get("edge_nodes", [])]}
        points = [
            {
                "camera": pid,
                "lat": (by_id.get(pid) or {}).get("lat"),
                "lng": (by_id.get(pid) or {}).get("lng"),
                "timestamp": None,
            }
            for pid in hit.get("points", [])
        ]
        return {"person": person, "label": hit.get("label"), "simulated": True,
                "connected": False, "points": points}


class WatchlistService(Protocol):
    """布控名单 / 告警通道协议。"""

    def alerts(self, limit: int = 50) -> dict: ...


class StubWatchlistService:
    """当前实现：无告警通道，返回空列表。"""

    connected = False

    def alerts(self, limit: int = 50) -> dict:
        return {
            "connected": False,
            "simulated": True,
            "channel": None,
            "items": [],
        }


# --------------------------------------------------------------- 注册表

#: 能力名 -> provider 实例。接入真实服务时替换这里即可，路由与 schema 不变。
PROVIDERS = {
    "device": StubDeviceManager(),
    "monitor": StubMonitorService(),
    "orchestrator": StubOrchestratorService(),
    "track": StubTrackService(),
    "watchlist": StubWatchlistService(),
}


def get_provider(name: str):
    """取一个 provider；未注册则抛 KeyError（由 api 层转 501）。"""
    return PROVIDERS[name]
