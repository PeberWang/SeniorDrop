# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - LLM服务
使用智谱AI生成课程学习指南

核心理念：
- 生成的内容要像学长学姐在跟学弟学妹说话，而非教科书
- 帮助学弟学妹快速掌握拿高分的要点，理解每份资料的价值
- 基于真实心得提炼，不编造信息，没有心得时坦诚说明
"""

import httpx
import asyncio
import json
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

    async def generate(self, prompt: str, system_prompt: str = None, temperature: float = 0.7) -> str:
        """调用智谱AI生成文本

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（角色设定）
            temperature: 创造性参数
        """
        url = f"{self.base_url}chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": 0.9,
            "max_tokens": 4000
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
        """从学长学姐的心得体会中提取课程关键信息"""

        system_prompt = "你是一个仔细认真的编辑，擅长从学长学姐的分享中提炼出最有价值的学习信息。"

        prompt = f"""
以下是某位学长学姐关于"{course_name}"课程的学习心得，请从中提取关键信息。

心得内容：
{experience_content}

请提取以下信息（严格返回JSON格式）：
{{
    "course_overview": "课程内容概述（100-150字，概括这门课学什么、怎么学）",
    "learning_difficulties": ["具体难点1", "具体难点2", "具体难点3"],
    "teacher_preferences": "授课老师的偏好和考核重点（100字以内）",
    "study_tips": ["学习建议1", "学习建议2", "学习建议3"]
}}

注意：
- 只从心得中提取，不要编造心得里没有的信息
- 如果心得中缺少某项信息，对应字段留空字符串或空数组
- 只返回JSON，不要任何其他内容
"""

        response = await self.generate(prompt, system_prompt=system_prompt)

        return self._parse_json_response(response, {
            "course_overview": "",
            "learning_difficulties": [],
            "teacher_preferences": "",
            "study_tips": []
        })

    async def generate_course_doc(
        self,
        course_name: str,
        teacher: str,
        exam_type: str,
        experiences: list,
        materials: list
    ) -> dict:
        """生成完整的课程学习指南

        这是核心方法。生成的文档会直接写入飞书云文档，供学弟学妹阅读。
        文档风格要像学长学姐在跟学弟学妹说话——真诚、实用、有温度。
        """

        system_prompt = """你是一位刚修完这门课、拿了高分的学长/学姐。你正在为即将选这门课的学弟学妹写一份课程学习指南。

你的写作原则：
1. 语气亲切自然，像在跟学弟学妹面对面聊天，不是写教科书
2. 帮学弟学妹节省时间——告诉他们什么重要、什么可以跳过、什么坑要避开
3. 基于真实心得提炼，绝不编造心得里没有的信息（老师喜好、考试形式等）
4. 如果某项信息没有心得支撑，坦诚说明"暂无学长学姐分享"，不要编造
5. 把复杂的知识点讲得通俗易懂，用比喻和类比
6. 实用至上——每个建议都要让学弟学妹觉得"这个我马上就能用上"
7. 适度幽默，但不过度，学术内容还是要严肃对待

你的写作要避免：
- 假大空的套话（"本课程旨在培养…"）
- 编造心得中没有的具体信息
- 过于简略、没有实质内容的描述
- 机械罗列，缺乏逻辑串联"""

        # 格式化心得信息
        if experiences:
            experience_sections = []
            for exp in experiences:
                score_text = f"成绩{exp['score']}分" if exp.get('score') else ""
                experience_sections.append(
                    f"【{exp['author']}（{exp['grade']}，{score_text}）】\n{exp['content']}"
                )
            combined_experience = "\n\n---\n\n".join(experience_sections)
            experience_note = "以下是多位学长学姐的真实心得，请认真提炼其中的共性和亮点："
        else:
            combined_experience = ""
            experience_note = "目前还没有学长学姐分享关于这门课的心得。请基于课程名称和基本信息，写一份框架性的概述，并坦诚说明暂无学长经验分享。"

        # 格式化资料信息
        if materials:
            materials_by_type = {}
            for m in materials:
                m_type = m["material_type"]
                if m_type not in materials_by_type:
                    materials_by_type[m_type] = []
                materials_by_type[m_type].append(m)

            materials_sections = []
            for m_type, items in materials_by_type.items():
                items_text = "\n".join([
                    f"  - {item['standard_name']}（{item['contributor']}推荐）"
                    for item in items
                ])
                materials_sections.append(f"【{m_type}】\n{items_text}")
            materials_text = "\n\n".join(materials_sections)
        else:
            materials_text = "暂无资料"

        prompt = f"""
请为以下课程生成一份学习指南：

**课程信息**
- 课程名称：{course_name}
- 授课老师：{teacher if teacher else '暂无信息'}
- 考试形式：{exam_type}

**学长学姐心得**
{experience_note}
{combined_experience}

**已有资料**
{materials_text}

---

请生成以下内容（严格返回JSON格式，不要有任何其他文字）：

{{
    "overview": "课程内容概述（200-300字）。用学弟学妹能听懂的话概括这门课学什么、整体难度如何、值不值得认真学。如果有心得，要融入学长学姐的真实感受；如果没有心得，基于课程名称做合理推测，但要坦诚说明信息有限。",
    "difficulties": [
        "具体难点1：用一两句话说明为什么难、怎么突破",
        "具体难点2：同上",
        "具体难点3：同上"
    ],
    "teacher_preferences": "老师偏好和考核风格（150-200字）。重点说明：老师出题风格（偏记忆还是偏理解？）、给分情况、课堂有没有值得特别注意的地方。只写心得中提到的，没有就坦诚说明。",
    "material_guide": "资料使用指南（200-300字）。像学长在跟你说'这本资料什么时候看、怎么用、重点看什么'。把资料和课程学习进度串联起来，让学弟学妹知道每份资料在整个学习过程中扮演什么角色。如果没有资料，说明目前暂无资料，建议关注课堂PPT和教材。"
}}

注意：
- 严格返回JSON，不要在JSON前后加任何文字或代码块标记
- 字段值必须是字符串或数组，不要嵌套JSON
- 如果某项信息无法从心得中获取，写"暂无学长学姐分享"而非编造
"""

        response = await self.generate(prompt, system_prompt=system_prompt, temperature=0.8)

        return self._parse_json_response(response, {
            "overview": "暂无概述",
            "difficulties": [],
            "teacher_preferences": "暂无学长学姐分享",
            "material_guide": "暂无学长学姐分享"
        })

    def _parse_json_response(self, response: str, fallback: dict) -> dict:
        """安全解析LLM返回的JSON"""
        if not response:
            return fallback

        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        try:
            # 尝试提取JSON部分（处理LLM返回中可能包含的额外文字）
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            pass

        print(f"  ⚠️ LLM返回内容无法解析为JSON，使用默认值")
        print(f"  ⚠️ 返回内容前100字: {response[:100]}")
        return fallback

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
