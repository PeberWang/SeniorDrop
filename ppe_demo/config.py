# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 配置文件
所有敏感信息通过环境变量或 .env 文件读取
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（从 ppe_demo 目录向上查找）
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

# 基础路径
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATES_DIR = BASE_DIR / "templates"

# 原始材料包路径（本地资料存放目录）
MATERIALS_BASE = Path(os.getenv(
    "MATERIALS_BASE",
    r"D:\c盘转移\Desktop\Claw工作文件夹\灵感实施附件\PPE云端智能大礼包\PPE大二上资料包"
))

# 课程教改笔记路径（不在仓库中，保留本地引用）
COURSE_REFORM_NOTES_DIR = Path(os.getenv(
    "COURSE_REFORM_NOTES_DIR",
    r"D:\c盘转移\Desktop\Claw工作文件夹\灵感实施附件\PPE云端智能大礼包\PPE课程教改笔记"
))

# 智谱AI配置
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
ZHIPU_BASE_URL = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
ZHIPU_MODEL = os.getenv("ZHIPU_MODEL", "glm-4-flash")

# 飞书配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_BASE_URL = os.getenv("FEISHU_BASE_URL", "https://open.feishu.cn/open-apis")

# 资料类型
MATERIAL_TYPES = [
    "PPT",
    "笔记",
    "真题",
    "阅读材料",
    "教材",
    "复习大纲",
    "练习题",
    "其他"
]

# 年级
GRADES = ["22级", "23级", "24级"]

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
(OUTPUT_DIR / "course_docs").mkdir(exist_ok=True)
