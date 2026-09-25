"""API 业务冒烟：在运行中的 API 容器内执行，以退出码报告结果。

校验内容：
1. /health 健康；
2. 一个可行案例返回可行解，并满足水源总量、节点守恒、分区需求与管路范围；
3. 一个下游缺水案例返回不可行及诊断；
4. 非法录入返回 422。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def call(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


FEASIBLE = {
    "source_total": 10,
    "nodes": [
        {"id": "S", "type": "source", "label": "水源"},
        {"id": "J", "type": "junction", "label": "分流点"},
        {"id": "A", "type": "zone", "label": "甲", "demand": 6},
        {"id": "B", "type": "zone", "label": "乙", "demand": 4},
    ],
    "pipes": [
        {"id": "p1", "from": "S", "to": "J", "minimum": 0, "maximum": 10, "preferred": 10},
        {"id": "p2", "from": "J", "to": "A", "minimum": 0, "maximum": 10, "preferred": 6},
        {"id": "p3", "from": "J", "to": "B", "minimum": 0, "maximum": 10, "preferred": 4},
        {"id": "p4", "from": "S", "to": "A", "minimum": 0, "maximum": 10, "preferred": 0},
    ],
}

INFEASIBLE = {
    "source_total": 10,
    "nodes": [
        {"id": "S", "type": "source"},
        {"id": "A", "type": "zone", "demand": 9},
        {"id": "B", "type": "zone", "demand": 1},
    ],
    "pipes": [
        {"id": "p1", "from": "S", "to": "A", "minimum": 0, "maximum": 4, "preferred": 4},
        {"id": "p2", "from": "S", "to": "B", "minimum": 0, "maximum": 10, "preferred": 1},
        {"id": "p3", "from": "S", "to": "A", "minimum": 0, "maximum": 0, "preferred": 0},
        {"id": "p4", "from": "S", "to": "B", "minimum": 0, "maximum": 10, "preferred": 0},
    ],
}


def main() -> int:
    status, body = call("GET", "/health")
    assert status == 200 and body["status"] == "ok", f"health 异常: {status} {body}"
    print("[smoke] /health ok")

    status, data = call("POST", "/api/balance", FEASIBLE)
    assert status == 200, f"balance HTTP {status}: {data}"
    assert data["feasible"] is True, f"应可行: {data.get('reason')}"

    pipes = {p["id"]: p for p in data["pipes"]}
    f = {k: p["flow"] for k, p in pipes.items()}
    assert f["p1"] + f["p4"] == 10, "水源流出必须恰等于总量"
    assert f["p1"] == f["p2"] + f["p3"], "分流节点收支必须相等"
    assert f["p2"] + f["p4"] == 6 and f["p3"] == 4, "分区流入必须恰等于需求"
    for p in data["pipes"]:
        assert p["minimum"] <= p["flow"] <= p["maximum"], f"{p['id']} 超出范围"
        assert isinstance(p["flow"], int), "流量必须为整数"
        assert p["deviation"] == abs(p["flow"] - p["preferred"])
    assert data["objective"] == 0, "优选量本身可行时偏差和应为 0"
    assert all(n["balanced"] for n in data["nodes"]), "节点收支应全部平衡"
    print(f"[smoke] 可行案例 ok，流量序列 = {[p['flow'] for p in data['pipes']]}")

    status, data = call("POST", "/api/balance", INFEASIBLE)
    assert status == 200 and data["feasible"] is False, "缺水案例必须不可行"
    assert "缺水" in data["reason"], f"应诊断下游缺水: {data['reason']}"
    print(f"[smoke] 不可行案例 ok：{data['reason']}")

    status, _ = call("POST", "/api/balance",
                     {"nodes": [], "pipes": [], "source_total": 0})
    assert status == 422, f"非法录入应 422，实际 {status}"
    print("[smoke] 非法录入 422 ok")

    print("SMOKE_OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"SMOKE_FAIL: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"SMOKE_ERROR: {e!r}", file=sys.stderr)
        sys.exit(2)
