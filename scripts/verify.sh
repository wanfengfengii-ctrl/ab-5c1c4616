#!/bin/sh
# 一次性验收入口：构建镜像 → 等待 API 健康 → 单元测试 + 业务冒烟 → 退出。
# verify 服务退出码即验收结果：0 通过，非 0 失败。
# 用法：sh scripts/verify.sh
set -e

cd "$(dirname "$0")/.."

if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "未找到 docker compose" >&2
  exit 127
fi

# 1) 构建全部镜像（api 与 web）；2) 启动一次性 verify 完成测试与业务冒烟。
$DC build
set +e
$DC run --rm verify
code=$?
set -e
$DC stop api >/dev/null 2>&1 || true
exit $code
