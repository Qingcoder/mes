"""系统管理员（超管）保护与权限变更审计。

保护对象：角色码为 admin 的系统管理员角色，以及持有该角色的账号。
保护内容：不可删除、不可改名/降级、不可回收或变更权限。
所有被拦截的操作都会写入 audit_logs，便于追溯。
"""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from . import auth, models

from datetime import datetime, timedelta

SUPER_ROLE_CODE = "admin"
PROTECTED_PERMISSION = "system:role:manage"
AUDIT_RETENTION_DAYS = 90


def actor_dep(username: str = Depends(auth.current_username)) -> str:
    """从已验证令牌获取操作人，不再信任前端传入的请求头。"""
    return username


def write_audit(
    db: Session,
    actor: str,
    action: str,
    target: str,
    detail: str = "",
    commit: bool = False,
) -> models.AuditLog:
    row = models.AuditLog(
        username=(actor or "system")[:64],
        action=action[:64],
        target=(target or "")[:128],
        detail=(detail or "")[:512],
    )
    db.add(row)
    if commit:
        db.commit()
    return row


def reject_protected(
    db: Session,
    actor: str,
    action: str,
    target: str,
    reason: str,
    message: str,
):
    """记录被拒绝的超管操作并中断请求。"""
    write_audit(db, actor, action, target, reason, commit=True)
    raise HTTPException(status_code=403, detail=message)


def guard_role_mutable(db: Session, role, actor: str, action: str):
    """角色删除/编辑前置保护。"""
    if role and role.code == SUPER_ROLE_CODE:
        reject_protected(
            db, actor, f"{action}.rejected", role.code,
            "attempt to modify super admin role",
            "系统管理员角色为最高权限，不可删除、降级或修改",
        )


def guard_permissions_mutable(db: Session, role, actor: str, action: str, requested):
    """角色权限变更前置保护：超管权限完全不可变更。"""
    if role and role.code == SUPER_ROLE_CODE:
        reject_protected(
            db, actor, f"{action}.rejected", role.code,
            "attempted permissions=" + ",".join(sorted(requested or [])),
            "系统管理员权限为最高权限，不可删除、降级或回收",
        )


def guard_account_mutable(db: Session, account, actor: str, action: str):
    """账号删除/降级前置保护，供用户管理接口复用。"""
    if account and account.role == SUPER_ROLE_CODE:
        reject_protected(
            db, actor, f"{action}.rejected", account.username,
            "attempt to delete or downgrade super admin account",
            "系统管理员账号不可删除或降级",
        )


def cleanup_role_audit(db: Session, actor: str, days: int = AUDIT_RETENTION_DAYS):
    """清理超出保留期的权限审计日志（仅 role.%），返回删除条数与截止时间。"""
    days = min(max(int(days or AUDIT_RETENTION_DAYS), 1), 365)
    cutoff = datetime.utcnow() - timedelta(days=days)
    write_audit(
        db, actor, "role.audit.cleanup", "audit_logs",
        f"cleanup role.% before {cutoff.isoformat()}Z",
    )
    deleted = db.query(models.AuditLog).filter(
        models.AuditLog.action.like("role.%"),
        models.AuditLog.ts < cutoff,
    ).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "deleted": deleted, "days": days, "cutoff": cutoff.isoformat() + "Z"}
