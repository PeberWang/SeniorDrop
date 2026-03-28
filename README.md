# PPE云端智能大礼包 (PPE CloudSmart GiftBox)

为南开大学 PPE 实验班构建的云端智能课程资料系统。通过收集学长学姐上传的资料和心得体会，利用 AI 自动生成结构化的课程学习指南。

> **愿景**：将分散在个人电脑里的课程经验和心得，变成一个可以沉淀、流通、持续生长的公共资源。如果做好了这个基础设施，可以复制到中国各个专业和本科班级，帮助凝聚经验、知识和视野，形成促进知识流动的微组织。

## 核心功能

- **资料上传与管理**：批量扫描本地资料包，按课程、类型、年级分类整理
- **心得体会收集**：收集学长学姐的课程心得（可由 AI 生成示例）
- **AI 文档生成**：基于智谱AI，自动生成包含概述、难点分析、老师偏好、资料串讲等内容的课程文档
- **飞书知识库集成**：自动创建知识库结构，将课程文档上传至飞书多维表格和知识库

## 技术栈

- **Python 3.10+**
- **智谱AI**（GLM-4-Flash）：AI 文本生成
- **飞书开放平台 API**：知识库、多维表格、云文档
- **httpx**：异步 HTTP 客户端

## 项目结构

```
├── .env.example          # 环境变量模板
├── .gitignore
├── README.md
├── requirements.txt
├── docs/                 # 文档与日志
│   ├── 课程教改目录.md
│   ├── 汇报文档.docx
│   ├── 实施日志.md
│   ├── issue_log.md
│   └── 知识库.md
└── ppe_demo/             # 核心代码
    ├── config.py         # 配置管理（从 .env 读取）
    ├── main.py           # 主流程
    ├── models.py         # 数据模型
    ├── init_wiki.py      # 飞书知识库初始化
    ├── data/             # 课程数据 (JSON)
    ├── templates/        # 提示词模板
    └── services/
        ├── llm_service.py         # 智谱AI服务
        ├── feishu_service.py      # 飞书API服务
        ├── upload_service.py      # 资料上传服务
        ├── experience_service.py  # 心得体会服务
        └── doc_generator.py       # 文档生成服务
```

## 安装部署

### 1. 克隆仓库

```bash
git clone git@github.com:PeberWang/PPE-CloudSmart-GiftBox.git
cd PPE-CloudSmart-GiftBox
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入真实的 API 凭据：

- `FEISHU_APP_ID` / `FEISHU_APP_SECRET`：飞书应用凭证
- `ZHIPU_API_KEY`：智谱AI API Key
- `MATERIALS_BASE`：本地资料包路径（可选，默认指向南开PPE资料包）

### 4. 运行

```bash
cd ppe_demo
python main.py          # 运行核心流程Demo
python init_wiki.py     # 初始化飞书知识库结构
```

## 使用方法

1. **运行 Demo**：`python ppe_demo/main.py` 会扫描本地资料包，生成示例心得，并调用 AI 生成课程文档
2. **初始化知识库**：`python ppe_demo/init_wiki.py` 在飞书中创建 PPE 知识库的目录结构
3. **输出文件**：生成的课程文档保存在 `ppe_demo/output/course_docs/` 目录下

## 开发计划

- [ ] 支持更多课程和学期
- [ ] 飞书机器人自动同步文档
- [ ] 多维表格前端展示
- [ ] 支持更多 AI 模型

## 许可

本项目仅供南开大学 PPE 实验班内部使用。
