"""工艺站点设计接口。"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth, deps, defect_code_store, equipment_store, models, permission_guard, process_design_store, product_profiles_store, relation_store, upload_session_store

router = APIRouter(
    prefix="/api/process-design", tags=["工艺站点设计"],
    dependencies=[Depends(auth.current_account)],
)


class DesignIn(BaseModel):
    config: dict


class MasterIn(BaseModel):
    groups: list | None = None
    library: list | None = None
    stationTypes: list | None = None
    libraryName: str | None = None


class UploadSessionIn(BaseModel):
    stationId: str
    name: str
    contentType: str = ""
    size: int
    chunkSize: int = 1024 * 1024
    fingerprint: str


get_db = deps.get_db


def _require_manage(db: Session, account: models.Account) -> str:
    codes = {r.perm_code for r in db.query(models.RolePermission).filter_by(role_code=account.role).all()}
    if account.role != "admin" and "method:manage" not in codes:
        raise HTTPException(403, "当前账号无工艺管理权限")
    return account.username


@router.get("")
def load_design(account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    _require_manage(db, account)
    return relation_store.enrich_process_design(process_design_store.load_config(), db)


@router.put("")
def save_design(body: DesignIn, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    try:
        config = process_design_store.normalize_config(body.config)
        for station in config.get("stations", []):
            station["failCodes"] = defect_code_store.normalize_fail_codes(station.get("failCodes") or [])
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, str(exc))
    for station in config.get("stations", []):
        relation_store.apply_full_selection("station", station.get("code") or station.get("id"), station, db)
    saved = process_design_store.save_config(config, db, actor)
    relation_store.sync_all(db)
    return relation_store.enrich_process_design(saved, db)


@router.get("/options")
def relation_options(account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    _require_manage(db, account)
    products = [
        {"code": str(row.get("code") or "").upper(), "name": str(row.get("name") or "")}
        for row in product_profiles_store.list_profiles() if row.get("code")
    ]
    equipment = [
        {"code": str(row.get("code") or "").upper(), "name": str(row.get("name") or "")}
        for row in equipment_store.list_devices() if row.get("code")
    ]
    persons = [
        {"code": row.username, "name": row.name or row.username}
        for row in db.query(models.Account).order_by(models.Account.name.asc()).all()
    ]
    return {"products": products, "equipment": equipment, "persons": persons}


@router.get("/master")
def load_master(account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    _require_manage(db, account)
    return process_design_store.master_snapshot()


@router.put("/master")
def save_master(body: MasterIn, account: models.Account = Depends(auth.current_account), db: Session = Depends(get_db)):
    actor = _require_manage(db, account)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        process_design_store.save_master_config(patch, db, actor)
        relation_store.sync_all(db)
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, str(exc))
    return process_design_store.master_snapshot()


@router.post("/upload-sessions", status_code=201)
def create_upload_session(
    body: UploadSessionIn,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    config = process_design_store.load_config()
    if not any(s.get("id") == body.stationId for s in config.get("stations", [])):
        raise HTTPException(404, "站点不存在")
    try:
        return upload_session_store.create_or_resume(
            body.stationId, body.name, body.contentType, body.size,
            body.chunkSize, body.fingerprint, actor,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/upload-sessions/{session_id}")
def upload_session_status(
    session_id: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_manage(db, account)
    try:
        return upload_session_store.get_status(session_id, account.username, account.role == "admin")
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))


@router.put("/upload-sessions/{session_id}/chunks/{index}")
async def upload_chunk(
    session_id: str,
    index: int,
    chunk: UploadFile = File(...),
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_manage(db, account)
    content = await chunk.read(4 * 1024 * 1024 + 1)
    try:
        return upload_session_store.save_chunk(
            session_id, index, content, account.username, account.role == "admin",
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/upload-sessions/{session_id}/complete")
def complete_upload_session(
    session_id: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    try:
        meta = upload_session_store.complete(session_id, actor, account.role == "admin")
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    permission_guard.write_audit(db, actor, "process.parameter.file.upload", meta["stationId"], f"name={meta['name']}; size={meta['size']}", commit=True)
    return meta


@router.delete("/upload-sessions/{session_id}")
def cancel_upload_session(
    session_id: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_manage(db, account)
    return {"ok": upload_session_store.cancel(session_id, account.username, account.role == "admin")}


@router.post("/parameter-files")
async def upload_parameter_file(
    station_id: str,
    file: UploadFile = File(...),
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    config = process_design_store.load_config()
    if not any(s.get("id") == station_id for s in config.get("stations", [])):
        raise HTTPException(404, "站点不存在")
    content = await file.read(process_design_store.MAX_PARAM_FILE_SIZE + 1)
    try:
        meta = process_design_store.param_file_meta(station_id, file.filename or "", file.content_type or "", len(content))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    process_design_store.save_param_file(meta, content)
    permission_guard.write_audit(db, actor, "process.parameter.file.upload", station_id, f"name={meta['name']}; size={meta['size']}", commit=True)
    return meta


@router.get("/parameter-files/{station_id}/{file_id}")
def download_parameter_file(
    station_id: str,
    file_id: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    _require_manage(db, account)
    try:
        path, _ = process_design_store.find_param_file(station_id, file_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc))
    config = process_design_store.load_config()
    name = file_id
    for station in config.get("stations", []):
        if station.get("id") == station_id:
            for meta in station.get("paramFiles", []):
                if meta.get("id") == file_id:
                    name = meta.get("name") or file_id
                    break
            break
    return FileResponse(path, filename=name)


@router.delete("/parameter-files/{station_id}/{file_id}")
def delete_parameter_file(
    station_id: str,
    file_id: str,
    account: models.Account = Depends(auth.current_account),
    db: Session = Depends(get_db),
):
    actor = _require_manage(db, account)
    removed = process_design_store.delete_param_file(station_id, file_id)
    if removed:
        permission_guard.write_audit(db, actor, "process.parameter.file.delete", station_id, f"file={file_id}", commit=True)
    return {"ok": removed}
