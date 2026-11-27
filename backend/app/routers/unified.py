"""统一访问入口：前端 /station 只依赖本组接口，不再感知本地/线上差异。"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from ..schemas import StationIn
from .. import access_control, auth, deps, integration, models
from ..station_route_config import get_station_route_config, validate_station_route_configs

validate_station_route_configs()

router = APIRouter(prefix="/api/unified", tags=["统一融合入口"])


def _route_config(path: str):
    cfg = get_station_route_config(path)
    if not cfg:
        raise HTTPException(404, "路由未配置站点作业参数")
    return dict(cfg, path=path)


get_db = deps.get_db


def _require_station_access(db: Session, account: models.Account) -> str:
    """操作人来自登录账号；X-Operator 不再作为身份依据。"""
    username = account.username
    if not username or username == "system":
        raise HTTPException(403, "无法识别当前登录账号")
    account = db.query(models.Account).filter_by(username=username).first()
    if not account:
        raise HTTPException(403, "账号不存在或已停用")
    allowed = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    if "station:op" not in allowed:
        raise HTTPException(403, "当前账号无过站作业权限")
    return username


@router.get("/assign")
def assign_wo(
    route: str = Query("/station"),
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    """按路由配置分配工单；响应不包含操作人角色。"""
    _require_station_access(db, account)
    config = _route_config(route)
    wo = integration.resolve_route_wo(db, config)
    if not wo:
        raise HTTPException(404, "当前路由配置没有可分配的工单")
    detail = integration.unified_get_wo(db, int(wo["id"]))
    return {
        "route": route, "config": config, "wo": wo, "stations": wo.get("stations") or [],
        "snPoolCount": len(detail.get("sns") or []),
        "rule": config.get("assignPolicy", "first"),
    }


@router.get("/station-context")
def station_context(
    route: str = Query("/station"),
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    """固定两站作业上下文：由路由配置提供流程，不携带操作人角色。"""
    username = _require_station_access(db, account)
    config = _route_config(route)
    try:
        ctx = integration.station_context_for_route(db, config, username)
        account = db.query(models.Account).filter_by(username=username).first()
        role = account.role if account else ""
        flow_value = ">".join(str(s["id"]) for s in ctx.get("flow", []))
        if not access_control.is_allowed(db, username, role, "flow", flow_value, "view"):
            raise HTTPException(403, "当前账号无权限访问该作业流程")
        ctx["flow"] = [
            s for s in ctx.get("flow", [])
            if access_control.is_allowed(db, username, role, "station", str(s["id"]), "view")
        ]
        if not ctx["flow"]:
            raise HTTPException(403, "当前账号无权限访问任何授权站点")
        ctx["allowedStations"] = [s["id"] for s in ctx["flow"]] + [ctx["repair"]["id"]]
        return ctx
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/resolve-sn")
def resolve_sn(
    body: dict,
    route: str = Query("/station"),
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    """校验当前人员、授权站点与工单 SN 池是否同时匹配。"""
    username = _require_station_access(db, account)
    config = _route_config(route)
    try:
        hit = integration.resolve_sn_for_route(db, str(body.get("sn") or ""), config)
        ctx = integration.station_context_for_route(db, config, username)
        allowed = {str(s["id"]) for s in ctx.get("flow", [])}
        allowed.add(str((ctx.get("repair") or {}).get("id") or ""))
        station = str(hit.get("station") or "")
        if station not in allowed:
            raise HTTPException(400, "不是这个SN：当前人员或站点不匹配")
        account = db.query(models.Account).filter_by(username=username).first()
        role = account.role if account else ""
        if not access_control.is_allowed(db, username, role, "station", station, "operate"):
            raise HTTPException(400, "不是这个SN：当前人员或站点不匹配")
        step = next((s for s in ctx.get("flow", []) if str(s.get("id")) == station), None)
        hit["matched"] = {
            "operator": username,
            "station": station,
            "stationName": str((step or {}).get("name") or (ctx.get("repair") or {}).get("name") or station),
        }
        return hit
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/config")
def get_config():
    return integration.load_config()


@router.post("/config")
def update_config(patch: Dict[str, Any]):
    allowed = {"mode", "remote_base_url", "local_base_url", "timeout_seconds", "write_retries", "sn_length", "remote_token"}
    clean = {k: v for k, v in (patch or {}).items() if k in allowed}
    return integration.save_config(clean)


@router.get("/query/sn/{sn}")
def query_sn(sn: str, source: str = Query(""), account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    """读取 SN 详情与过站日志，远端和本地使用同一返回结构。"""
    _require_station_access(db, account)
    try:
        return integration.unified_query_sn(db, sn, source)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/health")
def health(db: Session = Depends(get_db)):
    remote_ok = integration.remote_available()
    local_ok = True
    try:
        integration.list_local_wos(db)
    except Exception:
        local_ok = False
    cfg = integration.load_config()
    return {
        "mode": cfg["mode"],
        "remote": {"url": cfg["remote_base_url"], "ok": remote_ok},
        "local": {"url": cfg["local_base_url"], "ok": local_ok},
        "effective_source": "remote" if (cfg["mode"] == "auto" and remote_ok) or cfg["mode"] == "remote" else "local",
    }


@router.get("/wos")
def list_wos(db: Session = Depends(get_db)):
    try:
        return integration.unified_list_wos(db)
    except Exception as exc:
        raise HTTPException(502, f"读取工单失败：{exc}")


@router.get("/wos/{wo_id}")
def get_wo(wo_id: int, db: Session = Depends(get_db)):
    try:
        return integration.unified_get_wo(db, wo_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/query/wo/{wo_id}")
def query_wo(wo_id: int, db: Session = Depends(get_db)):
    try:
        return integration.unified_query_wo(db, wo_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/station")
def station(
    body: StationIn,
    route: str = Query("/station"),
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    username = _require_station_access(db, account)
    config = _route_config(route)
    try:
        account = db.query(models.Account).filter_by(username=username).first()
        role = account.role if account else ""
        if not access_control.is_allowed(db, username, role, "station", body.station, "operate"):
            raise HTTPException(403, "当前账号无权限操作该站点")
        body.operator = username
        return integration.unified_station(db, body, config, username)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, str(exc))
