# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 统一部署入口

用法:
    python deploy.py full              # 完整部署
    python deploy.py wiki              # 仅创建知识库
    python deploy.py tables            # 创建多维表格
    python deploy.py docs --limit 1    # 生成1份文档
    python deploy.py upload            # 上传资料
    python deploy.py link              # 关联文档链接
    python deploy.py sync              # 增量同步
"""

import asyncio
import sys
from enum import Enum
from typing import Optional

import typer

sys.stdout.reconfigure(encoding='utf-8')

from glue.deploy import DeployArgs, deploy_mode
from config.settings import Settings


class YearFilter(str, Enum):
    """学年过滤器。--year 参数用 Enum 强校验，typer 自动列出可选值，拼写错立刻报错。"""
    大一 = "大一"
    大二 = "大二"
    大三 = "大三"
    大四 = "大四"


app = typer.Typer(help="PPE云端智能大礼包 - 统一部署工具")


async def _run(mode: str, limit: Optional[int] = None, incremental: bool = False,
               year_filter: Optional[str] = None):
    settings = Settings()
    args = DeployArgs(mode=mode, limit=limit, incremental=incremental,
                      year_filter=year_filter)
    return await deploy_mode(settings, args)


@app.command()
def full(year: Optional[YearFilter] = typer.Option(None, "--year", help="仅处理指定学年")):
    """完整部署（知识库 + 表格 + 文档 + 资料 + 关联）"""
    asyncio.run(_run("full", year_filter=year.value if year else None))


@app.command()
def wiki(year: Optional[YearFilter] = typer.Option(None, "--year", help="仅处理指定学年")):
    """仅创建知识库结构"""
    asyncio.run(_run("wiki", year_filter=year.value if year else None))


@app.command()
def tables(
    incremental: bool = typer.Option(False, "--incremental", help="增量更新模式"),
    year: Optional[YearFilter] = typer.Option(None, "--year", help="仅处理指定学年"),
):
    """为每个学年创建多维表格"""
    asyncio.run(_run("tables", incremental=incremental,
                     year_filter=year.value if year else None))


@app.command()
def docs(
    limit: Optional[int] = typer.Option(None, "--limit", help="限制生成文档数量"),
    year: Optional[YearFilter] = typer.Option(None, "--year", help="仅处理指定学年"),
):
    """生成并上传课程学习指南文档"""
    asyncio.run(_run("docs", limit=limit,
                     year_filter=year.value if year else None))


@app.command()
def upload():
    """上传课程资料到飞书云盘"""
    asyncio.run(_run("upload"))


@app.command()
def link(year: Optional[YearFilter] = typer.Option(None, "--year", help="仅处理指定学年")):
    """关联表格与文档链接"""
    asyncio.run(_run("link", year_filter=year.value if year else None))


@app.command()
def sync():
    """增量同步课程记录"""
    asyncio.run(_run("sync"))


@app.command(name="sync-form")
def sync_form():
    """从飞书表单管理表同步已批准记录到 data/db/*.json"""
    asyncio.run(_run("sync-form"))


@app.command(name="init-bitable")
def init_bitable():
    """创建管理用 bitable（资料管理表 + 心得管理表），返回 app_token"""
    asyncio.run(_run("init-bitable"))


@app.command(name="grant-bitable")
def grant_bitable(
    member: str = typer.Argument(..., help="协作者 ID（默认按 email 处理）"),
    member_type: str = typer.Option("email", "--type", "-t",
                                    help="ID 类型：email / openid / userid / departmentid"),
    perm: str = typer.Option("full_access", "--perm", "-p",
                             help="权限：view / edit / full_access"),
):
    """给 bitable 添加协作者（解决应用是 owner 时人没法 UI 操作的问题）"""
    from glue.deploy import _deploy_grant_bitable
    settings = Settings()
    asyncio.run(_deploy_grant_bitable(settings, member_type, member, perm))


@app.command(name="open-bitable")
def open_bitable(
    entity: str = typer.Option(
        "anyone_editable", "--entity", "-e",
        help="链接分享范围：closed / tenant_readable / tenant_editable / anyone_readable / anyone_editable",
    ),
):
    """设置 bitable 链接分享权限（凭链接即可访问，不需要协作者 ID）"""
    from glue.deploy import _deploy_open_bitable
    settings = Settings()
    asyncio.run(_deploy_open_bitable(settings, entity))


@app.command(name="fix-bitable")
def fix_bitable():
    """给已存在 bitable 的单选字段补上选项（不删现有数据）"""
    asyncio.run(_run("fix-bitable"))


@app.command(name="archive-materials")
def archive_materials(
    purge_immediately: bool = typer.Option(
        False, "--purge-immediately",
        help="立即删飞书原件（默认保留 7 天安全期）",
    ),
):
    """飞书附件 → OSS 归档（回填 URL + 删原件）"""
    from glue.deploy import _deploy_archive
    settings = Settings()
    asyncio.run(_deploy_archive(settings, purge_immediately=purge_immediately))


@app.command(name="purge-archived")
def purge_archived(
    older_than_days: int = typer.Option(
        7, "--older-than-days",
        help="清理归档时间早于 N 天的飞书原件（默认 7 天）",
    ),
):
    """清理归档超期的飞书原件（7 天安全期机制）"""
    from glue.deploy import _deploy_purge_archived
    settings = Settings()
    asyncio.run(_deploy_purge_archived(settings, older_than_days=older_than_days))


@app.command(name="reset-bitable")
def reset_bitable(
    yes: bool = typer.Option(False, "--yes", "-y",
                              help="跳过确认提示（脚本调用用）"),
):
    """清空 bitable 三张表所有记录（不可逆！保留表结构 + 字段定义）"""
    if not yes:
        typer.echo("即将清空课程主数据表 + 资料管理表 + 心得管理表的所有记录。")
        typer.echo("这是不可逆操作。加 --yes 跳过此提示。")
        raise typer.Abort()
    from glue.deploy import _deploy_reset_bitable
    settings = Settings()
    asyncio.run(_deploy_reset_bitable(settings))


@app.command(name="seed-course")
def seed_course(
    name: Optional[str] = typer.Option(None, "--name", help="课程名称（单条录入）"),
    semester: Optional[str] = typer.Option(None, "--semester", help="开课学期，如 大二下"),
    course_type: Optional[str] = typer.Option("专业必修课", "--type", help="课程类型"),
    exam: Optional[str] = typer.Option("其他", "--exam", help="考试形式：闭卷/开卷/论文/其他"),
    teacher: str = typer.Option("", "--teacher", help="授课老师"),
    from_file: Optional[str] = typer.Option(None, "--from-file",
                                             help="批量导入：Excel/CSV/TSV 文件路径"),
):
    """录课程到主数据表。

    单条：python deploy.py seed-course --name 概率论与数理统计 --semester 大二下 --teacher 刘会刚 --exam 闭卷

    批量：python deploy.py seed-course --from-file data/课程清单.xlsx
    """
    from glue.deploy import _deploy_seed_course
    settings = Settings()
    asyncio.run(_deploy_seed_course(
        settings, name=name, semester=semester,
        course_type=course_type, exam=exam, teacher=teacher,
        from_file=from_file,
    ))


@app.command(name="seed-materials")
def seed_materials(
    local_dir: str = typer.Argument(..., help="本地资料目录（递归扫描所有文件）"),
    course_name: str = typer.Argument(..., help="关联课程名（必须已在主数据表中）"),
    contributor: str = typer.Option("管理员", "--contributor", help="贡献者署名"),
    grade: str = typer.Option("", "--grade", help="届别，如 22级"),
    material_type: str = typer.Option("其他", "--type",
                                       help="资料类型：PPT/笔记/真题/教材/..."),
    reason: str = typer.Option("", "--reason", help="推荐理由（一对多：本批次所有文件共享）"),
):
    """批量录入 raw 学习资料：扫本地文件夹 → 飞书 drive → 资料管理表。

    示例：
      python deploy.py seed-materials "data/courses/大二上/概率论与数理统计（刘会刚老师）" 概率论与数理统计 --grade 22级 --reason "初始录入测试资料"
    """
    from glue.deploy import _deploy_seed_materials
    settings = Settings()
    asyncio.run(_deploy_seed_materials(
        settings, local_dir, course_name,
        contributor=contributor, grade=grade,
        material_type=material_type, reason=reason,
    ))


@app.command(name="ocr-materials")
def ocr_materials_cmd():
    """OCR + 摘要：扫资料表已归档记录 → OSS 下载 → 转 PDF → GLM-OCR → LLM 摘要 → 回填 summary"""
    from glue.deploy import _deploy_ocr_materials
    settings = Settings()
    asyncio.run(_deploy_ocr_materials(settings))


@app.command()
def logs(limit: int = typer.Option(50, "--limit", help="显示最近 N 条日志")):
    """显示操作日志摘要和最近记录"""
    from libs.operation_log import recent_operations, operation_summary

    summary = operation_summary()
    typer.echo(f"总操作: {summary['total']}  失败: {summary['failed_count']}")
    if summary["by_operation"]:
        typer.echo("\n按操作统计:")
        for op, counts in sorted(summary["by_operation"].items()):
            typer.echo(f"  {op}: {counts['total']} 次, {counts['failed']} 次失败")

    entries = recent_operations(limit)
    if entries:
        typer.echo(f"\n最近 {len(entries)} 条:")
        for e in entries:
            status_icon = "[OK]" if e.get("status") == "ok" else ("[FAIL]" if e.get("status") == "failed" else "[..]")
            elapsed = f" ({e.get('elapsed_s', '')}s)" if e.get("elapsed_s") else ""
            typer.echo(f"  {status_icon} {e.get('operation','?')}{elapsed} — {e.get('started_at','?')}")


if __name__ == "__main__":
    app()
