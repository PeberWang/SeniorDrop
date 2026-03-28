# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - LLM服务
使用智谱AI
"""

import httpx
import asyncio
from typing import Optional
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ZHIPU_API_KEY, ZHIPU_BASE_URL, ZHIPU_MODEL


class LLMService:
    """智谱AI服务"""
    
    def __init__(self):
        self.api_key = ZHIPU_API_KEY
        self.base_url = ZHIPU_BASE_URL
        self.model = ZHIPU_MODEL
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def generate(self, prompt: str, temperature: float = 0.7) -> str:
        """调用智谱AI生成文本"""
        url = f"{self.base_url}chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "top_p": 0.9,
            "max_tokens": 2000
        }
        
        try:
            response = await self.client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"❌ LLM调用失败: {e}")
            return ""
    
    async def extract_course_info(self, experience_content: str, course_name: str) -> dict:
        """从心得体会中提取课程关键信息"""
        
        prompt = f"""
你是一个教学经验丰富的助教，需要从学长学姐的心得体会中提取关键信息。

课程：{course_name}
心得体会：
{experience_content}

请提取以下信息（JSON格式）：
{{
    "course_overview": "课程内容概述（100-150字）",
    "learning_difficulties": ["难点1", "难点2", "难点3"],
    "teacher_preferences": "老师偏好和考核重点（100字以内）",
    "study_tips": ["学习建议1", "学习建议2"]
}}

只返回JSON，不要其他内容。
"""
        
        response = await self.generate(prompt)
        
        # 解析JSON
        try:
            import json
            # 提取JSON部分
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            json_str = response[json_start:json_end]
            return json.loads(json_str)
        except:
            return {
                "course_overview": "",
                "learning_difficulties": [],
                "teacher_preferences": "",
                "study_tips": []
            }
    
    async def generate_course_doc(
        self,
        course_name: str,
        teacher: str,
        exam_type: str,
        experiences: list,
        materials: list
    ) -> dict:
        """生成完整的课程文档"""
        
        # 合并所有心得体会
        combined_experience = "\n\n---\n\n".join([
            f"【{exp['author']}（{exp['grade']}，成绩：{exp['score']}）】\n{exp['content']}"
            for exp in experiences
        ]) if experiences else "暂无心得体会"
        
        # 格式化资料列表
        materials_text = "\n".join([
            f"- {m['material_type']}: {m['standard_name']}（{m['contributor']}推荐）"
            for m in materials
        ]) if materials else "暂无资料"
        
        prompt = f"""
你是一个教学经验丰富的助教，需要为"{course_name}"课程编写一份学习指南。

课程信息：
- 课程名称：{course_name}
- 授课老师：{teacher}
- 考试形式：{exam_type}

学长学姐的心得体会：
{combined_experience}

已上传的资料：
{materials_text}

请生成以下内容（JSON格式）：
{{
    "overview": "课程内容概述（200-300字，基于心得体会）",
    "difficulties": ["学习难点1（简要说明）", "学习难点2（简要说明）", "学习难点3（简要说明）"],
    "teacher_preferences": "老师偏好（藏在考核要求之下的偏好，决定努力方向，100-150字）",
    "material_guide": "资料串讲（基于心得体会，说明如何使用这些资料进行学习，200-300字）"
}}

只返回JSON，不要其他内容。
"""
        
        response = await self.generate(prompt, temperature=0.8)
        
        # 解析JSON
        try:
            import json
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            json_str = response[json_start:json_end]
            return json.loads(json_str)
        except:
            return {
                "overview": "暂无概述",
                "difficulties": [],
                "teacher_preferences": "暂无信息",
                "material_guide": "暂无指导"
            }
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
