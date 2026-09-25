"use strict";

// ---------- 状态 ----------
const state = {
  zones: [
    { id: "A", label: "分区甲", demand: 6 },
    { id: "B", label: "分区乙", demand: 4 },
  ],
  junctions: [{ id: "J", label: "分流点" }],
  pipes: [
    { id: "p1", from: "S", to: "J", min: 0, max: 10, pref: 10 },
    { id: "p2", from: "J", to: "A", min: 0, max: 10, pref: 6 },
    { id: "p3", from: "J", to: "B", min: 0, max: 10, pref: 4 },
    { id: "p4", from: "S", to: "A", min: 0, max: 10, pref: 0 },
  ],
};

const $ = (sel) => document.querySelector(sel);

// ---------- 录入区渲染 ----------
function nodeOptions(excludeZone = false) {
  const opts = [`<option value="${$("#sourceId").value || "S"}">${$("#sourceId").value || "S"}（水源）</option>`];
  if (!excludeZone) {
    for (const z of state.zones) opts.push(`<option value="${z.id}">${z.id}（分区）</option>`);
  }
  for (const j of state.junctions) opts.push(`<option value="${j.id}">${j.id}（分流）</option>`);
  return opts.join("");
}

function renderZones() {
  $("#zoneBody").innerHTML = state.zones
    .map(
      (z, i) => `
    <tr>
      <td><input data-k="id" data-i="${i}" value="${z.id}" /></td>
      <td><input data-k="label" data-i="${i}" value="${z.label}" /></td>
      <td><input type="number" min="0" step="1" data-k="demand" data-i="${i}" value="${z.demand}" /></td>
      <td><button type="button" class="del" data-act="delZone" data-i="${i}">删除</button></td>
    </tr>`
    )
    .join("");
}

function renderJunctions() {
  $("#junctionBody").innerHTML = state.junctions
    .map(
      (j, i) => `
    <tr>
      <td><input data-k="id" data-j="${i}" value="${j.id}" /></td>
      <td><input data-k="label" data-j="${i}" value="${j.label}" /></td>
      <td><button type="button" class="del" data-act="delJunction" data-i="${i}">删除</button></td>
    </tr>`
    )
    .join("");
}

function renderPipes() {
  $("#pipeBody").innerHTML = state.pipes
    .map((p, i) => {
      const sel = (val, zoneOnly) =>
        nodeOptions(zoneOnly)
          .replace(`<option value="${val}"`, `<option value="${val}" selected`);
      return `
    <tr>
      <td>${i + 1}</td>
      <td><input data-k="id" data-p="${i}" value="${p.id}" /></td>
      <td><select data-k="from" data-p="${i}">${sel(p.from, false)}</select></td>
      <td class="arrow">→</td>
      <td><select data-k="to" data-p="${i}">${sel(p.to, false)}</select></td>
      <td><input type="number" min="0" step="1" data-k="min" data-p="${i}" value="${p.min}" /></td>
      <td><input type="number" min="0" step="1" data-k="max" data-p="${i}" value="${p.max}" /></td>
      <td><input type="number" min="0" step="1" data-k="pref" data-p="${i}" value="${p.pref}" /></td>
      <td><button type="button" class="del" data-act="delPipe" data-i="${i}">删除</button></td>
    </tr>`;
    })
    .join("");
}

function renderAll() {
  renderZones();
  renderJunctions();
  renderPipes();
}

// ---------- 编辑事件 ----------
function bindGridEdits() {
  document.addEventListener("input", (e) => {
    const t = e.target;
    const intKeys = new Set(["demand", "min", "max", "pref"]);
    const read = intKeys.has(t.dataset.k) ? parseInt(t.value || "0", 10) : t.value;
    if (t.dataset.p !== undefined) state.pipes[+t.dataset.p][t.dataset.k] = read;
    else if (t.dataset.j !== undefined) state.junctions[+t.dataset.j][t.dataset.k] = read;
    else if (t.dataset.i !== undefined && t.closest("#zoneBody"))
      state.zones[+t.dataset.i][t.dataset.k] = read;
  });

  // 节点编号或方向变化后需要重建下拉框
  document.addEventListener("change", (e) => {
    const t = e.target;
    if (t.tagName === "SELECT" && t.dataset.p !== undefined) {
      state.pipes[+t.dataset.p][t.dataset.k] = t.value;
    }
    if (t.dataset.k === "id" || t.tagName === "SELECT" || t.id === "sourceId") {
      renderPipes();
    }
  });

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const i = +btn.dataset.i;
    if (btn.dataset.act === "delZone") state.zones.splice(i, 1);
    if (btn.dataset.act === "delJunction") state.junctions.splice(i, 1);
    if (btn.dataset.act === "delPipe") state.pipes.splice(i, 1);
    renderAll();
  });
}

$("#addZone").addEventListener("click", () => {
  if (state.zones.length >= 4) return alert("分区最多 4 个");
  state.zones.push({ id: `Z${state.zones.length + 1}`, label: "", demand: 0 });
  renderAll();
});
$("#addJunction").addEventListener("click", () => {
  if (state.junctions.length >= 4) return alert("分流节点最多 4 个");
  state.junctions.push({ id: `J${state.junctions.length + 1}`, label: "" });
  renderAll();
});
$("#addPipe").addEventListener("click", () => {
  if (state.pipes.length >= 10) return alert("管路最多 10 条");
  state.pipes.push({
    id: `p${state.pipes.length + 1}`,
    from: $("#sourceId").value || "S",
    to: state.zones[0]?.id || "",
    min: 0,
    max: 10,
    pref: 0,
  });
  renderAll();
});

// ---------- 组装请求 ----------
function buildPayload() {
  const sourceId = $("#sourceId").value.trim();
  const sourceTotal = parseInt($("#sourceTotal").value, 10);
  const nodes = [
    { id: sourceId, type: "source", label: "水源" },
    ...state.zones.map((z) => ({ id: z.id.trim(), type: "zone", label: z.label, demand: z.demand })),
    ...state.junctions.map((j) => ({ id: j.id.trim(), type: "junction", label: j.label })),
  ];
  // 端点从当前 DOM 下拉框读取，保证节点改名后的选择不陈旧。
  const pipes = [...document.querySelectorAll("#pipeBody tr")].map((tr, i) => {
    const p = state.pipes[i];
    return {
      id: tr.querySelector('[data-k="id"]').value.trim(),
      from: tr.querySelector('[data-k="from"]').value,
      to: tr.querySelector('[data-k="to"]').value,
      minimum: p.min,
      maximum: p.max,
      preferred: p.pref,
    };
  });
  return { source_total: sourceTotal, nodes, pipes };
}

function clientCheck(p) {
  if (!p.nodes[0].id) return "请填写水源编号";
  if (!Number.isInteger(p.source_total) || p.source_total < 0) return "水源总量须为非负整数";
  if (p.nodes.filter((n) => n.type === "zone").some((z) => !z.id)) return "请补全分区编号";
  if (p.nodes.some((n, i) => p.nodes.findIndex((m) => m.id === n.id) !== i))
    return "节点编号存在重复";
  if (p.pipes.some((x) => !x.id)) return "请补全管路编号";
  const ids = new Set(p.nodes.map((n) => n.id));
  if (p.pipes.some((x) => !ids.has(x.from) || !ids.has(x.to))) return "存在管路端点未填写或不存在";
  if (p.pipes.some((x) => x.from === x.to)) return "存在管路自连";
  if (p.pipes.some((x) => x.minimum > x.maximum)) return "存在管路最小量大于最大量";
  if (p.pipes.some((x) => x.preferred < x.minimum || x.preferred > x.maximum))
    return "存在管路优选量超出最小/最大范围";
  return null;
}

// ---------- 结果展示 ----------
const TYPE_LABEL = { source: "水源", zone: "分区", junction: "分流节点" };

function renderResult(data) {
  $("#result").classList.remove("hidden");
  const sum = $("#summary");
  if (data.feasible) {
    sum.innerHTML = `<span class="verdict feasible">可行</span>
      最小绝对偏差和：<strong>${data.objective}</strong>`;
  } else {
    sum.innerHTML = `<span class="verdict infeasible">不可行</span>
      <span class="reason">${escapeHtml(data.reason || "无可行配平方案")}</span>`;
  }

  $("#pipeResultBody").innerHTML = data.pipes
    .map(
      (p, i) => `
    <tr>
      <td>${i + 1}</td>
      <td>${escapeHtml(p.id)}</td>
      <td>${escapeHtml(p.source)} → ${escapeHtml(p.target)}</td>
      <td><strong>${p.flow}</strong></td>
      <td>${p.minimum} ~ ${p.maximum}</td>
      <td>${p.preferred}</td>
      <td>${p.deviation}</td>
    </tr>`
    )
    .join("");

  $("#nodeResultBody").innerHTML = data.nodes
    .map(
      (n) => `
    <tr>
      <td>${escapeHtml(n.id)}${n.label ? "（" + escapeHtml(n.label) + "）" : ""}</td>
      <td><span class="tag ${n.type}">${TYPE_LABEL[n.type]}</span></td>
      <td>${n.inflow}</td>
      <td>${n.outflow}</td>
      <td>${n.expected === null ? "—" : n.expected}</td>
      <td class="${n.balanced ? "ok" : "bad"}">${n.balanced ? "平衡" : "失衡"}</td>
    </tr>`
    )
    .join("");

  if (!data.feasible) {
    $("#pipeResultBody").innerHTML = `<tr><td colspan="7" class="bad">不存在满足全部约束的整数流量，故无逐管结果。</td></tr>`;
    $("#nodeResultBody").innerHTML = `<tr><td colspan="6" class="bad">无可行方案，节点收支无法结清。</td></tr>`;
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- 发起配平 ----------
$("#balanceBtn").addEventListener("click", async () => {
  $("#formError").textContent = "";
  const payload = buildPayload();
  const err = clientCheck(payload);
  if (err) {
    $("#formError").textContent = err;
    return;
  }
  $("#balanceBtn").disabled = true;
  try {
    const r = await fetch("/api/balance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (r.status === 422) {
      const detail = (await r.json()).detail;
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg).join("；")
        : String(detail);
      $("#formError").textContent = "录入校验未通过：" + msg;
      $("#result").classList.add("hidden");
      return;
    }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    renderResult(await r.json());
  } catch (e) {
    $("#formError").textContent = "请求失败：" + e.message;
  } finally {
    $("#balanceBtn").disabled = false;
  }
});

$("#loadDemo").addEventListener("click", () => {
  Object.assign(state, {
    zones: [
      { id: "A", label: "分区甲", demand: 6 },
      { id: "B", label: "分区乙", demand: 4 },
    ],
    junctions: [{ id: "J", label: "分流点" }],
    pipes: [
      { id: "p1", from: "S", to: "J", min: 0, max: 10, pref: 10 },
      { id: "p2", from: "J", to: "A", min: 0, max: 10, pref: 6 },
      { id: "p3", from: "J", to: "B", min: 0, max: 10, pref: 4 },
      { id: "p4", from: "S", to: "A", min: 0, max: 10, pref: 0 },
    ],
  });
  $("#sourceId").value = "S";
  $("#sourceTotal").value = "10";
  $("#result").classList.add("hidden");
  renderAll();
});

bindGridEdits();
renderAll();
