"""戴盟 MES 生产管理平台 · 后端 API
启动：uvicorn app.main:app --reload --port 8007
接口文档：http://127.0.0.1:8007/docs
"""
import os
import re
import socket
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, event, func
from sqlalchemy.orm import sessionmaker, Session

from . import auth, deps, models, permission_registry, relation_store
from .permission_guard import write_audit
from .schemas import (
    LoginIn, LoginOut, WOIn, SNImportIn, StationIn, PackIn, SnReplaceIn,
    WOLine, UnitLine, RecordLine, BoxLine,
)

# ---- 数据库：SQLite 起步，改这一个 URL 即可迁 PostgreSQL ----
DB_URL = os.getenv("MES_DB_URL", "sqlite:///./mes.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if "sqlite" in DB_URL else {})
if "sqlite" in DB_URL:
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, conn_record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
models.Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    with SessionLocal() as db:
        seed(db)
    yield


_CORS_ORIGINS = [item.strip() for item in os.getenv("MES_CORS_ORIGINS", "").split(",") if item.strip()]
app = FastAPI(title="戴盟 MES 生产管理平台 API", version="V1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS or ["*"], allow_credentials=bool(_CORS_ORIGINS),
    allow_methods=["*"], allow_headers=["*"],
)

from .routers import unified, roles, search, collection, access, custom_sites, domain_config, persons, module_skeleton, function_tree, process_design, defect_codes, product_profiles, environment, equipment, account, sn_library, quality_dashboard  # noqa: E402  扩展路由需在主应用创建后注册
app.include_router(unified.router)
app.include_router(roles.router)
app.include_router(search.router)
app.include_router(collection.router)
app.include_router(access.router)
app.include_router(custom_sites.router)
app.include_router(domain_config.router)
app.include_router(persons.router)
app.include_router(module_skeleton.router)
app.include_router(function_tree.router)
app.include_router(process_design.router)
app.include_router(defect_codes.router)
app.include_router(product_profiles.router)
app.include_router(environment.router)
app.include_router(equipment.router)
app.include_router(account.router)
app.include_router(sn_library.router)
app.include_router(quality_dashboard.router)


get_db = deps.get_db


# ---- RBAC：权限点目录与角色默认权限（新建角色自动继承，无需手工勾选）----
PERMISSIONS = [
    (p["code"], p["name"], p["module"])
    for p in permission_registry.permission_rows()
]

ROLE_PERMS = {
    "admin": [c for c, _, _ in PERMISSIONS],
}
# 新建自定义角色的默认权限集（不含系统管理权限）
DEFAULT_ROLE_PERMS = [
    "wo:view", "wo:create", "sn:import", "station:op",
    "rework:op", "pack:op", "query:view",
]


def _grant_perms(db: Session, role_code: str, perm_codes):
    """幂等补齐角色权限：只新增缺失项，不删除已有授权。"""
    existing = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=role_code).all()}
    for pcode in perm_codes:
        if pcode not in existing:
            db.add(models.RolePermission(role_code=role_code, perm_code=pcode))


def ensure_default_permissions(db: Session):
    """幂等补齐权限点、admin 角色与管理员权限；保留已创建的自定义角色。"""
    known = {p.code for p in db.query(models.Permission).all()}
    for code, name, module in PERMISSIONS:
        if code not in known:
            db.add(models.Permission(code=code, name=name, module=module))

    if not db.query(models.Role).filter_by(code="admin").first():
        db.add(models.Role(code="admin", name="系统管理员", builtin=True))

    _grant_perms(db, "admin", ROLE_PERMS["admin"])

    module_perm_codes = [code for code, _, module in PERMISSIONS if module == "模块"]
    for role in db.query(models.Role).all():
        current = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=role.code).all()}
        if current.intersection({"system:access:manage", "system:user:manage", "system:role:manage"}):
            _grant_perms(db, role.code, module_perm_codes)
        elif role.code == "admin":
            _grant_perms(db, role.code, module_perm_codes)

    fallback_role = None
    for code in ("operator", "viewer"):
        if db.query(models.Role).filter_by(code=code).first():
            fallback_role = code
            break
    if not fallback_role:
        first = db.query(models.Role).filter(models.Role.code != "admin").first()
        fallback_role = first.code if first else None

    for a in db.query(models.Account).all():
        if not a.role and fallback_role:
            a.role = fallback_role
        if not a.avatar:
            a.avatar = (a.name or a.username or "?")[:1]


def permissions_of(db: Session, role_code: str) -> List[str]:
    return [r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=role_code).all()]


def _migrate_sn_replace_columns(db: Session) -> None:
    """幂等补齐 SN 替换链需要的列（create_all 不会给已有表加列）。"""
    from sqlalchemy import text
    columns = {row[1] for row in db.execute(text("PRAGMA table_info(units)")).fetchall()}
    if "origin_sn" not in columns:
        db.execute(text("ALTER TABLE units ADD COLUMN origin_sn VARCHAR(64)"))
    if "replaced_count" not in columns:
        db.execute(text("ALTER TABLE units ADD COLUMN replaced_count INTEGER DEFAULT 0"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_units_origin_sn ON units (origin_sn)"))
    db.commit()


def seed(db: Session):
    _migrate_sn_replace_columns(db)
    ensure_default_permissions(db)
    if db.query(models.Account).count() == 0:
        db.add(models.Account(username="admin", password="123456", name="系统管理员", role="admin"))
    if db.query(models.Product).count() == 0:
        for code, name in [
            ("BACKPACK", "V2.9 无本体数采背包"),
            ("GRIPPER", "V2.9 无本体数采夹爪"),
            ("TELEOP", "三代遥操-背包版本"),
            ("BRACKET", "三代遥操-支架板"),
        ]:
            db.add(models.Product(code=code, name=name))
    db.commit()


def require_auth(account: models.Account = Depends(auth.current_account)):
    return account


# ---- 登录 ----
@app.post("/api/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    a = db.query(models.Account).filter_by(username=(body.username or "").strip()).first()
    if not a or not auth.verify_password(body.password, a.password):
        return LoginOut(ok=False, msg="账号或密码错误")
    if auth.needs_rehash(a.password):
        a.password = auth.hash_password(body.password)
        db.commit()
    return LoginOut(
        ok=True, token=auth.create_token(a.username, a.role),
        username=a.username, name=a.name, role=a.role,
    )


# ---- 扫码登录（设备授权模式）：PC 建会话显示码 → 手机已登录扫确认 → PC 轮询拿 token ----
import secrets
import time
from fastapi import Query as _Query

_QR_TTL = 300  # 5 分钟
_qr_sessions: dict = {}  # sid -> {status, created, user}


@app.get("/api/lan-info")
def lan_info():
    """返回可用于手机访问的局域网地址，登录页/二维码生成时使用。"""
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip != "127.0.0.1" and not ip.startswith("169.254.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return {
        "ips": ips,
        "loginUrls": [f"http://{ip}:8007/login" for ip in ips],
        "recommended": f"http://{ips[0]}:8007" if ips else "",
    }


def _qr_cleanup():
    now = time.time()
    for k in [k for k, v in _qr_sessions.items() if now - v["created"] > _QR_TTL]:
        _qr_sessions.pop(k, None)


@app.post("/api/qr/create")
def qr_create():
    _qr_cleanup()
    sid = secrets.token_urlsafe(18)
    _qr_sessions[sid] = {"status": "pending", "created": time.time(), "user": None}
    return {"sid": sid, "ttl": _QR_TTL}


@app.get("/api/qr/status")
def qr_status(sid: str = _Query(...)):
    _qr_cleanup()
    s = _qr_sessions.get(sid)
    if not s:
        return {"status": "expired"}
    user = s.get("user")
    if s["status"] == "confirmed" and user:
        user = dict(user, token=auth.create_token(user["username"], user.get("role", "")))
    return {"status": s["status"], "user": user}


@app.post("/api/qr/confirm")
def qr_confirm(sid: str = _Query(...), account: models.Account = Depends(require_auth)):
    """手机端调用：把当前令牌账号作为扫码确认者绑定到会话。"""
    _qr_cleanup()
    s = _qr_sessions.get(sid)
    if not s or s["status"] != "pending":
        raise HTTPException(400, "二维码无效或已过期")
    a = account
    s["user"] = {
        "username": a.username,
        "name": a.name or a.username,
        "role": a.role or "",
    }
    s["status"] = "confirmed"
    return {"ok": True, "name": s["user"]["name"], "role": s["user"]["role"]}


# ---- 产品（建单下拉）----
@app.get("/api/products")
def products(db: Session = Depends(get_db), _=Depends(require_auth)):
    from .product_profiles_store import list_profiles
    rows = {p.code: {"code": p.code, "name": p.name} for p in db.query(models.Product).all()}
    for profile in list_profiles():
        code = str(profile.get("code", "")).strip().upper()
        if code:
            rows[code] = {"code": code, "name": str(profile.get("name") or code)}
    return sorted(rows.values(), key=lambda r: r["code"])


# ---- 工单 ----
def _next_wo_no(db: Session) -> str:
    prefix = f"WO-{datetime.now().strftime('%Y%m%d')}-"
    rows = db.query(models.WorkOrder.wo_no).filter(models.WorkOrder.wo_no.like(prefix + "%")).all()
    used = []
    for (value,) in rows:
        suffix = str(value or "")[len(prefix):]
        if suffix.isdigit():
            used.append(int(suffix))
    return f"{prefix}{max(used) + 1 if used else 1:03d}"


@app.get("/api/wos/next-no", dependencies=[Depends(require_auth)])
def next_wo_no(db: Session = Depends(get_db)):
    return {"wo_no": _next_wo_no(db)}


@app.get("/api/relation-options", dependencies=[Depends(require_auth)])
def relation_options(db: Session = Depends(get_db)):
    return relation_store.options(db)


@app.post("/api/wos", response_model=WOLine, dependencies=[Depends(require_auth)])
def create_wo(body: WOIn, db: Session = Depends(get_db)):
    wo_no = _next_wo_no(db)
    wo = models.WorkOrder(
        wo_no=wo_no, product=body.product, batch=body.batch,
        plan_qty=0, location=body.location or "戴盟公司",
        stations=body.stations, pack_qty=body.pack_qty or 1,
        status="released", rev=0,
    )
    db.add(wo); db.commit(); db.refresh(wo)
    desired = {
        "relatedProducts": [{"code": relation_store.resolve_relation_code("product", body.product, db)}],
        "relatedStations": [{"code": relation_store.resolve_relation_code("station", value, db)} for value in body.stations],
        "relatedEquipment": body.relatedEquipment,
        "relatedPersons": body.relatedPersons,
    }
    relation_store.apply_full_selection("workOrder", wo.wo_no, desired, db)
    relation_store.sync_all(db)
    return relation_store.enrich_work_order(WOLine.from_orm(wo).dict(), db)


@app.get("/api/wos", response_model=List[WOLine], dependencies=[Depends(require_auth)])
def list_wos(db: Session = Depends(get_db)):
    return [relation_store.enrich_work_order(WOLine.from_orm(wo).dict(), db)
            for wo in db.query(models.WorkOrder).order_by(models.WorkOrder.id.desc()).all()]


@app.get("/api/wos/flow-options", dependencies=[Depends(require_auth)])
def wo_flow_options():
    """工单建单可选的工艺站点流程，不要求工艺管理权限。"""
    from . import process_design_store
    try:
        config = process_design_store.load_config()
    except Exception:
        return {"templates": []}
    stations = [
        station for station in config.get("stations", [])
        if station.get("enabled") is not False and station.get("type") != "repair"
    ]
    templates = []
    for group in sorted(config.get("groups", []), key=lambda item: int(item.get("order") or 0)):
        names = [
            str(station.get("name") or station.get("code") or "").strip()
            for station in sorted(
                [station for station in stations if station.get("groupId") == group.get("id")],
                key=lambda item: int(item.get("order") or 0),
            )
            if str(station.get("name") or station.get("code") or "").strip()
        ]
        if names:
            templates.append({
                "key": "config:" + str(group.get("id") or ""),
                "name": str(group.get("name") or "工艺流程"),
                "stations": names,
            })
    return {"templates": templates}


@app.get("/api/wos/{wo_id}", dependencies=[Depends(require_auth)])
def get_wo(wo_id: int, db: Session = Depends(get_db)):
    wo = db.get(models.WorkOrder,wo_id)
    if not wo:
        raise HTTPException(404, "工单不存在")
    return {
        "wo": relation_store.enrich_work_order(WOLine.from_orm(wo).dict(), db),
        "sns": [UnitLine.from_orm(u) for u in wo.sns],
    }


# ---- SN 导入 ----
@app.post("/api/wos/{wo_id}/sns", dependencies=[Depends(require_auth)])
def import_sns(wo_id: int, body: SNImportIn, db: Session = Depends(get_db)):
    wo = db.get(models.WorkOrder,wo_id)
    if not wo:
        raise HTTPException(404, "工单不存在")
    normalized = [str(s).strip().upper() for s in body.sns if str(s).strip()]
    if not normalized:
        raise HTTPException(400, "导入清单为空")
    if len(normalized) > 1000:
        raise HTTPException(400, "单次最多导入 1000 条 SN")
    invalid = [s for s in normalized if not re.fullmatch(r"[A-Z0-9]{16}", s)]
    if invalid:
        preview = "、".join(invalid[:5])
        more = f" 等 {len(invalid)} 条" if len(invalid) > 5 else ""
        raise HTTPException(400, f"SN 格式错误：{preview}{more}；要求 16 位大写字母或数字")
    unique = list(dict.fromkeys(normalized))
    added, skipped = 0, []
    for sn in unique:
        if db.query(models.Unit).filter_by(sn=sn).first():
            skipped.append(sn)   # 幂等：重复 SN 跳过
            continue
        db.add(models.Unit(sn=sn, wo_id=wo_id, state="pending"))
        added += 1
    db.flush()
    wo.plan_qty = db.query(models.Unit).filter_by(wo_id=wo_id).count()
    db.commit()
    return {"added": added, "skipped": skipped, "invalid": 0, "total": len(unique), "planQty": wo.plan_qty}


# ---- 过站（核心：状态机收敛在服务层）----
def _sync_replaced_sn_to_master(old_sn: str, new_sn: str, wo) -> bool:
    """替换后的新 SN 登记到产品资料总表，旧 SN 保留作为历史来源。"""
    from . import product_profiles_store
    try:
        product_name = str(getattr(wo, "product", "") or "").strip()
        target = None
        for profile in product_profiles_store.list_profiles():
            if str(profile.get("code") or "").upper() == product_name.upper():
                target = profile
                break
            if str(profile.get("name") or "").strip() == product_name:
                target = profile
                break
        if not target:
            return False
        code = str(target.get("code") or "")
        existing = {
            str(item).strip().upper()
            for side in (target.get("sides") or [])
            for item in (side.get("sns") or [])
        }
        if new_sn in existing:
            return True
        product_profiles_store.add_sns(code, [new_sn])
        return True
    except Exception:
        return False


@app.post("/api/station/replace-sn", dependencies=[Depends(require_auth)])
def replace_sn(body: SnReplaceIn, db: Session = Depends(get_db)):
    """工站替换 SN：同一台设备换新标，数量不变，过站记录接续。"""
    from . import sn_replace

    old_sn = sn_replace.normalize_sn(body.sn)
    new_sn = sn_replace.normalize_sn(body.new_sn)
    if not sn_replace.valid_sn(new_sn):
        raise HTTPException(400, "新 SN 需为 16 位大写字母或数字")
    if new_sn == old_sn:
        raise HTTPException(400, "新 SN 与原 SN 相同")
    unit = sn_replace.find_unit_by_sn(db, old_sn)
    if not unit:
        raise HTTPException(404, "SN 不存在")
    if unit.sn == new_sn:
        raise HTTPException(400, "该设备已使用此 SN")
    if db.query(models.Unit).filter_by(sn=new_sn).first():
        raise HTTPException(400, "新 SN 已被其他设备使用")
    if db.query(models.SnReplacement).filter_by(new_sn=new_sn).first():
        raise HTTPException(400, "新 SN 已被替换使用过")

    wo = db.get(models.WorkOrder, unit.wo_id)
    stations = list(wo.stations or []) if wo else []
    station_code = body.station or unit.current_station or ""
    if station_code and stations and station_code not in stations:
        raise HTTPException(400, f"站点 {station_code} 不在本工单序列中")

    old_value = unit.sn
    records = list(unit.records)
    origin = unit.origin_sn or old_value
    unit.sn = new_sn
    unit.origin_sn = origin
    unit.replaced_count = int(unit.replaced_count or 0) + 1
    if station_code:
        unit.current_station = station_code
    db.add(models.SnReplacement(
        unit_id=unit.id, wo_id=unit.wo_id, old_sn=old_value, new_sn=new_sn,
        station=station_code, reason=str(body.reason or "").strip()[:256],
        operator=body.operator or "system",
    ))
    db.add(models.StationRecord(
        unit_id=unit.id, station=station_code, result="replace",
        source_type="replace", operator=body.operator or "system",
    ))
    write_audit(
        db, body.operator or "system", "sn.replace", new_sn,
        f"old_sn={old_value}; new_sn={new_sn}; station={station_code}; reason={str(body.reason or '').strip()[:120]}",
    )
    db.commit()
    db.refresh(unit)
    _sync_replaced_sn_to_master(old_value, new_sn, wo)
    return {
        "ok": True,
        "oldSn": old_value,
        "newSn": new_sn,
        "unit": UnitLine.from_orm(unit),
        "wo_no": wo.wo_no if wo else "",
        "chain": sn_replace.chain_for_unit(db, unit),
        "msg": f"已替换 SN：{old_value} → {new_sn}",
    }


@app.post("/api/station", dependencies=[Depends(require_auth)])
def station(body: StationIn, db: Session = Depends(get_db)):
    u = db.query(models.Unit).filter_by(sn=body.sn).first()
    if not u:
        raise HTTPException(404, "SN 不存在")
    wo = db.get(models.WorkOrder,u.wo_id)
    stations = wo.stations or []

    # 校验 1：站点必须在本单序列里
    if body.station not in stations:
        raise HTTPException(400, f"站点 {body.station} 不在本工单序列中")
    # 校验 2：不能跳站——最后一站必须是当前站或之前已过
    idx = stations.index(body.station)
    done = {r.station for r in u.records if r.result == "pass"}
    for s in stations[:idx]:
        if s not in done:
            raise HTTPException(400, f"不能跳站：请先完成 {s}")
    # 校验 3：重复提交幂等——本站已通过就不再记
    if body.station in done:
        write_audit(db, body.operator or "system", "station.skip", body.sn,
                    f"wo={wo.wo_no}; station={body.station}; reason=already_passed", commit=True)
        return {"ok": True, "msg": "本站已通过（幂等跳过）", "state": u.state}

    result = body.result
    u.current_station = body.station
    repair_payload = {}
    if result == "pass":
        u.state = "station_done" if idx == len(stations) - 1 else "passed"
        u.fail_code = None
    elif result == "fail":
        from . import process_design_store
        design = process_design_store.load_config()
        configured = next((
            item for item in design.get("stations", [])
            if str(item.get("code") or "").upper() == str(body.station or "").upper()
            or str(item.get("name") or "") == str(body.station or "")
        ), None)
        fail_codes = [str(item.get("code") or "").strip() for item in (configured or {}).get("failCodes", [])]
        fail_code = str(body.fail_code or "").strip()
        if fail_codes and fail_code not in fail_codes:
            raise HTTPException(400, "请选择当前站别已配置的不良代码")
        repair_id = str((design.get("settings") or {}).get("repairStationId") or "")
        repair_station = next(
            (item for item in design.get("stations", []) if str(item.get("id") or "") == repair_id),
            None,
        )
        if not repair_station:
            repair_station = next((item for item in design.get("stations", []) if item.get("type") == "repair"), {})
        repair_value = str(repair_station.get("name") or repair_station.get("code") or "")
        repair_payload = {
            "id": str(repair_station.get("code") or repair_value or "R100"),
            "name": str(repair_station.get("name") or "维修站"),
        }
        u.state = "failed"
        u.fail_code = fail_code
        u.current_station = repair_value or body.station
    else:
        raise HTTPException(400, "result 只能是 pass 或 fail")

    db.add(models.StationRecord(
        unit_id=u.id, station=body.station, result=result,
        fail_code=body.fail_code, operator=body.operator,
        source_type="station",
    ))
    write_audit(db, body.operator or "system", f"station.{result}", body.sn,
                f"wo={wo.wo_no}; station={body.station}; fail_code={body.fail_code or ''}; repair={u.current_station if result == 'fail' else ''}")
    db.commit()
    return {
        "ok": True, "state": u.state, "currentStation": u.current_station,
        "repairStation": repair_payload,
        "msg": "不良已转入维修站" if result == "fail" and repair_payload else "过站成功",
    }


# ---- 返修回当前站 ----
@app.post("/api/wos/{wo_id}/sns/{sn}/rework", dependencies=[Depends(require_auth)])
def rework(wo_id: int, sn: str, db: Session = Depends(get_db)):
    u = db.query(models.Unit).filter_by(sn=sn, wo_id=wo_id).first()
    if not u:
        raise HTTPException(404, "SN 不存在")
    u.state = "rework"
    u.fail_code = None
    db.add(models.StationRecord(
        unit_id=u.id, station=u.current_station or "", result="rework",
        operator="system", source_type="station",
    ))
    write_audit(db, "system", "rework", sn, f"wo_id={wo_id}; station={u.current_station or ''}")
    db.commit()
    return {"ok": True, "state": u.state, "msg": "已回到当前站重测"}


# ---- 包装出库 ----
@app.post("/api/pack", dependencies=[Depends(require_auth)])
def pack(body: PackIn, db: Session = Depends(get_db)):
    units = db.query(models.Unit).filter(models.Unit.sn.in_(body.sns)).all()
    if len(units) != len(set(body.sns)):
        raise HTTPException(400, "有 SN 不存在")
    wo_ids = {u.wo_id for u in units}
    if len(wo_ids) != 1:
        raise HTTPException(400, "一箱只能装同一工单的 SN")
    wo = db.get(models.WorkOrder, next(iter(wo_ids)))

    for u in units:
        if u.state != "station_done":
            raise HTTPException(400, f"SN {u.sn} 未通过全部站点，不能装箱")

    box = models.Box(box_no=body.box_no, wo_id=wo.id, qty=len(units), status="closed", closed_at=datetime.utcnow())
    db.add(box); db.flush()
    for u in units:
        u.state = "packed"; u.box_no = body.box_no
        write_audit(db, body.operator or "system", "pack.close", u.sn,
                    f"box={body.box_no}; wo={wo.wo_no}")
    packed_qty = db.query(models.Box).filter_by(wo_id=wo.id, status="closed").with_entities(
        func.coalesce(func.sum(models.Box.qty), 0)
    ).scalar()
    if wo.plan_qty and packed_qty >= wo.plan_qty:
        wo.status = "finished"
    db.commit()
    return {"ok": True, "box_no": body.box_no, "qty": len(units)}


# ---- 查询 ----
@app.get("/api/query/sn/{sn}", dependencies=[Depends(require_auth)])
def query_sn(sn: str, db: Session = Depends(get_db)):
    from . import sn_replace

    u = sn_replace.find_unit_by_sn(db, sn)
    if not u:
        raise HTTPException(404, "SN 不存在")
    wo = db.get(models.WorkOrder,u.wo_id)
    return {
        "unit": UnitLine.from_orm(u),
        "wo_no": wo.wo_no if wo else None,
        "records": [RecordLine.from_orm(r) for r in u.records],
        "chain": sn_replace.chain_for_unit(db, u),
        "history": sn_replace.unit_history(db, u),
    }


@app.get("/api/query/wo/{wo_id}", dependencies=[Depends(require_auth)])
def query_wo(wo_id: int, db: Session = Depends(get_db)):
    wo = db.get(models.WorkOrder,wo_id)
    if not wo:
        raise HTTPException(404, "工单不存在")
    units = wo.sns
    return {
        "wo": WOLine.from_orm(wo),
        "total": len(units),
        "station_done": sum(1 for u in units if u.state in ("station_done", "packed")),
        "failed": sum(1 for u in units if u.state == "failed"),
        "packed": sum(1 for u in units if u.state == "packed"),
    }


@app.get("/api/query/box/{box_no}", dependencies=[Depends(require_auth)])
def query_box(box_no: str, db: Session = Depends(get_db)):
    box = db.query(models.Box).filter_by(box_no=box_no).first()
    if not box:
        raise HTTPException(404, "箱号不存在")
    wo = db.get(models.WorkOrder,box.wo_id)
    return {
        "box": BoxLine.from_orm(box),
        "wo_no": wo.wo_no if wo else None,
        "sns": [u.sn for u in db.query(models.Unit).filter_by(box_no=box_no).all()],
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "platform": "戴盟 MES 生产管理平台"}


# ---- 静态前端：构建产物同端口托管，手机访问 http://<局域网IP>:8007 即可 ----
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
             "Pragma": "no-cache", "Expires": "0"}

if os.path.isdir(_DIST):
    _assets = os.path.join(_DIST, "assets")
    if os.path.isdir(_assets):
        class _NoCacheStaticFiles(StaticFiles):
            async def get_response(self, path, scope):
                response = await super().get_response(path, scope)
                response.headers.update(_NO_CACHE)
                return response
        app.mount("/assets", _NoCacheStaticFiles(directory=_assets), name="assets")

    # 入口页禁止缓存：重新构建前端后浏览器能立刻拿到新版本，避免旧 index.html
    # 引用已被覆盖的旧 JS 文件名导致 "Failed to fetch" / 停留在旧界面。

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "接口不存在")
        root = os.path.realpath(_DIST)
        target = os.path.realpath(os.path.join(root, full_path))
        try:
            inside = os.path.commonpath([root, target]) == root
        except ValueError:
            inside = False
        if full_path and inside and os.path.isfile(target):
            return FileResponse(target, headers=_NO_CACHE)
        return FileResponse(os.path.join(_DIST, "index.html"), headers=_NO_CACHE)
