# 纸本修复室 · 雾化管路配平

回湿脆化古画前，用本系统审核雾化管路能否把**规定水量稳定送到每个分区**：
不会因为只看某条支路的余量而让下游分区缺水，也不会在分流点凭空增减流量。

修复师在网页录入：

- 一处水源及水源总量；
- 2–4 个分区及各自的**精确需求量**；
- 0–4 个分流节点；
- 4–10 条**按方向连接**的管路，每条给整数最小量、最大量、优选量。

修改草稿后发起配平，系统经业务 API 联合求出各管路的**整数**流量。

## 业务规则

一条方案必须同时满足：

1. **水源流出恰等于总量**；
2. 每个**分流节点流入 = 流出**（不截留、不凭空增减）；
3. 每个**分区流入恰等于需求**（分区为末端，不允许出流）；
4. 每条管路流量都是 `[最小量, 最大量]` 内的整数。

在全部可行方案中：

- 先取**相对优选量的绝对偏差和最小**的方案；
- 若仍有并列，按**管路录入顺序的流量序列**做字典序最小的稳定决胜，
  因此同一草稿反复配平结果完全一致，调换录入顺序会相应改变决胜结果。

页面展示：

- 逐管流量（含范围、优选量、偏差）；
- 每个节点的流入 / 流出 / 期望值 / 是否平衡；
- 不可行时给出明确结论与诊断（如下游分区入边能力不足必然缺水、
  水源总量与分区需求合计不符等）。

## 技术栈

- API：FastAPI + Pydantic + PuLP（CBC 整数规划）；
- Web：纯静态页面 + nginx 反向代理 `/api/` 与 `/health`；
- 测试：pytest；
- 容器：Dockerfile + Docker Compose（`api` / `web` / `verify` 三个服务）。

## 快速开始

```bash
# 可选：复制并修改宿主机端口
cp .env.example .env   # WEB_PORT 默认 8080，API_PORT 默认 8000

docker compose up -d --build
```

- 页面：http://localhost:${WEB_PORT:-8080}
- API 健康检查：http://localhost:${API_PORT:-8000}/health
- Web 健康检查（nginx → API 全链路）：http://localhost:${WEB_PORT:-8080}/health

端口均可通过环境变量 / `.env` 配置：`WEB_PORT`、`API_PORT`。

## 一键验收（verify 一次性服务）

```bash
docker compose run --rm verify
# 或
sh scripts/verify.sh
```

`verify` 是**一次性**服务：等待 `api` 健康后，在镜像内完成

1. `pytest` 全部代码测试；
2. 针对**已启动 API** 的业务冒烟（健康检查、可行案例守恒校验、
   下游缺水不可行诊断、非法录入 422）；

随后自行退出，**以退出码报告验收结果**：`0` 通过，非 `0` 失败。

## 本地开发（无 Docker 时）

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

PYTHONPATH=. python -m pytest tests -q
uvicorn app.main:app --host 127.0.0.1 --port 8000
# 另开终端：
BASE_URL=http://127.0.0.1:8000 python scripts/smoke.py
```

## 目录结构

```
app/
  main.py            # FastAPI：/health、/api/balance、静态页面
  models.py          # 请求/响应模型与录入校验
  solver.py          # 整数规划建模、偏差目标、录入顺序决胜、不可行诊断
  static/            # 前端页面（index.html / app.js / style.css）
tests/               # pytest 测试
scripts/
  smoke.py           # API 业务冒烟（退出码报告）
  verify.sh          # 一键构建 + verify 的便捷脚本
web/
  Dockerfile         # nginx Web 镜像
  nginx.conf         # 静态托管 + 反代 API
Dockerfile           # API 镜像（含健康检查）
docker-compose.yml   # api / web / verify
```
