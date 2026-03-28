# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 心得体会服务
"""

import os
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Experience, save_json, load_json
from config import DATA_DIR
from services.llm_service import LLMService


class ExperienceService:
    """心得体会服务"""
    
    def __init__(self):
        self.experiences_file = DATA_DIR / "experiences.json"
        self.experiences = load_json(self.experiences_file)
        self.experience_id_counter = len(self.experiences) + 1
        self.llm_service = LLMService()
    
    async def submit_experience(
        self,
        author: str,
        grade: str,
        course_name: str,
        score: str,
        content: str
    ) -> dict:
        """
        提交心得体会
        
        Args:
            author: 作者ID（如"22级小王"）
            grade: 年级
            course_name: 课程名称
            score: 该课程成绩
            content: 心得体会内容
        
        Returns:
            处理结果
        """
        
        # 1. 生成心得ID
        experience_id = f"EXP{self.experience_id_counter:04d}"
        self.experience_id_counter += 1
        
        # 2. AI提取关键信息
        print(f"🤖 正在提取课程信息...")
        extracted_info = await self.llm_service.extract_course_info(content, course_name)
        
        # 3. 创建Experience对象
        experience = Experience(
            experience_id=experience_id,
            author=author,
            grade=grade,
            course_name=course_name,
            score=score,
            content=content,
            extracted_info=extracted_info,
            status="pending"
        )
        
        # 4. 保存到数据
        self.experiences.append(experience.to_dict())
        save_json(self.experiences, self.experiences_file)
        
        print(f"✅ 心得体会提交成功: {author} - {course_name}")
        
        return {
            "success": True,
            "experience_id": experience_id,
            "extracted_info": extracted_info
        }
    
    def get_experiences_by_course(self, course_name: str) -> List[dict]:
        """获取某课程的所有心得体会（已审核）"""
        return [
            e for e in self.experiences
            if e["course_name"] == course_name and e["status"] in ["verified", "pending"]
        ]
    
    def verify_experience(self, experience_id: str, reviewer: str = "学委"):
        """审核通过心得体会"""
        for e in self.experiences:
            if e["experience_id"] == experience_id:
                e["status"] = "verified"
                e["reviewer"] = reviewer
                break
        save_json(self.experiences, self.experiences_file)
        print(f"✅ 心得体会审核通过: {experience_id}")
    
    async def generate_sample_experiences(self, courses: List[dict]):
        """
        生成示例心得体会（用于Demo）
        
        Args:
            courses: 课程列表
        """
        print("📝 生成示例心得体会...")
        
        sample_experiences = [
            {
                "author": "22级小王",
                "grade": "22级",
                "course_name": "中国经济概论",
                "score": "92",
                "content": """中国经济概论这门课，龚关老师讲得很系统。重点是理解中国经济增长的逻辑，特别是改革开放以来的发展模式。

**学习难点**：
1. 理解"李约瑟之谜"——为什么工业革命没有发生在中国
2. 双轨制改革的逻辑和效果
3. 中国特色的社会主义市场经济体制

**老师偏好**：
龚关老师喜欢学生有宏观视野，能用经济学理论分析中国实际问题。考试时要注意结合林毅夫的《解读中国经济》，老师很看重对书本知识的理解和应用。

**学习建议**：
- 认真读林毅夫的教材，特别是每一章的案例
- 关注中国经济热点问题，如房地产、地方政府债务等
- 考试前整理好知识框架，特别是改革开放以来的重大经济政策

我上传了教材PDF和我的复习笔记，希望能帮到学弟学妹。"""
            },
            {
                "author": "22级小李",
                "grade": "22级",
                "course_name": "世界经济概论",
                "score": "88",
                "content": """世界经济概论（雷鸣老师）是开卷考试，但不要以为开卷就简单。

**学习难点**：
1. 世界经济史的时间线很长，需要记住关键事件和年代
2. 理解不同国家的经济发展模式和路径
3. 全球化进程中的制度变迁

**老师偏好**：
雷鸣老师特别强调制度经济学视角，喜欢学生用"制度变迁"的理论框架分析问题。考试时要注意理论联系实际。

**学习建议**：
- PPT是核心，要仔细看每一页
- 重点关注中西方历史大分流的原因（推荐看郭金兴的论文）
- 考试时带好教材和PPT打印版，但更重要的是理解逻辑

我上传了世界经济史PPT和备考指南，希望能有用。"""
            },
            {
                "author": "22级小张",
                "grade": "22级",
                "course_name": "西方政治思想史",
                "score": "90",
                "content": """西方政治思想史（柳建文老师）内容很多，从古希腊到现代，跨度很大。

**学习难点**：
1. 记住各个思想家的核心观点和代表作
2. 理解不同思想流派之间的传承和批判关系
3. 能够用思想史的分析框架解读现实政治问题

**老师偏好**：
柳老师特别看重对经典文本的理解，喜欢学生能引用原著原文。马工程教材是必读的，考试时如果能准确引用思想家原话会加分。

**学习建议**：
- 认真读马工程教材，特别是每一章的总结
- PPT要仔细看，老师上课讲的重点都在里面
- 考试前整理时间线，把思想家按时代和流派分类

我上传了PPT、教材PDF和我的思考题整理，加油！"""
            },
            {
                "author": "22级小陈",
                "grade": "22级",
                "course_name": "概率论与数理统计",
                "score": "95",
                "content": """概率论（刘会刚老师）对PPE同学来说可能有点难，但只要掌握方法就能拿高分。

**学习难点**：
1. 概率分布的理解和应用（正态分布、t分布等）
2. 参数估计和假设检验的逻辑
3. 公式推导和计算

**老师偏好**：
刘老师出题比较规范，基本就是PPT上的题型。重点考察对基本概念的理解和计算能力，不会出偏题怪题。

**学习建议**：
- PPT前五章是重点，要反复看
- 做练习题！我上传了计算机学院的练习题（难度比PPE高），做会了这些考试就没问题
- 考试时带好计算器，注意时间分配

PPE同学不要怕数学，概率论其实很有逻辑性。我上传了PPT和练习题，大家加油！"""
            }
        ]
        
        # 提交这些示例心得
        for exp_data in sample_experiences:
            result = await self.submit_experience(**exp_data)
            # 自动审核通过
            self.verify_experience(result["experience_id"])
        
        print(f"✅ 生成并审核了 {len(sample_experiences)} 条示例心得")
        
        await self.llm_service.close()
        return len(sample_experiences)
