#!/bin/bash
# Ascendara Installer Script Hosted at https://ascendara.app/install.sh
# This script installs Ascendara on Linux systems

set -e

VERSION=$(curl -s https://api.ascendara.app | grep -o '"appVer":"[^"]*"' | cut -d'"' -f4)
APP_NAME="Ascendara"
INSTALL_DIR="$HOME/.local/bin"
APPIMAGE_PATH="$INSTALL_DIR/$APP_NAME.AppImage"
DESKTOP_FILE="$HOME/.local/share/applications/ascendara.desktop"

echo "Installing Ascendara..."

mkdir -p "$INSTALL_DIR"

wget -O "$APPIMAGE_PATH" \
https://github.com/Ascendara/ascendara/releases/download/$VERSION/Ascendara-$VERSION.AppImage

chmod +x "$APPIMAGE_PATH"

mkdir -p ~/.local/share/applications
mkdir -p ~/.local/share/icons/hicolor/256x256/apps

ICON_PATH="$HOME/.local/share/icons/hicolor/256x256/apps/ascendara.png"
wget -O "$ICON_PATH" https://ascendara.app/icon.png

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
    update-desktop-database ~/.local/share/applications
fi

echo "Ascendara installed successfully!"
echo "You can now find it in your application menu."
