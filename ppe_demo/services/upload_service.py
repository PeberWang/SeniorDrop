# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 上传服务
处理资料上传和归档
"""

import os
import sys
import shutil
from pathlib import Path
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Material, save_json, load_json
from config import DATA_DIR, MATERIALS_BASE


class UploadService:
    """资料上传服务"""
    
    def __init__(self):
        self.materials_file = DATA_DIR / "materials.json"
        self.materials = load_json(self.materials_file)
        self.material_id_counter = len(self.materials) + 1
    
    def process_upload(
        self,
        uploader_id: str,
        uploader_grade: str,
        course_name: str,
        material_type: str,
        recommendation_reason: str,
        file_path: str,
        original_filename: str
    ) -> dict:
        """
        处理资料上传
        
        Args:
            uploader_id: 上传者ID（如"23级小陈"）
            uploader_grade: 年级
            course_name: 课程名称
            material_type: 资料类型（PPT/笔记/真题/阅读材料等）
            recommendation_reason: 推荐理由
            file_path: 原始文件路径
            original_filename: 原始文件名
        
        Returns:
            处理结果
        """
        
        # 1. 生成标准化文件名
        file_ext = Path(original_filename).suffix
        standard_name = f"{material_type}_{uploader_id}_{Path(original_filename).stem}{file_ext}"
        
        # 2. 生成资料ID
        material_id = f"MAT{self.material_id_counter:04d}"
        self.material_id_counter += 1
        
        # 3. 创建Material对象
        material = Material(
            material_id=material_id,
            original_name=original_filename,
            standard_name=standard_name,
            contributor=uploader_id,
            grade=uploader_grade,
            course_name=course_name,
            material_type=material_type,
            recommendation=recommendation_reason,
            file_path=file_path
        )
        
        # 4. 保存到数据
        self.materials.append(material.to_dict())
        save_json(self.materials, self.materials_file)
        
        print(f"✅ 资料上传成功: {standard_name}")
        
        return {
            "success": True,
            "material_id": material_id,
            "standard_name": standard_name
        }
    
    def get_materials_by_course(self, course_name: str) -> List[dict]:
        """获取某课程的所有资料"""
        return [
            m for m in self.materials
            if m["course_name"] == course_name and m["status"] == "approved"
        ]
    
    def approve_material(self, material_id: str):
        """审核通过资料"""
        for m in self.materials:
            if m["material_id"] == material_id:
                m["status"] = "approved"
                break
        save_json(self.materials, self.materials_file)
        print(f"✅ 资料审核通过: {material_id}")
    
    def scan_existing_materials(self):
        """
        扫描现有的资料包，自动导入
        """
        print("🔍 扫描现有资料包...")
        
        import_count = 0
        
        # 遍历课程文件夹
        for course_folder in MATERIALS_BASE.iterdir():
            if not course_folder.is_dir():
                continue
            
            # 提取课程名和老师名
            folder_name = course_folder.name
            if "（" in folder_name and "）" in folder_name:
                course_name = folder_name.split("（")[0]
                teacher = folder_name.split("（")[1].replace("）", "").replace("老师", "")
            else:
                course_name = folder_name
                teacher = ""
            
            print(f"\n📁 扫描课程: {course_name}（{teacher}老师）")
            
            # 遍历所有文件
            for root, dirs, files in os.walk(course_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # 判断资料类型
                    material_type = self._detect_material_type(file)
                    
                    # 模拟上传（不复制文件，只记录元信息）
                    self.process_upload(
                        uploader_id="22级学长",
                        uploader_grade="22级",
                        course_name=course_name,
                        material_type=material_type,
                        recommendation_reason="从大礼包导入",
                        file_path=file_path,
                        original_filename=file
                    )
                    
                    # 自动审核通过
                    material_id = f"MAT{self.material_id_counter - 1:04d}"
                    self.approve_material(material_id)
                    
                    import_count += 1
        
        print(f"\n✅ 导入完成: 共 {import_count} 个资料")
        return import_count
    
    def _detect_material_type(self, filename: str) -> str:
        """根据文件名判断资料类型"""
        filename_lower = filename.lower()
        
        if "ppt" in filename_lower or ".ppt" in filename_lower:
            return "PPT"
        elif "笔记" in filename or "复习" in filename:
            return "笔记"
        elif "考试" in filename or "真题" in filename or "试卷" in filename:
            return "真题"
        elif "练习" in filename or "习题" in filename:
            return "练习题"
        elif "大纲" in filename:
            return "复习大纲"
        elif ".pdf" in filename_lower and ("教材" in filename or len(filename) > 30):
            return "教材"
        else:
            return "其他"
