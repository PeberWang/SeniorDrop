@echo off
cd /d "%~dp0"

echo ============================================
echo   课程资料智能大礼包 - 项目终端
echo ============================================
echo.

if not exist venv (
    echo [错误] 未找到 venv 目录
    echo.
    echo 请先双击 setup.bat 完成安装。
    echo.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo 虚拟环境已激活。提示符前应有 (venv) 标志。
echo.
echo 可以跑命令了，常用命令：
echo   python deploy.py init-bitable       初始化 bitable
echo   python deploy.py seed-course ...     录入课程
echo   python deploy.py wiki                建知识库
echo   python deploy.py docs                生成课程文档
echo   python deploy.py link                回填链接
echo   python deploy.py archive-materials   归档资料
echo   python deploy.py ocr-materials       OCR + 摘要
echo   python deploy.py sync                同步 bitable
echo   python deploy.py logs                查日志
echo.
echo 完整命令清单跑 python deploy.py --help
echo.
echo 退出虚拟环境：输入 exit
echo.

REM 保持 cmd 窗口打开，让用户继续跑命令
cmd /k
