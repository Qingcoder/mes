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
