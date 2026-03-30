# PPE云端智能大礼包

> 南开大学PPE专业课程资料智能管理与分发系统

## 📋 项目简介

PPE云端智能大礼包是一个基于飞书开放平台的知识库自动构建系统，旨在帮助PPE专业学生：
- 📚 系统化管理各学年课程资料
- 📝 智能生成课程学习指南
- 🔗 打通知识库、文档、多维表格的完整链路
- 🤖 利用AI自动提取学长学姐的经验心得

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repo-url>
cd PPE云端智能大礼包

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写以下配置：

```env
# 飞书配置
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret

# 智谱AI配置
ZHIPU_API_KEY=your_api_key
```

### 3. 一键部署

```bash
# 完整部署（推荐首次使用）
python deploy.py --mode full

# 其他模式
python deploy.py --mode wiki      # 仅创建知识库
python deploy.py --mode tables    # 仅创建多维表格
python deploy.py --mode docs      # 仅生成文档
python deploy.py --mode link      # 仅关联链接
```

## 📖 核心功能

### 1. 知识库自动构建

- 创建"PPE云端智能大礼包"知识空间
- 按学年创建节点（大一/大二/大三/大四）
- 每门课程自动生成知识库节点

### 2. 多维表格管理

每个学年一个多维表格，包含字段：
- 课程名称
- 授课老师
- 开课学期
- 课程类型
- 考试形式
- 学习指南（自动关联文档链接）
- 资料数量
- 贡献者
- 最后更新时间

### 3. 智能文档生成

基于V3文档结构：
1. 课程内容概述
2. 学习难点
3. 老师偏好
4. 资料分类列表
5. 资料串讲
6. 贡献者列表

### 4. 完整用户链路

```
学生 → 飞书知识库 → 学年多维表格 → 课程详情 → 学习指南文档 → 资料下载
```

## 🛠️ 技术架构

```
PPE云端智能大礼包/
├── deploy.py                  # 统一部署入口
├── .env                       # 环境变量配置
├── requirements.txt           # Python依赖
└── ppe_demo/
    ├── config.py              # 全局配置
    ├── models.py              # 数据模型
    ├── data/                  # 数据文件
    │   ├── courses.json       # 课程列表
    │   ├── experiences.json   # 心得体会
    │   └── materials.json     # 资料元信息
    └── services/              # 核心服务
        ├── feishu_service.py  # 飞书API封装
        ├── wiki_builder.py    # 知识库构建
        ├── table_service.py   # 多维表格管理
        ├── doc_generator.py   # 文档生成
        ├── link_service.py    # 关联服务
        ├── llm_service.py     # 智谱AI调用
        └── upload_service.py  # 资料上传
```

## 🔧 开发指南

### 添加新课程

编辑 `ppe_demo/config.py` 中的 `COURSES_BY_YEAR` 字典：

```python
COURSES_BY_YEAR = {
    "大一": [
        {
            "name": "课程名称",
            "teacher": "授课老师",
            "semester": "开课学期",
            "type": "必修/选修",
            "exam": "考试形式"
        },
        ...
    ]
}
```

### 添加心得体会

编辑 `ppe_demo/data/experiences.json`：

```json
[
  {
    "experience_id": "EXP0001",
    "author": "贡献者",
    "grade": "22级",
    "course_name": "课程名称",
    "score": "92",
    "content": "心得体会内容..."
  }
]
```

## ⚠️ 注意事项

1. **飞书权限**：需要开通以下权限
   - `wiki:wiki` - 知识库管理
   - `docx:document` - 云文档
   - `bitable:app` - 多维表格
   - `drive:file:upload` - 文件上传

2. **API频率限制**：
   - Docx块操作：3次/秒
   - 系统已内置退避重试机制

3. **知识空间复用**：
   - 系统会先检查是否已存在同名空间
   - 避免重复创建

## 📝 更新日志

### v2.0 (2026-03-30)
- ✨ 重构为飞书云文档架构
- 🔗 打通多维表格与知识库链接
- 📄 文档自动上传到飞书
- 🚀 统一部署入口

### v1.0 (2026-02-28)
- 📚 本地Markdown文档生成
- 📝 心得体会管理
- 🎯 AI智能提取

## 📄 License

MIT License

## 👥 贡献者

- 铭培（产品设计与需求）
- 小劳（技术实现）
- 南开大学PPE专业全体同学（资料贡献）

---

*Made with ❤️ for Nankai PPE*
