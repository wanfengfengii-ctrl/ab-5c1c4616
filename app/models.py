"""雾化管路配平的请求/响应数据模型。"""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field, model_validator

NodeType = Literal["source", "zone", "junction"]


class Node(BaseModel):
    id: str = Field(..., min_length=1, description="节点编号")
    type: NodeType
    label: str = Field("", description="显示名称")
    demand: int | None = Field(None, ge=0, description="分区精确需求量")


class Pipe(BaseModel):
    id: str = Field(..., min_length=1, description="管路编号")
    source: str = Field(..., alias="from", description="起点节点编号")
    target: str = Field(..., alias="to", description="终点节点编号")
    minimum: int = Field(..., ge=0)
    maximum: int = Field(..., ge=0)
    preferred: int = Field(..., ge=0)
    label: str = ""

    model_config = {"populate_by_name": True}


class BalanceRequest(BaseModel):
    nodes: List[Node]
    pipes: List[Pipe]
    # 水源总量；不传时以水源出边最大量之和作为上界参考
    source_total: int = Field(..., ge=0)

    @model_validator(mode="after")
    def _validate(self) -> "BalanceRequest":
        errs: list[str] = []

        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            errs.append("节点编号存在重复")
        id_set = set(ids)

        by_type: dict[str, list[Node]] = {"source": [], "zone": [], "junction": []}
        for n in self.nodes:
            by_type[n.type].append(n)
        if len(by_type["source"]) != 1:
            errs.append("必须恰有一处水源")
        if not 2 <= len(by_type["zone"]) <= 4:
            errs.append("分区数量必须在 2 至 4 个之间")
        for z in by_type["zone"]:
            if z.demand is None:
                errs.append(f"分区 {z.id} 缺少精确需求量")
        if not 0 <= len(by_type["junction"]) <= 4:
            errs.append("分流节点数量必须在 0 至 4 个之间")

        if not 4 <= len(self.pipes) <= 10:
            errs.append("管路数量必须在 4 至 10 条之间")

        pipe_ids = [p.id for p in self.pipes]
        if len(pipe_ids) != len(set(pipe_ids)):
            errs.append("管路编号存在重复")

        type_of = {n.id: n.type for n in self.nodes}
        for i, p in enumerate(self.pipes):
            if p.source not in id_set:
                errs.append(f"管路 {p.id} 的起点 {p.source} 不存在")
            if p.target not in id_set:
                errs.append(f"管路 {p.id} 的终点 {p.target} 不存在")
            if p.source == p.target:
                errs.append(f"管路 {p.id} 不能自连")
            if p.source in id_set and type_of[p.source] == "zone":
                errs.append(f"管路 {p.id} 不能从分区 {p.source} 引出（分区为末端）")
            if p.target in id_set and type_of[p.target] == "source":
                errs.append(f"管路 {p.id} 不能汇入水源 {p.target}")
            if p.minimum > p.maximum:
                errs.append(f"管路 {p.id} 的最小量大于最大量")
            if not p.minimum <= p.preferred <= p.maximum:
                errs.append(f"管路 {p.id} 的优选量必须落在最小量与最大量之间")

        if errs:
            raise ValueError("；".join(errs))
        return self


class PipeResult(BaseModel):
    id: str
    source: str
    target: str
    flow: int
    minimum: int
    maximum: int
    preferred: int
    deviation: int


class NodeBalance(BaseModel):
    id: str
    type: NodeType
    label: str
    inflow: int
    outflow: int
    expected: int | None = None
    """水源为总量、分区为需求；分流节点无期望值。"""
    balanced: bool


class BalanceResponse(BaseModel):
    feasible: bool
    objective: int | None = None
    pipes: List[PipeResult] = []
    nodes: List[NodeBalance] = []
    reason: str | None = None
    """不可行时的诊断信息（尽可能指出缺水分区或过量水源）。"""
