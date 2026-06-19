# -*- coding: utf-8 -*-
"""阿里云 OSS 后端 — 通过 oss2 SDK 实现 CloudDriveAdapter。

认证模式:
    access_key  — 个人/开发期，AK+SK 直接鉴权
    ram_role    — 企业/交付期，AssumeRole 获取 STS 临时凭证（无永久密钥落地）

下载策略（优先级从高到低）:
    1. OSS_PUBLIC_BASE → 纯直链 URL（bucket 改公共读后使用，长期有效，学生随时可访问）
    2. OSS_CDN_DOMAIN → CDN 稳定 URL（企业交付推荐）
    3. 未设置 → 返回预签名 URL（OSS_PRESIGNED_TTL 控制有效期，默认 86400s，过期失效）
"""

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime

import oss2

from libs.cloud.base import CloudDriveAdapter
from libs.exceptions import FileUploadException


class AliyunOSSDrive(CloudDriveAdapter):
    """阿里云 OSS 云盘适配器。"""

    def __init__(self, bucket: str, endpoint: str,
                 auth_mode: str = "access_key",
                 access_key_id: str = "", access_key_secret: str = "",
                 role_arn: str = "", role_session_name: str = "ppe-giftbox-deploy",
                 presigned_ttl: int = 86400, cdn_domain: str = "",
                 public_base: str = ""):
        self.presigned_ttl = presigned_ttl
        self.cdn_domain = cdn_domain
        self.public_base = public_base

        if auth_mode == "access_key":
            if not access_key_id or not access_key_secret:
                raise ValueError("access_key 模式需要 OSS_ACCESS_KEY_ID 和 OSS_ACCESS_KEY_SECRET")
            auth = oss2.Auth(access_key_id, access_key_secret)
        elif auth_mode == "ram_role":
            creds = self._assume_role(access_key_id, access_key_secret,
                                      role_arn, role_session_name)
            auth = oss2.StsAuth(creds["access_key_id"],
                                creds["access_key_secret"],
                                creds["security_token"])
        else:
            raise ValueError(f"不支持的认证模式: {auth_mode}（可选: access_key, ram_role）")

        self._auth_mode = auth_mode
        self._role_arn = role_arn
        self._role_session_name = role_session_name
        self._long_term_ak = access_key_id
        self._long_term_sk = access_key_secret
        self._sts_expire_at: float = 0
        self.bucket = oss2.Bucket(auth, endpoint, bucket)

    # ------------------------------------------------------------------
    # STS AssumeRole（仅 ram_role 模式）
    # 基于阿里云 API 签名 V1 协议，无额外 SDK 依赖
    # ------------------------------------------------------------------

    def _assume_role(self, ak: str, sk: str, role_arn: str, session_name: str) -> dict:
        """通过 AssumeRole 获取临时 STS 凭证（有效期 3600s）。"""
        if not role_arn:
            raise ValueError("ram_role 模式需要 OSS_ROLE_ARN")

        params = {
            "Action": "AssumeRole",
            "RoleArn": role_arn,
            "RoleSessionName": session_name,
            "DurationSeconds": "3600",
            "Format": "JSON",
            "Version": "2015-04-01",
            "AccessKeyId": ak,
            "SignatureMethod": "HMAC-SHA1",
            "SignatureVersion": "1.0",
            "SignatureNonce": str(int(time.time() * 1000000)),
            "Timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        params["Signature"] = self._sign("GET", params, sk)

        url = "https://sts.aliyuncs.com/?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        creds = data["Credentials"]
        self._sts_expire_at = time.time() + 3300  # 提前 5 分钟刷新
        return {
            "access_key_id": creds["AccessKeyId"],
            "access_key_secret": creds["AccessKeySecret"],
            "security_token": creds["SecurityToken"],
        }

    @staticmethod
    def _sign(method: str, params: dict, secret: str) -> str:
        """阿里云 API 签名 V1（HMAC-SHA1 + Base64）。"""
        sorted_params = sorted(params.items())
        canon = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
            for k, v in sorted_params
        )
        sign_str = f"{method}&{urllib.parse.quote('/', safe='')}&{urllib.parse.quote(canon, safe='')}"
        key = (secret + "&").encode("utf-8")
        return base64.b64encode(hmac.new(key, sign_str.encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")

    # ------------------------------------------------------------------
    # CloudDriveAdapter 接口
    # ------------------------------------------------------------------

    async def upload(self, src_path: str, dest_name: str = "") -> str:
        name = dest_name or os.path.basename(src_path)
        try:
            self.bucket.put_object_from_file(name, src_path)
        except oss2.exceptions.OssError as e:
            raise FileUploadException(f"OSS 上传失败 [{name}]: {e}")
        return name

    async def download_url(self, key: str) -> str:
        if self.public_base:
            return f"{self.public_base.rstrip('/')}/{key}"
        if self.cdn_domain:
            return f"https://{self.cdn_domain}/{key}"
        return self.bucket.sign_url("GET", key, self.presigned_ttl)

