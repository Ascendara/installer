#!/bin/bash
# Ascendara Installer Script Hosted at https://ascendara.app/install.sh
# This script installs Ascendara on Linux systems

set -e

# Colors and formatting
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'

# Symbols
CHECK="${GREEN}✓${RESET}"
ARROW="${CYAN}→${RESET}"
STAR="${YELLOW}★${RESET}"

# Variables
APP_NAME="Ascendara"
INSTALL_DIR="$HOME/.local/bin"
APPIMAGE_PATH="$INSTALL_DIR/$APP_NAME.AppImage"
DESKTOP_FILE="$HOME/.local/share/applications/ascendara.desktop"
ICON_PATH="$HOME/.local/share/icons/hicolor/256x256/apps/ascendara.png"

# Print functions
print_header() {
    echo -e "\n${BOLD}${CYAN}╔════════════════════════════════════════╗${RESET}"
    echo -e "${BOLD}${CYAN}║                                        ║${RESET}"
    echo -e "${BOLD}${CYAN}║         ${MAGENTA}ASCENDARA INSTALLER${CYAN}            ║${RESET}"
    echo -e "${BOLD}${CYAN}║                                        ║${RESET}"
    echo -e "${BOLD}${CYAN}╚════════════════════════════════════════╝${RESET}\n"
}

print_step() {
    echo -e "${ARROW} ${BOLD}$1${RESET}"
}

print_success() {
    echo -e "${CHECK} ${GREEN}$1${RESET}"
}

print_info() {
    echo -e "  ${DIM}$1${RESET}"
}

# Clear screen and show header
clear
print_header

# Fetch version
print_step "Fetching latest version..."
VERSION=$(curl -s https://api.ascendara.app | grep -o '"appVer":"[^"]*"' | cut -d'"' -f4)
print_success "Found version ${BOLD}${MAGENTA}$VERSION${RESET}"
echo

# Create directories
print_step "Creating installation directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p ~/.local/share/applications
mkdir -p ~/.local/share/icons/hicolor/256x256/apps
print_success "Directories ready"
echo

# Download AppImage
print_step "Downloading Ascendara AppImage..."
print_info "This may take a moment depending on your connection"
wget -q --show-progress -O "$APPIMAGE_PATH" \
https://github.com/Ascendara/ascendara/releases/download/$VERSION/Ascendara-$VERSION.AppImage
print_success "AppImage downloaded"
echo

# Make executable
print_step "Setting permissions..."
chmod +x "$APPIMAGE_PATH"
print_success "AppImage is now executable"
echo

# Download icon
print_step "Downloading application icon..."
wget -q -O "$ICON_PATH" https://ascendara.app/icon.png
print_success "Icon installed"
echo

# Create desktop entry
print_step "Creating desktop entry..."
cat > "$DESKTOP_FILE" <<EOL
[Desktop Entry]
Version=1.0
Type=Application
Name=Ascendara
Comment=Game launcher and library manager
Exec=$APPIMAGE_PATH --no-sandbox %U
Icon=$ICON_PATH
Categories=Game;
Terminal=false
StartupNotify=true
MimeType=x-scheme-handler/ascendara;
X-AppImage-Version=$VERSION
EOL

if command -v update-desktop-database &> /dev/null; then
    update-desktop-database ~/.local/share/applications 2>/dev/null
fi
print_success "Desktop entry created"
echo

# Final message
echo -e "${BOLD}${GREEN}╔════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║                                        ║${RESET}"
echo -e "${BOLD}${GREEN}║     ${STAR}  Installation Complete!  ${STAR}       ${GREEN}║${RESET}"
echo -e "${BOLD}${GREEN}║                                        ║${RESET}"
echo -e "${BOLD}${GREEN}╚════════════════════════════════════════╝${RESET}"
echo
echo -e "${BOLD}${CYAN}Launch Ascendara:${RESET}"
echo -e "  ${ARROW} Search for ${BOLD}Ascendara${RESET} in your application menu"
echo -e "  ${ARROW} Or run: ${DIM}$APPIMAGE_PATH${RESET}"
echo
echo -e "${DIM}Installed to: $INSTALL_DIR${RESET}"
echo
