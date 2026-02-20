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

cat > "$DESKTOP_FILE" <<EOL
[Desktop Entry]
Name=Ascendara
Exec=$APPIMAGE_PATH
Icon=ascendara
Type=Application
Categories=Game;
Terminal=false
EOL

echo "Ascendara installed successfully!"
echo "You can now find it in your application menu."
