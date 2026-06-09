# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 资料上传服务
负责将本地资料文件上传到飞书云盘
"""

import structlog
import os
import json
from typing import Dict, List, Optional, Any

from libs.feishu import FeishuAdapter
from libs.cloud.base import CloudDriveAdapter
from libs.storage_path import raw_material_key

logger = structlog.get_logger()


class MaterialService:
    """资料上传服务 — 支持 OSS（推荐）和飞书 Drive（向后兼容）两种上传后端。"""

    def __init__(self, feishu: FeishuAdapter,
                 cloud: CloudDriveAdapter = None,
                 settings=None):
        self.feishu = feishu
        self.cloud = cloud
        self.settings = settings
        self.uploaded_files: Dict[str, Dict] = {}
        self._material_manifests: Dict[str, List[Dict]] = {}

    async def upload_file(self, file_path: str, course_name: str = "",
                          material_type: str = "", contributor: str = "",
                          custom_name: Optional[str] = None) -> Dict[str, str]:
        """上传单个文件到云盘（OSS 优先，回退飞书 Drive）。"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")

            file_name = custom_name or os.path.basename(file_path)

            if self.cloud:
                # OSS 路径上传
                oss_key = raw_material_key(course_name or "general", file_name)
                await self.cloud.upload(file_path, oss_key)
                download_url = await self.cloud.download_url(oss_key)
                result = {"file_key": oss_key, "url": download_url, "backend": "oss"}
                logger.info("文件上传到 OSS", file_path=file_path, oss_key=oss_key)
            else:
                # 回退：飞书 Drive 上传
                logger.info("上传文件到飞书 Drive", file_path=file_path, file_name=file_name)
                result = await self.feishu.upload_file(file_path, file_name)
                result["backend"] = "feishu"

            file_key = result["file_key"]
            self.uploaded_files[file_key] = {
                "file_path": file_path,
                "course_name": course_name,
                "material_type": material_type,
                "contributor": contributor,
                "url": result["url"],
                "backend": result.get("backend", "feishu"),
            }

            # 累积按课程分组的资料清单（供 DocService 使用）
            if course_name:
                if course_name not in self._material_manifests:
                    self._material_manifests[course_name] = []
                self._material_manifests[course_name].append({
                    "name": custom_name or os.path.basename(file_path),
                    "material_type": material_type,
                    "contributor": contributor,
                    "file_link": result["url"],
                })

            logger.info("文件上传成功", file_path=file_path, file_key=file_key)
            return result

        except Exception as e:
            logger.error("文件上传失败", file_path=file_path, error=str(e))
            raise

    async def upload_course_files(
        self,
        course_name: str,
        file_paths: List[str],
        course_dir: Optional[str] = None,
        material_meta: List[Dict] = None,
    ) -> Dict[str, Any]:
        """批量上传课程文件。material_meta 可为每个文件提供 {name, type, contributor}。"""
        results = []
        errors = []
        meta_list = material_meta or []

        if course_dir and os.path.isdir(course_dir):
            logger.info("上传课程目录下的所有文件", course_name=course_name, course_dir=course_dir)
            for root, dirs, files in os.walk(course_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, course_dir)
                    try:
                        result = await self.upload_file(file_path, course_name)
                        results.append({"file_path": file_path, "relative_path": relative_path, **result})
                    except Exception as e:
                        errors.append({"file_path": file_path, "error": str(e)})

        for i, file_path in enumerate(file_paths):
            try:
                meta = meta_list[i] if i < len(meta_list) else {}
                result = await self.upload_file(
                    file_path, course_name,
                    material_type=meta.get("type", ""),
                    contributor=meta.get("contributor", ""),
                    custom_name=meta.get("name"),
                )
                results.append({"file_path": file_path, **result})
            except Exception as e:
                errors.append({"file_path": file_path, "error": str(e)})

        return {
            "course_name": course_name,
            "total_files": len(file_paths) + (len(os.listdir(course_dir)) if course_dir else 0),
            "success_count": len(results), "error_count": len(errors),
            "results": results, "errors": errors,
        }

    async def upload_materials_from_config(self, config_path: str) -> Dict[str, Any]:
        """从配置文件上传所有课程的资料"""
        try:
            # 读取配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            materials_data = config.get("materials", {})
            logger.info("读取配置文件", file_path=config_path, course_count=len(materials_data))

            all_results = []
            all_errors = []
            total_file_count = 0

            # 为每个课程上传资料
            for course_name, materials in materials_data.items():
                try:
                    logger.info("上传课程资料", course_name=course_name, material_count=len(materials))

                    # 收集文件路径
                    file_paths = []
                    for material in materials:
                        file_path = material.get("path")
                        if file_path and os.path.exists(file_path):
                            file_paths.append(file_path)
                        else:
                            logger.warning("文件不存在", course_name=course_name, path=file_path)
                            all_errors.append({
                                "course_name": course_name,
                                "material": material,
                                "error": "文件不存在"
                            })

                    total_file_count += len(file_paths)

                    if file_paths:
                        result = await self.upload_course_files(
                            course_name, file_paths, material_meta=materials
                        )
                        all_results.append(result)

                        # 为每个资料添加原始配置信息
                        for i, result_item in enumerate(result.get("results", [])):
                            if i < len(materials):
                                result_item["type"] = materials[i].get("type")
                                result_item["original_name"] = materials[i].get("name")
                    else:
                        logger.warning("没有可上传的文件", course_name=course_name)
                        all_errors.append({
                            "course_name": course_name,
                            "error": "没有可上传的文件"
                        })

                except Exception as e:
                    logger.error("课程资料上传失败", course_name=course_name, error=str(e))
                    all_errors.append({
                        "course_name": course_name,
                        "error": str(e)
                    })

            return {
                "total_courses": len(materials_data),
                "successful_courses": len([r for r in all_results if r["error_count"] == 0]),
                "total_files": total_file_count,
                "total_success": sum(r["success_count"] for r in all_results),
                "total_errors": len(all_errors),
                "results": all_results,
                "errors": all_errors
            }

        except FileNotFoundError:
            logger.error("配置文件不存在", file_path=config_path)
            return {
                "status": "error",
                "message": f"配置文件不存在: {config_path}"
            }
        except json.JSONDecodeError as e:
            logger.error("配置文件格式错误", file_path=config_path, error=str(e))
            return {
                "status": "error",
                "message": f"配置文件格式错误: {str(e)}"
            }
        except Exception as e:
            logger.error("上传资料失败", error=str(e))
            return {
                "status": "error",
                "message": f"上传资料失败: {str(e)}"
            }

    async def link_materials_to_tables(self, app_token: str, space_id: str = None) -> Dict[str, Any]:
        """将上传的资料链接到多维表格"""
        try:
            logger.info("开始关联资料到表格")

            results = []
            errors = []
            course_materials_map = {}

            # 按课程分组整理上传的资料
            for file_key, file_info in self.uploaded_files.items():
                course_name = file_info["course_name"]
                if course_name:
                    if course_name not in course_materials_map:
                        course_materials_map[course_name] = []
                    course_materials_map[course_name].append({
                        "file_key": file_key,
                        "url": file_info["url"],
                        "type": file_info.get("type", "其他")
                    })

            # 为每个课程更新表格记录
            for course_name, materials in course_materials_map.items():
                try:
                    logger.info("更新课程资料", course_name=course_name, material_count=len(materials))

                    # 查找课程记录
                    record = await self.feishu.search_bitable_record(
                        app_token=app_token,
                        table_id=None,  # 需要确定哪个表格
                        field_name="课程名称",
                        value=course_name
                    )

                    if not record:
                        logger.warning("未找到课程记录", course_name=course_name)
                        errors.append({
                            "course_name": course_name,
                            "error": "未找到课程记录"
                        })
                        continue

                    # 计算资料数量
                    material_count = len(materials)

                    # 准备更新的字段
                    update_fields = {"资料数量": material_count}

                    # 如果有资料链接，构建链接列表
                    if materials:
                        material_links = []
                        for material in materials:
                            material_links.append(f"[{material['type']}]({material['url']})")
                        update_fields["资料列表"] = "\n".join(material_links)

                    # 更新记录
                    update_result = await self.feishu.update_bitable_record(
                        app_token=app_token,
                        table_id=record["table_id"],
                        record_id=record["record_id"],
                        fields=update_fields
                    )

                    results.append({
                        "course_name": course_name,
                        "record_id": record["record_id"],
                        "material_count": material_count,
                        "updated_fields": list(update_fields.keys())
                    })

                    logger.info("资料关联成功", course_name=course_name, record_id=record["record_id"])

                except Exception as e:
                    logger.error("课程资料关联失败", course_name=course_name, error=str(e))
                    errors.append({
                        "course_name": course_name,
                        "error": str(e)
                    })

            logger.info("资料关联完成", success_count=len(results), error_count=len(errors))
            return {
                "total_updates": len(results),
                "success_count": len(results),
                "error_count": len(errors),
                "results": results,
                "errors": errors
            }

        except Exception as e:
            logger.error("关联资料到表格失败", error=str(e))
            return {
                "status": "error",
                "message": f"关联资料到表格失败: {str(e)}"
            }

    def get_upload_record(self, file_key: str) -> Optional[Dict]:
        """获取文件上传记录"""
        return self.uploaded_files.get(file_key)

    def get_course_files(self, course_name: str) -> List[Dict]:
        """获取指定课程的所有上传文件"""
        return [info for info in self.uploaded_files.values() if info["course_name"] == course_name]

    def get_material_manifests(self) -> Dict[str, List[Dict]]:
        """获取按课程分组的资料清单 {course_name: [{name, material_type, contributor, file_link}, ...]}。

        供 DocService 在构建课程文档的数据表格时使用。
        """
        return dict(self._material_manifests)