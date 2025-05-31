# Kompanion Python API 文档

## 概述

Kompanion Python 是一个为 KOReader 设计的书籍库管理 Web 应用程序，提供与原始 Go 版本完全兼容的API。本文档详细描述了所有可用的 API 端点、请求格式和响应格式。

### 基础信息
- **Base URL**: `http://localhost:8000/api/v1`
- **API 版本**: v1
- **认证方式**: JWT Bearer Token / KOReader kosync 兼容认证
- **数据格式**: JSON / Form Data (兼容 kosync)

---

## 认证 API

### 用户注册
**端点**: `POST /auth/register`
**描述**: 注册新用户账户

**请求体**:
```json
{
  "username": "string",
  "password": "string", 
  "email": "string"
}
```

**响应** (201):
```json
{
  "id": 1,
  "username": "testuser",
  "email": "test@example.com",
  "is_active": true,
  "is_admin": false,
  "created_at": "2025-01-31T12:00:00Z"
}
```

### 用户登录
**端点**: `POST /auth/login`
**描述**: 用户登录获取访问令牌

**请求体**:
```json
{
  "username": "string",
  "password": "string"
}
```

**响应** (200):
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "is_active": true,
    "is_admin": false
  }
}
```

### KOReader 用户创建 (kosync 兼容)
**端点**: `POST /users/create`
**描述**: KOReader kosync 插件兼容的用户创建端点

**请求体** (Form Data):
```
username=koreader_user
password=koreader_pass
```

**响应** (201):
```json
{
  "username": "koreader_user",
  "authorized": "OK"
}
```

### KOReader 用户认证 (kosync 兼容)
**端点**: `POST /users/auth`
**描述**: KOReader kosync 插件兼容的用户认证端点

**请求体** (Form Data):
```
username=koreader_user
password=koreader_pass
```

**响应** (200):
```json
{
  "username": "koreader_user",
  "authorized": "OK"
}
```

### 设备注册
**端点**: `POST /auth/device-register`
**描述**: 注册新的 KOReader 设备
**认证**: 需要 Bearer Token

**请求体**:
```json
{
  "device_id": "koreader-123",
  "device_name": "My KOReader",
  "device_type": "koreader"
}
```

**响应** (201):
```json
{
  "id": 1,
  "device_id": "koreader-123",
  "device_name": "My KOReader",
  "device_type": "koreader",
  "user_id": 1,
  "created_at": "2025-01-31T12:00:00Z"
}
```

---

## 同步 API

### 上传同步进度 (kosync 兼容)
**端点**: `PUT /syncs/progress`
**描述**: KOReader kosync 插件兼容的进度上传

**请求体** (Form Data):
```
document=book.epub
progress=0.25
percentage=25.0
device=My KOReader
device_id=koreader-123
user=username
timestamp=1640995200
```

**响应** (200):
```json
{
  "document": "book.epub",
  "progress": 0.25,
  "percentage": 25.0,
  "device": "My KOReader",
  "sync_status": "updated",
  "timestamp": 1640995200
}
```

### 获取同步进度 (kosync 兼容)
**端点**: `GET /syncs/progress/{document}`
**描述**: 获取指定文档的同步进度
**查询参数**: `user`, `device`

**响应** (200):
```json
{
  "document": "book.epub",
  "progress": 0.25,
  "percentage": 25.0,
  "device": "My KOReader",
  "timestamp": 1640995200
}
```

### 同步进度 (kosync 兼容)
**端点**: `POST /syncs/progress`
**描述**: KOReader kosync 插件兼容的双向同步

**请求体** (Form Data):
```
document=book.epub
progress=0.35
percentage=35.0
device=My KOReader
user=username
timestamp=1640995300
```

**响应** (200):
```json
{
  "document": "book.epub",
  "progress": 0.35,
  "percentage": 35.0,
  "sync_status": "updated"
}
```

### 获取用户同步进度列表
**端点**: `GET /syncs/progress`
**描述**: 获取当前用户的所有同步进度
**认证**: 需要 Bearer Token
**查询参数**: `page`, `size`, `device_id`, `search`

**响应** (200):
```json
{
  "total": 10,
  "items": [
    {
      "id": 1,
      "document": "book.epub",
      "progress": 0.25,
      "percentage": 25.0,
      "timestamp": 1640995200,
      "device": {
        "device_id": "koreader-123",
        "device_name": "My KOReader"
      }
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 1,
    "page_size": 10
  }
}
```

### 批量上传同步进度
**端点**: `POST /syncs/progress/batch`
**描述**: 批量上传多个同步进度
**认证**: 需要 Bearer Token

**请求体**:
```json
{
  "device_id": "koreader-123",
  "progresses": [
    {
      "document": "book1.epub",
      "progress": 0.1,
      "percentage": 10.0
    },
    {
      "document": "book2.epub",
      "progress": 0.2,
      "percentage": 20.0
    }
  ]
}
```

**响应** (200):
```json
{
  "uploaded_count": 2,
  "results": [
    {
      "document": "book1.epub",
      "status": "success"
    },
    {
      "document": "book2.epub",
      "status": "success"
    }
  ]
}
```

---

## OPDS 目录服务

### OPDS 根目录
**端点**: `GET /opds/`
**描述**: OPDS 目录根目录，返回导航目录
**内容类型**: `application/atom+xml;profile=opds-catalog;kind=navigation`

**响应** (200): OPDS XML 格式的导航目录

### 最新书籍目录
**端点**: `GET /opds/catalog/recent`
**描述**: 最新上传的书籍目录
**查询参数**: `page`, `size`
**内容类型**: `application/atom+xml;profile=opds-catalog;kind=acquisition`

### 热门书籍目录
**端点**: `GET /opds/catalog/popular`
**描述**: 按下载次数排序的热门书籍目录
**查询参数**: `page`, `size`

### 所有书籍目录
**端点**: `GET /opds/catalog/all`
**描述**: 所有可用书籍目录
**查询参数**: `page`, `size`

### 书籍搜索
**端点**: `GET /opds/search`
**描述**: 搜索书籍目录
**查询参数**: `q` (搜索关键词), `page`, `size`

---

## 书籍管理 API

### 上传书籍
**端点**: `POST /books/upload`
**描述**: 上传书籍文件 (仅管理员)
**认证**: 需要管理员权限
**请求体**: Multipart form data

**响应** (201):
```json
{
  "id": 1,
  "title": "示例书籍",
  "author": "作者名称",
  "isbn": "9781234567890",
  "publisher": "出版社",
  "language": "zh",
  "file_path": "/storage/books/example.epub",
  "file_name": "example.epub",
  "file_size": 1024000,
  "file_hash": "md5hash123",
  "file_format": "epub",
  "is_available": true,
  "download_count": 0,
  "created_at": "2025-01-31T12:00:00Z"
}
```

### 下载书籍
**端点**: `GET /books/{book_id}/download`
**描述**: 下载书籍文件
**认证**: 可选 (支持匿名下载)

**响应** (200): 书籍文件二进制数据
**Headers**: 
- `Content-Type`: `application/epub+zip` (或对应格式)
- `Content-Disposition`: `attachment; filename="book.epub"`

### 获取书籍封面
**端点**: `GET /books/{book_id}/cover`
**描述**: 获取书籍封面图片
**查询参数**: `thumbnail` (true/false)

**响应** (200): 图片文件二进制数据
**Headers**: `Content-Type`: `image/jpeg`

### 书籍列表
**端点**: `GET /books/`
**描述**: 获取书籍列表
**查询参数**: `page`, `size`, `search`, `format`, `sort`, `order`

**响应** (200):
```json
{
  "total": 100,
  "items": [
    {
      "id": 1,
      "title": "示例书籍",
      "author": "作者名称",
      "file_format": "epub",
      "file_size": 1024000,
      "download_count": 5,
      "created_at": "2025-01-31T12:00:00Z"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 10,
    "page_size": 10
  }
}
```

### 书籍详情
**端点**: `GET /books/{book_id}`
**描述**: 获取书籍详细信息

**响应** (200):
```json
{
  "id": 1,
  "title": "示例书籍",
  "author": "作者名称",
  "isbn": "9781234567890",
  "publisher": "出版社",
  "language": "zh",
  "description": "书籍描述",
  "file_name": "example.epub",
  "file_size": 1024000,
  "file_format": "epub",
  "download_count": 5,
  "is_available": true,
  "created_at": "2025-01-31T12:00:00Z",
  "updated_at": "2025-01-31T12:00:00Z"
}
```

### 更新书籍信息
**端点**: `PUT /books/{book_id}`
**描述**: 更新书籍信息 (仅管理员)
**认证**: 需要管理员权限

**请求体**:
```json
{
  "title": "更新的标题",
  "author": "更新的作者",
  "description": "更新的描述"
}
```

### 删除书籍
**端点**: `DELETE /books/{book_id}`
**描述**: 删除书籍 (仅管理员)
**认证**: 需要管理员权限

**响应** (200):
```json
{
  "message": "书籍删除成功"
}
```

---

## WebDAV 服务

### WebDAV 选项
**端点**: `OPTIONS /webdav/{path:path}`
**描述**: 返回支持的 WebDAV 方法
**认证**: 需要 Bearer Token

**响应** (200):
**Headers**: 
- `Allow`: `GET,PUT,DELETE,PROPFIND,MKCOL,OPTIONS`
- `DAV`: `1`

### WebDAV 属性查找
**端点**: `PROPFIND /webdav/{path:path}`
**描述**: 获取文件或目录属性
**认证**: 需要 Bearer Token
**Headers**: `Depth` (0 或 1)

**响应** (207): XML 格式的 Multi-Status 响应

### WebDAV 文件上传
**端点**: `PUT /webdav/{path:path}`
**描述**: 上传文件到 WebDAV 服务器
**认证**: 需要 Bearer Token

**响应** (201): 文件创建成功

### WebDAV 文件下载
**端点**: `GET /webdav/{path:path}`
**描述**: 从 WebDAV 服务器下载文件
**认证**: 需要 Bearer Token

**响应** (200): 文件内容

### WebDAV 删除文件
**端点**: `DELETE /webdav/{path:path}`
**描述**: 删除文件或目录
**认证**: 需要 Bearer Token

**响应** (204): 删除成功

### WebDAV 创建目录
**端点**: `MKCOL /webdav/{path:path}`
**描述**: 创建目录
**认证**: 需要 Bearer Token

**响应** (201): 目录创建成功

### WebDAV 使用统计
**端点**: `GET /webdav/stats/overview`
**描述**: 获取 WebDAV 使用统计
**认证**: 需要 Bearer Token

**响应** (200):
```json
{
  "total_files": 150,
  "total_size": 1073741824,
  "file_types": {
    "json": 45,
    "txt": 30,
    "pdf": 25
  }
}
```

### 阅读统计查看
**端点**: `GET /webdav/stats/reading`
**描述**: 获取 KOReader 阅读统计
**认证**: 需要 Bearer Token
**查询参数**: `page`, `size`, `device_filter`

**响应** (200):
```json
{
  "total": 20,
  "items": [
    {
      "id": 1,
      "title": "阅读的书籍",
      "authors": "作者",
      "current_page": 50,
      "total_pages": 200,
      "reading_percentage": 25.0,
      "total_reading_time": 3600,
      "highlights_count": 5,
      "notes_count": 2,
      "last_read_at": "2025-01-31T12:00:00Z"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 2,
    "page_size": 10
  }
}
```

---

## Web 管理界面

### 管理仪表板
**端点**: `GET /web/dashboard`
**描述**: 管理仪表板页面
**认证**: 需要登录

**响应** (200): HTML 页面

### 书籍管理页面
**端点**: `GET /web/books`
**描述**: 书籍管理界面
**认证**: 需要登录
**查询参数**: `page`, `search`, `format`

**响应** (200): HTML 页面

### 用户管理页面
**端点**: `GET /web/users`
**描述**: 用户管理界面 (仅管理员)
**认证**: 需要管理员权限

**响应** (200): HTML 页面

---

## 错误响应格式

所有 API 错误都遵循统一的错误响应格式：

```json
{
  "detail": "错误描述信息",
  "error_code": "ERROR_CODE",
  "timestamp": "2025-01-31T12:00:00Z"
}
```

### 常见 HTTP 状态码
- `200 OK`: 请求成功
- `201 Created`: 资源创建成功
- `204 No Content`: 操作成功无返回内容
- `400 Bad Request`: 请求参数错误
- `401 Unauthorized`: 认证失败
- `403 Forbidden`: 权限不足
- `404 Not Found`: 资源不存在
- `422 Unprocessable Entity`: 数据验证失败
- `500 Internal Server Error`: 服务器内部错误

---

## 认证说明

### JWT Token 认证
大多数现代 API 端点使用 JWT Bearer Token 认证：

```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

### KOReader kosync 兼容认证
KOReader 同步相关端点支持 kosync 协议的表单认证，使用用户名、密码、设备信息进行认证。

### 权限级别
- **匿名用户**: 可访问 OPDS 目录和书籍下载
- **登录用户**: 可访问个人同步数据、WebDAV 服务
- **管理员**: 可访问用户管理、书籍上传、系统设置

---

## 兼容性注意事项

1. **KOReader kosync 插件**: 完全兼容原始 kosync 协议
2. **OPDS 客户端**: 支持 OPDS 1.2 标准
3. **WebDAV 客户端**: 支持标准 WebDAV 协议
4. **密码格式**: 支持 MD5 哈希（KOReader 兼容）和现代 bcrypt 哈希

---

## 示例客户端代码

### Python 客户端示例

```python
import requests

# 登录获取 token
response = requests.post("http://localhost:8000/api/v1/auth/login", json={
    "username": "your_username",
    "password": "your_password"
})
token = response.json()["access_token"]

# 使用 token 访问 API
headers = {"Authorization": f"Bearer {token}"}
books = requests.get("http://localhost:8000/api/v1/books/", headers=headers)
print(books.json())
```

### curl 示例

```bash
# 登录
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# 获取书籍列表
curl -X GET "http://localhost:8000/api/v1/books/" \
  -H "Authorization: Bearer YOUR_TOKEN"

# KOReader 上传进度
curl -X PUT "http://localhost:8000/api/v1/syncs/progress" \
  -d "document=book.epub&progress=0.25&device=KOReader&user=username"
```

---

## OpenAPI/Swagger 文档

完整的交互式 API 文档可通过以下地址访问：
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json` 