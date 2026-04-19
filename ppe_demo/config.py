# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 配置文件
所有敏感信息通过环境变量或 .env 文件读取

路径解析优先级：
  1. 环境变量（MATERIALS_BASE / COURSE_REFORM_NOTES_DIR）
  2. .env 文件中的值
  3. 自动检测：先尝试绝对路径，再尝试相对于项目根目录的路径
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── 路径常量 ──
BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent  # PPE-CloudSmart-GiftBox/
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATES_DIR = BASE_DIR / "templates"

# 加载 .env 文件（从项目根目录）
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


def _resolve_path(env_key: str, absolute_default: str, relative_default: str) -> Path:
    """解析路径，支持绝对路径和相对路径

    优先级：
      1. 环境变量（已由 load_dotenv 加载 .env）
      2. 绝对路径默认值
      3. 相对于项目根目录的路径

    Args:
        env_key: 环境变量名
        absolute_default: 绝对路径默认值
        relative_default: 相对于项目根目录的默认路径

    Returns:
        解析后的 Path 对象
    """
    env_val = os.getenv(env_key, "").strip()

    if env_val:
        p = Path(env_val)
        # 如果是绝对路径，直接使用
        if p.is_absolute():
            return p
        # 如果是相对路径，相对于项目根目录解析
        return (PROJECT_ROOT / p).resolve()

    # 尝试绝对路径默认值
    abs_path = Path(absolute_default)
    if abs_path.exists():
        return abs_path

    # 尝试相对于项目根目录的路径
    rel_path = PROJECT_ROOT / relative_default
    if rel_path.exists():
        return rel_path.resolve()

    # 都不存在时返回绝对路径默认值（保持向后兼容，运行时会报错提醒用户）
    return abs_path


# 原始材料包路径
MATERIALS_BASE = _resolve_path(
    env_key="MATERIALS_BASE",
    absolute_default=r"D:\c盘转移\Desktop\Claw工作文件夹\灵感实施附件\PPE云端智能大礼包\PPE大二上资料包",
    relative_default="materials",  # 项目根目录下的 materials/ 文件夹
)

# 课程教改笔记路径
COURSE_REFORM_NOTES_DIR = _resolve_path(
    env_key="COURSE_REFORM_NOTES_DIR",
    absolute_default=r"D:\c盘转移\Desktop\Claw工作文件夹\灵感实施附件\PPE云端智能大礼包\PPE课程教改笔记",
    relative_default="course_reform_notes",  # 项目根目录下的 course_reform_notes/ 文件夹
)

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

# PPE课程按学年分类
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
WIKI_SPACE_NAME = "Demo PPE CloudSmart Giftbox"
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

# ── 保护字段：增量更新时不覆盖这些用户手动编辑的字段 ──
PROTECTED_FIELDS = {"贡献者", "最后更新"}

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
(OUTPUT_DIR / "course_docs").mkdir(exist_ok=True)
