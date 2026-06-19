# -*- coding: utf-8 -*-
"""
飞书SDK适配器
组合各模块，对外提供统一接口
基于 lark-oapi 官方 SDK（自动 Token 刷新，无需手动管理认证）
"""

import lark_oapi as lark
import structlog
from config.settings import Settings
from libs.feishu.wiki import WikiMixin
from libs.feishu.docx import DocxMixin
from libs.feishu.docx_table import DocxTableMixin
from libs.feishu.drive import DriveMixin
from libs.feishu.bitable import BitableMixin
from libs.feishu.perm import PermMixin
from libs.feishu.contact import ContactMixin


class FeishuAdapter(WikiMixin, DocxMixin, DocxTableMixin, DriveMixin, BitableMixin, PermMixin, ContactMixin):
    """飞书API适配器 - 基于 lark-oapi 1.6.5"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.app_id = settings.feishu_app_id
        self.app_secret = settings.feishu_app_secret
        self.base_url = settings.feishu_base_url
        self.client = lark.Client.builder() \
            .app_id(settings.feishu_app_id) \
            .app_secret(settings.feishu_app_secret) \
            .build()
        self.logger = structlog.get_logger()

    async def close(self):
        pass
