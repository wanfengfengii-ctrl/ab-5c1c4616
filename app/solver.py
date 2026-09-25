"""整数流量配平求解器。

约束：
* 水源流出恰等于总量；
* 每个分流节点流入 = 流出；
* 各分区流入恰等于需求；
* 每条管路流量为 [minimum, maximum] 内的整数。

目标：先最小化各管路相对优选量的绝对偏差和；
再在全部最优方案中，按管路录入顺序做字典序最小的稳定决胜。
"""
from __future__ import annotations

import warnings

import pulp

from .models import BalanceRequest, NodeBalance, PipeResult, BalanceResponse


def _solver() -> pulp.LpSolver:
    """优先使用系统 CBC，其次 PuLP 自带 CBC。"""
    candidates = ("COIN_CMD", "PULP_CBC_CMD")
    for name in candidates:
        cls = getattr(pulp, name, None)
        if cls is None:
            continue
        try:
            s = cls(msg=0)
            if s.available():
                return s
        except Exception:
            continue
    raise RuntimeError("未找到可用的 CBC 整数求解器")


def _node_report(req: BalanceRequest, flows: dict[str, int]) -> list[NodeBalance]:
    inflow: dict[str, int] = {n.id: 0 for n in req.nodes}
    outflow: dict[str, int] = {n.id: 0 for n in req.nodes}
    for p in req.pipes:
        outflow[p.source] += flows[p.id]
        inflow[p.target] += flows[p.id]

    report: list[NodeBalance] = []
    for n in req.nodes:
        expected: int | None
        if n.type == "source":
            expected = req.source_total
            balanced = outflow[n.id] == expected and inflow[n.id] == 0
        elif n.type == "zone":
            expected = n.demand
            balanced = inflow[n.id] == expected and outflow[n.id] == 0
        else:
            expected = None
            balanced = inflow[n.id] == outflow[n.id]
        report.append(
            NodeBalance(
                id=n.id,
                type=n.type,
                label=n.label,
                inflow=inflow[n.id],
                outflow=outflow[n.id],
                expected=expected,
                balanced=balanced,
            )
        )
    return report


def _diagnose(req: BalanceRequest) -> str:
    """不可行时给出尽量贴近业务的诊断。"""
    notes: list[str] = []
    total_demand = sum(n.demand or 0 for n in req.nodes if n.type == "zone")
    if total_demand != req.source_total:
        notes.append(
            f"水源总量 {req.source_total} 与分区需求合计 {total_demand} 不相等，"
            "而分流节点不允许截留水量"
        )

    # 容量类诊断：用区间极值做必要条件检查。
    # 每个分区可由入边最大量送达的上限
    zone_in_max: dict[str, int] = {}
    zone_in_min: dict[str, int] = {}
    for n in req.nodes:
        if n.type == "zone":
            zone_in_max[n.id] = sum(
                p.maximum for p in req.pipes if p.target == n.id
            )
            zone_in_min[n.id] = sum(
                p.minimum for p in req.pipes if p.target == n.id
            )
            d = n.demand or 0
            if zone_in_max[n.id] < d:
                notes.append(
                    f"分区 {n.id} 入边最大输水能力 {zone_in_max[n.id]} 小于需求 {d}，"
                    "该分区必然缺水"
                )
            if zone_in_min[n.id] > d:
                notes.append(
                    f"分区 {n.id} 入边最小输水合计 {zone_in_min[n.id]} 已超过需求 {d}"
                )

    source = next(n for n in req.nodes if n.type == "source")
    src_out_max = sum(p.maximum for p in req.pipes if p.source == source.id)
    src_out_min = sum(p.minimum for p in req.pipes if p.source == source.id)
    if src_out_max < req.source_total:
        notes.append(
            f"水源出边最大输水能力 {src_out_max} 小于总量 {req.source_total}"
        )
    if src_out_min > req.source_total:
        notes.append(
            f"水源出边最小输水合计 {src_out_min} 已超过总量 {req.source_total}"
        )

    if not notes:
        notes.append(
            "管路容量与拓扑无法同时满足全部守恒约束"
            "（可能存在孤立分区、环流锁死或分流点容量受限）"
        )
    return "；".join(notes)


def solve(req: BalanceRequest) -> BalanceResponse:
    prob = pulp.LpProblem("mist_pipe_balance", pulp.LpMinimize)
    solver = _solver()

    flows = {
        p.id: pulp.LpVariable(f"f_{i}", lowBound=p.minimum, upBound=p.maximum,
                              cat="Integer")
        for i, p in enumerate(req.pipes)
    }
    devs = {
        p.id: pulp.LpVariable(f"d_{i}", lowBound=0, cat="Integer")
        for i, p in enumerate(req.pipes)
    }
    for p in req.pipes:
        f = flows[p.id]
        prob += f - p.preferred <= devs[p.id]
        prob += p.preferred - f <= devs[p.id]

    source = next(n for n in req.nodes if n.type == "source")

    # 水源流出恰等于总量，且不允许有管路流入水源。
    prob += (
        pulp.lpSum(flows[p.id] for p in req.pipes if p.source == source.id)
        == req.source_total
    )
    prob += (
        pulp.lpSum(flows[p.id] for p in req.pipes if p.target == source.id) == 0
    )

    for n in req.nodes:
        if n.type == "zone":
            prob += (
                pulp.lpSum(flows[p.id] for p in req.pipes if p.target == n.id)
                == (n.demand or 0)
            )
            prob += (
                pulp.lpSum(flows[p.id] for p in req.pipes if p.source == n.id) == 0
            )
        elif n.type == "junction":
            prob += (
                pulp.lpSum(flows[p.id] for p in req.pipes if p.target == n.id)
                - pulp.lpSum(flows[p.id] for p in req.pipes if p.source == n.id)
                == 0
            )

    objective = pulp.lpSum(devs[p.id] for p in req.pipes)
    prob.objective = objective

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        status = prob.solve(solver)
    if pulp.LpStatus[status] != "Optimal":
        return BalanceResponse(feasible=False, reason=_diagnose(req))

    best_obj = int(round(pulp.value(objective)))

    # 稳定决胜：固定最优偏差和，按录入顺序逐管最小化。
    prob += objective <= best_obj
    ordered = list(req.pipes)
    final: dict[str, int] = {}
    for p in ordered:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            prob += flows[p.id]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            status2 = prob.solve(solver)
        if pulp.LpStatus[status2] != "Optimal":
            # 理论上不会发生：上一最优解仍可行。
            return BalanceResponse(feasible=False, reason="决胜阶段求解异常")
        v = int(round(pulp.value(flows[p.id])))
        final[p.id] = v
        prob += flows[p.id] == v

    pipe_results = [
        PipeResult(
            id=p.id,
            source=p.source,
            target=p.target,
            flow=final[p.id],
            minimum=p.minimum,
            maximum=p.maximum,
            preferred=p.preferred,
            deviation=abs(final[p.id] - p.preferred),
        )
        for p in ordered
    ]
    return BalanceResponse(
        feasible=True,
        objective=sum(r.deviation for r in pipe_results),
        pipes=pipe_results,
        nodes=_node_report(req, final),
    )
