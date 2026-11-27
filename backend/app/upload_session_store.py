"""可断点续传的上传会话存储。

- 分片独立写入临时目录，只有合并成功后才生成正式工艺文件。
- 会话元数据采用临时文件 + os.replace 原子写入。
- 不修改 process_design.json，正式文件仍需在页面“保存设计”后写入配置。
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .process_design_store import (
    MAX_PARAM_FILE_SIZE, UPLOAD_DIR, param_file_meta, save_param_file,
)

SESSION_DIR = os.path.join(UPLOAD_DIR, "_sessions")
_LOCK = threading.RLock()
SESSION_TTL_HOURS = 24


def _now() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _safe(value: Any, limit: int = 128) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", str(value or ""))[:limit]


def _session_dir(session_id: str) -> str:
    safe = _safe(session_id, 64)
    if not safe:
        raise ValueError("上传会话标识不合法")
    return os.path.join(SESSION_DIR, safe)


def _meta_path(session_id: str) -> str:
    return os.path.join(_session_dir(session_id), "session.json")


def _write_meta(session_id: str, meta: Dict[str, Any]) -> None:
    path = _meta_path(session_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _read_meta(session_id: str) -> Optional[Dict[str, Any]]:
    path = _meta_path(session_id)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cleanup(session_id: str) -> None:
    folder = _session_dir(session_id)
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass
        try:
            os.rmdir(folder)
        except OSError:
            pass


def _expired(meta: Dict[str, Any]) -> bool:
    try:
        updated = datetime.fromisoformat(str(meta.get("updatedAt") or meta.get("createdAt") or ""))
    except ValueError:
        return True
    return datetime.now() - updated > timedelta(hours=SESSION_TTL_HOURS)


def _status(meta: Dict[str, Any]) -> Dict[str, Any]:
    folder = _session_dir(str(meta["id"]))
    total = int(meta["totalSize"])
    chunk_size = int(meta["chunkSize"])
    chunk_count = int(meta["chunkCount"])
    uploaded: List[int] = []
    for index in range(chunk_count):
        if os.path.isfile(os.path.join(folder, f"{index}.part")):
            uploaded.append(index)
    received = sum(min(chunk_size, max(0, total - index * chunk_size)) for index in uploaded)
    next_chunk = next((i for i in range(chunk_count) if i not in set(uploaded)), chunk_count)
    return {
        "sessionId": meta["id"],
        "name": meta.get("name", ""),
        "size": total,
        "chunkSize": chunk_size,
        "chunkCount": chunk_count,
        "uploadedChunks": uploaded,
        "received": received,
        "progress": round(received / total, 6) if total else 0,
        "nextChunk": next_chunk,
        "complete": len(uploaded) == chunk_count,
    }


def _owned(meta: Dict[str, Any], actor: str, allow_admin: bool = False) -> bool:
    if allow_admin:
        return True
    return str(meta.get("actor") or "") == str(actor or "")


def create_or_resume(
    station_id: str,
    name: str,
    content_type: str,
    total_size: int,
    chunk_size: int,
    fingerprint: str,
    actor: str,
) -> Dict[str, Any]:
    if total_size <= 0 or total_size > MAX_PARAM_FILE_SIZE:
        raise ValueError("文件不能为空且不能超过 20MB")
    if chunk_size < 64 * 1024 or chunk_size > 4 * 1024 * 1024:
        raise ValueError("分片大小需在 64KB 到 4MB 之间")
    safe_fp = _safe(fingerprint, 128)
    if not safe_fp:
        raise ValueError("文件标识缺失，请刷新后重试")
    meta = param_file_meta(station_id, name, content_type, total_size)
    with _LOCK:
        os.makedirs(SESSION_DIR, exist_ok=True)
        for entry in os.listdir(SESSION_DIR):
            if not entry.endswith(".json"):
                continue
            path = os.path.join(SESSION_DIR, entry)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    old = json.load(f)
            except Exception:
                continue
            if (
                old.get("fingerprint") == safe_fp
                and old.get("actor") == actor
                and old.get("stationId") == meta["stationId"]
                and int(old.get("totalSize") or 0) == total_size
            ):
                if _expired(old) or int(old.get("chunkSize") or 0) != chunk_size:
                    _cleanup(str(old.get("id") or ""))
                    continue
                old["updatedAt"] = _now()
                _write_meta(str(old["id"]), old)
                return _status(old)
        session_id = "upl_" + uuid.uuid4().hex
        new_meta = {
            "id": session_id,
            "actor": actor,
            "stationId": meta["stationId"],
            "fingerprint": safe_fp,
            "name": meta["name"],
            "contentType": meta["contentType"],
            "totalSize": total_size,
            "chunkSize": chunk_size,
            "chunkCount": (total_size + chunk_size - 1) // chunk_size,
            "fileMeta": meta,
            "createdAt": _now(),
            "updatedAt": _now(),
        }
        _write_meta(session_id, new_meta)
        return _status(new_meta)


def get_status(session_id: str, actor: str, allow_admin: bool = False) -> Dict[str, Any]:
    with _LOCK:
        meta = _read_meta(session_id)
        if not meta or not _owned(meta, actor, allow_admin):
            raise FileNotFoundError("上传会话不存在")
        if _expired(meta):
            _cleanup(session_id)
            raise FileNotFoundError("上传会话已过期，请重新上传")
        return _status(meta)


def save_chunk(session_id: str, index: int, content: bytes, actor: str, allow_admin: bool = False) -> Dict[str, Any]:
    with _LOCK:
        meta = _read_meta(session_id)
        if not meta or not _owned(meta, actor, allow_admin):
            raise FileNotFoundError("上传会话不存在")
        if _expired(meta):
            _cleanup(session_id)
            raise FileNotFoundError("上传会话已过期，请重新上传")
        if index < 0 or index >= int(meta["chunkCount"]):
            raise ValueError("分片序号超出范围")
        expected = min(int(meta["chunkSize"]), int(meta["totalSize"]) - index * int(meta["chunkSize"]))
        if len(content) != expected:
            raise ValueError(f"分片大小不正确，期望 {expected} 字节，实际 {len(content)} 字节")
        folder = _session_dir(session_id)
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, f"{index}.part")
        tmp = target + ".tmp"
        with open(tmp, "wb") as f:
            f.write(content)
        os.replace(tmp, target)
        meta["updatedAt"] = _now()
        _write_meta(session_id, meta)
        return _status(meta)


def complete(session_id: str, actor: str, allow_admin: bool = False) -> Dict[str, Any]:
    with _LOCK:
        meta = _read_meta(session_id)
        if not meta or not _owned(meta, actor, allow_admin):
            raise FileNotFoundError("上传会话不存在")
        status = _status(meta)
        if not status["complete"]:
            raise ValueError(f"还有 {status['chunkCount'] - len(status['uploadedChunks'])} 个分片未上传")
        folder = _session_dir(session_id)
        target = os.path.join(UPLOAD_DIR, str(meta["fileMeta"]["path"]))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = target + ".tmp"
        written = 0
        with open(tmp, "wb") as out:
            for index in range(int(meta["chunkCount"])):
                with open(os.path.join(folder, f"{index}.part"), "rb") as part:
                    while True:
                        block = part.read(1024 * 1024)
                        if not block:
                            break
                        out.write(block)
                        written += len(block)
        if written != int(meta["totalSize"]):
            os.remove(tmp)
            raise ValueError("合并后的文件大小不一致，请重新上传")
        os.replace(tmp, target)
        result = dict(meta["fileMeta"])
        _cleanup(session_id)
        return result


def cancel(session_id: str, actor: str, allow_admin: bool = False) -> bool:
    with _LOCK:
        meta = _read_meta(session_id)
        if not meta or not _owned(meta, actor, allow_admin):
            return False
        _cleanup(session_id)
        return True
