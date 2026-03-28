# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import json


@dataclass
class Material:
    """资料模型"""
    material_id: str
    original_name: str
    standard_name: str
    contributor: str
    grade: str
    course_name: str
    material_type: str
    recommendation: str
    file_path: str
    upload_time: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"  # pending, approved, rejected
    
    def to_dict(self):
        return {
            "material_id": self.material_id,
            "original_name": self.original_name,
            "standard_name": self.standard_name,
            "contributor": self.contributor,
            "grade": self.grade,
            "course_name": self.course_name,
            "material_type": self.material_type,
            "recommendation": self.recommendation,
            "file_path": self.file_path,
            "upload_time": self.upload_time,
            "status": self.status
        }


@dataclass
class Experience:
    """心得体会模型"""
    experience_id: str
    author: str
    grade: str
    course_name: str
    score: str
    content: str
    extracted_info: dict = field(default_factory=dict)
    submit_time: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"  # pending, verified, rejected
    reviewer: Optional[str] = None
    
    def to_dict(self):
        return {
            "experience_id": self.experience_id,
            "author": self.author,
            "grade": self.grade,
            "course_name": self.course_name,
            "score": self.score,
            "content": self.content,
            "extracted_info": self.extracted_info,
            "submit_time": self.submit_time,
            "status": self.status,
            "reviewer": self.reviewer
        }


@dataclass
class CourseDocument:
    """课程文档模型"""
    course_name: str
    teacher: str
    exam_type: str
    overview: str
    difficulties: List[str]
    teacher_preferences: str
    material_list: dict
    material_guide: str
    contributors: List[dict]
    generated_time: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return {
            "course_name": self.course_name,
            "teacher": self.teacher,
            "exam_type": self.exam_type,
            "overview": self.overview,
            "difficulties": self.difficulties,
            "teacher_preferences": self.teacher_preferences,
            "material_list": self.material_list,
            "material_guide": self.material_guide,
            "contributors": self.contributors,
            "generated_time": self.generated_time
        }


@dataclass
class Contributor:
    """贡献者模型"""
    name: str
    grade: str
    contributions: List[dict]  # [{"type": "资料上传", "detail": "..."}, {"type": "心得撰写", "detail": "..."}]
    
    def to_dict(self):
        return {
            "name": self.name,
            "grade": self.grade,
            "contributions": self.contributions
        }


def save_json(data: list, filepath: str):
    """保存JSON数据"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(filepath: str) -> list:
    """加载JSON数据"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
