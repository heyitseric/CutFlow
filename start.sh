#!/bin/bash
# ═══════════════════════════════════════
#  A-Roll 粗剪工具 — 一键启动
# ═══════════════════════════════════════

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Colors
AMBER='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

echo ""
echo -e "${AMBER}◉  A-Roll 粗剪工具${NC}"
echo -e "${DIM}───────────────────────────${NC}"

# Check .env
if [ ! -f .env ] || ! grep -q 'ARK_API_KEY=.' .env 2>/dev/null; then
  echo -e "${RED}✗ 未检测到 API Key，请先编辑 .env 文件${NC}"
  exit 1
fi

# Check backend venv
if [ ! -d backend/.venv ]; then
  echo -e "${AMBER}→ 首次运行，正在创建 Python 环境...${NC}"
  python3 -m venv backend/.venv
  source backend/.venv/bin/activate
  pip install -r backend/requirements.txt -q
  pip install whisperx -q
else
  source backend/.venv/bin/activate
fi

# Check frontend node_modules
if [ ! -d frontend/node_modules ]; then
  echo -e "${AMBER}→ 首次运行，正在安装前端依赖...${NC}"
  cd frontend && npm install --silent && cd ..
fi

# Kill any existing instances on our ports
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null

# Start backend
echo -e "${DIM}→ 启动后端 (port 8000)...${NC}"
cd "$DIR/backend"
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level warning &
BACKEND_PID=$!

# Start frontend
echo -e "${DIM}→ 启动前端 (port 5173)...${NC}"
cd "$DIR/frontend"
npm run dev -- --host 0.0.0.0 2>/dev/null &
FRONTEND_PID=$!

# Wait for backend to be ready
for i in $(seq 1 15); do
  if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Check if both started
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
  echo ""
  echo -e "${GREEN}✓ 启动成功！${NC}"
  echo ""
  echo -e "  打开浏览器访问: ${AMBER}http://localhost:5173${NC}"
  echo ""
  echo -e "${DIM}  按 Ctrl+C 停止所有服务${NC}"
  echo ""
else
  echo -e "${RED}✗ 后端启动失败，请检查日志${NC}"
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  exit 1
fi

# Cleanup on exit
cleanup() {
  echo ""
  echo -e "${DIM}→ 正在停止服务...${NC}"
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
  echo -e "${GREEN}✓ 已停止${NC}"
}
trap cleanup EXIT INT TERM

# Auto-open browser
if command -v open &>/dev/null; then
  sleep 2
  open "http://localhost:5173"
fi

# Keep running
wait
