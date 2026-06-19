# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 统一配置管理
使用 pydantic-settings 统一管理环境变量和配置
"""

from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用配置类"""

    # 飞书配置
    feishu_app_id: str = Field(..., env="FEISHU_APP_ID")
    feishu_app_secret: str = Field(..., env="FEISHU_APP_SECRET")
    feishu_base_url: str = Field("https://open.feishu.cn/open-apis", env="FEISHU_BASE_URL")
    feishu_doc_host: str = Field("feishu.cn", env="FEISHU_DOC_HOST")

    # LLM 配置（DeepSeek，OpenAI 兼容；用于总论/课程文档/摘要生成）
    llm_api_key: str = Field(..., env="LLM_API_KEY")
    llm_base_url: str = Field("https://api.deepseek.com", env="LLM_BASE_URL")
    llm_model: str = Field("deepseek-v4-pro", env="LLM_MODEL")

    # OCR 配置（智谱 GLM-OCR，layout_parsing 接口；与文本 LLM 独立）
    glm_api_key: str = Field("", env="GLM_API_KEY")
    glm_ocr_url: str = Field("https://open.bigmodel.cn/api/paas/v4/layout_parsing", env="GLM_OCR_URL")

    # 云盘存储配置（本次用本地占位 LocalStubDrive，真实后端下次接入）
    cloud_drive_backend: str = Field("local_stub", env="CLOUD_DRIVE_BACKEND")
    cloud_stub_dir: Path = Field("./cloud_stub", env="CLOUD_STUB_DIR")

    # 阿里云 OSS 配置（cloud_drive_backend=aliyun_oss 时生效）
    oss_bucket: str = Field("", env="OSS_BUCKET")
    oss_endpoint: str = Field("", env="OSS_ENDPOINT")
    oss_access_key_id: str = Field("", env="OSS_ACCESS_KEY_ID")
    oss_access_key_secret: str = Field("", env="OSS_ACCESS_KEY_SECRET")
    oss_presigned_ttl: int = Field(86400, env="OSS_PRESIGNED_TTL")
    # 认证模式：access_key（个人AK/SK）| ram_role（企业AssumeRole+STS）
    oss_auth_mode: str = Field("access_key", env="OSS_AUTH_MODE")
    # RAM Role ARN（oss_auth_mode=ram_role 时必填）
    oss_role_arn: str = Field("", env="OSS_ROLE_ARN")
    oss_role_session_name: str = Field("ppe-giftbox-deploy", env="OSS_ROLE_SESSION_NAME")
    # CDN 域名（设置后 download_url 返回 CDN 地址，而非预签名 URL）
    oss_cdn_domain: str = Field("", env="OSS_CDN_DOMAIN")
    # 公共读直链 base（bucket ACL 改公共读后使用，长期有效链接，不依赖 ttl）
    # 示例：https://ppe-giftbox.oss-cn-beijing.aliyuncs.com
    oss_public_base: Optional[str] = Field(None, env="OSS_PUBLIC_BASE")

    # 摘要存储目录（OCR 全文摘要落地，供飞书上传与目录聚合）
    summary_dir: Path = Field("./data/summaries", env="SUMMARY_DIR")

    # 路径配置
    materials_base: Path = Field("./data/courses", env="MATERIALS_BASE")
    course_reform_notes_dir: Path = Field("./data/course_reform_notes", env="COURSE_REFORM_NOTES_DIR")

    # 知识库配置
    wiki_space_name: str = Field("Demo PPE CloudSmart Giftbox", env="WIKI_SPACE_NAME")

    # 多维表格配置
    bitable_app_token: Optional[str] = Field(None, env="BITABLE_APP_TOKEN")

    # 日志配置
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_to_file: bool = Field(True, env="LOG_TO_FILE")
    log_file_path: Path = Field("./logs/app.log", env="LOG_FILE_PATH")

    # 项目根目录（自动计算：config/settings.py 上溯两级）
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 确保路径是绝对路径
        self.materials_base = self._resolve_path(self.materials_base)
        self.course_reform_notes_dir = self._resolve_path(self.course_reform_notes_dir)
        self.log_file_path = self._resolve_path(self.log_file_path)
        self.cloud_stub_dir = self._resolve_path(self.cloud_stub_dir)
        self.summary_dir = self._resolve_path(self.summary_dir)

    def _resolve_path(self, path: Path) -> Path:
        """解析路径，支持绝对路径和相对于项目根目录的路径"""
        if path.is_absolute():
            return path.resolve()
        return (self.project_root / path).resolve()


# 创建全局配置实例
settings = Settings()