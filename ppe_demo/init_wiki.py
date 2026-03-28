# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 知识库初始化脚本
用于创建飞书知识库结构并上传课程文档
"""

import os
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional


class FeishuWikiClient:
    """飞书知识库客户端"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = "https://open.feishu.cn/open-apis"
        self.token = None
        self.token_expire = 0

    def get_token(self) -> str:
        """获取 tenant_access_token"""
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal/"
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        response = requests.post(url, json=data)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"获取Token失败: {result}")

        self.token = result["tenant_access_token"]
        self.token_expire = result.get("expire", 7200)
        return self.token

    def _request(self, method: str, path: str, data: dict = None, params: dict = None) -> dict:
        """统一API请求"""
        if not self.token:
            self.get_token()

        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        if method == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data)
        else:
            raise ValueError(f"不支持的方法: {method}")

        return response.json()

    def create_space(self, name: str, description: str = "") -> Dict:
        """创建知识空间"""
        return self._request("POST", "/wiki/v2/spaces", {
            "name": name,
            "description": description
        })

    def list_spaces(self) -> List[Dict]:
        """获取知识空间列表"""
        result = self._request("GET", "/wiki/v2/spaces")
        return result.get("data", {}).get("items", [])

    def create_node(
        self,
        space_id: str,
        title: str,
        obj_type: str = "docx",
        parent_node_token: str = None
    ) -> Dict:
        """创建知识库节点"""
        data = {
            "obj_type": obj_type,
            "node_title": title
        }
        if parent_node_token:
            data["parent_node_token"] = parent_node_token

        return self._request("POST", f"/wiki/v2/spaces/{space_id}/nodes", data)

    def get_node(self, token: str) -> Dict:
        """获取节点信息"""
        return self._request("GET", "/wiki/v2/spaces/get_node", params={"token": token})

    def write_doc_content(self, doc_token: str, content: str) -> Dict:
        """写入文档内容"""
        url = f"{self.base_url}/docx/v1/documents/{doc_token}/blocks/{doc_token}/children/batch_create"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        data = {
            "children": [
                {
                    "block_type": 2,  # Text
                    "text": {
                        "elements": [
                            {"text_run": {"content": content}}
                        ],
                        "style": {}
                    }
                }
            ],
            "index": 0
        }
        response = requests.post(url, headers=headers, json=data)
        return response.json()


class PPEWikiBuilder:
    """PPE知识库构建器"""

    # 知识库目录结构
    WIKI_STRUCTURE = {
        "哲学 Philosophy": {
            "通识课程": {},
            "专业课程": {
                "中国哲学史": {},
                "西方哲学史": {},
                "伦理学": {}
            },
            "专业资源": {
                "推荐阅读": {},
                "学习笔记": {}
            }
        },
        "政治学 Politics": {
            "通识课程": {},
            "专业课程": {
                "政治学原理": {},
                "比较政治": {},
                "国际关系": {}
            },
            "专业资源": {}
        },
        "经济学 Economics": {
            "通识课程": {},
            "专业课程": {
                "微观经济学": {},
                "宏观经济学": {},
                "计量经济学": {}
            },
            "专业资源": {}
        },
        "综合资源": {
            "学习指南": {},
            "课程表": {},
            "资料汇总": {}
        }
    }

    def __init__(self, client: FeishuWikiClient):
        self.client = client
        self.space_id = None
        self.node_map = {}  # 节点路径 -> node_token

    def create_space(self, name: str = "PPE云端智能大礼包") -> str:
        """创建知识空间"""
        print(f"📋 创建知识空间: {name}")
        result = self.client.create_space(
            name=name,
            description="南开大学PPE实验班学习资料库"
        )

        if result.get("code") != 0:
            # 空间已存在，尝试查找
            spaces = self.client.list_spaces()
            for space in spaces:
                if space.get("name") == name:
                    self.space_id = space.get("space_id")
                    print(f"  ⚠️ 使用已有空间: {self.space_id}")
                    return self.space_id
            raise Exception(f"创建知识空间失败: {result}")

        self.space_id = result["data"]["space"]["space_id"]
        print(f"  ✅ 空间ID: {self.space_id}")
        return self.space_id

    def build_structure(self, structure: dict = None, parent_token: str = None, path: str = ""):
        """递归创建目录结构"""
        structure = structure or self.WIKI_STRUCTURE

        for name, children in structure.items():
            current_path = f"{path}/{name}" if path else name
            print(f"  📁 创建: {current_path}")

            result = self.client.create_node(
                space_id=self.space_id,
                title=name,
                obj_type="folder" if children else "docx",
                parent_node_token=parent_token
            )

            if result.get("code") != 0:
                print(f"    ⚠️ 创建失败: {result.get('msg')}")
                continue

            node_token = result["data"]["node"]["node_token"]
            self.node_map[current_path] = node_token
            print(f"    ✅ {node_token}")

            if children:
                self.build_structure(children, node_token, current_path)

    def upload_document(self, node_path: str, title: str, content: str) -> bool:
        """上传文档到指定节点"""
        if node_path not in self.node_map:
            print(f"  ⚠️ 节点不存在: {node_path}")
            return False

        parent_token = self.node_map[node_path]

        result = self.client.create_node(
            space_id=self.space_id,
            title=title,
            obj_type="docx",
            parent_node_token=parent_token
        )

        if result.get("code") != 0:
            print(f"  ⚠️ 创建文档失败: {result.get('msg')}")
            return False

        obj_token = result["data"]["node"]["obj_token"]
        self.client.write_doc_content(obj_token, content)
        print(f"  ✅ 上传文档: {title}")
        return True

    def save_node_map(self, path: str = "node_map.json"):
        """保存节点映射"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                "space_id": self.space_id,
                "nodes": self.node_map
            }, f, ensure_ascii=False, indent=2)
        print(f"💾 节点映射已保存: {path}")


def main():
    """主流程"""
    from config import FEISHU_APP_ID, FEISHU_APP_SECRET

    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("❌ 请先在 .env 文件中配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
        return

    client = FeishuWikiClient(
        app_id=FEISHU_APP_ID,
        app_secret=FEISHU_APP_SECRET
    )

    builder = PPEWikiBuilder(client)

    space_id = builder.create_space()

    print("\n🏗️ 构建目录结构...")
    builder.build_structure()

    builder.save_node_map()

    print(f"\n✅ 知识库初始化完成!")
    print(f"   空间ID: {space_id}")
    print(f"   节点数: {len(builder.node_map)}")


if __name__ == "__main__":
    main()
