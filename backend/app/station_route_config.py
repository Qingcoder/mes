"""站点作业路由配置。

与前端 `frontend/src/router/routeConfig.ts` 的 `STATION_ROUTE_CONFIG` 按路由 path 关联。
配置只描述站点流程，不包含任何操作人角色字段；角色仅用于功能权限校验，不参与站点配置。
"""
from typing import Any, Dict, Optional

STATION_ROUTE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "/station": {
        "flowStations": ["OP10", "OP20"],
        "repairStation": {"id": "R100", "name": "维修站"},
        "assignPolicy": "first",
        "snPoolScope": "workOrder",
        "failCodeScope": "station",
    },
}


def get_station_route_config(path: str) -> Optional[Dict[str, Any]]:
    return STATION_ROUTE_CONFIGS.get((path or "").strip())


def validate_station_route_configs() -> None:
    forbidden = {"role", "role_code", "roleCode"}
    for path, cfg in STATION_ROUTE_CONFIGS.items():
        if forbidden.intersection(cfg or {}):
            raise RuntimeError(f"[station-route-config] {path} 不应包含角色字段")
