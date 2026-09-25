"""求解器与 API 的测试。"""
from __future__ import annotations

import pytest

from app.models import BalanceRequest
from app.solver import solve


def _req(payload: dict) -> BalanceRequest:
    return BalanceRequest.model_validate(payload)


# 一处水源、一个分流节点、两个分区。
FEASIBLE = {
    "source_total": 10,
    "nodes": [
        {"id": "S", "type": "source", "label": "水源"},
        {"id": "J", "type": "junction", "label": "分流点"},
        {"id": "A", "type": "zone", "label": "分区甲", "demand": 6},
        {"id": "B", "type": "zone", "label": "分区乙", "demand": 4},
    ],
    "pipes": [
        {"id": "p1", "from": "S", "to": "J", "minimum": 0, "maximum": 10, "preferred": 10},
        {"id": "p2", "from": "J", "to": "A", "minimum": 0, "maximum": 10, "preferred": 6},
        {"id": "p3", "from": "J", "to": "B", "minimum": 0, "maximum": 10, "preferred": 4},
        {"id": "p4", "from": "S", "to": "A", "minimum": 0, "maximum": 10, "preferred": 0},
    ],
}


def test_feasible_balance_conservation():
    res = solve(_req(FEASIBLE))
    assert res.feasible, res.reason
    flows = {p.id: p.flow for p in res.pipes}
    # 水源总量守恒
    assert flows["p1"] + flows["p4"] == 10
    # 分流节点收支相等
    assert flows["p1"] == flows["p2"] + flows["p3"]
    # 分区精确需求
    assert flows["p2"] + flows["p4"] == 6
    assert flows["p3"] == 4
    for p in res.pipes:
        assert p.minimum <= p.flow <= p.maximum
        assert p.deviation == abs(p.flow - p.preferred)
    assert res.objective == sum(p.deviation for p in res.pipes)
    # 节点收支报告全部平衡
    assert all(n.balanced for n in res.nodes)
    node_map = {n.id: n for n in res.nodes}
    assert node_map["S"].outflow == 10
    assert node_map["A"].inflow == 6
    assert node_map["J"].inflow == node_map["J"].outflow


def test_preferred_objective_picks_zero_deviation():
    # 优选量本身即构成可行解时，偏差和必须为 0。
    res = solve(_req(FEASIBLE))
    assert res.objective == 0
    flows = {p.id: p.flow for p in res.pipes}
    assert flows == {"p1": 10, "p2": 6, "p3": 4, "p4": 0}


def test_deterministic_tie_break_by_entry_order():
    # 两条并联管同时给分区甲送水，优选量均为 0 而需求为 5：
    # 任意 (x, 5-x) 的偏差和都为 5，存在真实平局，
    # 决胜必须按录入顺序取字典序最小，且重复求解一致。
    payload = {
        "source_total": 10,
        "nodes": [
            {"id": "S", "type": "source"},
            {"id": "A", "type": "zone", "demand": 5},
            {"id": "B", "type": "zone", "demand": 5},
        ],
        "pipes": [
            {"id": "p1", "from": "S", "to": "A", "minimum": 0, "maximum": 5, "preferred": 0},
            {"id": "p2", "from": "S", "to": "A", "minimum": 0, "maximum": 5, "preferred": 0},
            {"id": "p3", "from": "S", "to": "B", "minimum": 0, "maximum": 5, "preferred": 5},
            {"id": "p4", "from": "S", "to": "B", "minimum": 0, "maximum": 5, "preferred": 0},
        ],
    }
    sequences = [tuple(p.flow for p in solve(_req(payload)).pipes) for _ in range(3)]
    assert sequences[0] == sequences[1] == sequences[2]
    # p1 录入在先，被压到区间最小 0，p2 承担 5。
    assert sequences[0] == (0, 5, 5, 0)
    assert solve(_req(payload)).objective == 5

    # 交换 p1/p2 的录入顺序后，决胜结果相应翻转。
    reordered = {**payload, "pipes": [payload["pipes"][1], payload["pipes"][0],
                                      payload["pipes"][2], payload["pipes"][3]]}
    seq2 = tuple(p.flow for p in solve(_req(reordered)).pipes)
    assert seq2 == (0, 5, 5, 0)  # 现在排第一的原 p2 取 0
    flow_by_id = {p.id: p.flow for p in solve(_req(reordered)).pipes}
    assert flow_by_id == {"p1": 5, "p2": 0, "p3": 5, "p4": 0}


def test_downstream_zone_starvation_is_infeasible():
    # 分区甲需求 9，但入边最大能力只有 4；另一条支路余量再大也救不了下游。
    payload = {
        "source_total": 10,
        "nodes": [
            {"id": "S", "type": "source"},
            {"id": "A", "type": "zone", "demand": 9},
            {"id": "B", "type": "zone", "demand": 1},
        ],
        "pipes": [
            {"id": "p1", "from": "S", "to": "A", "minimum": 0, "maximum": 4, "preferred": 4},
            {"id": "p2", "from": "S", "to": "B", "minimum": 0, "maximum": 10, "preferred": 6},
            {"id": "p3", "from": "S", "to": "A", "minimum": 0, "maximum": 0, "preferred": 0},
            {"id": "p4", "from": "S", "to": "B", "minimum": 0, "maximum": 10, "preferred": 0},
        ],
    }
    res = solve(_req(payload))
    assert not res.feasible
    assert "A" in (res.reason or "")
    assert "缺水" in (res.reason or "")


def test_source_total_mismatch_diagnosed():
    payload = {
        "source_total": 9,
        "nodes": [
            {"id": "S", "type": "source"},
            {"id": "A", "type": "zone", "demand": 6},
            {"id": "B", "type": "zone", "demand": 4},
        ],
        "pipes": [
            {"id": "p1", "from": "S", "to": "A", "minimum": 0, "maximum": 9, "preferred": 5},
            {"id": "p2", "from": "S", "to": "B", "minimum": 0, "maximum": 9, "preferred": 4},
            {"id": "p3", "from": "S", "to": "A", "minimum": 0, "maximum": 9, "preferred": 1},
            {"id": "p4", "from": "S", "to": "B", "minimum": 0, "maximum": 9, "preferred": 0},
        ],
    }
    res = solve(_req(payload))
    assert not res.feasible
    assert "总量" in res.reason


def test_integer_bounds_respected_with_minimums():
    payload = {
        "source_total": 10,
        "nodes": [
            {"id": "S", "type": "source"},
            {"id": "A", "type": "zone", "demand": 7},
            {"id": "B", "type": "zone", "demand": 3},
        ],
        "pipes": [
            {"id": "p1", "from": "S", "to": "A", "minimum": 2, "maximum": 8, "preferred": 6},
            {"id": "p2", "from": "S", "to": "A", "minimum": 1, "maximum": 8, "preferred": 1},
            {"id": "p3", "from": "S", "to": "B", "minimum": 3, "maximum": 3, "preferred": 3},
            {"id": "p4", "from": "S", "to": "B", "minimum": 0, "maximum": 0, "preferred": 0},
        ],
    }
    res = solve(_req(payload))
    assert res.feasible, res.reason
    flows = {p.id: p.flow for p in res.pipes}
    assert flows["p3"] == 3
    assert flows["p1"] + flows["p2"] == 7
    assert flows["p1"] >= 2 and flows["p2"] >= 1
    assert all(isinstance(p.flow, int) for p in res.pipes)


def test_full_scale_network():
    # 上限规模：4 分区 + 4 分流节点 + 10 条管路，全部优选量可行。
    payload = {
        "source_total": 10,
        "nodes": [
            {"id": "S", "type": "source"},
            {"id": "J1", "type": "junction"}, {"id": "J2", "type": "junction"},
            {"id": "J3", "type": "junction"}, {"id": "J4", "type": "junction"},
            {"id": "A", "type": "zone", "demand": 3},
            {"id": "B", "type": "zone", "demand": 2},
            {"id": "C", "type": "zone", "demand": 2},
            {"id": "D", "type": "zone", "demand": 3},
        ],
        "pipes": [
            {"id": "p1", "from": "S", "to": "A", "minimum": 0, "maximum": 10, "preferred": 3},
            {"id": "p2", "from": "S", "to": "B", "minimum": 0, "maximum": 10, "preferred": 2},
            {"id": "p3", "from": "S", "to": "C", "minimum": 0, "maximum": 10, "preferred": 2},
            {"id": "p4", "from": "S", "to": "D", "minimum": 0, "maximum": 10, "preferred": 3},
            {"id": "p5", "from": "S", "to": "J1", "minimum": 0, "maximum": 10, "preferred": 0},
            {"id": "p6", "from": "J1", "to": "J2", "minimum": 0, "maximum": 10, "preferred": 0},
            {"id": "p7", "from": "J2", "to": "J3", "minimum": 0, "maximum": 10, "preferred": 0},
            {"id": "p8", "from": "J3", "to": "J4", "minimum": 0, "maximum": 10, "preferred": 0},
            {"id": "p9", "from": "J4", "to": "A", "minimum": 0, "maximum": 10, "preferred": 0},
            {"id": "p10", "from": "J1", "to": "B", "minimum": 0, "maximum": 10, "preferred": 0},
        ],
    }
    res = solve(_req(payload))
    assert res.feasible, res.reason
    assert res.objective == 0
    assert [p.flow for p in res.pipes] == [3, 2, 2, 3, 0, 0, 0, 0, 0, 0]
    assert all(n.balanced for n in res.nodes)


def test_isolated_zone_is_infeasible():
    # 分区 C 没有任何入边：拓扑上必然缺水，其它支路再有余量也无法送达。
    payload = {
        "source_total": 10,
        "nodes": [
            {"id": "S", "type": "source"},
            {"id": "A", "type": "zone", "demand": 5},
            {"id": "B", "type": "zone", "demand": 3},
            {"id": "C", "type": "zone", "demand": 2},
        ],
        "pipes": [
            {"id": "p1", "from": "S", "to": "A", "minimum": 0, "maximum": 10, "preferred": 5},
            {"id": "p2", "from": "S", "to": "B", "minimum": 0, "maximum": 10, "preferred": 3},
            {"id": "p3", "from": "S", "to": "A", "minimum": 0, "maximum": 10, "preferred": 0},
            {"id": "p4", "from": "S", "to": "B", "minimum": 0, "maximum": 10, "preferred": 0},
        ],
    }
    res = solve(_req(payload))
    assert not res.feasible
    assert "C" in (res.reason or "") and "缺水" in (res.reason or "")


def test_validation_errors():
    from pydantic import ValidationError

    bad = dict(FEASIBLE)
    bad = {**bad, "nodes": [n for n in bad["nodes"] if n["type"] != "zone"]}
    with pytest.raises(ValidationError):
        _req(bad)

    bad2 = {
        **FEASIBLE,
        "pipes": [{**FEASIBLE["pipes"][0], "minimum": 8, "maximum": 3}],
    }
    with pytest.raises(ValidationError):
        _req(bad2)


def test_api_endpoint():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    r = client.post("/api/balance", json=FEASIBLE)
    assert r.status_code == 200
    data = r.json()
    assert data["feasible"] is True
    assert len(data["pipes"]) == 4
    assert all(n["balanced"] for n in data["nodes"])

    bad_input = {"nodes": [], "pipes": [], "source_total": 0}
    assert client.post("/api/balance", json=bad_input).status_code == 422
