@echo off
chcp 65001 >nul
echo ========================================
echo  Mewgenics 中文补丁 - 打包为EXE
echo ========================================
echo.

REM 检查依赖
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 正在安装PyInstaller...
    pip install pyinstaller
)
pip show fonttools >nul 2>&1
if errorlevel 1 (
    echo 正在安装fonttools...
    pip install fonttools
)

echo 正在打包补丁工具...
pyinstaller --onefile --name "Mewgenics中文补丁" --add-data "translations;translations" --hidden-import=font_to_swf --hidden-import=fontTools --hidden-import=fontTools.ttLib --hidden-import=fontTools.pens.recordingPen --collect-submodules fontTools --console mewgenics_cn_patch.py

echo.
echo 正在打包恢复工具...
pyinstaller --onefile --name "Mewgenics中文补丁_恢复" --console mewgenics_cn_restore.py

echo.
echo ========================================
echo  打包完成！文件位于 dist\ 目录
echo ========================================
echo.
echo 分发时需要的文件:
echo   dist\Mewgenics中文补丁.exe
echo   dist\Mewgenics中文补丁_恢复.exe
echo   (可选) 将.ttf/.otf字体文件放在exe同目录下
echo.
pause
