#!/bin/bash
# ═══════════════════════════════════════
#  A-Roll 粗剪工具 — 卸载清理
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
echo -e "${AMBER}◉  A-Roll 粗剪工具 — 卸载${NC}"
echo -e "${DIM}───────────────────────────${NC}"
echo ""

# ── 1. 停止正在运行的服务 ──
if lsof -ti:8000 >/dev/null 2>&1 || lsof -ti:5173 >/dev/null 2>&1; then
  echo -e "${DIM}→ 正在停止运行中的服务...${NC}"
  lsof -ti:8000 | xargs kill -9 2>/dev/null
  lsof -ti:5173 | xargs kill -9 2>/dev/null
  echo -e "${GREEN}✓${NC} 服务已停止"
fi

# ── 2. 清理依赖和缓存（无需确认） ──
cleaned=false

if [ -d backend/.venv ]; then
  echo -e "${DIM}→ 删除 Python 虚拟环境...${NC}"
  rm -rf backend/.venv
  cleaned=true
fi

if [ -d frontend/node_modules ]; then
  echo -e "${DIM}→ 删除前端依赖...${NC}"
  rm -rf frontend/node_modules
  cleaned=true
fi

if [ -d frontend/dist ]; then
  rm -rf frontend/dist
  cleaned=true
fi

# 清理缓存
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
rm -rf backend/data/.mpl_cache 2>/dev/null
rm -rf frontend/.vite 2>/dev/null
rm -rf .coverage htmlcov 2>/dev/null

if [ "$cleaned" = true ]; then
  echo -e "${GREEN}✓${NC} 依赖和缓存已清理"
else
  echo -e "${DIM}→ 没有需要清理的依赖${NC}"
fi

# ── 3. 用户数据（需确认） ──
has_user_data=false
[ -f .env ] && has_user_data=true
[ -d backend/data/uploads ] && [ "$(ls -A backend/data/uploads 2>/dev/null)" ] && has_user_data=true
[ -d backend/data/outputs ] && [ "$(ls -A backend/data/outputs 2>/dev/null)" ] && has_user_data=true
[ -f backend/data/jobs.json ] && has_user_data=true

if [ "$has_user_data" = true ]; then
  echo ""
  echo -e "${AMBER}是否同时删除用户数据？${NC}（包括 .env 密钥配置、上传的文件、导出的文件）"
  read -p "输入 y 删除，其他键跳过: " answer
  if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
    rm -f .env
    rm -rf backend/data/uploads
    rm -rf backend/data/outputs
    rm -f backend/data/jobs.json
    echo -e "${GREEN}✓${NC} 用户数据已清理"
  else
    echo -e "${DIM}→ 已跳过用户数据${NC}"
  fi
fi

# ── 完成 ──
echo ""
echo -e "${GREEN}✓ 卸载完成${NC}"
echo ""
echo -e "  项目源码仍保留在: ${DIM}$DIR${NC}"
echo -e "  如需彻底删除，把整个文件夹拖到废纸篓即可。"
echo ""
