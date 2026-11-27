"""双地址融合层：把本地 8007 与线上 8080 的统一为一套读写入口。

设计目标：
- 不改动任何现有数据库结构；本地侧只读取既有表，线上侧只走 /api/state。
- 配置驱动：mode=auto 时优先线上，线上不可达自动回退本地；local/remote 可强制指定。
- 写入线上时按 rev 乐观锁重试，冲突则重新拉取状态再提交，避免覆盖其他站点数据。
"""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from . import models, process_design_store, product_profiles_store
from .schemas import StationIn

CONFIG_PATH = Path(__file__).resolve().parent.parent / "integration.json"
_REMOTE_PROBE_AT = 0.0
_REMOTE_PROBE_OK = False

DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": "auto",
    "remote_base_url": "http://10.30.120.18:8080",
    "local_base_url": "http://127.0.0.1:8007",
    "timeout_seconds": 8,
    "write_retries": 2,
    "sn_length": 16,
    "remote_token": "",
}


def load_config() -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    for key, env in [
        ("mode", "MES_INTEGRATION_MODE"),
        ("remote_base_url", "MES_REMOTE_BASE_URL"),
        ("local_base_url", "MES_LOCAL_BASE_URL"),
    ]:
        if os.getenv(env):
            cfg[key] = os.environ[env]
    return cfg


def save_config(patch: Dict[str, Any]) -> Dict[str, Any]:
    cfg = load_config()
    cfg.update(patch or {})
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


def _remote_url(path: str) -> str:
    return load_config()["remote_base_url"].rstrip("/") + path


def _http_get(path: str) -> Any:
    req = urllib.request.Request(_remote_url(path), headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=load_config()["timeout_seconds"]) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_state(rev: int, data: Dict[str, Any]) -> Any:
    body = json.dumps({"rev": rev, "data": data}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        _remote_url("/api/state"), data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=load_config()["timeout_seconds"]) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "ignore")
        try:
            return json.loads(raw)
        except Exception:
            return {"error": raw, "status": exc.code}


def remote_available() -> bool:
    try:
        req = urllib.request.Request(_remote_url("/api/state"), headers={"Accept": "application/json"})
        timeout = min(8.0, float(load_config()["timeout_seconds"]))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return bool(payload.get("data"))
    except Exception:
        return False


def get_remote_state() -> Tuple[int, Dict[str, Any]]:
    payload = _http_get("/api/state")
    return int(payload.get("rev") or 0), payload.get("data") or {}


def _remote_wos(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for idx, w in enumerate(data.get("wos") or [], start=1):
        stations = sorted(w.get("stations") or [], key=lambda s: int(s.get("order", 0)))
        out.append({
            "id": idx,
            "wo_no": w.get("id", ""),
            "product": w.get("product", ""),
            "batch": w.get("batch", ""),
            "plan_qty": int(w.get("plan") or 0),
            "location": w.get("location", ""),
            "status": w.get("status", ""),
            "stations": [s.get("id", "") for s in stations if s.get("id")],
            "pack_qty": 1,
            "rev": 0,
            "source": "remote",
        })
    return out


def _find_remote_wo(data: Dict[str, Any], wo_no: str) -> Optional[Dict[str, Any]]:
    return next((w for w in (data.get("wos") or []) if str(w.get("id")) == str(wo_no)), None)


def list_remote_wos() -> List[Dict[str, Any]]:
    _, data = get_remote_state()
    return _remote_wos(data)


def get_remote_wo(wo_id: int) -> Dict[str, Any]:
    _, data = get_remote_state()
    rows = _remote_wos(data)
    row = next((r for r in rows if r["id"] == wo_id), None)
    if not row:
        raise ValueError("线上工单不存在")
    raw = _find_remote_wo(data, row["wo_no"]) or {}
    sns = [{"id": i + 1, "sn": e.get("sn", ""), "state": e.get("state", ""), "wo_no": row["wo_no"]}
           for i, e in enumerate(raw.get("snList") or [])]
    return {"wo": row, "sns": sns}


def query_remote_wo(wo_id: int) -> Dict[str, Any]:
    detail = get_remote_wo(wo_id)
    wo_no = detail["wo"]["wo_no"]
    _, data = get_remote_state()
    units = [u for u in (data.get("units") or []) if u.get("woId") == wo_no]
    done = sum(1 for u in units if u.get("status") == "completed")
    failed = sum(1 for u in units if u.get("status") in ("fail", "hold"))
    packed = sum(1 for u in units if u.get("boxNo"))
    return {"wo": detail["wo"], "total": len(units), "station_done": done, "failed": failed, "packed": packed}


def submit_remote_station(body: StationIn) -> Dict[str, Any]:
    cfg = load_config()
    retries = int(cfg["write_retries"])
    for attempt in range(retries + 1):
        rev, data = get_remote_state()
        unit = next((u for u in (data.get("units") or []) if u.get("sn") == body.sn.strip().upper()), None)
        if not unit:
            raise ValueError("线上未找到该 SN")
        wo = _find_remote_wo(data, unit.get("woId"))
        if not wo:
            raise ValueError("线上未找到该 SN 所属工单")
        stations = sorted(wo.get("stations") or [], key=lambda s: int(s.get("order", 0)))
        codes = [s.get("id") for s in stations]
        if body.station not in codes and body.station != (wo.get("repair") or {}).get("id"):
            raise ValueError("站点不属于该工单")
        history = unit.setdefault("history", [])
        if body.result == "pass" and any(h.get("station") == body.station and h.get("code") == "PASS" for h in history):
            if unit.get("currentStation") != body.station:
                return {"ok": True, "state": unit.get("status", ""), "msg": "本站已通过（幂等跳过）", "source": "remote"}
        if unit.get("currentStation") != body.station:
            raise ValueError(f"SN 当前在 {unit.get('currentStation')}，不在 {body.station}")
        if body.result not in ("pass", "fail"):
            raise ValueError("result 仅支持 pass / fail")

        now = int(time.time() * 1000)
        op = (body.operator or "OP").strip() or "OP"
        if body.result == "pass":
            history.append({"station": body.station, "code": "PASS", "time": now, "op": op})
            idx = codes.index(body.station) if body.station in codes else -1
            nxt = codes[idx + 1] if idx >= 0 and idx + 1 < len(codes) else None
            unit["currentStation"] = nxt
            unit["status"] = "pending" if nxt else "completed"
            msg = "通过 · 已流转到下一站" if nxt else "通过 · 整单完工"
        else:
            code = (body.fail_code or "FAIL").strip().upper()
            history.append({"station": body.station, "code": code, "time": now, "op": op})
            unit["status"] = "fail"
            unit["currentStation"] = (wo.get("repair") or {}).get("id") or body.station
            unit["repairCount"] = int(unit.get("repairCount") or 0) + 1
            unit["repairStage"] = "待送修"
            unit["firstPass"] = False
            msg = "不良已推送维修站"

        result = _http_post_state(rev, data)
        if result.get("ok") or result.get("rev"):
            return {"ok": True, "state": unit["status"], "msg": msg, "source": "remote", "rev": result.get("rev")}
        if result.get("error") == "conflict" or result.get("status") == 409:
            continue
        raise ValueError(str(result.get("error") or "线上提交失败"))
    raise ValueError("线上 rev 持续冲突，请稍后重试")


# ---- 本地侧：复用既有表，不新增字段 ----
def list_local_wos(db: Session) -> List[Dict[str, Any]]:
    return [{
        "id": w.id, "wo_no": w.wo_no, "product": w.product, "batch": w.batch or "",
        "plan_qty": w.plan_qty, "location": w.location or "", "status": w.status,
        "stations": list(w.stations or []), "pack_qty": w.pack_qty, "rev": w.rev or 0, "source": "local",
    } for w in db.query(models.WorkOrder).order_by(models.WorkOrder.id).all()]


def get_local_wo(db: Session, wo_id: int) -> Dict[str, Any]:
    w = db.get(models.WorkOrder, wo_id)
    if not w:
        raise ValueError("本地工单不存在")
    return {
        "wo": {"id": w.id, "wo_no": w.wo_no, "product": w.product, "batch": w.batch or "",
               "plan_qty": w.plan_qty, "location": w.location or "", "status": w.status,
               "stations": list(w.stations or []), "pack_qty": w.pack_qty, "rev": w.rev or 0, "source": "local"},
        "sns": [{"id": u.id, "sn": u.sn, "state": u.state, "wo_no": w.wo_no}
                for u in db.query(models.Unit).filter_by(wo_id=w.id).all()],
    }


def query_local_wo(db: Session, wo_id: int) -> Dict[str, Any]:
    detail = get_local_wo(db, wo_id)
    us = db.query(models.Unit).filter_by(wo_id=wo_id).all()
    return {
        "wo": detail["wo"], "total": len(us),
        "station_done": sum(1 for u in us if u.state in ("passed", "station_done", "packed")),
        "failed": sum(1 for u in us if u.state in ("failed", "rework")),
        "packed": sum(1 for u in us if u.box_no),
    }


def submit_local_station(db: Session, body: StationIn) -> Dict[str, Any]:
    from .main import station as local_station_endpoint
    r = local_station_endpoint(body, db)
    r["source"] = "local"
    return r


# ---- 统一入口 ----
def _use_remote() -> bool:
    global _REMOTE_PROBE_AT, _REMOTE_PROBE_OK
    mode = load_config()["mode"]
    if mode == "remote":
        return True
    if mode == "local":
        return False
    now = time.monotonic()
    if now - _REMOTE_PROBE_AT < 60:
        return _REMOTE_PROBE_OK
    _REMOTE_PROBE_OK = remote_available()
    _REMOTE_PROBE_AT = now
    return _REMOTE_PROBE_OK


def unified_list_wos(db: Session) -> List[Dict[str, Any]]:
    if _use_remote():
        try:
            return list_remote_wos()
        except Exception:
            if load_config()["mode"] == "remote":
                raise
    return list_local_wos(db)


def unified_get_wo(db: Session, wo_id: int) -> Dict[str, Any]:
    if _use_remote():
        try:
            return get_remote_wo(wo_id)
        except Exception:
            if load_config()["mode"] == "remote":
                raise
    return get_local_wo(db, wo_id)


def unified_query_wo(db: Session, wo_id: int) -> Dict[str, Any]:
    if _use_remote():
        try:
            return query_remote_wo(wo_id)
        except Exception:
            if load_config()["mode"] == "remote":
                raise
    return query_local_wo(db, wo_id)


def resolve_route_wo(db: Session, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """按路由配置分配工单：配置驱动，不读取操作人角色。"""
    wos = unified_list_wos(db)
    if not wos:
        return None
    policy = str((config or {}).get("assignPolicy") or "first")
    if policy == "pendingFirst":
        for wo in wos:
            try:
                if (unified_get_wo(db, int(wo["id"])).get("sns") or []):
                    return wo
            except Exception:
                continue
        return wos[0]
    return wos[0]


def _find_remote_sn(data: Dict[str, Any], sn: str) -> Optional[Dict[str, Any]]:
    code = (sn or "").strip().upper()
    for unit in data.get("units") or []:
        if str(unit.get("sn", "")).strip().upper() != code:
            continue
        wo_no = str(unit.get("woId") or "")
        wo = _find_remote_wo(data, wo_no)
        stations = sorted(wo.get("stations") or [], key=lambda s: int(s.get("order", 0))) if wo else []
        station = str(unit.get("currentStation") or "")
        if not station and stations:
            station = str(stations[0].get("id") or "")
        return {
            "sn": code, "wo_no": wo_no,
            "wo_id": next((w["id"] for w in _remote_wos(data) if w["wo_no"] == wo_no), None),
            "station": station, "state": unit.get("status", ""), "source": "remote",
        }
    return None


def _find_local_sn(db: Session, sn: str) -> Optional[Dict[str, Any]]:
    code = (sn or "").strip().upper()
    unit = db.query(models.Unit).filter(models.Unit.sn == code).first()
    if not unit:
        return None
    wo = db.get(models.WorkOrder, unit.wo_id)
    stations = list(wo.stations or []) if wo else []
    return {
        "sn": code, "wo_no": wo.wo_no if wo else "", "wo_id": unit.wo_id,
        "station": unit.current_station or (stations[0] if stations else ""),
        "state": unit.state, "source": "local",
    }


def _register_scanned_sn(db: Session, code: str, assigned: Dict[str, Any]) -> Dict[str, Any]:
    """站点扫入的新 SN 自动登记到当前工单，作为 SN 数据来源。"""
    if not product_profiles_store.validate_sn_prefix(code):
        raise ValueError("不是这个SN：应为 16 位大写字母或数字")
    existing = _find_local_sn(db, code)
    if existing:
        if str(existing.get("wo_id")) != str(assigned.get("id")):
            raise ValueError("SN 不属于当前工单")
        return existing
    wo = db.get(models.WorkOrder, int(assigned["id"]))
    if not wo:
        raise ValueError("当前工单不存在")
    stations = list(wo.stations or [])
    unit = models.Unit(sn=code, wo_id=wo.id, state="pending", current_station=stations[0] if stations else "")
    db.add(unit)
    db.flush()
    wo.plan_qty = db.query(models.Unit).filter_by(wo_id=wo.id).count()
    db.commit()
    return {
        "sn": code, "wo_no": wo.wo_no, "wo_id": wo.id,
        "station": unit.current_station or "", "state": unit.state, "source": "local",
    }


def resolve_sn_for_route(db: Session, sn: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """在路由配置对应的工单 SN 池中匹配 SN，未登记的合规 SN 由站点扫入建档。"""
    code = (sn or "").strip().upper()
    if not code:
        raise ValueError("SN 不能为空")
    assigned = resolve_route_wo(db, config)
    if not assigned:
        raise ValueError("当前路由配置没有可分配的工单")
    if _use_remote():
        try:
            _, data = get_remote_state()
            hit = _find_remote_sn(data, code)
            if hit:
                if str(hit.get("wo_no") or "") != str(assigned.get("wo_no") or ""):
                    raise ValueError("SN 不在当前工单的 SN 池中")
                hit["assigned"] = assigned
                hit["routeConfig"] = config
                hit["productDetail"] = _product_detail(str(assigned.get("product") or ""), code)
                return hit
            if load_config()["mode"] == "remote":
                raise ValueError("SN 不在当前工单的 SN 池中")
        except ValueError:
            raise
        except Exception:
            if load_config()["mode"] == "remote":
                raise
    hit = _find_local_sn(db, code)
    if not hit:
        hit = _register_scanned_sn(db, code, assigned)
    if str(hit.get("wo_id")) != str(assigned.get("id")):
        raise ValueError("不是这个SN：SN 不属于当前工单")
    hit["assigned"] = assigned
    hit["routeConfig"] = config
    hit["productDetail"] = _product_detail(str(assigned.get("product") or ""), code)
    return hit


def _product_detail(product: str, sn: str = "") -> Dict[str, Any]:
    def norm(value: Any) -> str:
        return "".join(str(value or "").split()).lower()

    key = norm(product)
    profiles = product_profiles_store.list_profiles()
    profile = next((
        item for item in profiles
        if key and key in {
            norm(item.get("code")),
            norm(item.get("name")),
            norm(item.get("family")),
        }
    ), None)
    if not profile:
        return {"code": "", "name": str(product or ""), "family": "", "description": "", "sides": []}
    sides = [
        {
            "key": str(side.get("key") or ""),
            "name": str(side.get("name") or ""),
            "count": len(side.get("sns") or []),
            "prefix": str(side.get("prefix") or ""),
        }
        for side in profile.get("sides", [])
    ]
    matched = next((side for side in sides if side["prefix"] and str(sn).startswith(side["prefix"])), None)
    return {
        "code": str(profile.get("code") or ""),
        "name": str(profile.get("name") or product or ""),
        "family": str(profile.get("family") or ""),
        "description": str(profile.get("description") or ""),
        "sides": sides,
        "matchedSide": matched,
    }


def _station_matches_person(station: Dict[str, Any], account: Optional[models.Account]) -> bool:
    if account and account.role == "admin":
        return True
    relations = station.get("relatedPersons") or []
    if not relations or not account:
        return False
    targets = {
        str(account.username or "").strip().lower(),
        str(account.name or "").strip().lower(),
    }
    return any(
        str(item.get("code") or "").strip().lower() in targets
        or str(item.get("name") or "").strip().lower() in targets
        for item in relations
    )


def _station_matches_product(station: Dict[str, Any], product_detail: Dict[str, Any]) -> bool:
    relations = station.get("relatedProducts") or []
    if not relations:
        return True
    targets = {
        str(product_detail.get("code") or "").strip().lower(),
        str(product_detail.get("name") or "").strip().lower(),
        str(product_detail.get("family") or "").strip().lower(),
    }
    return any(
        str(item.get("code") or "").strip().lower() in targets
        or str(item.get("name") or "").strip().lower() in targets
        for item in relations
    )


def _configured_station_flow(db: Session, assigned: Dict[str, Any], username: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    design = process_design_store.load_config()
    account = db.query(models.Account).filter_by(username=username).first() if username else None
    product_detail = _product_detail(str(assigned.get("product") or ""))
    all_stations = [
        station for station in design.get("stations", [])
        if station.get("enabled") is not False and station.get("type") != "repair"
    ]
    by_code = {str(item.get("code") or "").strip().upper(): item for item in all_stations}
    by_name = {str(item.get("name") or "").strip(): item for item in all_stations}
    wo_stations = [str(item).strip() for item in (assigned.get("stations") or []) if str(item).strip()]
    flow: List[Dict[str, Any]] = []
    source = wo_stations or [str(item.get("name") or item.get("code") or "") for item in all_stations]
    for station_value in source:
        configured = by_name.get(station_value) or by_code.get(station_value.upper())
        if configured and not _station_matches_person(configured, account):
            continue
        if configured and not _station_matches_product(configured, product_detail):
            continue
        flow.append({
            "id": station_value,
            "code": str((configured or {}).get("code") or ""),
            "name": str((configured or {}).get("name") or station_value),
            "failCodes": [
                {"code": str(item.get("code") or ""), "name": str(item.get("name") or "")}
                for item in (configured or {}).get("failCodes", [])
            ],
            "relatedPersons": (configured or {}).get("relatedPersons", []),
            "relatedProducts": (configured or {}).get("relatedProducts", []),
            "relatedEquipment": (configured or {}).get("relatedEquipment", []),
        })
    repair_id = str((design.get("settings") or {}).get("repairStationId") or "")
    repair_station = next(
        (item for item in design.get("stations", []) if str(item.get("id") or "") == repair_id),
        None,
    )
    if not repair_station:
        repair_station = next((item for item in design.get("stations", []) if item.get("type") == "repair"), {})
    repair = {
        "id": str(repair_station.get("code") or repair_station.get("name") or "R100"),
        "name": str(repair_station.get("name") or "维修站"),
        "value": str(repair_station.get("name") or repair_station.get("code") or "维修站"),
    }
    return flow, repair, product_detail


def station_context_for_route(db: Session, config: Dict[str, Any], username: str = "") -> Dict[str, Any]:
    """按当前人员、工单产品与工艺配置生成本次可作业站点。"""
    assigned = resolve_route_wo(db, config)
    if not assigned:
        raise ValueError("当前路由配置没有可分配的工单")
    use_remote = _use_remote()
    if use_remote:
        expected = [str(x) for x in ((config or {}).get("flowStations") or [])]
        flow = []
        raw_stations = {}
        try:
            _, data = get_remote_state()
            raw = _find_remote_wo(data, str(assigned.get("wo_no") or "")) or {}
            raw_stations = {
                str(s.get("id") or ""): s for s in (raw.get("stations") or [])
            }
        except Exception:
            if load_config()["mode"] == "remote":
                raise
        design = process_design_store.load_config()
        configured_stations = [
            item for item in design.get("stations", [])
            if item.get("enabled") is not False and item.get("type") != "repair"
        ]
        by_code = {str(item.get("code") or "").strip().upper(): item for item in configured_stations}
        by_name = {str(item.get("name") or "").strip(): item for item in configured_stations}
        account = db.query(models.Account).filter_by(username=username).first() if username else None
        product_detail = _product_detail(str(assigned.get("product") or ""))
        for sid in expected:
            station = raw_stations.get(sid) or {}
            configured = by_code.get(sid.upper()) or by_name.get(str(station.get("name") or ""))
            if configured and not _station_matches_person(configured, account):
                continue
            if configured and not _station_matches_product(configured, product_detail):
                continue
            flow.append({
                "id": sid,
                "code": str((configured or {}).get("code") or sid),
                "name": str(station.get("name") or (configured or {}).get("name") or sid),
                "failCodes": [
                    {"code": str(c.get("code") or ""), "name": str(c.get("name") or "")}
                    for c in (station.get("failCodes") or (configured or {}).get("failCodes") or [])
                ],
                "relatedPersons": (configured or {}).get("relatedPersons", []),
                "relatedProducts": (configured or {}).get("relatedProducts", []),
            })
        if not flow and not raw_stations:
            for code in (assigned.get("stations") or [])[:2]:
                flow.append({"id": str(code), "code": str(code), "name": str(code), "failCodes": []})
        repair = dict((config or {}).get("repairStation") or {"id": "REPAIR", "name": "维修站"})
    else:
        flow, repair, product_detail = _configured_station_flow(db, assigned, username)
    try:
        pool_count = len((unified_get_wo(db, int(assigned["id"])).get("sns") or []))
    except Exception:
        pool_count = 0
    return {
        "route": (config or {}).get("path", ""),
        "config": config,
        "wo": assigned,
        "operator": username,
        "product": assigned.get("product", ""),
        "productDetail": product_detail,
        "snPoolCount": pool_count,
        "flow": flow,
        "repair": repair,
        "allowedStations": [s["id"] for s in flow] + [repair.get("id", ""), repair.get("value", "")],
    }


def unified_query_sn(db: Session, sn: str, source: str = "") -> Dict[str, Any]:
    code = (sn or "").strip().upper()
    if not code:
        raise ValueError("SN 不能为空")
    use_remote = str(source).strip().lower() == "remote" or (not source and _use_remote())
    if use_remote:
        try:
            _, data = get_remote_state()
            unit = next((item for item in (data.get("units") or []) if str(item.get("sn") or "").strip().upper() == code), None)
            if unit:
                records = []
                for index, item in enumerate(unit.get("history") or [], start=1):
                    result_code = str(item.get("code") or "").upper()
                    ts = int(item.get("time") or 0)
                    records.append({
                        "id": index,
                        "station": str(item.get("station") or ""),
                        "result": "pass" if result_code == "PASS" else "fail",
                        "fail_code": "" if result_code == "PASS" else result_code,
                        "operator": str(item.get("op") or ""),
                        "created_at": datetime.fromtimestamp(ts / 1000).isoformat(timespec="milliseconds") if ts else "",
                    })
                return {
                    "source": "remote",
                    "unit": {
                        "sn": code,
                        "current_station": str(unit.get("currentStation") or ""),
                        "state": str(unit.get("status") or ""),
                        "fail_code": str(unit.get("failCode") or ""),
                        "box_no": str(unit.get("boxNo") or ""),
                    },
                    "wo_no": str(unit.get("woId") or ""),
                    "records": records,
                }
            if load_config()["mode"] == "remote":
                raise ValueError("SN 不存在")
        except ValueError:
            raise
        except Exception:
            if load_config()["mode"] == "remote":
                raise
    local = _find_local_sn(db, code)
    if not local:
        raise ValueError("SN 不存在")
    unit = db.query(models.Unit).filter_by(sn=code).first()
    records = [{
        "id": row.id,
        "station": str(row.station or ""),
        "result": str(row.result or ""),
        "fail_code": str(row.fail_code or ""),
        "operator": str(row.operator or ""),
        "created_at": row.created_at.isoformat(timespec="milliseconds") if row.created_at else "",
    } for row in unit.records]
    return {
        "source": "local",
        "unit": {
            "sn": code,
            "current_station": str(unit.current_station or ""),
            "state": str(unit.state or ""),
            "fail_code": str(unit.fail_code or ""),
            "box_no": str(unit.box_no or ""),
        },
        "wo_no": str(local.get("wo_no") or ""),
        "records": records,
    }


def unified_station(db: Session, body: StationIn, route_config: Optional[Dict[str, Any]] = None, username: str = "") -> Dict[str, Any]:
    if route_config:
        hit = resolve_sn_for_route(db, body.sn, route_config)
        body.station = hit["station"] or body.station
        ctx = station_context_for_route(db, route_config, username)
        if body.station not in ctx["allowedStations"]:
            raise ValueError("站点不在当前路由配置允许的流程内")
    if _use_remote():
        try:
            return submit_remote_station(body)
        except ValueError:
            raise
        except Exception:
            if load_config()["mode"] == "remote":
                raise
    return submit_local_station(db, body)
