# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 配置管理层
"""

from .settings import Settings
from .course_schema import (
    Course,
    CourseData,
    Insight,
    Material,
    Contributor,
    COURSES_BY_YEAR,
    WIKI_YEAR_NODES,
    NAV_TABLE_FIELDS,
    BITABLE_COURSE_FIELDS,
    PROTECTED_FIELDS,
    MATERIALS_TABLE_FIELDS,
    INSIGHTS_TABLE_FIELDS,
)

__all__ = [
    "Settings",
    "Course",
    "CourseData",
    "Insight",
    "Material",
    "Contributor",
    "COURSES_BY_YEAR",
    "WIKI_YEAR_NODES",
    "NAV_TABLE_FIELDS",
    "BITABLE_COURSE_FIELDS",
    "PROTECTED_FIELDS",
    "MATERIALS_TABLE_FIELDS",
    "INSIGHTS_TABLE_FIELDS",
]
