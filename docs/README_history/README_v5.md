# PPE云端智能大礼包

> 南开大学PPE专业课程资料智能管理与分发系统
>
> 历史版本：[README_v4](docs/README_history/README_v4.md)

---

## 产品定位

**搜集 → 整合 → 分发。**

大礼包本质是一条数据管道：
1. **搜集**：通过飞书表单采集学长学姐的课程心得与推荐资料，SyncService 自动同步到本地数据库
2. **整合**：以 `data/db/*.json`（`CourseData` 结构）作为源真相，LLM（DeepSeek）提炼与组织内容
3. **分发**：自动在飞书知识库生成可读性强的「学年文档 + 内嵌课程导航表 + 独立课程学习指南」

---

## 知识库结构

```
知识库 Space
├── 大一 (docx 节点) — 总论 + 内嵌 nav 表（大一所有课程，每行一门）
├── 大二 (docx 节点) — 总论 + 内嵌 nav 表
├── 大三 (docx 节点) — 总论 + 内嵌 nav 表
└── 大四 (docx 节点) — 总论 + 内嵌 nav 表
        nav 表「学习指南」字段链接到 ↓
课程独立文档 (docx，非知识库节点)：6段结构
  1. 课程内容概述
  2. 学习难点与应对策略
  3. 老师教学风格与偏好
  4. 推荐资料（含贡献者）
  5. 学长学姐心得
  6. 贡献者致谢 + 资料下载区（云盘链接）
```

---

## 数据流

```
data/db/*.json  (CourseData 源真相，Pydantic 校验)
      │
      ├──► 前台 nav 多维表格（每学年一张）──内嵌──► 学年文档
      ├──► 课程学习指南文档（6段，DeepSeek 生成）
      └──► 三级存储链路
            源文件 + OCR全文 → 云盘（现：LocalStubDrive 占位）
            摘要(md)         → 飞书云盘
            摘要目录          → 飞书云盘（供知识助手问答）
```

---

## 快速开始

**环境要求**：Python 3.11+，飞书企业应用（机器人权限）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 填写：FEISHU_APP_ID、FEISHU_APP_SECRET、BITABLE_APP_TOKEN
#       LLM_API_KEY（DeepSeek）、GLM_API_KEY（OCR，可选）

# 3. 生成模拟数据（首次）
python scripts/seed_course_db.py

# 4. 部署
python deploy.py --mode full
```

---

## 部署模式

| 命令 | 说明 |
|------|------|
| `--mode wiki` | 创建/复用 4 个学年 docx 知识库节点，内嵌 nav 多维表格，保存 deploy_state.json |
| `--mode tables` | 独立重建各学年 nav 多维表格（不需要知识库） |
| `--mode docs` | 生成课程学习指南文档，回填 nav 表「学习指南」链接，追加学年总论 |
| `--mode docs --limit N` | 仅生成前 N 份文档（测试用，跳过总论追加） |
| `--mode upload` | 上传本地资料到飞书云盘 |
| `--mode link` | 将 doc_url 回填到 nav 表（若文档已存在） |
| `--mode ocr` | 扫描 materials_base 下 PDF，走三级存储链路（OCR + 摘要 + 上传） |
| `--mode catalog` | 聚合 data/summaries/ 下摘要，生成资料目录并上传飞书 |
| `--mode full` | 完整流程：wiki + tables + docs + upload + link |
| `--mode sync` | 全量重建多维表格 |
| `--mode sync-form` | 从管理表拉取已批准记录 → 合并到 data/db/*.json |
| `logs` | 查看操作日志摘要与最近记录 |

---

## 关键配置

| 变量 | 说明 | 默认 |
|------|------|------|
| `FEISHU_APP_ID` | 飞书应用 ID | 必填 |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | 必填 |
| `BITABLE_APP_TOKEN` | 多维表格 App Token | 可选 |
| `LLM_API_KEY` | DeepSeek API Key | 必填 |
| `LLM_BASE_URL` | LLM 接入点（OpenAI 兼容） | `https://api.deepseek.com` |
| `LLM_MODEL` | 使用的模型 | `deepseek-v4-pro` |
| `GLM_API_KEY` | 智谱 API Key（OCR 用） | 可选 |
| `FEISHU_DOC_HOST` | 文档链接域名（企业部署填 xyz.feishu.cn） | `feishu.cn` |
| `WIKI_SPACE_NAME` | 知识空间名称 | `Demo PPE CloudSmart Giftbox` |
| `CLOUD_DRIVE_BACKEND` | 云盘后端（local_stub / aliyun_oss） | `local_stub` |

---

## 四层架构

```
deploy.py (CLI 入口，typer)
    ↓
glue/         — 编排层：串联 services，零业务逻辑
    ↓
services/     — 业务层：功能单元，调用 libs
    ↓
libs/         — 适配层：封装第三方库差异
    ↓
config/       — 配置 + 数据模型
```

严格单向：glue → services → libs → config，同级不互通。

---

## 课程数据管理

**源真相**：`data/db/{学年}.json`，每条记录为 `CourseData` 对象（含心得、资料、贡献者）。

```bash
# 初始化 / 重置演示数据
python scripts/seed_course_db.py

# 添加真实心得（编辑 data/db/ 对应 json 文件，遵守 CourseData schema）
```

**前台 nav 表字段**：课程名称 / 授课老师 / 开课学期 / 课程类型 / 考试形式 / 学习指南（URL）/ 资料数量 / 最后更新

---

## 飞书应用权限

部署前需在飞书开放平台为应用开通：

- `wiki:wiki`（知识库读写）
- `docx:document`（文档读写）
- `bitable:app`（多维表格读写）
- `drive:drive`（云盘上传）
- `drive:media:upload`（媒体上传）

内嵌多维表格的学年文档还需将应用手动添加为文档协作者（运营步骤，首次部署后操作一次）。

---

---

## 贡献者

- 铭培（产品设计与需求）
- 南开大学PPE专业全体同学（资料贡献者）
