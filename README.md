# 课程资料智能大礼包

> 把每届学长学姐的课程资料、心得、推荐理由，结构化沉淀下来，传给下一届同学。
>
> 适用任意院校、任意专业。下面以「南开大学 PPE 专业」为示例，你可以替换为自己的专业和课程清单。

---

## 一、这是什么

一句话：**一条「搜集 → 整合 → 分发」的数据管道，部署在飞书云上**。

- **搜集**：学长学姐通过飞书表单提交资料（笔记 / PPT / 真题 / 教材 / 心得），附推荐理由
- **整合**：自动归档到阿里云 OSS；OCR 提取全文；LLM（DeepSeek）按课程生成「学长学姐视角」的学习指南
- **分发**：在飞书知识库生成 4 个学年导航文档，每门课一个独立学习指南文档，所有资料带可点击下载链接

学生端看到的：点开知识库 → 大一/大二/大三/大四 4 个文档 → 点击任意课程的「学习指南」→ 看到 LLM 写好的课程概述 + 推荐资料表 + 资料串讲 + 贡献者致谢，所有资料名都是可点击下载的超链接。

---

## 二、工作原理

学生通过飞书表单提交资料 → 落到飞书 bitable 三张表（课程主数据 / 资料管理 / 心得管理）→ `archive-materials` 归档到 OSS → `ocr-materials` 提取全文 + LLM 摘要 → `sync` 聚合 + 双层门控 → `docs` 用 LLM 生成课程文档 → `link` 把链接回填到学年导航表。学生最终看到的就是飞书知识库里的可读文档。

**双层门控保证**：学生填的课程必须先在「课程主数据表」里存在（管理员维护），否则 sync 跳过 + 警告，避免乱填污染文档库。

---

## 三、快速开始

### 3.1 准备环境（约 30-60 分钟）

部署需要完成 7 件事。**第 1-3 件在本地电脑操作，第 4-7 件是注册 4 个云账号拿凭证**。

**本地电脑（3 件事）**：

1. **检查 / 装 Python 3.10+**（项目代码的解释器，无法自动装）

   先看看你电脑是否已经有 Python：
   - Windows：按 Win+R → 输入 `cmd` 回车 → 在 cmd 里输入 `python --version`
   - macOS/Linux：终端输入 `python3 --version`

   - 如果看到 `Python 3.10.x` 或更新 → 已装，跳到第 2 步
   - 如果看到 `Python 3.9` 或更旧 → 装过但版本太旧，setup 脚本会提示升级
   - 如果提示「不是内部或外部命令」→ 没装，去 https://www.python.org/downloads/ 下载（Windows 安装时**务必勾选底部「Add Python.exe to PATH」**）

2. **下载项目代码**

   ```bash
   git clone https://github.com/PeberWang/PPE-CloudSmart-GiftBox.git
   cd PPE-CloudSmart-GiftBox
   ```

   不熟悉 git？GitHub 页面点「Code」→「Download ZIP」→ 解压也行。

3. **双击 `setup.bat`**（Windows）或 **跑 `bash setup.sh`**（macOS/Linux）
   - 自动检测 Python 版本（过旧会提示升级，没装会打开下载页）
   - 自动创建虚拟环境（venv，不污染系统 Python）
   - 自动检测并装 LibreOffice（Office 文档 OCR 用）
   - 自动装 Python 依赖（装在 venv 里）
   - 自动创建 `.env` 配置文件
   - 脚本逻辑和排错见 [00 § 2.2](docs/00-快速开始.md#22-一键装所有依赖--配置推荐)

**注册 4 个云账号拿凭证（4 件事）**：

按 [00 § 1.1-1.4](docs/00-快速开始.md#一准备账号--装环境) 操作，每个都有详细步骤（包括截图级菜单路径）：

| 账号 | 用途 | 拿到什么 |
|---|---|---|
| 飞书企业版 | 知识库 + bitable 载体 | App ID + App Secret |
| 阿里云 OSS | 资料归档存储 | AK + SK + bucket 名 + endpoint |
| DeepSeek | LLM（生成课程文档 + 摘要） | API Key |
| 智谱 GLM-OCR | OCR API | API Key |

**三个特别提醒**：
- 装 Python 时**务必勾选「Add Python to PATH」**（Windows）
- 阿里云 OSS bucket 读写权限选「**公共读**」（学生凭链接直接下载）
- AccessKey Secret 只显示一次，**立刻复制保存**

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

## 八、系列文档

| 文档 | 适合谁 |
|---|---|
| [00-快速开始.md](docs/00-快速开始.md) | 第一次部署的管理员 |
| [01-管理员指南.md](docs/01-管理员指南.md) | 日常运维的同学 |
| [02-学生使用指南.md](docs/02-学生使用指南.md) | 通过表单提交资料的学长学姐 |
| [03-故障排查.md](docs/03-故障排查.md) | 遇到问题时 |
| [04-技术原理.md](docs/04-技术原理.md) | 想理解工作原理、做二次开发的同学 |

---

部署遇到问题？先看 [03-故障排查.md](docs/03-故障排查.md)，再看 [01-管理员指南.md](docs/01-管理员指南.md)。
