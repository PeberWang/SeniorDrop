# 课程资料智能大礼包

> 把每届学长学姐的课程资料、心得、推荐理由，结构化沉淀下来，传给下一届同学。
>
> 适用任意院校、任意专业。下面以「南开大学 PPE 专业」为示例，你可以替换为自己的专业和课程清单。
>
> 历史版本：[README_v5](docs/README_history/README_v5.md)

---

## 一、这是什么

一句话：**一条「搜集 → 整合 → 分发」的数据管道，部署在飞书云上**。

- **搜集**：学长学姐通过飞书表单提交资料（笔记 / PPT / 真题 / 教材 / 心得），附推荐理由
- **整合**：自动归档到阿里云 OSS；OCR 提取全文；LLM（DeepSeek）按课程生成「学长学姐视角」的学习指南
- **分发**：在飞书知识库生成 4 个学年导航文档，每门课一个独立学习指南文档，所有资料带可点击下载链接

学生端看到的：点开知识库 → 大一/大二/大三/大四 4 个文档 → 点击任意课程的「学习指南」→ 看到 LLM 写好的课程概述 + 推荐资料表 + 资料串讲 + 贡献者致谢，所有资料名都是可点击下载的超链接。

---

## 二、工作原理

```
              [学生表单]                [管理员 UI]
                  │                         │
                  ▼                         ▼
       ┌───────────────────────────────────────────┐
       │  飞书 bitable（三张表，唯一真相源）         │
       │  ├─ 课程主数据表（课程名/老师/学期/类型/考试）│
       │  ├─ 资料管理表（贡献者/课程/类型/理由/附件）│
       │  └─ 心得管理表（作者/课程/成绩/心得）       │
       └──────────────┬────────────────────────────┘
                      │
                      ▼
       ┌───────────────────────────────────────────┐
       │  archive-materials：飞书附件 → 阿里云 OSS  │
       │  ocr-materials：OSS → PDF → OCR → 摘要    │
       │  sync：聚合 bitable 三表 + 双层门控        │
       └──────────────┬────────────────────────────┘
                      │
                      ▼
       ┌───────────────────────────────────────────┐
       │  docs：LLM 生成课程学习指南文档            │
       │  link：回填导航表的「学习指南」字段        │
       └──────────────┬────────────────────────────┘
                      │
                      ▼
                飞书知识库
       4 个学年文档 + N 个课程文档
```

**双层门控（鲁棒性保证）**：
- 学生表单提交的资料，关联的课程**必须**在「课程主数据表」里存在，才会被 sync 聚合 + 进入文档
- 第一层：sync 阶段，发现资料表有课程但主数据表无 → 跳过 + 警告「请管理员在 bitable 加该课」
- 第二层：docs 阶段，CourseDataService 只返回主数据表里存在的课程

这样能挡住学生乱填课程名（拼写错 / 测试 / 没有的课），不会污染文档库。

---

## 三、5 分钟快速开始

### 3.1 准备环境

**必装**：
- Python 3.11+
- [LibreOffice](https://www.libreoffice.org/)（Office 文档转 PDF 用，OCR 流程必需）

**注册账号**：
- 飞书企业版（免费版 50 人内即可），创建一个企业应用
- 阿里云账号，开通 OSS 服务，新建一个 bucket（建议改「公共读」权限）

### 3.2 安装

```bash
git clone <your-repo-url>
cd 课程资料智能大礼包

pip install -r requirements.txt
```

### 3.3 配置 .env

```bash
cp .env.example .env
```

打开 `.env`，填入以下字段（字段含义详见 [04-技术原理.md](docs/04-技术原理.md)）：

```bash
# 飞书（开放平台获取）
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# LLM（DeepSeek，OpenAI 兼容；总论/课程文档/摘要生成）
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-pro

# OCR（智谱 GLM-OCR，layout_parsing 接口）
GLM_API_KEY=xxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxx
GLM_OCR_URL=https://open.bigmodel.cn/api/paas/v4/layout_parsing

# 云盘存储
CLOUD_DRIVE_BACKEND=aliyun_oss
OSS_BUCKET=your-bucket-name
OSS_ENDPOINT=https://oss-cn-beijing.aliyuncs.com
OSS_ACCESS_KEY_ID=LTAIxxxxxxxxxxxxxxxx
OSS_ACCESS_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# 公共读直链（bucket 改公共读后启用，学生长期可下载）
OSS_PUBLIC_BASE=https://your-bucket-name.oss-cn-beijing.aliyuncs.com

# 知识库 + bitable（首次跑 init-bitable 后自动写入 BITABLE_APP_TOKEN）
WIKI_SPACE_NAME=XX 专业课程大礼包
```

### 3.4 首次部署（5 命令）

```bash
# 1. 初始化 bitable（建课程主数据表 + 资料管理表 + 心得管理表）
python deploy.py init-bitable
# 把返回的 app_token 填回 .env 的 BITABLE_APP_TOKEN

# 2. 设置 bitable 链接分享（凭链接即可访问，方便管理员 UI 操作）
python deploy.py open-bitable

# 3. 录入课程清单（Excel/CSV/TSV 均可，自动识别编码 + 分隔符）
#    列名：名称 / 学期 / 授课老师 / 考核方式（类型列可选，默认专业必修课）
python deploy.py seed-course --from-file data/课程清单.xlsx

# 4. 建飞书知识库 + 4 个学年文档 + 内嵌课程导航表
python deploy.py wiki

# 5. 生成每门课的学习指南文档（基于课程基本信息，insights 为空时降级）
python deploy.py docs

# 6. 回填导航表的「学习指南」字段（让链接可点）
python deploy.py link
```

完成后，打开飞书知识库，应能看到 4 个学年文档，每个文档里有这门学年的课程导航表，每行有可点击的「学习指南」链接。

**首次没有资料怎么办？** docs 会基于课程基本信息 + 占位内容生成（串讲段落写「待同学补充」），等你后续通过表单收集资料，重跑 sync + docs + link 就会更新。

---

## 四、日常维护（管理员）

### 4.1 学生通过表单提交了新资料后

学生通过飞书表单填了资料 → 资料管理表多了一条记录（审核状态默认「待审核」）→ 你需要：

```bash
# Step 1：在 bitable UI 把记录的「审核状态」改为「已通过」

# Step 2：跑归档（飞书附件 → OSS）
python deploy.py archive-materials --purge-immediately

# Step 3：跑 OCR + 摘要（PDF/Word/Excel/PPT 自动转 PDF + OCR）
python deploy.py ocr-materials

# Step 4：跑 sync（聚合 bitable + 双层门控 + 更新主数据表派生字段）
python deploy.py sync

# Step 5：重跑 docs + link（让新资料出现在课程文档里）
python deploy.py docs
python deploy.py link
```

**注意**：如果学生表单选的课程不在主数据表里（拼写错或新课），sync 会跳过 + 警告。你需要：
1. 在 bitable UI 课程主数据表加这门课（基本字段：老师 / 学期 / 类型 / 考试）
2. 重跑 sync + docs + link

### 4.2 学生反馈「没有我的课程」

飞书表单单选字段不支持「其他 + 自由填写」。学生下拉里只能选已录入的课。处理流程：

1. 学生通过班委 / 群反馈新课
2. 管理员在 bitable UI 课程主数据表加这门课
3. 学生重新填表单（此时下拉里有了新课）
4. 走 4.1 流程

### 4.3 查日志

```bash
python deploy.py logs              # 查看操作摘要 + 最近 50 条
python deploy.py logs --limit 100  # 查看最近 100 条
```

### 4.4 重置 / 重建（危险！）

```bash
# 清空 bitable 三张表所有记录（保留表结构 + 字段定义）
python deploy.py reset-bitable

# 注意：清空后必须重新 seed-course 录入课程
```

---

## 五、学生使用指南

详见 [02-学生使用指南.md](docs/02-学生使用指南.md)。简要：

1. 收到班委发的表单链接
2. 选课程（下拉，必须是你这学期实际开的课）
3. 填贡献者署名（如「22级小赵」）+ 届别
4. 选资料类型（PPT / 笔记 / 真题 / 教材 / 阅读材料 / 复习大纲 / 练习题 / 其他）
5. 写推荐理由（为什么推荐这份资料？怎么用最有效？给学弟学妹的话）
6. 拖拽文件附件（可以一次拖多份，多份资料共享同一段推荐理由完全 OK）
7. 提交 → 等管理员审核 → 几天后你的资料就出现在课程文档里

---

## 六、进阶配置

详见 [04-技术原理.md](docs/04-技术原理.md)。简要：

- **自定义学年数**：编辑 `config/course_schema.py` 的 `WIKI_YEAR_NODES`
- **自定义学期枚举**：编辑 `SEMESTERS` 列表
- **自定义课程类型**：编辑 `COURSE_TYPES` 列表
- **自定义考试形式**：编辑 `EXAM_TYPES` 列表
- **自定义资料类型**：编辑 `MATERIAL_TYPES` 列表
- **STS 临时凭证**：`.env` 改 `OSS_AUTH_MODE=ram_role` + 配 `OSS_ROLE_ARN`（生产推荐）

---

## 七、故障排查

详见 [03-故障排查.md](docs/03-故障排查.md)。常见问题：

- **OSS AccessDenied**：bucket ACL 改公共读，`.env` 配 OSS_PUBLIC_BASE
- **LibreOffice 未装**：Office 文件 OCR 跳过 + 警告，装 [LibreOffice](https://www.libreoffice.org/) 即可
- **课程文档没生成**：检查 sync 警告，课程主数据表是否有这门课
- **OCR 摘要空**：检查 `.env` 的 `GLM_API_KEY`

---

## 八、技术架构（给好奇的同学）

四层架构：

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

详见 [04-技术原理.md](docs/04-技术原理.md) 和 [CLAUDE.md](CLAUDE.md)。

---

## 九、系列文档

| 文档 | 适合谁 |
|---|---|
| [00-快速开始.md](docs/00-快速开始.md) | 第一次部署的管理员 |
| [01-管理员指南.md](docs/01-管理员指南.md) | 日常运维的同学 |
| [02-学生使用指南.md](docs/02-学生使用指南.md) | 通过表单提交资料的学长学姐 |
| [03-故障排查.md](docs/03-故障排查.md) | 遇到问题时 |
| [04-技术原理.md](docs/04-技术原理.md) | 想理解工作原理、做二次开发的同学 |

---

## 十、贡献者

- 项目设计 + 维护：你的名字 / 团队
- 资料贡献者：每届学长学姐

部署遇到问题？先看 [03-故障排查.md](docs/03-故障排查.md)，再看 [01-管理员指南.md](docs/01-管理员指南.md)。
