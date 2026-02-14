@echo off
chcp 65001 >nul
echo ========================================
echo  咪咪汉化工具箱 - 打包为EXE
echo ========================================
echo.

REM 检查依赖
echo 检查 Python 依赖...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 正在安装 PyInstaller...
    pip install pyinstaller
)
pip show fonttools >nul 2>&1
if errorlevel 1 (
    echo 正在安装 fonttools...
    pip install fonttools
)
pip show json-repair >nul 2>&1
if errorlevel 1 (
    echo 正在安装 json-repair...
    pip install json-repair
)
pip show openai >nul 2>&1
if errorlevel 1 (
    echo 正在安装 openai...
    pip install openai
)
pip show httpx >nul 2>&1
if errorlevel 1 (
    echo 正在安装 httpx...
    pip install httpx
)

echo.
echo 正在打包咪咪汉化工具箱...
pyinstaller "游戏汉化工具箱.spec" --noconfirm --clean

echo.
echo ========================================
echo  打包完成！
echo ========================================
echo.
echo 输出文件:
echo   dist\游戏汉化工具箱.exe
echo.
echo 使用说明:
echo   1. 双击运行 exe 文件
echo   2. 设置游戏目录
echo   3. 使用工具进行翻译和打补丁
echo.
pause
