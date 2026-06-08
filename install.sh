#!/usr/bin/env sh
# ═══════════════════════════════════════════════════════
#  UltraWater Client — macOS / Linux Installer
#  Usage:  curl -fsSL https://kithlicat98-hub.github.io/ultrawater/install.sh | sh
# ═══════════════════════════════════════════════════════
set -e

GH_USER="kithlicat98-hub"
GH_REPO="ultrawater"
BASE="https://github.com/${GH_USER}/${GH_REPO}/releases/latest/download"
INSTALL_DIR="${HOME}/.local/share/ultrawater"
BIN_DIR="${HOME}/.local/bin"

# ── Colours ──────────────────────────────────────────
if [ -t 1 ]; then
  C_CYAN='\033[0;36m' C_GRN='\033[0;32m' C_RED='\033[0;31m'
  C_YEL='\033[0;33m' C_RST='\033[0m' C_BOLD='\033[1m'
else
  C_CYAN='' C_GRN='' C_RED='' C_YEL='' C_RST='' C_BOLD=''
fi
info()  { printf "${C_CYAN}→  %s${C_RST}\n" "$1"; }
ok()    { printf "${C_GRN}✓  %s${C_RST}\n" "$1"; }
warn()  { printf "${C_YEL}⚠  %s${C_RST}\n" "$1"; }
die()   { printf "${C_RED}✗  %s${C_RST}\n" "$1"; exit 1; }

printf "\n${C_BOLD}${C_CYAN}"
printf "┌─────────────────────────────────────┐\n"
printf "│   UltraWater Client Installer       │\n"
printf "│   github.com/%s/%s\n" "$GH_USER" "$GH_REPO"
printf "└─────────────────────────────────────┘\n"
printf "${C_RST}\n"

# ── Detect OS + Arch ─────────────────────────────────
OS=$(uname -s)
ARCH=$(uname -m)

case "$OS" in
  Linux)
    case "$ARCH" in
      x86_64)         FILE="UltraWater-linux-x64.tar.gz" ;;
      aarch64|arm64)  FILE="UltraWater-linux-arm64.tar.gz" ;;
      *) die "Unsupported CPU architecture: $ARCH" ;;
    esac ;;
  Darwin)
    FILE="UltraWater-macos-arm64.tar.gz" ;;
  *)
    warn "Unsupported OS: $OS"
    printf "  Download manually: ${BASE}\n\n"; exit 1 ;;
esac

DOWNLOAD_URL="${BASE}/${FILE}"
info "Platform : $OS / $ARCH"
info "File     : $FILE"
info "Dest     : $INSTALL_DIR"
printf "\n"

# ── Check downloader ────────────────────────────────
if command -v curl >/dev/null 2>&1; then
  DOWNLOADER="curl -fsSL"
elif command -v wget >/dev/null 2>&1; then
  DOWNLOADER="wget -qO-"
else
  die "curl or wget is required but neither was found."
fi

# ── Download ────────────────────────────────────────
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

info "Downloading $FILE..."
if command -v curl >/dev/null 2>&1; then
  curl -fSL --progress-bar "$DOWNLOAD_URL" -o "$TMP/ultrawater.tar.gz" || die "Download failed. Check your internet connection."
else
  wget -q --show-progress "$DOWNLOAD_URL" -O "$TMP/ultrawater.tar.gz" || die "Download failed."
fi
ok "Download complete"

# ── Extract ─────────────────────────────────────────
info "Extracting..."
mkdir -p "$INSTALL_DIR"
tar -xzf "$TMP/ultrawater.tar.gz" -C "$INSTALL_DIR" --strip-components=1
chmod +x "$INSTALL_DIR/UltraWater" 2>/dev/null || true
ok "Extracted to $INSTALL_DIR"

# ── Symlink ─────────────────────────────────────────
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/UltraWater" "$BIN_DIR/ultrawater"
ok "Symlink: $BIN_DIR/ultrawater"

# ── Linux desktop entry ─────────────────────────────
if [ "$OS" = "Linux" ]; then
  APPS_DIR="${HOME}/.local/share/applications"
  mkdir -p "$APPS_DIR"
  cat > "$APPS_DIR/ultrawater.desktop" << DESKTOP
[Desktop Entry]
Name=UltraWater Client
GenericName=Minecraft Launcher
Comment=Ultralight Minecraft Launcher
Exec=${INSTALL_DIR}/UltraWater
Path=${INSTALL_DIR}
Terminal=false
Type=Application
Categories=Game;
StartupWMClass=UltraWater
DESKTOP
  ok "Desktop shortcut created"
fi

# ── PATH reminder ───────────────────────────────────
SHELL_RC="${HOME}/.bashrc"
case "${SHELL}" in
  */zsh)  SHELL_RC="${HOME}/.zshrc" ;;
  */fish) SHELL_RC="${HOME}/.config/fish/config.fish" ;;
esac

if ! echo "$PATH" | grep -q "$BIN_DIR"; then
  warn "$BIN_DIR is not in your PATH"
  printf "  Add this to %s:\n" "$SHELL_RC"
  printf "  ${C_CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${C_RST}\n\n"
fi

printf "\n${C_GRN}${C_BOLD}Installation complete!${C_RST}\n\n"
printf "  Run with:  ${C_CYAN}ultrawater${C_RST}\n"
printf "  Or open:   ${C_CYAN}%s/UltraWater${C_RST}\n\n" "$INSTALL_DIR"

# ── Optionally launch ────────────────────────────────
if [ -t 1 ]; then
  printf "Launch UltraWater now? [Y/n] "
  read -r ANSWER
  case "$ANSWER" in
    n|N) printf "  OK — run 'ultrawater' any time.\n\n" ;;
    *)
      info "Launching UltraWater..."
      nohup "$INSTALL_DIR/UltraWater" >/dev/null 2>&1 &
      ok "Running in background" ;;
  esac
else
  nohup "$INSTALL_DIR/UltraWater" >/dev/null 2>&1 &
fi
