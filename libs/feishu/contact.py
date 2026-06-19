# -*- coding: utf-8 -*-
"""飞书通讯录模块 - 基于 lark-oapi SDK

主要用途：把 email / mobile 转 openid/userid（wiki API 的 add_member 只接受 openid）。
"""

from typing import Dict, List, Optional
from lark_oapi.api.contact.v3 import (
    BatchGetIdUserRequest,
    BatchGetIdUserRequestBody,
)

from libs.exceptions import FeishuAPIException


class ContactMixin:
    """通讯录查询操作"""

    async def batch_get_user_id(self, *, emails: List[str] = None,
                                 mobiles: List[str] = None) -> Dict[str, Dict[str, str]]:
        """通过 email 或 mobile 批量查 user_id / open_id。

        返回：{"邮箱或手机号": {"user_id": "...", "open_id": "..."}, ...}
        查不到的 email/mobile 不在返回 dict 里。

        emails 和 mobiles 至少传一个。
        """
        emails = emails or []
        mobiles = mobiles or []
        if not emails and not mobiles:
            raise ValueError("emails 和 mobiles 至少传一个")

        body_builder = BatchGetIdUserRequestBody.builder()
        if emails:
            body_builder = body_builder.emails(emails)
        if mobiles:
            body_builder = body_builder.mobiles(mobiles)

        req = (BatchGetIdUserRequest.builder()
               .request_body(body_builder.build())
               .build())
        resp = await self.client.contact.v3.user.abatch_get_id(req)
        if not resp.success():
            raise FeishuAPIException(
                f"batch_get_user_id 失败: {resp.msg}", error_code=str(resp.code))

        # 解析返回：user_list = [{"user_id": ..., "open_id": ..., "email": ..., "mobile": ...}]
        result: Dict[str, Dict[str, str]] = {}
        for item in (resp.data.user_list or []):
            uid = item.open_id or ""
            email = item.email or ""
            mobile = item.mobile or ""
            user_id = item.user_id or ""
            if not uid:
                continue  # 未找到对应用户
            entry = {"open_id": uid, "user_id": user_id}
            if email:
                result[email] = entry
            if mobile:
                result[mobile] = entry
        return result

    async def resolve_to_openid(self, member_type: str, member_id: str) -> str:
        """把 email / mobile 转 openid。openid/userid 直接返回。

        member_type: "email" / "mobile" / "openid" / "userid" / "departmentid"
        member_id: 对应的值

        返回 openid（如果原样是 openid 则原样返回）。
        如果查不到用户，抛 FeishuAPIException。
        """
        if member_type == "openid":
            return member_id
        if member_type == "email":
            data = await self.batch_get_user_id(emails=[member_id])
        elif member_type == "mobile":
            data = await self.batch_get_user_id(mobiles=[member_id])
        else:
            raise ValueError(f"不支持的 member_type: {member_type}（contact 仅支持 email/mobile/openid）")

        entry = data.get(member_id)
        if not entry or not entry.get("open_id"):
            raise FeishuAPIException(
                f"无法把 {member_type}={member_id} 解析为 openid，用户可能不在飞书企业内")
        return entry["open_id"]
