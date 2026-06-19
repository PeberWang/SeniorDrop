# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 课程数据模型与字段定义

数据分层：
- CourseData（含 insights/materials/contributors）是运行时聚合对象，从 bitable 三张表实时构造，不持久化到本地。
- 前台 nav 表（NAV_TABLE_FIELDS）：面向新生的入口导航，内嵌进学年文档。
- 后台管理表（COURSE/MATERIALS/INSIGHTS_TABLE_FIELDS）：bitable 三张表是真相源，飞书表单采集。
- COURSES_BY_YEAR 是项目示例种子（用于单选字段初始化选项），不再作为运行时真相源。
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field


# ==================== 富数据模型（源真相）====================

class Insight(BaseModel):
    """高分心得体会 —— 课程文档的核心资产，质量直接决定文档质量。"""
    author: str = ""          # 作者，如 "22级小王"
    grade: str = ""           # 年级，如 "22级"
    score: str = ""           # 该课程成绩（用于验证"高分"）
    content: str = ""         # 心得正文


class Material(BaseModel):
    """推荐资料（教材/笔记/真题/讲义/阅读材料…）。"""
    name: str = ""                   # 标准化名称，如 "课程笔记_23级小陈"
    material_type: str = ""          # PPT/笔记/真题/阅读材料/教材...
    contributor: str = ""            # 贡献者，如 "23级小陈"
    grade: str = ""                  # 贡献者年级
    recommendation_reason: str = ""  # 推荐理由（贡献者主观视角）
    summary: str = ""                # 资料摘要（OCR 后 LLM 生成，客观视角，用于精细化串讲区分）
    file_link: str = ""              # OSS 下载链接（归档后回填）
    review_status: str = "已通过"     # 待审核/已通过/已拒绝


class Contributor(BaseModel):
    """贡献者及其贡献描述（参与感设计：不止"传了什么"，更是"如何丰富了对课程的理解"）。"""
    name: str = ""           # 贡献者，如 "22级小王"；心得作者带得分后缀 "22级小王（98分）"
    contribution: str = ""   # 贡献描述（同一人多条贡献会合并，如 "贡献了 2 份资料 + 1 篇高分心得"）
    score: str = ""          # 心得作者的得分（资料贡献者空），用于姓名后缀和排序


class CourseData(BaseModel):
    """课程完整数据模型 —— 运行时从 bitable 三张表聚合，不持久化到本地。"""
    # 基本字段（用于前台 nav 表；飞书 bitable 课程主数据表结构）
    name: str
    teacher: str = ""
    semester: str = ""       # 大一上/大一下/...
    type: str = ""           # 专业必修课/非专业必修课
    exam: str = ""           # 闭卷/开卷/论文/其他
    # 核心资产
    insights: List[Insight] = Field(default_factory=list)
    materials: List[Material] = Field(default_factory=list)
    contributors: List[Contributor] = Field(default_factory=list)
    # 派生 / 回填字段
    doc_url: str = ""        # 课程独立文档链接（生成后回填到 nav 表"学习指南"）
    updated_at: str = ""     # 最后更新时间（ISO 字符串）

    @property
    def material_count(self) -> int:
        return len(self.materials)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CourseData":
        return cls.model_validate(data)


# 向后兼容别名（旧代码 `from config.course_schema import Course`）
Course = CourseData


# ==================== 枚举常量 ====================

MATERIAL_TYPES = ["PPT", "笔记", "真题", "阅读材料", "教材", "复习大纲", "练习题", "其他"]
COURSE_TYPES = ["专业必修课", "非专业必修课"]
GRADES = ["22级", "23级", "24级"]
WIKI_YEAR_NODES = ["大一", "大二", "大三", "大四"]


# ==================== 课程花名册（项目示例种子，仅用于单选字段初始化选项）====================

COURSES_BY_YEAR = {
    "大一": [
        {"name": "伦理学导论", "teacher": "李虎老师", "semester": "大一上", "type": "专业必修课", "exam": "闭卷"},
        {"name": "宪法学", "teacher": "赵聚军老师", "semester": "大一上", "type": "专业必修课", "exam": "闭卷"},
        {"name": "微观经济学", "teacher": "", "semester": "大一上", "type": "专业必修课", "exam": "闭卷"},
        {"name": "政治学原理", "teacher": "", "semester": "大一下", "type": "专业必修课", "exam": "闭卷"},
        {"name": "宏观经济学", "teacher": "", "semester": "大一下", "type": "专业必修课", "exam": "闭卷"},
        {"name": "概率论与数理统计", "teacher": "刘会刚老师", "semester": "大一下", "type": "专业必修课", "exam": "闭卷"},
    ],
    "大二": [
        {"name": "世界经济概论", "teacher": "雷鸣老师", "semester": "大二上", "type": "专业必修课", "exam": "开卷"},
        {"name": "中国经济概论", "teacher": "龚关老师", "semester": "大二上", "type": "专业必修课", "exam": "闭卷"},
        {"name": "西方政治思想史", "teacher": "柳建文老师", "semester": "大二上", "type": "专业必修课", "exam": "闭卷"},
        {"name": "中国政治思想史", "teacher": "孙晓春老师", "semester": "大二上", "type": "专业必修课", "exam": "闭卷"},
        {"name": "比较政治制度", "teacher": "贾义猛老师", "semester": "大二上", "type": "专业必修课", "exam": "闭卷"},
        {"name": "外国经济学说史", "teacher": "蒋雅文老师", "semester": "大二下", "type": "专业必修课", "exam": "闭卷"},
        {"name": "计量经济学", "teacher": "", "semester": "大二下", "type": "专业必修课", "exam": "闭卷"},
    ],
    "大三": [
        {"name": "中国哲学史", "teacher": "", "semester": "大三上", "type": "非专业必修课", "exam": "闭卷"},
        {"name": "西方哲学史", "teacher": "", "semester": "大三上", "type": "非专业必修课", "exam": "闭卷"},
        {"name": "国际关系", "teacher": "", "semester": "大三上", "type": "非专业必修课", "exam": "论文"},
        {"name": "比较政治", "teacher": "", "semester": "大三下", "type": "非专业必修课", "exam": "论文"},
    ],
    "大四": [
        {"name": "毕业论文", "teacher": "", "semester": "大四上", "type": "专业必修课", "exam": "论文"},
    ],
}


# ==================== 前台 nav 表字段（内嵌进学年文档）====================
# 字段类型编号对照（飞书）：1 文本 / 2 数字 / 3 单选 / 5 日期 / 15 URL
NAV_TABLE_FIELDS = [
    ("课程名称", 1),
    ("授课老师", 1),
    ("开课学期", 3),
    ("课程类型", 3),
    ("考试形式", 3),
    ("学习指南", 15),
    ("资料数量", 2),
    ("最后更新", 5),
]

# 向后兼容别名
BITABLE_COURSE_FIELDS = NAV_TABLE_FIELDS

# 飞书 bitable 课程主数据表（真相源）— 仅基本字段，insights/materials 通过关联表查询
COURSE_TABLE_FIELDS = [
    ("课程名称", 1),
    ("授课老师", 1),
    ("开课学期", 3),
    ("课程类型", 3),
    ("考试形式", 3),
    ("资料数量", 2),   # 派生：sync 时从资料表 count
    ("最后更新", 5),   # 派生：sync 时刷新
]

# 增量更新时不覆盖的字段（避免清掉手动刷新的时间戳）
PROTECTED_FIELDS = {"最后更新"}


# ==================== 后台管理表字段（设计蓝图，飞书表单采集，下次接入）====================
# 来源：技术方案 v3.0 §4.1.1 / §4.1.2
MATERIALS_TABLE_FIELDS = [
    # 学生填表字段（表单可见）
    ("贡献者", 1),
    ("届别", 3),
    ("课程", 3),
    ("资料类型", 3),
    ("推荐理由", 1),
    ("文件附件", 17),
    # 系统自动填（代码归档后回填，表单隐藏）
    ("资料名称", 1),
    ("原始文件名", 1),
    ("文件链接", 15),
    ("资料摘要", 1),
    ("归档时间", 5),
    ("上传时间", 5),
    # 管理员填
    ("审核状态", 3),
]

INSIGHTS_TABLE_FIELDS = [
    # 学生填（特邀高分同学）
    ("作者", 1),
    ("届别", 3),
    ("课程", 3),
    ("成绩", 1),
    ("心得内容", 1),
    # 系统自动
    ("提交时间", 5),
    # 管理员填
    ("审核状态", 3),
    ("审核人", 1),
]


# 单选字段 → 选项列表（创建/修复字段时填充 property.options）
AUDIT_STATUS = ["待审核", "已通过", "已拒绝"]
SEMESTERS = ["大一上", "大一下", "大二上", "大二下", "大三上", "大三下", "大四上", "大四下"]
EXAM_TYPES = ["闭卷", "开卷", "论文", "其他"]
COURSE_NAMES = sorted({c["name"] for courses in COURSES_BY_YEAR.values() for c in courses})
SINGLE_SELECT_OPTIONS = {
    "届别": GRADES,
    "课程": COURSE_NAMES,
    "资料类型": MATERIAL_TYPES,
    "课程类型": COURSE_TYPES,
    "开课学期": SEMESTERS,
    "考试形式": EXAM_TYPES,
    "审核状态": AUDIT_STATUS,
}


# ==================== 课程展示名 helper（运行时聚合用）====================

def material_display_name(material: "Material") -> str:
    """资料展示名规则：名称-类型-贡献者(届别+姓名)。

    contributor 已含届别（如 '22级小赵'）则直接用；
    否则拼 grade（如 grade='22级' + contributor='牧远' → '22级牧远'）。
    缺字段时降级（无 type → '资料'，无 contributor → '匿名'）。
    """
    c = (material.contributor or "").strip()
    if "级" not in c and (material.grade or "").strip():
        c = f"{material.grade.strip()}{c}"
    if not c:
        c = "匿名"
    mtype = (material.material_type or "").strip() or "资料"
    name = (material.name or "").strip() or "未命名资料"
    return f"{name}-{mtype}-{c}"
