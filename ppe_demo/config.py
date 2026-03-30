# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 配置文件
所有敏感信息通过环境变量或 .env 文件读取
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（从项目根目录）
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
    # print(f"[OK] 已加载环境变量: {_env_path}")
# else:
    # print(f"[WARN] 未找到 .env 文件: {_env_path}")

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

# PPE课程按学年分类（基于现有课程数据扩展）
# 每门课包含：name(课程名), teacher(授课老师), semester(开课学期), type(必修/选修), exam(考试形式)
COURSES_BY_YEAR = {
    "大一": [
        {"name": "伦理学导论", "teacher": "李虎老师", "semester": "大一上", "type": "必修", "exam": "闭卷"},
        {"name": "宪法学", "teacher": "赵聚军老师", "semester": "大一上", "type": "必修", "exam": "闭卷"},
        {"name": "微观经济学", "teacher": "", "semester": "大一上", "type": "必修", "exam": "闭卷"},
        {"name": "政治学原理", "teacher": "", "semester": "大一下", "type": "必修", "exam": "闭卷"},
        {"name": "宏观经济学", "teacher": "", "semester": "大一下", "type": "必修", "exam": "闭卷"},
        {"name": "概率论与数理统计", "teacher": "刘会刚老师", "semester": "大一下", "type": "必修", "exam": "闭卷"},
    ],
    "大二": [
        {"name": "世界经济概论", "teacher": "雷鸣老师", "semester": "大二上", "type": "必修", "exam": "开卷"},
        {"name": "中国经济概论", "teacher": "龚关老师", "semester": "大二上", "type": "必修", "exam": "闭卷"},
        {"name": "西方政治思想史", "teacher": "柳建文老师", "semester": "大二上", "type": "必修", "exam": "闭卷"},
        {"name": "中国政治思想史", "teacher": "孙晓春老师", "semester": "大二上", "type": "必修", "exam": "闭卷"},
        {"name": "比较政治制度", "teacher": "贾义猛老师", "semester": "大二上", "type": "必修", "exam": "闭卷"},
        {"name": "外国经济学说史", "teacher": "蒋雅文老师", "semester": "大二下", "type": "必修", "exam": "闭卷"},
        {"name": "计量经济学", "teacher": "", "semester": "大二下", "type": "必修", "exam": "闭卷"},
    ],
    "大三": [
        {"name": "中国哲学史", "teacher": "", "semester": "大三上", "type": "选修", "exam": "闭卷"},
        {"name": "西方哲学史", "teacher": "", "semester": "大三上", "type": "选修", "exam": "闭卷"},
        {"name": "国际关系", "teacher": "", "semester": "大三上", "type": "选修", "exam": "论文"},
        {"name": "比较政治", "teacher": "", "semester": "大三下", "type": "选修", "exam": "论文"},
    ],
    "大四": [
        {"name": "毕业论文", "teacher": "", "semester": "大四上", "type": "必修", "exam": "论文"},
    ],
}

# 知识库配置
WIKI_SPACE_NAME = "PPE云端智能大礼包"
WIKI_YEAR_NODES = ["大一", "大二", "大三", "大四"]

# 多维表格字段定义（学年课程表）
BITABLE_COURSE_FIELDS = [
    ("课程名称", 1),
    ("授课老师", 1),
    ("开课学期", 3),
    ("课程类型", 3),
    ("考试形式", 3),
    ("学习指南", 15),
    ("资料数量", 2),
    ("贡献者", 1),
    ("最后更新", 5),
]

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
(OUTPUT_DIR / "course_docs").mkdir(exist_ok=True)
