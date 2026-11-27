"""主链路回归测试。

覆盖：登录 → 建单 → 导入 SN → 过站（站点校验 / 跳站拦截 / 重复过站幂等）
      → 不良与返修 → 装箱 → SN/工单/箱号三维度查询。

跑法（backend 目录下）：
    .venv\\Scripts\\python.exe -m pytest tests -q

注意：全部用例跑在临时 sqlite（见 conftest.py），不会碰 mes.db。
SN 用随机串生成，避免跨用例串数据。
"""
import random
import string

import pytest

# 站点名故意取测试专用名称：过站 fail 分支会去 process_design 配置里查 failCodes，
# 用生产站名可能被配置校验拦掉，这里保证 fail 用例稳定。
ST_A = "单测站A"
ST_B = "单测站B"


def _sn(prefix: str = "T") -> str:
    """16 位大写字母+数字，满足导入接口的 [A-Z0-9]{16} 校验。"""
    body = "".join(random.choices(string.ascii_uppercase + string.digits, k=15))
    return (prefix + body)[:16]


def _create_wo(client, auth, stations, pack_qty=2, product="BACKPACK"):
    r = client.post("/api/wos", headers=auth,
                    json={"product": product, "stations": stations, "pack_qty": pack_qty})
    assert r.status_code == 200, r.text
    wo = r.json()
    assert wo["id"] > 0
    assert wo["stations"] == stations
    assert wo["status"] == "released"
    return wo


def _import(client, auth, wo_id, sns):
    return client.post(f"/api/wos/{wo_id}/sns", headers=auth,
                       json={"wo_id": wo_id, "sns": sns})


def _station(client, auth, sn, station, result="pass", fail_code=None):
    payload = {"sn": sn, "station": station, "result": result, "operator": "pytest"}
    if fail_code:
        payload["fail_code"] = fail_code
    return client.post("/api/station", headers=auth, json=payload)


# ---------------------------------------------------------------- 登录
def test_login_ok(client):
    r = client.post("/api/login", json={"username": "admin", "password": "123456"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["token"]
    assert data["role"] == "admin"


def test_login_wrong_password(client):
    r = client.post("/api/login", json={"username": "admin", "password": "wrong-pass"})
    assert r.status_code == 200          # 业务失败也返回 200，用 ok 字段区分
    assert r.json()["ok"] is False


def test_api_requires_token(client):
    assert client.get("/api/wos").status_code == 401


# ---------------------------------------------------------------- 主链路
def test_main_chain(client, auth):
    sns = [_sn("A") for _ in range(3)]
    wo = _create_wo(client, auth, [ST_A, ST_B], pack_qty=3)
    wo_id = wo["id"]

    # 1. SN 格式校验：必须 16 位大写字母/数字
    bad = _import(client, auth, wo_id, ["SHORT-SN"])
    assert bad.status_code == 400
    assert "格式" in bad.json()["detail"]

    # 2. 正常导入；同批次内重复 SN 被幂等跳过，planQty 回写为实际数量
    imp = _import(client, auth, wo_id, sns + [sns[0]])
    assert imp.status_code == 200, imp.text
    data = imp.json()
    assert data["added"] == 3
    assert data["skipped"] == [sns[0]]
    assert data["planQty"] == 3

    # 3. 跳站拦截：第一站没过就提交第二站
    skip = _station(client, auth, sns[0], ST_B)
    assert skip.status_code == 400
    assert "不能跳站" in skip.json()["detail"]

    # 4. 站点不在本工单序列
    wrong = _station(client, auth, sns[0], "不存在的站")
    assert wrong.status_code == 400

    # 5. 第一站通过 → passed
    ok1 = _station(client, auth, sns[0], ST_A)
    assert ok1.status_code == 200, ok1.text
    assert ok1.json()["state"] == "passed"

    # 6. 重复提交同一站 → 幂等跳过，不重复落记录
    again = _station(client, auth, sns[0], ST_A)
    assert again.status_code == 200
    assert "幂等" in again.json()["msg"]

    # 7. 末站通过 → station_done
    ok2 = _station(client, auth, sns[0], ST_B)
    assert ok2.status_code == 200
    assert ok2.json()["state"] == "station_done"

    # 8. 有 SN 未过完全部站点时不能装箱
    bad_pack = client.post("/api/pack", headers=auth,
                           json={"box_no": f"BOX-{sns[0]}", "sns": [sns[0], sns[1]]})
    assert bad_pack.status_code == 400
    assert "不能装箱" in bad_pack.json()["detail"]

    # 9. 第二个 SN 过完两站后，两个一起装箱
    for st in (ST_A, ST_B):
        r = _station(client, auth, sns[1], st)
        assert r.status_code == 200, r.text
    box_no = f"BOX-{sns[0]}"
    pack = client.post("/api/pack", headers=auth, json={"box_no": box_no, "sns": [sns[0], sns[1]]})
    assert pack.status_code == 200, pack.text
    assert pack.json()["qty"] == 2

    # 10. 查询 SN：站点记录里 pass 只有两条（幂等没有多写）
    q_sn = client.get(f"/api/query/sn/{sns[0]}", headers=auth)
    assert q_sn.status_code == 200
    records = q_sn.json()["records"]
    assert len([r for r in records if r["result"] == "pass"]) == 2
    assert {r["station"] for r in records} == {ST_A, ST_B}

    # 11. 查询工单：总数 3、已装箱 2、不良 0
    q_wo = client.get(f"/api/query/wo/{wo_id}", headers=auth)
    assert q_wo.status_code == 200
    stat = q_wo.json()
    assert stat["total"] == 3
    assert stat["packed"] == 2
    assert stat["failed"] == 0

    # 12. 查询箱号：箱内 SN 与装箱的一致
    q_box = client.get(f"/api/query/box/{box_no}", headers=auth)
    assert q_box.status_code == 200
    assert sorted(q_box.json()["sns"]) == sorted([sns[0], sns[1]])


# ---------------------------------------------------------------- 不良 / 返修
def test_fail_and_rework(client, auth):
    wo = _create_wo(client, auth, [ST_A, ST_B], pack_qty=1)
    sn = _sn("B")
    assert _import(client, auth, wo["id"], [sn]).status_code == 200

    fail = _station(client, auth, sn, ST_A, result="fail", fail_code="E01")
    assert fail.status_code == 200, fail.text
    assert fail.json()["state"] == "failed"

    # 不良品不能装箱
    pack = client.post("/api/pack", headers=auth, json={"box_no": f"BOX-{sn}", "sns": [sn]})
    assert pack.status_code == 400

    # 返修：回到当初判不良的站，而不是维修站
    rew = client.post(f"/api/wos/{wo['id']}/sns/{sn}/rework", headers=auth)
    assert rew.status_code == 200, rew.text
    assert rew.json()["state"] == "rework"
    assert rew.json()["currentStation"] == ST_A

    # 返修后可重测通过
    again = _station(client, auth, sn, ST_A)
    assert again.status_code == 200, again.text
    assert again.json()["state"] == "passed"

    # 继续走完末站
    last = _station(client, auth, sn, ST_B)
    assert last.status_code == 200
    assert last.json()["state"] == "station_done"


# ---------------------------------------------------------------- SN 替换链
def test_replace_sn_chain(client, auth):
    wo = _create_wo(client, auth, [ST_A, ST_B], pack_qty=1)
    old_sn, new_sn = _sn("C"), _sn("D")
    assert _import(client, auth, wo["id"], [old_sn]).status_code == 200
    assert _station(client, auth, old_sn, ST_A).status_code == 200

    r = client.post("/api/station/replace-sn", headers=auth,
                    json={"sn": old_sn, "new_sn": new_sn, "station": ST_A, "operator": "pytest"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["oldSn"] == old_sn
    assert body["newSn"] == new_sn
    assert body["unit"]["sn"] == new_sn
    assert body["unit"]["origin_sn"] == old_sn

    # 已被替换掉的 SN 不能再当新 SN 用
    dup = client.post("/api/station/replace-sn", headers=auth,
                      json={"sn": new_sn, "new_sn": old_sn, "station": ST_A, "operator": "pytest"})
    assert dup.status_code == 400

    # 过站记录跟着新 SN 走
    q = client.get(f"/api/query/sn/{new_sn}", headers=auth)
    assert q.status_code == 200
    assert len(q.json()["chain"]) >= 1
    assert q.json()["unit"]["origin_sn"] == old_sn
