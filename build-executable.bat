@echo off
cargo build --release || exit /b 1
if not exist dist mkdir dist
copy /Y target\release\AscendaraInstaller.exe dist\AscendaraInstaller.exe >nul
echo Built dist\AscendaraInstaller.exe
