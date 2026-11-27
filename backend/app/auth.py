"""真实登录令牌与密码校验。

- 令牌：HMAC-SHA256 签名，包含账号、签发时间、过期时间；服务端按账号实时读取角色与权限。
- 密码：PBKDF2-HMAC-SHA256 加盐存储；兼容旧明文密码并在登录成功后自动升级。
- 密钥：优先环境变量 MES_TOKEN_SECRET；未配置时使用项目内 .token_secret，首次自动生成。
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import models
from .deps import get_db

TOKEN_TTL_SECONDS = int(os.getenv("MES_TOKEN_TTL_SECONDS", "43200"))
PBKDF2_ITERATIONS = 120_000
_SECRET_CACHE: bytes | None = None


def _secret() -> bytes:
    global _SECRET_CACHE
    if _SECRET_CACHE is not None:
        return _SECRET_CACHE
    env = os.getenv("MES_TOKEN_SECRET", "").strip()
    if env:
        _SECRET_CACHE = env.encode("utf-8")
        return _SECRET_CACHE
    path = Path(__file__).resolve().parent.parent / ".token_secret"
    if path.exists():
        _SECRET_CACHE = path.read_text(encoding="utf-8").strip().encode("utf-8")
    else:
        _SECRET_CACHE = secrets.token_hex(32).encode("utf-8")
        path.write_text(_SECRET_CACHE.decode("utf-8"), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return _SECRET_CACHE


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_token(username: str, role: str = "", ttl_seconds: int | None = None) -> str:
    now = int(time.time())
    payload: Dict[str, Any] = {
        "u": username,
        "r": role,
        "iat": now,
        "exp": now + int(ttl_seconds or TOKEN_TTL_SECONDS),
        "n": secrets.token_hex(8),
    }
    body = _b64e(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    sig = _b64e(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def decode_token(token: str) -> Dict[str, Any]:
    try:
        body, sig = token.split(".", 1)
        expected = _b64e(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        payload = json.loads(_b64d(body).decode("utf-8"))
        if not isinstance(payload, dict) or not payload.get("u"):
            raise ValueError("bad payload")
        if int(payload.get("exp") or 0) <= int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", (password or "").encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    stored = stored or ""
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, digest = stored.split("$", 3)
            candidate = hashlib.pbkdf2_hmac(
                "sha256", (password or "").encode("utf-8"), bytes.fromhex(salt), int(iterations),
            ).hex()
            return hmac.compare_digest(candidate, digest)
        except Exception:
            return False
    return hmac.compare_digest(password or "", stored)


def needs_rehash(stored: str) -> bool:
    return not (stored or "").startswith("pbkdf2_sha256$")


def current_account(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> models.Account:
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    payload = decode_token(token)
    account = db.query(models.Account).filter_by(username=payload["u"]).first()
    if not account:
        raise HTTPException(status_code=401, detail="账号不存在或已停用")
    return account


def current_username(account: models.Account = Depends(current_account)) -> str:
    return account.username
