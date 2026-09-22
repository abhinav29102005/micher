#!/usr/bin/env bash
# ── Micher Installer for Linux ───────────────────────────────────────────── #
# Install: curl -sSL https://micher.pages.dev/install.sh | bash
# ─────────────────────────────────────────────────────────────────────────── #

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${CYAN}${BOLD}⚡ Micher Installer${NC}"
echo -e "${DIM}Multi-link network bonding${NC}"
echo ""

# ── Check Python ──
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✖ Python 3 is required but not found.${NC}"
    echo -e "${DIM}Install it with:${NC}"
    echo "  sudo apt install python3 python3-pip    # Debian/Ubuntu"
    echo "  sudo dnf install python3 python3-pip    # Fedora"
    echo "  sudo pacman -S python python-pip        # Arch"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "  ${GREEN}✓${NC} Python ${PY_VERSION} found"

# ── Check pip ──
if ! python3 -m pip --version &>/dev/null; then
    echo -e "${YELLOW}⚠ pip not found. Installing...${NC}"
    python3 -m ensurepip --upgrade 2>/dev/null || {
        echo -e "${RED}✖ Could not install pip. Install manually:${NC}"
        echo "  sudo apt install python3-pip"
        exit 1
    }
fi
echo -e "  ${GREEN}✓${NC} pip available"

# ── Check tkinter ──
if python3 -c "import tkinter" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} tkinter available"
    HAS_TK=1
else
    echo -e "  ${YELLOW}⚠${NC} tkinter not found (GUI will not work, CLI will)"
    echo -e "  ${DIM}Install with: sudo apt install python3-tk${NC}"
    HAS_TK=0
fi

# ── Install micher ──
echo ""
echo -e "${CYAN}Installing micher...${NC}"

pip install --user --upgrade "micher[gui]" 2>/dev/null || \
pip install --user --upgrade git+https://github.com/abhinav29102005/micher.git#egg=micher[gui] 2>/dev/null || {
    # Fallback: install from current directory if run locally
    echo -e "${YELLOW}PyPI/GitHub install failed. Trying local install...${NC}"
    if [ -f "pyproject.toml" ]; then
        pip install --user -e ".[gui]"
    else
        echo -e "${RED}✖ Installation failed. Clone the repo and run:${NC}"
        echo "  git clone https://github.com/abhinav29102005/micher.git"
        echo "  cd micher && pip install -e '.[gui]'"
        exit 1
    fi
}

echo -e "  ${GREEN}✓${NC} micher installed"

# ── Ensure ~/.local/bin is on PATH ──
LOCAL_BIN="$HOME/.local/bin"
if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
    echo -e "  ${YELLOW}⚠${NC} Adding $LOCAL_BIN to PATH"
    echo "" >> ~/.bashrc
    echo '# Micher' >> ~/.bashrc
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    export PATH="$LOCAL_BIN:$PATH"
fi

# ── Desktop entry ──
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_DIR/micher.desktop" << DESKTOP_EOF
[Desktop Entry]
Version=1.1
Type=Application
Name=Micher
GenericName=Network Bonding
Comment=Combine multiple network interfaces for maximum transfer speed
Exec=micher-gui
Icon=micher
Terminal=false
Categories=Network;Utility;
Keywords=network;bonding;transfer;speed;wifi;ethernet;
StartupWMClass=micher
StartupNotify=true
DESKTOP_EOF

echo -e "  ${GREEN}✓${NC} Desktop entry installed"

# ── Icon (create a simple one if we don't have the real one) ──
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$ICON_DIR"
# The icon will be included in the pip package, but if not available yet:
python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (256, 256), (13, 17, 23, 255))
draw = ImageDraw.Draw(img)
draw.polygon([(60,80),(180,128),(60,176)], fill=(0,212,255,255))
draw.rectangle([(170,100),(220,156)], fill=(0,212,255,255))
img.save('$ICON_DIR/micher.png')
" 2>/dev/null && echo -e "  ${GREEN}✓${NC} Icon installed" || true

# ── Done ──
echo ""
echo -e "${GREEN}${BOLD}✅ Micher installed successfully!${NC}"
echo ""
echo -e "  ${BOLD}CLI:${NC}  micher interfaces"
echo -e "        micher send <host> <file>"
echo -e "        micher receive"
echo ""
echo -e "  ${BOLD}GUI:${NC}  micher-gui   ${DIM}(or find 'Micher' in your app launcher)${NC}"
echo ""
echo -e "  ${BOLD}Docker server:${NC}"
echo -e "        docker run -p 9191:9191 micher-server"
echo ""
echo -e "${DIM}You may need to restart your shell or log out/in for PATH changes.${NC}"
echo ""
