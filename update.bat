@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================
echo   课程资料智能大礼包 - 检查更新
echo ============================================
echo.

if not exist .git (
    echo [错误] 这份项目不是通过 git 下载的，无法自动更新。
    echo.
    echo 请到 https://github.com/PeberWang/PPE-CloudSmart-GiftBox
    echo 点击绿色 Code 按钮 - Download ZIP，解压后用以下文件夹覆盖你的项目目录：
    echo   deploy.py / glue/ / services/ / libs/ / config/ / tools/
    echo   setup.bat / start.bat / update.bat
    echo.
    echo 注意：不要覆盖 .env 和 data/（那是你的本地配置和数据）。
    echo.
    pause
    exit /b 1
)

echo [1/2] 从云端拉取最新代码...
git pull --ff-only
if !errorlevel! neq 0 (
    echo.
    echo [错误] 自动更新失败。可能原因：
    echo   - 网络问题：检查能否访问 github.com
    echo   - 本地文件被改过：需要项目维护者协助
    echo.
    echo 请把上面的完整输出发给项目维护者。
    echo.
    pause
    exit /b 1
)
echo.

echo [2/2] 检查 Python 依赖...
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe -m pip install -r requirements.txt -q
    if !errorlevel! neq 0 (
        echo       官方源慢，换清华镜像源...
        venv\Scripts\python.exe -m pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    )
    echo       依赖已是最新
) else (
    echo       [警告] 未找到 venv，跳过依赖检查。
    echo       如果还没跑过 setup.bat，请先跑一次。
)
echo.

echo ============================================
echo   更新完成
echo ============================================
echo.
echo 你的项目已是最新版本。
echo 你的飞书知识库 / 表格 / 文档不受任何影响。
echo 现在可以关掉这个窗口。
echo.
pause
