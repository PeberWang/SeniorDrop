# 自动化知识库（基于飞书 Drive 和阿里云 OSS）

> 把每届学长学姐的课程资料、心得、推荐理由，自动化和结构化地沉淀下来，弱化专业传承活动的激励问题。
>
> 适用任意院校的任意专业。

---

## 一、这是什么

一句话：**一条「搜集 → 整合 → 分发」的数据管道**。

- **搜集**：学长学姐通过飞书表单提交资料，附推荐理由
- **整合**：自动归档到阿里云 OSS；OCR 提取全文为 Markdown 格式，并调用 LLM 形成摘要；LLM 基于摘要、推荐理由、心得形成课程学习指南文档，文中埋入资料原件下载链接，阅读过程中可直接点击链接下载原件
- **分发**：在飞书知识库生成以学年为单位的导航文档，导航文档内列出归属于该学年的课程学习指南

## 使用端体验

点开知识库 → 大一/大二/大三/大四等若干学年导航文档 → 点击任意课程的「学习指南」→ 看到 LLM 写好的课程概述 + 推荐资料表 + 资料综述 + 贡献者致谢 → 读指南的过程中感到某份资料对自己有用，点击埋入资料名或贡献者名字的超链接，下载资料原件至本机。

## 工作原理

学生通过飞书表单提交资料 → 资料/心得数据入库于飞书 bitable → 资料原件/心得原件经由 `archive-materials` 归档到阿里云 OSS → 调用 `ocr-materials` 命令提取原件全文为 Markdown 格式 + 形成 LLM 摘要 → 调用 `sync` 命令将摘要存至飞书 Drive，并将原件下载链接回填至飞书 bitable → 调用 `docs` 命令用生成课程学习指南（飞书云文档） → 调用 `link` 命令把云文档链接回填到学年导航表。

---

## 三、快速开始

### 3.1 准备环境（约 30-60 分钟）

分两步走：**先在本地电脑装好运行环境，再注册 4 个云账号拿访问凭证**。

**第一步：本地准备**

1. **打开命令行，下载项目代码**

   这个项目全程要在命令行里跑命令，所以第一步先把命令行打开。

   **Windows**：用文件管理器打开你想存放项目的文件夹（比如 `D:\projects`），点上方地址栏（显示路径那个长条），把内容全选删掉，输入 `cmd` 回车——命令行就开在这个文件夹里了。

   **macOS / Linux**：打开终端，用 `cd` 切到你想放的目录。

   命令行打开后，跑：

   ```bash
   git clone https://github.com/PeberWang/PPE-CloudSmart-GiftBox.git
   cd PPE-CloudSmart-GiftBox
   ```

   提示「git 不是内部或外部命令」？系统没装 git，去 https://git-scm.com/downloads 下载安装包装一下，装完**关闭当前命令行窗口重新打开**（让 PATH 生效），再跑上面的命令。

   > 不建议走 GitHub 页面的「Download ZIP」按钮——看起来省事，其实解压完还是要打开命令行跑下面的 `setup.bat`，并没省步骤；后续双击 `update.bat` 自动更新也用不了（每次更新都得重新下载、解压、覆盖）。所以即使要花一两分钟装 git，也建议走 git 这条路。

   截图级步骤见 [00 § 2.1](docs/00-快速开始.md#21-下载代码)。

2. **在项目目录里跑一行命令**，自动检查 Python、装虚拟环境、装 LibreOffice、装依赖、生成 `.env` 配置文件

   已经 cd 进项目目录的话，直接打：

   Windows（cmd 或 PowerShell）：
   ```cmd
   setup.bat
   ```

   macOS / Linux：
   ```bash
   bash setup.sh
   ```

   Python 没装或版本太旧（< 3.10）？脚本会自动打开下载页引导你装。**下载安装包运行安装程序时，务必勾选安装界面底部的「Add Python.exe to PATH」**（漏勾的话命令行还是找不到 python），装完重新跑一次 `setup.bat` 即可。脚本逻辑和排错见 [00 § 2.2](docs/00-快速开始.md#22-一键装所有依赖--配置推荐)。

**第二步：注册 4 个云账号拿凭证**：

按 [00 § 1.1-1.4](docs/00-快速开始.md#一准备账号--装环境) 操作，每个账号都有截图级菜单路径 + 关键提醒（OSS bucket 选公共读、AccessKey Secret 立刻复制保存等）：

| 账号 | 用途 | 拿到什么 |
|---|---|---|
| 飞书企业版 | 知识库 + bitable 载体 | App ID + App Secret |
| 阿里云 OSS | 资料归档存储 | AK + SK + bucket 名 + endpoint |
| DeepSeek | LLM（生成课程文档 + 摘要） | API Key |
| 智谱 GLM-OCR | OCR API | API Key |

### 3.2 配置 .env

setup 脚本已经帮你创建了 `.env` 文件。用记事本打开它，按 [00 § 三](docs/00-快速开始.md#三配置-env-文件) 填入凭证。

关键字段（字段含义详见 [04-技术原理.md](docs/04-技术原理.md)）：

```bash
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx                  # 飞书应用 ID
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx   # 飞书应用 Secret
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx      # DeepSeek API Key
GLM_API_KEY=xxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxx        # 智谱 GLM API Key
OSS_BUCKET=your-bucket-name                          # 你的 OSS bucket 名
OSS_ENDPOINT=https://oss-cn-beijing.aliyuncs.com     # 你的 OSS endpoint
OSS_ACCESS_KEY_ID=LTAIxxxxxxxxxxxxxxxx               # 阿里云 AK
OSS_ACCESS_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx# 阿里云 SK
OSS_PUBLIC_BASE=https://your-bucket-name.oss-cn-beijing.aliyuncs.com  # 公共读直链
WIKI_SPACE_NAME=XX 专业课程大礼包                   # 你的专业名
# BITABLE_APP_TOKEN 先留空，下一步 init-bitable 后填回
```

### 3.3 首次部署（7 命令）

**每次跑命令前先双击 `start.bat`**（Windows）或跑 `bash start.sh`（macOS/Linux）。这个脚本会激活虚拟环境，弹出一个已经准备好跑 python 命令的终端窗口。

在激活的终端里按顺序跑：

```bash
# 1. 初始化 bitable（建课程主数据表 + 资料管理表 + 心得管理表）
python deploy.py init-bitable
# 把返回的 app_token 填回 .env 的 BITABLE_APP_TOKEN，保存 .env
# 同时把返回的 bitable URL 发到飞书群保存（之后管理员想编辑 bitable 都靠这个链接）

# 2. 设置 bitable 链接分享（凭链接即可访问，方便管理员 UI 操作）
python deploy.py open-bitable

# 3. 录入课程清单
```

准备课程清单 Excel/CSV/TSV 文件。**直接填文字**，不要在 Excel 里创建下拉列表。每列填法：

| 列名 | 是否必填 | 合法值 |
|---|---|---|
| 名称 | 必填 | 课程全称，如「概率论与数理统计」 |
| 学期 | 必填 | `大一上` / `大一下` / `大二上` / `大二下` / `大三上` / `大三下` / `大四上` / `大四下`（8 个值之一，必须精确匹配） |
| 授课老师 | 可空 | 老师姓名，如「刘会刚」 |
| 考核方式 | 可空 | `闭卷` / `开卷` / `论文` / `其他`（4 个值之一，必须精确匹配） |
| 类型 | 可空 | `专业必修课` / `非专业必修课`（2 个值之一；不填默认专业必修课） |

示例（Excel 表格长这样）：

| 名称 | 学期 | 授课老师 | 考核方式 | 类型 |
|---|---|---|---|---|
| 概率论与数理统计 | 大二下 | 刘会刚 | 闭卷 | 专业必修课 |
| 微观经济学 | 大一上 |  | 闭卷 | 专业必修课 |

存为 `data/课程清单.xlsx`（或 .csv / .tsv），然后跑：

```bash
# 批量录入
python deploy.py seed-course --from-file data/课程清单.xlsx

# 或单条录入
python deploy.py seed-course --name 概率论与数理统计 --semester 大二下 --teacher 刘会刚 --exam 闭卷
```

```bash
# 4. 建飞书知识库 + 4 个学年文档 + 内嵌课程导航表
python deploy.py wiki
# 把返回的 wiki URL 发到飞书群保存（之后管理员想编辑知识库都靠这个链接）

# 5. 给自己（管理员）加知识库权限（重要！否则 UI 里没法编辑）
python deploy.py grant-wiki 你的邮箱@example.com
# 默认 admin 角色；想给只读权限加 --perm viewer
#
# 邮箱注册 → grant-wiki your-email@example.com
# 手机号注册 → grant-wiki 13800138000 --type mobile
# 知道 openid/userid → grant-wiki ou_xxxxx --type openid

# 或者用更简单的 open-wiki（凭链接即可编辑，不需要协作者 ID）
# python deploy.py open-wiki

# 6. 生成每门课的学习指南文档（基于课程基本信息，insights 为空时降级）
python deploy.py docs

# 7. 回填导航表的「学习指南」字段（让链接可点）
python deploy.py link
```

完成后，打开飞书知识库（用刚 grant-wiki 加的账号登录），应能看到 4 个学年文档，每个文档里有这门学年的课程导航表，每行有可点击的「学习指南」链接。

**关于权限**：wiki 命令建的知识库默认应用是 owner，真实管理员账号无权编辑。两种解决方式：

| 方案 | 命令 | 适合场景 |
|---|---|---|
| **grant-wiki**（精细） | `python deploy.py grant-wiki <email或手机号> [--type email/mobile/openid/userid]` | 团队不大、想精细控制每个成员权限 |
| **open-wiki**（简单） | `python deploy.py open-wiki` | demo / 内部小团队用，凭链接即可编辑 |

手机号注册的用户用 `--type mobile`，命令内部会自动调飞书 contact API 把手机号解析成 openid。

**保存链接到飞书群（重要！）**：把第 1 步的 bitable URL 和第 4 步的 wiki URL 都发到你的飞书工作群置顶保存。理由：
- 应用是资源 owner，管理员在飞书 UI「我的文档」里默认看不到这些资源
- 没有链接就找不到 bitable / 知识库，更别说编辑
- 团队换管理员时，新管理员凭这些链接也能接手

**首次没有资料怎么办？** docs 会基于课程基本信息 + 占位内容生成（串讲段落写「待同学补充」），等你后续通过表单收集资料，重跑 sync + docs + link 就会更新。

> **提示**：所有 `python deploy.py xxx` 命令必须在激活的虚拟环境里跑（双击 start.bat 后的终端）。否则会报「找不到模块」错误。详见 [00 § 2.4](docs/00-快速开始.md#24-日常使用双击-startbat)。

---

## 四、日常维护（管理员）

### 4.1 学生提交了新资料后

学生通过飞书表单填了资料 → 资料管理表多了一条记录（审核状态默认「待审核」）→ 你需要：

**先双击 `start.bat` 打开激活虚拟环境的终端**，然后跑下面的命令：

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
python deploy.py reset-bitable --yes

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

## 八、如何更新代码（不会破坏知识库）

**Q1：项目代码更新了，我怎么同步到本地？**

双击项目目录里的 `update.bat`，它会自动做完所有事：
1. 从云端拉取最新代码
2. 如果有新的 Python 依赖，自动装上（已装的会跳过）

跑完会显示「更新完成」，通常只要几秒到十几秒。整个过程**不需要你输入任何命令**。

**Q2：更新会不会破坏我维护的知识库？**

**不会。** 你维护的知识库 = 飞书云端的 bitable 三张表 + wiki 文档 + 阿里云 OSS 文件。这些**全部在云端，不在代码仓库里**。`update.bat` 只换 Python 脚本（`deploy.py` / `glue/` / `services/` / `config/`），永远碰不到你的云端数据。

**极端情况验证**：即使把整个项目文件夹删了重 clone，只要 `.env` 里的 `BITABLE_APP_TOKEN` 还在，你的数据原封不动——bitable 三张表记录、知识库文档、OSS 资料全在云端。

**哪些代码更新需要你做事？**
- 大部分代码更新：双击 `update.bat` 即可，下次跑命令自动用新逻辑
- 新增 bitable 字段：跑 `init-bitable` 会自动补字段（**只补不删**，已有数据不动）
- 新增枚举选项（课程类型、学期等）：跑 `fix-bitable` 补选项

**会真正破坏数据的命令**（你主动跑才会发生）：
- `reset-bitable --yes`：清空 bitable 三张表全部记录
- `archive-materials --purge-immediately`：归档后立即删飞书原件（OSS 副本仍在）

详见 [4.4 重置 / 重建（危险！）](#44-重置--重建危险)。

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

部署遇到问题？先看 [03-故障排查.md](docs/03-故障排查.md)，再看 [01-管理员指南.md](docs/01-管理员指南.md)。
