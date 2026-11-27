"""站点/流程访问权限：事件溯源存储在 audit_logs，不新增数据库表。

事件：
- access.grant.create
- access.grant.update
- access.grant.delete

detail 保存完整授权快照，按 grant id 回放得到当前配置；
所有写操作同时保留审计记录，天然可查询、可追溯。
"""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from . import models
from .permission_guard import write_audit

CREATE = "access.grant.create"
UPDATE = "access.grant.update"
DELETE = "access.grant.delete"
EVENTS = (CREATE, UPDATE, DELETE)

SCOPE_TYPES = ("station", "flow")
TARGET_TYPES = ("role", "user")
EFFECTS = ("allow", "deny")
ACTIONS = ("view", "operate")


def _detail(row) -> Dict[str, Any]:
    try:
        return json.loads(row.detail or "{}")
    except Exception:
        return {}


def current_grants(db: Session) -> List[Dict[str, Any]]:
    rows = db.query(models.AuditLog).filter(
        models.AuditLog.action.in_(EVENTS),
    ).order_by(models.AuditLog.id.asc()).all()

    state: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        data = _detail(row)
        gid = data.get("grantId") or row.target
        if not gid:
            continue
        if row.action == DELETE:
            state.pop(gid, None)
            continue
        data["grantId"] = gid
        data["updatedAt"] = row.ts.isoformat() + "Z" if row.ts else ""
        data["updatedBy"] = row.username
        data.setdefault("createdAt", data.get("updatedAt", ""))
        data.setdefault("createdBy", row.username)
        state[gid] = data
    return sorted(state.values(), key=lambda g: (g.get("scopeType", ""), g.get("scopeValue", ""), g.get("grantId", "")))


def find_grant(db: Session, grant_id: str) -> Optional[Dict[str, Any]]:
    return next((g for g in current_grants(db) if g.get("grantId") == grant_id), None)


def _validate(payload: Dict[str, Any]) -> None:
    scope_type = str(payload.get("scopeType") or "").strip()
    scope_value = str(payload.get("scopeValue") or "").strip()
    target_type = str(payload.get("targetType") or "").strip()
    target_value = str(payload.get("targetValue") or "").strip()
    effect = str(payload.get("effect") or "allow").strip()
    actions = payload.get("actions") or []
    if scope_type not in SCOPE_TYPES:
        raise ValueError("授权维度只能是 station 或 flow")
    if not scope_value:
        raise ValueError("站点或流程值不能为空")
    if target_type not in TARGET_TYPES:
        raise ValueError("授权对象只能是 role 或 user")
    if not target_value:
        raise ValueError("被授权角色或用户不能为空")
    if effect not in EFFECTS:
        raise ValueError("授权效果只能是 allow 或 deny")
    if not isinstance(actions, list) or not actions or any(a not in ACTIONS for a in actions):
        raise ValueError("至少选择一个有效操作：view / operate")


def _target_exists(db: Session, target_type: str, target_value: str) -> bool:
    if target_type == "role":
        return db.query(models.Role).filter_by(code=target_value).first() is not None
    return db.query(models.Account).filter_by(username=target_value).first() is not None


def create_grant(db: Session, payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    _validate(payload)
    target_type = str(payload["targetType"]).strip()
    target_value = str(payload["targetValue"]).strip()
    if not _target_exists(db, target_type, target_value):
        raise ValueError("被授权角色或用户不存在")
    scope_type = str(payload["scopeType"]).strip()
    scope_value = str(payload["scopeValue"]).strip()
    for g in current_grants(db):
        if (g.get("scopeType"), g.get("scopeValue"), g.get("targetType"), g.get("targetValue")) == \
           (scope_type, scope_value, target_type, target_value):
            raise ValueError("该维度下已存在相同对象的授权，请编辑现有记录")

    now = datetime.utcnow().isoformat() + "Z"
    grant = {
        "grantId": "ACL-" + uuid.uuid4().hex[:10].upper(),
        "scopeType": scope_type,
        "scopeValue": scope_value,
        "targetType": target_type,
        "targetValue": target_value,
        "effect": str(payload.get("effect") or "allow"),
        "actions": list(payload.get("actions") or []),
        "description": str(payload.get("description") or "")[:256],
        "enabled": True,
        "createdAt": now,
        "createdBy": actor,
        "updatedAt": now,
        "updatedBy": actor,
    }
    write_audit(db, actor, CREATE, grant["grantId"],
                json.dumps(grant, ensure_ascii=False, separators=(",", ":"))[:512], commit=False)
    db.commit()
    return grant


def update_grant(db: Session, grant_id: str, payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    old = find_grant(db, grant_id)
    if not old:
        raise ValueError("授权记录不存在")
    merged = dict(old)
    for key in ("scopeType", "scopeValue", "targetType", "targetValue", "effect", "actions", "description", "enabled"):
        if key in payload:
            merged[key] = payload[key]
    _validate(merged)
    target_type = str(merged["targetType"]).strip()
    target_value = str(merged["targetValue"]).strip()
    if not _target_exists(db, target_type, target_value):
        raise ValueError("被授权角色或用户不存在")
    for g in current_grants(db):
        if g.get("grantId") != grant_id and \
           (g.get("scopeType"), g.get("scopeValue"), g.get("targetType"), g.get("targetValue")) == \
           (merged["scopeType"], merged["scopeValue"], target_type, target_value):
            raise ValueError("该维度下已存在相同对象的授权，请编辑现有记录")
    merged["grantId"] = grant_id
    merged["createdAt"] = old.get("createdAt", "")
    merged["createdBy"] = old.get("createdBy", actor)
    merged["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    merged["updatedBy"] = actor
    write_audit(db, actor, UPDATE, grant_id,
                json.dumps(merged, ensure_ascii=False, separators=(",", ":"))[:512], commit=False)
    db.commit()
    return merged


def delete_grant(db: Session, grant_id: str, actor: str) -> bool:
    old = find_grant(db, grant_id)
    if not old:
        raise ValueError("授权记录不存在")
    write_audit(db, actor, DELETE, grant_id,
                json.dumps({**old, "deletedAt": datetime.utcnow().isoformat() + "Z"}, ensure_ascii=False, separators=(",", ":"))[:512],
                commit=False)
    db.commit()
    return True


def _scope_matches(grant: Dict[str, Any], scope_type: str, scope_value: str) -> bool:
    g_type = grant.get("scopeType")
    g_value = str(grant.get("scopeValue") or "")
    if g_type == scope_type and g_value == scope_value:
        return True
    if scope_type == "station" and g_type == "flow":
        return scope_value in [s.strip() for s in g_value.replace(">", ",").split(",") if s.strip()]
    return False


def _decide(matches: List[Dict[str, Any]], action: str) -> Optional[bool]:
    if not matches:
        return None
    denies = [g for g in matches if g.get("effect") == "deny"]
    if denies:
        return False
    allows = [g for g in matches if g.get("effect") == "allow" and action in (g.get("actions") or [])]
    return True if allows else False


def is_allowed(db: Session, username: str, role: str, scope_type: str, scope_value: str, action: str) -> bool:
    """用户级授权优先于角色级；无显式配置时沿用原路由权限的默认行为。"""
    grants = [g for g in current_grants(db) if g.get("enabled", True)]
    relevant = [g for g in grants if _scope_matches(g, scope_type, scope_value)]

    user_matches = [g for g in relevant if g.get("targetType") == "user" and g.get("targetValue") == username]
    decided = _decide(user_matches, action)
    if decided is not None:
        return decided

    role_matches = [g for g in relevant if g.get("targetType") == "role" and g.get("targetValue") == role]
    decided = _decide(role_matches, action)
    if decided is not None:
        return decided

    return True
