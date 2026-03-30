# 飞书知识库API系统性调查报告

> 调查时间：2026-03-30
> 调查范围：飞书开放平台 Wiki/Doc/Bitable/Drive API

---

## 一、概述：飞书知识库体系架构

飞书知识库是一个面向组织的知识管理系统，通过结构化的高价值信息沉淀，形成完整的知识体系。飞书的云文档生态系统包含以下核心模块：

```
飞书云文档生态
├── 知识库 (Wiki) - 结构化知识管理
│   ├── 知识空间 (Space) - 知识库容器
│   ├── 节点 (Node) - 文档/表格等在知识库中的映射
│   └── 成员/权限管理
├── 云文档 (Docx) - 富文本文档
│   ├── 文档创建与编辑
│   └── 块级操作 (Block)
├── 多维表格 (Bitable) - 数据管理平台
│   ├── 表格 (Table)
│   ├── 视图 (View)
│   ├── 记录 (Record)
│   └── 字段 (Field)
└── 云空间 (Drive) - 文件存储
    ├── 文件夹管理
    └── 文件上传/下载
```

### 认证方式

所有API均需要通过 `tenant_access_token` 或 `user_access_token` 进行认证：

```python
# 获取 tenant_access_token
import requests

def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {
        "app_id": app_id,
        "app_secret": app_secret
    }
    response = requests.post(url, json=payload)
    return response.json()["tenant_access_token"]
```

**请求头格式**：
```
Authorization: Bearer <access_token>
Content-Type: application/json; charset=utf-8
```

---

## 二、知识库 (Wiki) API 详解

### 2.1 概述

知识库API用于管理知识空间、节点以及权限设置。

**Base URL**: `https://open.feishu.cn/open-apis/wiki/v2`

**权限要求**：
- `wiki:wiki` - 查看、编辑和管理Wiki
- `wiki:wiki:readonly` - 仅查看Wiki内容
- `wiki:node:create` - 创建知识空间节点
- `wiki:node:move` - 移动知识空间节点

### 2.2 知识空间 (Space) API

#### 获取知识空间列表

| 项目 | 说明 |
|------|------|
| URL | `GET /open-apis/wiki/v2/spaces` |
| 方法 | GET |
| 频率限制 | 100次/分钟 |
| Scope | `wiki:wiki` 或 `wiki:wiki:readonly` |

**请求参数**：无

**响应示例**：
```json
{
    "code": 0,
    "msg": "success",
    "data": {
        "items": [
            {
                "space_id": "7034502641455497244",
                "name": "产品文档",
                "description": "产品相关文档",
                "space_type": "team"
            }
        ]
    }
}
```

#### 创建知识空间

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/wiki/v2/spaces` |
| 方法 | POST |
| Scope | `wiki:wiki` |
| Token | 需要 `user_access_token` |

**请求体**：
```json
{
    "title": "新知识库",
    "description": "知识库描述"
}
```

#### 获取知识空间信息

| 项目 | 说明 |
|------|------|
| URL | `GET /open-apis/wiki/v2/spaces/:space_id` |
| 方法 | GET |
| Scope | `wiki:wiki` 或 `wiki:wiki:readonly` |

### 2.3 节点 (Node) API

#### 创建知识空间节点

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/wiki/v2/spaces/:space_id/nodes` |
| 方法 | POST |
| 频率限制 | 100次/分钟 |
| Scope | `wiki:node:create` 或 `wiki:wiki` |

**请求体参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| obj_type | string | 是 | 文档类型：`docx`, `sheet`, `bitable`, `mindnote`, `file`, `slides` |
| parent_node_token | string | 否 | 父节点token，为空则创建一级节点 |
| node_type | string | 是 | 节点类型：`origin`(实体) 或 `shortcut`(快捷方式) |
| origin_node_token | string | 否 | 创建快捷方式时，源节点的token |
| title | string | 否 | 文档标题 |

**请求示例**：
```json
// 创建docx文档节点
{
    "obj_type": "docx",
    "parent_node_token": "wikcnKQ1k3p******8Vabcef",
    "node_type": "origin"
}

// 创建多维表格节点
{
    "obj_type": "bitable",
    "node_type": "origin",
    "title": "项目跟踪表"
}
```

**响应示例**：
```json
{
    "code": 0,
    "msg": "success",
    "data": {
        "node": {
            "space_id": "6946843325487906839",
            "node_token": "wikcnKQ1k3p******8Vabcef",
            "obj_token": "doccnzAaO******8g9Spprd",
            "obj_type": "docx",
            "parent_node_token": "wikcnKQ1k3p******8Vabcef",
            "node_type": "origin",
            "has_child": false,
            "title": "新文档"
        }
    }
}
```

#### 移动节点

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/wiki/v2/spaces/:space_id/nodes/:node_token/move` |
| 方法 | POST |
| 频率限制 | 100次/分钟 |
| Scope | `wiki:node:move` 或 `wiki:wiki` |

**请求体**：
```json
{
    "target_parent_token": "wikbcd6ydSUyOEzbdlt1BfpA5Yc",
    "target_space_id": "7008061636015512345"  // 可选，跨空间移动
}
```

#### 获取子节点列表

| 项目 | 说明 |
|------|------|
| URL | `GET /open-apis/wiki/v2/spaces/:space_id/nodes` |
| 方法 | GET |
| Scope | `wiki:wiki` 或 `wiki:wiki:readonly` |

**查询参数**：
- `parent_node_token` - 父节点token（可选）
- `page_size` - 分页大小

#### 获取节点信息

| 项目 | 说明 |
|------|------|
| URL | `GET /open-apis/wiki/v2/spaces/get_node` |
| 方法 | GET |
| Scope | `wiki:wiki` 或 `wiki:wiki:readonly` |

**查询参数**：
- `token` - 节点token
- `obj_type` - 对象类型（可选）

#### 添加已有云文档到知识库

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/wiki/v2/spaces/:space_id/nodes/move_docs_to_wiki` |
| 方法 | POST |
| Scope | `wiki:wiki` |

**请求体**：
```json
{
    "parent_node_token": "wikcnKQ1k3p******8Vabcef",
    "obj_token": "doxcni6mOy7jLRWbEylaKKC7K88",
    "obj_type": "docx"
}
```

### 2.4 成员管理 API

#### 添加知识空间成员

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/wiki/v2/spaces/:space_id/members` |
| 方法 | POST |
| Scope | `wiki:wiki` |

**请求体**：
```json
{
    "member_id": "ou_51427140ab9f450411135757bcbf932f",
    "member_type": "User",
    "member_role": "admin"  // admin 或 reader
}
```

#### 删除知识空间成员

| 项目 | 说明 |
|------|------|
| URL | `DELETE /open-apis/wiki/v2/spaces/:space_id/members/:member_id` |
| 方法 | DELETE |
| Scope | `wiki:wiki` |

### 2.5 限制和注意事项

1. **节点数量限制**：
   - 知识空间总节点数不超过 400,000
   - 目录树不超过 50 层
   - 单层节点数不超过 2,000
   - 单次移动节点不超过 2,000

2. **权限要求**：
   - 创建节点需要父节点的"容器编辑权限"
   - 移动节点需要源和目标父节点的"容器编辑权限"
   - 应用需要被添加为知识库管理员或文档协作者

3. **不支持创建 file 类型节点**（需通过Drive API上传后关联）

---

## 三、云文档 (Docx) API 详解

### 3.1 概述

云文档API用于创建和编辑新版飞书文档（docx）。文档内容由块(Block)组成，支持层级嵌套。

**Base URL**: `https://open.feishu.cn/open-apis/docx/v1`

**权限要求**：
- `docx:document` - 创建和编辑新版文档
- `docx:document:create` - 仅创建新版文档
- `docx:document:write_only` - 仅编辑新版文档

### 3.2 文档管理 API

#### 创建文档

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/docx/v1/documents` |
| 方法 | POST |
| 频率限制 | 3次/秒（应用级）|
| Scope | `docx:document` 或 `docx:document:create` |

**请求体**：
```json
{
    "folder_token": "fldcnqquW1svRIYVT2Np6Iabcef",  // 可选，空则为根目录
    "title": "我的新文档"  // 可选，1-800字符
}
```

**响应示例**：
```json
{
    "code": 0,
    "msg": "success",
    "data": {
        "document": {
            "document_id": "doxcni6mOy7jLRWbEylaKKC7K88",
            "revision_id": 1,
            "title": "我的新文档"
        }
    }
}
```

**注意**：此API只支持创建空文档并指定标题，不支持直接写入内容。如需基于模板创建，需使用[复制文件](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/drive-v1/file/copy)接口。

#### 获取文档信息

| 项目 | 说明 |
|------|------|
| URL | `GET /open-apis/docx/v1/documents/:document_id` |
| 方法 | GET |
| Scope | `docx:document` |

#### 获取文档所有块

| 项目 | 说明 |
|------|------|
| URL | `GET /open-apis/docx/v1/documents/:document_id/blocks` |
| 方法 | GET |
| Scope | `docx:document` |

**查询参数**：
- `page_size` - 分页大小（1-50）
- `page_token` - 分页token

### 3.3 块操作 API

#### 创建子块

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/docx/v1/documents/:document_id/blocks/:block_id/children` |
| 方法 | POST |
| 频率限制 | 3次/秒（应用级），3次/秒（文档级）|
| Scope | `docx:document` 或 `docx:document:write_only` |

**路径参数**：
- `document_id` - 文档ID
- `block_id` - 父块ID（可以是文档ID，表示在文档根级别创建）

**请求体参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| children | array | 是 | 子块列表（1-50个） |
| document_revision_id | int | 否 | 文档版本ID，-1表示最新版本 |
| client_token | string | 否 | 操作唯一标识，用于幂等更新 |
| user_id_type | string | 否 | 用户ID类型：`open_id`, `union_id`, `user_id` |

**块类型 (block_type)**：

| 值 | 类型 | 说明 |
|----|------|------|
| 1 | Page | 页面块 |
| 2 | Text | 文本块 |
| 3-11 | Heading1-9 | 1-9级标题 |
| 12 | BulletList | 无序列表 |
| 13 | OrderedList | 有序列表 |
| 14 | Code | 代码块 |
| 15 | Quote | 引用块 |
| 17 | Todo | 待办事项 |
| 18 | Bitable | 多维表格块 |
| 19 | Callout | 高亮块 |
| 22 | Divider | 分割线 |
| 23 | File | 文件块 |
| 24 | Grid | 分栏块 |
| 27 | Image | 图片块 |
| 30 | Sheet | 电子表格块 |
| 31 | Table | 表格块 |
| 42 | WikiCatalog | 知识库目录块 |

**请求示例 - 创建文本和标题**：
```json
{
    "children": [
        {
            "block_type": 3,
            "heading1": {
                "elements": [
                    {
                        "text_run": {
                            "content": "第一章 概述"
                        }
                    }
                ]
            }
        },
        {
            "block_type": 2,
            "text": {
                "elements": [
                    {
                        "text_run": {
                            "content": "这是一段普通文本。"
                        }
                    }
                ]
            }
        },
        {
            "block_type": 2,
            "text": {
                "elements": [
                    {
                        "text_run": {
                            "content": "加粗文本",
                            "text_element_style": {
                                "bold": true
                            }
                        }
                    },
                    {
                        "text_run": {
                            "content": " 和 "
                        }
                    },
                    {
                        "text_run": {
                            "content": "斜体文本",
                            "text_element_style": {
                                "italic": true
                            }
                        }
                    }
                ]
            }
        }
    ]
}
```

**请求示例 - 创建带链接的文本**：
```json
{
    "children": [
        {
            "block_type": 2,
            "text": {
                "elements": [
                    {
                        "text_run": {
                            "content": "点击访问",
                            "text_element_style": {
                                "link": {
                                    "url": "https%3A%2F%2Fopen.feishu.cn%2F"
                                }
                            }
                        }
                    }
                ]
            }
        }
    ]
}
```

**请求示例 - 创建@文档链接**：
```json
{
    "children": [
        {
            "block_type": 2,
            "text": {
                "elements": [
                    {
                        "mention_doc": {
                            "token": "doxbc873Y7cXD153gXqb76abcef",
                            "obj_type": 22,  // 22表示docx
                            "url": "https%3A%2F%2Fopen.feishu.cn%2Fdocx%2Fdoxbc873Y7cXD153gXqb76abcef",
                            "title": "相关文档"
                        }
                    }
                ]
            }
        }
    ]
}
```

**请求示例 - 创建代码块**：
```json
{
    "children": [
        {
            "block_type": 14,
            "code": {
                "elements": [
                    {
                        "text_run": {
                            "content": "print('Hello, World!')"
                        }
                    }
                ],
                "language": 49,  // Python
                "wrap": true
            }
        }
    ]
}
```

#### 更新块

| 项目 | 说明 |
|------|------|
| URL | `PATCH /open-apis/docx/v1/documents/:document_id/blocks/:block_id` |
| 方法 | PATCH |
| Scope | `docx:document` 或 `docx:document:write_only` |

#### 删除块

| 项目 | 说明 |
|------|------|
| URL | `DELETE /open-apis/docx/v1/documents/:document_id/blocks/:block_id/children/batch_delete` |
| 方法 | DELETE |
| Scope | `docx:document` 或 `docx:document:write_only` |

### 3.4 限制和注意事项

1. **频率限制**：
   - 应用级别：3次/秒
   - 文档级别：3次/秒
   - 单次请求最多创建50个块

2. **内容限制**：
   - 标题长度：1-800字符
   - 文档块数量有上限
   - 块嵌套层级有上限
   - 表格列数/单元格数有上限

3. **注意事项**：
   - URL需要进行url_encode
   - 创建图片/文件块需要先上传素材
   - 使用指数退避算法处理限频

---

## 四、多维表格 (Bitable) API 详解

### 4.1 概述

多维表格是飞书的数据管理平台，可用于构建应用和管理在线数据协作。

**Base URL**: `https://open.feishu.cn/open-apis/bitable/v1`

**权限要求**：
- `bitable:app` - 查看、评论、编辑和管理多维表格
- `bitable:app:readonly` - 查看、评论和导出多维表格

### 4.2 多维表格的形式与 app_token 获取

| 形式 | URL特征 | app_token获取方式 |
|------|---------|-------------------|
| 云空间中的多维表格 | `feishu.cn/base/...` | URL中的高亮部分 |
| 知识库中的多维表格 | `feishu.cn/wiki/...` | 调用[获取节点信息]API，obj_type为bitable时obj_token即为app_token |
| 文档中嵌入的多维表格 | `feishu.cn/docx/...` | 调用[获取文档块]API，bitable.token |
| 表格中嵌入的多维表格 | `feishu.cn/sheets/...` | 调用[获取电子表格元数据]API |

### 4.3 表格 (Table) API

#### 创建表格

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/bitable/v1/apps/:app_token/tables` |
| 方法 | POST |
| 频率限制 | 10次/秒 |
| Scope | `bitable:app` |

**请求体**：
```json
{
    "table": {
        "name": "项目跟踪表",
        "default_view_name": "表格视图",
        "fields": [
            {
                "field_name": "项目名称",
                "type": 1  // 多行文本
            },
            {
                "field_name": "负责人",
                "type": 11  // 人员
            },
            {
                "field_name": "状态",
                "type": 3,  // 单选
                "property": {
                    "options": [
                        {"name": "进行中", "color": 0},
                        {"name": "已完成", "color": 1}
                    ]
                }
            },
            {
                "field_name": "相关文档",
                "type": 15  // 超链接
            }
        ]
    }
}
```

**字段类型 (type)**：

| 值 | 类型 | 说明 |
|----|------|------|
| 1 | Multiline | 多行文本 |
| 2 | Number | 数字 |
| 3 | SingleSelect | 单选 |
| 4 | MultiSelect | 多选 |
| 5 | Date | 日期 |
| 7 | Checkbox | 复选框 |
| 11 | User | 人员 |
| 13 | PhoneNumber | 电话号码 |
| 15 | Link | 超链接 |
| 17 | Attachment | 附件 |
| 18 | SingleLink | 单向关联 |
| 20 | Formula | 公式 |
| 21 | DuplexLink | 双向关联 |
| 22 | Location | 地理位置 |
| 1001 | CreatedTime | 创建时间 |
| 1002 | ModifiedTime | 最后更新时间 |
| 1003 | CreatedUser | 创建人 |
| 1004 | ModifiedUser | 修改人 |
| 1005 | AutoNumber | 自动编号 |

**响应示例**：
```json
{
    "code": 0,
    "msg": "success",
    "data": {
        "table_id": "tblDBTWm6Es84d8c",
        "default_view_id": "vewUuKOz2R",
        "field_id_list": ["fldhr2hBEA", "fldXXXXX"]
    }
}
```

#### 列出表格

| 项目 | 说明 |
|------|------|
| URL | `GET /open-apis/bitable/v1/apps/:app_token/tables` |
| 方法 | GET |
| Scope | `bitable:app` 或 `bitable:app:readonly` |

### 4.4 记录 (Record) API

#### 创建记录

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records` |
| 方法 | POST |
| Scope | `bitable:app` |

**请求体 - 超链接字段**：
```json
{
    "fields": {
        "项目名称": "API集成项目",
        "负责人": [{"id": "ou_xxxxx"}],
        "状态": "进行中",
        "相关文档": {
            "text": "需求文档",
            "link": "https://feishu.cn/docx/xxxxx"
        }
    }
}
```

**请求体 - 附件字段**：
```json
{
    "fields": {
        "附件": [
            {
                "file_token": "boxcnOj88GDkmWGm2zsTyCBqoLb",
                "name": "报告.pdf",
                "type": "file",
                "size": 102400
            }
        ]
    }
}
```

#### 批量创建记录

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records/batch_create` |
| 方法 | POST |
| Scope | `bitable:app` |

**请求体**：
```json
{
    "records": [
        {
            "fields": {
                "项目名称": "项目A",
                "状态": "进行中"
            }
        },
        {
            "fields": {
                "项目名称": "项目B",
                "状态": "已完成"
            }
        }
    ]
}
```

**注意**：单次批量操作最多处理1,000条记录。

#### 列出记录

| 项目 | 说明 |
|------|------|
| URL | `GET /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records` |
| 方法 | GET |
| Scope | `bitable:app` 或 `bitable:app:readonly` |

**查询参数**：
- `view_id` - 视图ID
- `field_names` - 字段名称列表（逗号分隔）
- `page_size` - 分页大小

#### 更新记录

| 项目 | 说明 |
|------|------|
| URL | `PUT /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records/:record_id` |
| 方法 | PUT |
| Scope | `bitable:app` |

#### 删除记录

| 项目 | 说明 |
|------|------|
| URL | `DELETE /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records/:record_id` |
| 方法 | DELETE |
| Scope | `bitable:app` |

### 4.5 字段 (Field) API

#### 列出字段

| 项目 | 说明 |
|------|------|
| URL | `GET /open-apis/bitable/v1/apps/:app_token/tables/:table_id/fields` |
| 方法 | GET |
| Scope | `bitable:app` 或 `bitable:app:readonly` |

#### 创建字段

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/fields` |
| 方法 | POST |
| Scope | `bitable:app` |

### 4.6 限制和注意事项

1. **资源数量限制**（单个多维表格）：
   - 记录数：按租户配置
   - 字段数：最多300个（公式字段最多100个）
   - 视图数：最多200个
   - 表格数：最多100个
   - 自定义角色：最多30个

2. **操作限制**：
   - 批量操作最多1,000条记录
   - 同一多维表格建议串行执行写操作

3. **权限要求**：
   - 使用 `tenant_access_token` 时，应用需为多维表格的所有者或协作者

---

## 五、云空间 (Drive) API 详解

### 5.1 概述

云空间API用于管理文件和文件夹，包括上传文件、创建文件夹、获取文件信息等。

**Base URL**: `https://open.feishu.cn/open-apis/drive/v1`

**权限要求**：
- `drive:drive` - 查看、评论、编辑和管理云空间
- `drive:drive:readonly` - 查看云空间
- `drive:file:upload` - 上传文件

### 5.2 文件上传 API

#### 上传素材到云文档

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/drive/v1/medias/upload_all` |
| 方法 | POST |
| 内容类型 | multipart/form-data |
| Scope | `drive:file:upload` |

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_name | string | 是 | 文件名（带后缀） |
| parent_type | string | 是 | 上传点类型：`docx_image`, `docx_file`, `bitable_file` 等 |
| parent_node | string | 是 | 父节点token（文档块ID或表格token） |
| size | string | 是 | 文件大小（字节） |
| file | file | 是 | 文件内容 |

**请求示例**：
```bash
curl -X POST 'https://open.feishu.cn/open-apis/drive/v1/medias/upload_all' \
  -H 'Authorization: Bearer <access_token>' \
  -F 'file_name="test.png"' \
  -F 'parent_type="docx_image"' \
  -F 'parent_node="<image_block_id>"' \
  -F 'size=102400' \
  -F 'file=@"/path/test.png"'
```

#### 上传文件到云空间（发送消息用）

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/im/v1/files` |
| 方法 | POST |
| 内容类型 | multipart/form-data |
| Scope | `im:resource` 或 `im:resource:upload` |
| 文件大小限制 | ≤30MB |

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_type | string | 是 | 文件类型：`opus`, `mp4`, `pdf`, `doc`, `xls`, `ppt`, `stream` |
| file_name | string | 是 | 文件名（带后缀） |
| duration | int | 否 | 音视频时长（毫秒） |
| file | file | 是 | 文件内容 |

**响应示例**：
```json
{
    "code": 0,
    "msg": "success",
    "data": {
        "file_key": "file_456a92d6-c6ea-4de4-ac3f-7afcf44ac78g"
    }
}
```

### 5.3 文件夹管理 API

#### 创建文件夹

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/drive/v1/folders` |
| 方法 | POST |
| Scope | `drive:drive` |

**请求体**：
```json
{
    "name": "新建文件夹",
    "parent_token": "fldcnqquW1svRIYVT2Np6Iabcef"  // 父文件夹token，空则为根目录
}
```

#### 获取文件夹信息

| 项目 | 说明 |
|------|------|
| URL | `GET /open-apis/drive/v1/folders/:folder_token` |
| 方法 | GET |
| Scope | `drive:drive` 或 `drive:drive:readonly` |

#### 列出文件夹内容

| 项目 | 说明 |
|------|------|
| URL | `GET /open-apis/drive/v1/folders/:folder_token/children` |
| 方法 | GET |
| Scope | `drive:drive` 或 `drive:drive:readonly` |

### 5.4 文件管理 API

#### 获取文件信息

| 项目 | 说明 |
|------|------|
| URL | `GET /open-apis/drive/v1/files/:file_token` |
| 方法 | GET |
| Scope | `drive:drive` 或 `drive:drive:readonly` |

#### 复制文件

| 项目 | 说明 |
|------|------|
| URL | `POST /open-apis/drive/v1/files/:file_token/copy` |
| 方法 | POST |
| Scope | `drive:drive` |

**请求体**：
```json
{
    "name": "副本名称",
    "type": "docx",  // file类型
    "folder_token": "fldcnqquW1svRIYVT2Np6Iabcef"
}
```

#### 下载文件

| 项目 | 说明 |
|------|------|
| URL | `GET /open-apis/drive/v1/files/:file_token/download` |
| 方法 | GET |
| Scope | `drive:drive` 或 `drive:drive:readonly` |

### 5.5 限制和注意事项

1. **文件大小限制**：
   - IM文件上传：≤30MB
   - 图片上传：≤10MB
   - 不允许上传空文件

2. **权限要求**：
   - 使用 `tenant_access_token` 时只能操作应用创建的文件夹
   - 需要相应文件夹的编辑权限

---

## 六、集成场景实战指南

### 6.1 场景一：在知识库中创建带内容的文档

**步骤**：
1. 创建知识空间节点（获取node_token和obj_token）
2. 使用obj_token作为document_id创建文档块

```python
import requests

def create_wiki_document_with_content(
    access_token: str,
    space_id: str,
    parent_node_token: str,
    title: str,
    content_blocks: list
):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # 步骤1：创建知识库节点
    create_node_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes"
    node_payload = {
        "obj_type": "docx",
        "parent_node_token": parent_node_token,
        "node_type": "origin",
        "title": title
    }
    node_response = requests.post(create_node_url, headers=headers, json=node_payload)
    document_id = node_response.json()["data"]["node"]["obj_token"]
    
    # 步骤2：创建文档内容
    create_blocks_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children"
    blocks_payload = {"children": content_blocks}
    requests.post(create_blocks_url, headers=headers, json=blocks_payload)
    
    return document_id
```

### 6.2 场景二：在知识库中嵌入多维表格

**步骤**：
1. 创建多维表格类型的知识库节点
2. 获取app_token后配置表格结构

```python
def create_wiki_bitable(access_token: str, space_id: str, title: str):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # 创建bitable节点
    url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes"
    payload = {
        "obj_type": "bitable",
        "node_type": "origin",
        "title": title
    }
    response = requests.post(url, headers=headers, json=payload)
    
    # 返回app_token用于后续操作
    return response.json()["data"]["node"]["obj_token"]
```

### 6.3 场景三：在文档中插入文件下载链接

**步骤**：
1. 上传文件获取file_token
2. 创建带链接的文本块

```python
def create_document_with_file_link(
    access_token: str,
    document_id: str,
    file_name: str,
    file_path: str
):
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 步骤1：上传文件（示例为消息文件上传，获取file_key）
    upload_url = "https://open.feishu.cn/open-apis/im/v1/files"
    with open(file_path, 'rb') as f:
        files = {
            'file_type': (None, 'stream'),
            'file_name': (None, file_name),
            'file': (file_name, f)
        }
        upload_response = requests.post(upload_url, headers=headers, files=files)
    file_key = upload_response.json()["data"]["file_key"]
    
    # 步骤2：创建带链接的文本块
    # 注：实际文件下载链接需要通过Drive API获取
    blocks_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children"
    headers["Content-Type"] = "application/json; charset=utf-8"
    payload = {
        "children": [
            {
                "block_type": 2,
                "text": {
                    "elements": [
                        {
                            "text_run": {
                                "content": f"📎 下载{file_name}",
                                "text_element_style": {
                                    "link": {
                                        "url": f"file_key_{file_key}"  # 实际使用时替换为真实URL
                                    }
                                }
                            }
                        }
                    ]
                }
            }
        ]
    }
    requests.post(blocks_url, headers=headers, json=payload)
```

### 6.4 场景四：在多维表格中链接知识库文档

**步骤**：
1. 获取知识库文档的URL
2. 创建包含超链接字段的记录

```python
def add_record_with_wiki_link(
    access_token: str,
    app_token: str,
    table_id: str,
    project_name: str,
    wiki_doc_url: str,
    wiki_doc_title: str
):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    payload = {
        "fields": {
            "项目名称": project_name,
            "相关文档": {
                "text": wiki_doc_title,
                "link": wiki_doc_url
            }
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()
```

### 6.5 场景五：将现有文档添加到知识库

```python
def add_existing_doc_to_wiki(
    access_token: str,
    space_id: str,
    doc_token: str,
    parent_node_token: str = None
):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes/move_docs_to_wiki"
    payload = {
        "obj_token": doc_token,
        "obj_type": "docx",
        "parent_node_token": parent_node_token
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()
```

---

## 七、已知限制和注意事项

### 7.1 通用限制

1. **API频率限制**：
   - Wiki节点操作：100次/分钟
   - Docx创建：3次/秒
   - Docx块操作：3次/秒（应用级+文档级双重限制）
   - Bitable表格创建：10次/秒
   - 文件上传：1000次/分钟、50次/秒

2. **内容大小限制**：
   - 文档标题：1-800字符
   - 单次创建块数：1-50个
   - 批量记录操作：最多1,000条

### 7.2 权限注意事项

1. **tenant_access_token 限制**：
   - 只能操作应用创建的文件夹
   - 需要被添加为文档协作者才能操作他人文档
   - 权限变更需要等待token刷新（版本发布前获取的token不会自动更新scope）

2. **资源权限**：
   - 创建节点需要父节点的"容器编辑权限"
   - 移动节点需要源和目标的"容器编辑权限"
   - 可通过添加应用为知识库管理员获取完整权限

### 7.3 已知问题

1. **Docs 1.0 已废弃**：创建文档请使用 `docx` 类型，不再支持 `doc` 类型创建
2. **file类型节点不能直接创建**：需通过Drive API上传后关联到知识库
3. **并发写操作冲突**：同一多维表格不支持并发写操作，需串行执行

---

## 八、参考链接

| 资源 | 链接 |
|------|------|
| 飞书开放平台文档首页 | https://open.feishu.cn/document/ |
| 知识库API概述 | https://open.feishu.cn/document/server-docs/docs/wiki-v2/wiki-overview |
| 创建知识空间节点 | https://open.feishu.cn/document/server-docs/docs/wiki-v2/space-node/create |
| 云文档概述 | https://open.feishu.cn/document/server-docs/docs/docs-overview |
| 创建文档 | https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/create |
| 创建块 | https://open.feishu.cn/document/ukTMukTMukTM/uUDN04SN0QjL1QDN/document-docx/docx-v1/document-block-children/create |
| 多维表格概述 | https://open.feishu.cn/document/server-docs/docs/bitable-v1/bitable-overview |
| 创建表格 | https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table/create |
| 创建记录 | https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/create |
| 上传文件 | https://open.feishu.cn/document/server-docs/im-v1/file/create |
| 文件夹概述 | https://open.feishu.cn/document/docs/drive-v1/folder/folder-overview |
| 频率限制说明 | https://open.feishu.cn/document/ukTMukTMukTM/uUzN04SN3QjL1cDN |
| 权限列表 | https://open.feishu.cn/document/ukTMukTMukTM/uQjN3QjL0YzN04CN2cDN |

---

*报告生成时间：2026-03-30*
