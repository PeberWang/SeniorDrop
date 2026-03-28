# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 主程序
核心流程：资料上传 → 心得收集 → 文档生成
"""

import os
import sys
import asyncio
import json
import io

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR, MATERIALS_BASE
from models import save_json
from services.upload_service import UploadService
from services.experience_service import ExperienceService
from services.doc_generator import DocGenerator


async def main():
    """主流程"""
    
    print("=" * 60)
    print("   PPE云端智能大礼包 - 核心流程Demo")
    print("=" * 60)
    
    # 1. 初始化服务
    print("\n📦 初始化服务...")
    upload_service = UploadService()
    experience_service = ExperienceService()
    doc_generator = DocGenerator()
    
    # 2. 加载课程数据
    courses_file = DATA_DIR / "courses.json"
    with open(courses_file, 'r', encoding='utf-8') as f:
        courses = json.load(f)
    print(f"✅ 加载了 {len(courses)} 门课程")
    
    # 3. 扫描并导入现有资料（模拟批量上传）
    print("\n" + "=" * 60)
    print("   步骤1: 扫描现有资料包")
    print("=" * 60)
    import_count = upload_service.scan_existing_materials()
    
    # 4. 生成示例心得体会（模拟学生提交）
    print("\n" + "=" * 60)
    print("   步骤2: 生成示例心得体会")
    print("=" * 60)
    exp_count = await experience_service.generate_sample_experiences(courses)
    
    # 5. 生成课程文档
    print("\n" + "=" * 60)
    print("   步骤3: 生成课程文档")
    print("=" * 60)
    await doc_generator.generate_all_course_docs(courses)
    
    # 6. 生成汇总报告
    print("\n" + "=" * 60)
    print("   生成汇总报告")
    print("=" * 60)
    
    # 统计数据
    materials = upload_service.materials
    experiences = experience_service.experiences
    
    report = {
        "生成时间": "2026-02-28",
        "课程数量": len(courses),
        "资料总数": len(materials),
        "心得总数": len(experiences),
        "贡献者": list(set([m["contributor"] for m in materials] + [e["author"] for e in experiences]))
    }
    
    print(f"\n📊 数据统计：")
    print(f"  - 课程数量: {report['课程数量']}")
    print(f"  - 资料总数: {report['资料总数']}")
    print(f"  - 心得总数: {report['心得总数']}")
    print(f"  - 贡献者: {', '.join(report['贡献者'])}")
    
    # 保存报告
    report_path = DATA_DIR / "report.json"
    save_json([report], report_path)
    print(f"\n✅ 报告已保存: {report_path}")
    
    print("\n" + "=" * 60)
    print("   ✅ 核心流程Demo运行完成！")
    print("=" * 60)
    print(f"\n📁 输出目录: {DATA_DIR.parent / 'output' / 'course_docs'}")
    print(f"   - 每门课程都生成了 .md 和 .json 文档")
    print(f"   - 包含6个部分：概述、难点、老师偏好、资料列表、串讲、贡献者")


if __name__ == "__main__":
    asyncio.run(main())
