"""pytest 公共夹具：独立临时数据库 + 已登录客户端。

注意：必须在 import app.main 之前设置 MES_DB_URL。
main.py 在模块加载时就 create_engine 并 create_all，之后再改环境变量已经没用，
所以这里把环境变量的设置放在文件最顶部，早于任何 from app import ...
"""
import os
import sys
import tempfile
from pathlib import Path

_TMP_DIR = Path(tempfile.mkdtemp(prefix="mes-test-"))
_DB_FILE = _TMP_DIR / "test.db"

# Windows 下 sqlite 绝对路径用正斜杠拼成 sqlite:///C:/xxxx/test.db
os.environ["MES_DB_URL"] = "sqlite:///" + _DB_FILE.as_posix()
os.environ["MES_TOKEN_SECRET"] = "pytest-only-secret-do-not-use-in-prod"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

# ---- JSON store 隔离 ----
# 产品档案、站点配置、关联边等业务主数据存在 backend/*.json，不走数据库。
# 不隔离的话，跑一次测试就会写真实档案库（建单会触发 relation_store.sync_all
# 回写多个 json）。这里把各 store 的路径改到临时目录，并把真实文件复制一份作为初始数据。
import shutil  # noqa: E402

from app import (  # noqa: E402
    custom_site_store,
    defect_code_store,
    domain_config_store,
    environment_store,
    equipment_store,
    function_tree_store,
    module_skeleton_store,
    permission_registry,
    personnel_store,
    process_design_store,
    product_profiles_store,
    relation_store,
    role_meta_store,
    sn_library_store,
    upload_session_store,
)

for _mod in (
    custom_site_store,
    defect_code_store,
    domain_config_store,
    environment_store,
    equipment_store,
    function_tree_store,
    module_skeleton_store,
    permission_registry,
    personnel_store,
    process_design_store,
    product_profiles_store,
    relation_store,
    role_meta_store,
    sn_library_store,
):
    _src = Path(str(getattr(_mod, "DATA_FILE", "")))
    if not _src.name:
        continue
    _dst = _TMP_DIR / _src.name
    if _src.exists():
        shutil.copy2(_src, _dst)
    _mod.DATA_FILE = str(_dst)

for _mod in (environment_store, process_design_store):
    if hasattr(_mod, "UPLOAD_DIR"):
        _mod.UPLOAD_DIR = str(_TMP_DIR / "uploads" / _mod.__name__)
        os.makedirs(_mod.UPLOAD_DIR, exist_ok=True)

# upload_session_store 是 from ... import UPLOAD_DIR，名字已绑定，要单独改
upload_session_store.UPLOAD_DIR = process_design_store.UPLOAD_DIR
upload_session_store.SESSION_DIR = str(_TMP_DIR / "uploads" / "_sessions")
os.makedirs(upload_session_store.SESSION_DIR, exist_ok=True)


@pytest.fixture(scope="session")
def client():
    # with 语句会触发 lifespan，里面会执行 seed()（建 admin、内置产品、权限点）
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client):
    r = client.post("/api/login", json={"username": "admin", "password": "123456"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True, data
    return data["token"]


@pytest.fixture()
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
