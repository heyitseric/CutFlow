#!/bin/bash
# ═══════════════════════════════════════
#  CutFlow — 一键环境安装
# ═══════════════════════════════════════

set -e

AMBER='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

echo ""
echo -e "${AMBER}◉  CutFlow 环境安装${NC}"
echo -e "${DIM}───────────────────────────${NC}"
echo ""

# ── 1. Homebrew ──
if command -v brew &>/dev/null; then
  echo -e "${GREEN}✓${NC} Homebrew 已安装"
else
  echo -e "${AMBER}→ 正在安装 Homebrew（Mac 软件管理工具）...${NC}"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  # Apple Silicon Mac 需要手动激活 Homebrew
  if [ -f /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
  fi
  echo -e "${GREEN}✓${NC} Homebrew 安装完成"
fi

# ── 2. Python ──
if command -v python3 &>/dev/null && python3 -c "import sys; assert sys.version_info >= (3, 10)" 2>/dev/null; then
  echo -e "${GREEN}✓${NC} Python 已安装 ($(python3 --version))"
else
  echo -e "${AMBER}→ 正在安装 Python...${NC}"
  brew install python@3.11
  echo -e "${GREEN}✓${NC} Python 安装完成"
fi

# ── 3. Node.js ──
if command -v node &>/dev/null; then
  echo -e "${GREEN}✓${NC} Node.js 已安装 ($(node --version))"
else
  echo -e "${AMBER}→ 正在安装 Node.js...${NC}"
  brew install node
  echo -e "${GREEN}✓${NC} Node.js 安装完成"
fi

# ── 4. FFmpeg ──
if command -v ffmpeg &>/dev/null; then
  echo -e "${GREEN}✓${NC} FFmpeg 已安装"
else
  echo -e "${AMBER}→ 正在安装 FFmpeg（音频处理工具）...${NC}"
  brew install ffmpeg
  echo -e "${GREEN}✓${NC} FFmpeg 安装完成"
fi

# ── 5. Git ──
if command -v git &>/dev/null; then
  echo -e "${GREEN}✓${NC} Git 已安装"
else
  echo -e "${AMBER}→ 正在安装 Git...${NC}"
  xcode-select --install 2>/dev/null || brew install git
  echo -e "${GREEN}✓${NC} Git 安装完成"
fi

echo ""
echo -e "${DIM}───────────────────────────${NC}"
echo -e "${AMBER}→ 正在安装项目依赖...${NC}"
echo ""

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# ── 6. Python 虚拟环境 + 后端依赖 ──
if [ ! -d backend/.venv ]; then
  echo -e "${DIM}  → 创建 Python 环境...${NC}"
  python3 -m venv backend/.venv
fi
source backend/.venv/bin/activate
echo -e "${DIM}  → 安装后端依赖（可能需要几分钟）...${NC}"
pip install -r backend/requirements.txt -q
pip install whisperx -q
echo -e "${GREEN}  ✓${NC} 后端依赖安装完成"

# ── 7. 前端依赖 ──
echo -e "${DIM}  → 安装前端依赖...${NC}"
cd "$DIR/frontend"
npm install --silent
echo -e "${GREEN}  ✓${NC} 前端依赖安装完成"

cd "$DIR"

# ── 8. 配置文件 ──
if [ ! -f .env ]; then
  cp .env.example .env
  echo -e "${AMBER}→ 已创建 .env 配置文件，请稍后在「设置」页面中填写 API 密钥${NC}"
else
  echo -e "${GREEN}✓${NC} .env 配置文件已存在"
fi

echo ""
echo -e "${DIM}═══════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}✓ 安装完成！${NC}"
echo ""
echo -e "  运行以下命令启动 CutFlow："
echo ""
echo -e "    ${AMBER}./start.sh${NC}"
echo ""
echo -e "${DIM}  首次启动后，请在网页「设置」页面中填写 API 密钥。${NC}"
echo ""
