# -*- coding: utf-8 -*-
from libs.cloud.base import CloudDriveAdapter
from libs.cloud.stub import LocalStubDrive
from libs.cloud.oss import AliyunOSSDrive


def get_drive(settings) -> CloudDriveAdapter:
    """工厂：按 settings.cloud_drive_backend 返回对应适配器。"""
    if settings.cloud_drive_backend == "local_stub":
        return LocalStubDrive(settings.cloud_stub_dir)
    if settings.cloud_drive_backend == "aliyun_oss":
        return AliyunOSSDrive(
            bucket=settings.oss_bucket,
            endpoint=settings.oss_endpoint,
            auth_mode=settings.oss_auth_mode,
            access_key_id=settings.oss_access_key_id,
            access_key_secret=settings.oss_access_key_secret,
            role_arn=settings.oss_role_arn,
            role_session_name=settings.oss_role_session_name,
            presigned_ttl=settings.oss_presigned_ttl,
            cdn_domain=settings.oss_cdn_domain,
            public_base=settings.oss_public_base or "",
        )
    raise ValueError(f"未知云盘后端: {settings.cloud_drive_backend}")


__all__ = ["CloudDriveAdapter", "LocalStubDrive", "AliyunOSSDrive", "get_drive"]
