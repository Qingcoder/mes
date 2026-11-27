"""全局搜索：复用现有主数据与业务表，返回分类结果和跳转目标。"""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from .. import auth, deps, models, product_profiles_store

router = APIRouter(
    prefix="/api", tags=["全局搜索"], dependencies=[Depends(auth.current_account)],
)


get_db = deps.get_db


TYPE_LABEL = {
    "product": "产品",
    "user": "人员",
    "station": "站点",
    "wo": "工单",
    "sn": "SN",
    "box": "箱号",
}

# 与前端 routeConfig.ts 的路由权限保持一致：搜索结果跳转目标决定所需权限。
TYPE_PERMISSION = {
    "product": "wo:view",
    "user": "system:role:manage",
    "station": "station:op",
    "wo": "wo:view",
    "sn": "query:view",
    "box": "pack:op",
}


class SearchItem(BaseModel):
    type: str
    id: str
    title: str
    subtitle: str = ""
    route: str
    query: dict = {}
    badge: str = ""


class SearchTypeCount(BaseModel):
    type: str
    label: str
    count: int


class SearchOut(BaseModel):
    query: str
    total: int
    types: list[SearchTypeCount] = []
    items: list[SearchItem] = []
    allowedTypes: list[str] = []


def _hit(needle: str, *values) -> bool:
    low = needle.lower()
    return any(low in str(v or "").lower() for v in values)


def _score(needle: str, title: str) -> tuple:
    return (0 if str(title or "").lower().startswith(needle.lower()) else 1, str(title or ""))


@router.get("/search", response_model=SearchOut)
def global_search(
    q: str = Query(..., min_length=1, max_length=64),
    type: str = Query("all"),
    limit: int = Query(40, ge=1, le=100),
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    needle = (q or "").strip()
    if not needle:
        raise HTTPException(400, "搜索关键词不能为空")
    if type != "all" and type not in TYPE_LABEL:
        raise HTTPException(400, "搜索类型不合法")

    username = account.username
    perms = {
        row.perm_code
        for row in db.query(models.RolePermission).filter_by(role_code=account.role).all()
    }
    allowed_types = [t for t, p in TYPE_PERMISSION.items() if p in perms]
    if type != "all" and type not in allowed_types:
        label = TYPE_LABEL.get(type, type)
        raise HTTPException(403, f"无权限搜索{label}")

    effective_types = allowed_types if type == "all" else [type]
    per_type = max(3, min(10, limit // max(len(effective_types), 1)))
    items: list[SearchItem] = []

    if "product" in effective_types:
        product_rows = {p.code: {"code": p.code, "name": p.name} for p in db.query(models.Product).all()}
        for profile in product_profiles_store.list_profiles():
            code = str(profile.get("code", "")).strip().upper()
            if code:
                product_rows[code] = {"code": code, "name": str(profile.get("name") or code)}
        for code, row in sorted(product_rows.items()):
            if _hit(needle, code, row["name"]):
                items.append(SearchItem(
                    type="product", id=code, title=row["name"], subtitle=f"产品编码 {code}",
                    route="/product-info", query={"code": code}, badge=TYPE_LABEL["product"],
                ))

    if "user" in effective_types:
        for a in db.query(models.Account).all():
            if _hit(needle, a.username, a.name, a.role):
                items.append(SearchItem(
                    type="user", id=str(a.id), title=a.name or a.username,
                    subtitle=f"@{a.username} · {a.role}", route="/roles",
                    query={"user": a.username, "name": a.name or "", "role": a.role or ""},
                    badge=TYPE_LABEL["user"],
                ))

    if "station" in effective_types:
        seen = set()
        for w in db.query(models.WorkOrder).all():
            candidates = list(w.stations or [])
            if w.location:
                candidates.append(w.location)
            for s in candidates:
                if s and s not in seen and _hit(needle, s):
                    seen.add(s)
                    items.append(SearchItem(
                        type="station", id=s, title=s, subtitle=f"工单 {w.wo_no}",
                        route="/station", query={"wo": w.id, "station": s}, badge=TYPE_LABEL["station"],
                    ))

    if "wo" in effective_types:
        for w in db.query(models.WorkOrder).all():
            if _hit(needle, w.wo_no, w.product, w.batch, w.location):
                items.append(SearchItem(
                    type="wo", id=str(w.id), title=w.wo_no,
                    subtitle=f"{w.product} · {w.batch or '无批次'}", route="/wo",
                    query={"wo": w.id}, badge=TYPE_LABEL["wo"],
                ))

    if "sn" in effective_types:
        for u in db.query(models.Unit).all():
            if _hit(needle, u.sn):
                items.append(SearchItem(
                    type="sn", id=str(u.id), title=u.sn, subtitle=f"状态 {u.state}",
                    route="/query", query={"sn": u.sn}, badge=TYPE_LABEL["sn"],
                ))

    if "box" in effective_types:
        for b in db.query(models.Box).all():
            if _hit(needle, b.box_no):
                items.append(SearchItem(
                    type="box", id=str(b.id), title=b.box_no, subtitle=f"数量 {b.qty}",
                    route="/pack", query={"box": b.box_no}, badge=TYPE_LABEL["box"],
                ))

    grouped = {}
    for it in items:
        grouped.setdefault(it.type, []).append(it)
    selected = []
    for t, arr in grouped.items():
        arr.sort(key=lambda x: _score(needle, x.title))
        selected.extend(arr[:per_type])

    counts = []
    for t, label in TYPE_LABEL.items():
        c = len(grouped.get(t, []))
        if c:
            counts.append(SearchTypeCount(type=t, label=label, count=min(c, per_type)))
    return SearchOut(
        query=needle, total=len(selected), types=counts, items=selected,
        allowedTypes=allowed_types,
    )
