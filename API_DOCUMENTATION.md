# Kompanion Python API 文档

## 概述

Kompanion是一个与KOReader兼容的书籍管理和同步服务器，提供完整的REST API用于：
- 用户认证和管理
- 设备注册和同步
- 阅读进度跟踪
- 书籍管理和下载
- OPDS目录服务
- WebDAV兼容
- 统计分析和可视化

**基础URL**: `http://localhost:8080`
**API版本**: v1
**认证方式**: JWT Bearer Token / HTTP Basic Auth

## 认证说明

### JWT Token认证
大多数API端点需要JWT Token认证：

```http
Authorization: Bearer <your_jwt_token>
```

### HTTP Basic认证
WebDAV端点使用HTTP Basic认证：

```http
Authorization: Basic <base64(username:password)>
```

### 获取Token
```bash
curl -X POST "http://localhost:8080/api/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

## API端点列表

## 1. 认证系统 (`/api/v1/auth`)

### 1.1 用户注册
- **端点**: `POST /api/v1/auth/register`
- **描述**: 注册新用户（现代化API）
- **认证**: 无需认证

**请求体**:
```json
{
  "username": "string",
  "password": "string",
  "email": "string" // 可选
}
```

**响应**:
```json
{
  "username": "string"
}
```

### 1.2 用户登录
- **端点**: `POST /api/v1/auth/login`
- **描述**: 用户登录（现代化API）
- **认证**: 无需认证

**请求体**:
```json
{
  "username": "string",
  "password": "string"
}
```

**响应**:
```json
{
  "username": "string",
  "userkey": "string"
}
```

### 1.3 获取JWT Token
- **端点**: `POST /api/v1/auth/token`
- **描述**: 获取JWT访问令牌
- **认证**: 无需认证

**请求体**:
```json
{
  "username": "string",
  "password": "string"
}
```

**响应**:
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### 1.4 获取当前用户信息
- **端点**: `GET /api/v1/auth/me`
- **描述**: 获取当前认证用户的信息
- **认证**: JWT Token

**响应**:
```json
{
  "id": 1,
  "username": "string",
  "email": "string",
  "is_admin": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 1.5 设备注册
- **端点**: `POST /api/v1/auth/device/register`
- **描述**: 注册KOReader设备
- **认证**: 无需认证

**请求体**:
```json
{
  "user_data": {
    "username": "string",
    "password": "string"
  },
  "device_data": {
    "device_name": "string",
    "device_id": "string",
    "model": "string",
    "firmware_version": "string",
    "app_version": "string"
  }
}
```

### 1.6 KOReader兼容端点

#### 1.6.1 KOReader用户创建
- **端点**: `POST /api/v1/auth/users/create`
- **描述**: KOReader kosync兼容的用户创建
- **认证**: 无需认证
- **内容类型**: `application/x-www-form-urlencoded`

**请求参数**:
```
username=string&password=string
```

#### 1.6.2 KOReader用户认证
- **端点**: `POST /api/v1/auth/users/auth`
- **描述**: KOReader kosync兼容的用户认证
- **认证**: 无需认证
- **内容类型**: `application/x-www-form-urlencoded`

**请求参数**:
```
username=string&password=string
```

## 2. 同步API (`/api/v1/syncs`)

### 2.1 上传同步进度
- **端点**: `PUT /api/v1/syncs/progress`
- **描述**: 上传阅读进度（KOReader kosync兼容）
- **认证**: JWT Token
- **内容类型**: `application/x-www-form-urlencoded`

**请求参数**:
```
document=string&progress=string&percentage=number&device=string&page=integer&pos=string&chapter=string&timestamp=integer
```

**响应**:
```json
{
  "document": "string",
  "progress": "string", 
  "percentage": 85.5,
  "device": "string",
  "device_id": "string",
  "timestamp": 1640995200
}
```

### 2.2 同步进度（POST）
- **端点**: `POST /api/v1/syncs/progress`
- **描述**: POST方式的进度同步
- **认证**: JWT Token
- **内容类型**: `application/x-www-form-urlencoded`

### 2.3 获取同步进度列表
- **端点**: `GET /api/v1/syncs/progress`
- **描述**: 获取用户所有同步进度
- **认证**: JWT Token

**查询参数**:
- `page`: 页码（默认1）
- `size`: 每页大小（默认20，最大100）
- `document_filter`: 文档名称过滤

**响应**:
```json
{
  "total": 100,
  "items": [
    {
      "id": 1,
      "user_id": 1,
      "device_id": 1,
      "book_id": 1,
      "document": "book_name.pdf",
      "progress": "50.5",
      "percentage": 50.5,
      "reading_percentage": "50.5%",
      "device_name": "KOReader Device",
      "book_title": "Book Title",
      "book_author": "Author Name",
      "last_sync_at": "2024-01-01T00:00:00Z",
      "sync_count": 5,
      "is_finished": false,
      "is_recently_synced": true,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "page": 1,
  "size": 20
}
```

### 2.4 获取文档同步进度
- **端点**: `GET /api/v1/syncs/progress/{document}`
- **描述**: 获取特定文档的同步进度
- **认证**: JWT Token

### 2.5 获取同步进度详情
- **端点**: `GET /api/v1/syncs/progress/detail/{progress_id}`
- **描述**: 获取特定进度记录详情
- **认证**: JWT Token

### 2.6 更新同步进度
- **端点**: `PUT /api/v1/syncs/progress/detail/{progress_id}`
- **描述**: 更新特定进度记录
- **认证**: JWT Token

**请求体**:
```json
{
  "progress": 75.5,
  "percentage": 75.5,
  "page": 150,
  "pos": "chapter_5",
  "chapter": "第五章"
}
```

### 2.7 删除同步进度
- **端点**: `DELETE /api/v1/syncs/progress/detail/{progress_id}`
- **描述**: 删除进度记录
- **认证**: JWT Token

### 2.8 批量上传同步进度
- **端点**: `POST /api/v1/syncs/progress/batch`
- **描述**: 批量上传多个文档的阅读进度
- **认证**: JWT Token

**请求体**:
```json
[
  {
    "document": "book1.pdf",
    "progress": "25.5",
    "percentage": 25.5,
    "device": "device1"
  },
  {
    "document": "book2.epub",
    "progress": "75.0",
    "percentage": 75.0,
    "device": "device1"
  }
]
```

### 2.9 获取设备同步状态
- **端点**: `GET /api/v1/syncs/devices/status`
- **描述**: 获取用户所有设备的同步状态
- **认证**: JWT Token

## 3. OPDS目录 (`/api/v1/opds`)

### 3.1 OPDS根目录
- **端点**: `GET /api/v1/opds/`
- **描述**: OPDS目录根端点
- **认证**: JWT Token

### 3.2 最新书籍
- **端点**: `GET /api/v1/opds/catalog/recent`
- **描述**: 最新书籍目录
- **认证**: JWT Token

**查询参数**:
- `page`: 页码（默认1）
- `size`: 每页大小（默认20，最大100）

### 3.3 热门书籍
- **端点**: `GET /api/v1/opds/catalog/popular`
- **描述**: 热门书籍目录（按下载次数排序）
- **认证**: JWT Token

### 3.4 所有书籍
- **端点**: `GET /api/v1/opds/catalog/all`
- **描述**: 所有书籍目录
- **认证**: JWT Token

### 3.5 搜索书籍
- **端点**: `GET /api/v1/opds/search`
- **描述**: 搜索书籍
- **认证**: JWT Token

**查询参数**:
- `q`: 搜索关键词（必需）
- `page`: 页码（默认1）
- `size`: 每页大小（默认20，最大100）

## 4. 书籍管理 (`/api/v1/books`)

### 4.1 上传书籍
- **端点**: `POST /api/v1/books/upload`
- **描述**: 上传书籍文件，支持自动元数据提取
- **认证**: JWT Token
- **内容类型**: `multipart/form-data`

**请求参数**:
- `file`: 书籍文件（必需）
- `title`: 书籍标题（可选）
- `author`: 作者（可选）
- `description`: 描述（可选）
- `publisher`: 出版商（可选）
- `genre`: 类型（可选）
- `series`: 系列（可选）
- `series_index`: 系列索引（可选）
- `language`: 语言（可选）
- `extract_metadata`: 是否自动提取元数据（默认true）

### 4.2 获取书籍列表
- **端点**: `GET /api/v1/books/`
- **描述**: 获取书籍列表，支持搜索、过滤和排序
- **认证**: JWT Token

**查询参数**:
- `page`: 页码（默认1）
- `size`: 每页大小（默认20，最大100）
- `search`: 搜索关键词
- `author`: 作者过滤
- `genre`: 类型过滤
- `format`: 格式过滤
- `sort_by`: 排序字段（默认created_at）
- `sort_order`: 排序方向（默认desc）

### 4.3 获取书籍详情
- **端点**: `GET /api/v1/books/{book_id}`
- **描述**: 获取书籍详细信息
- **认证**: JWT Token

### 4.4 更新书籍信息
- **端点**: `PUT /api/v1/books/{book_id}`
- **描述**: 更新书籍信息（仅管理员）
- **认证**: JWT Token
- **内容类型**: `application/x-www-form-urlencoded`

### 4.5 删除书籍
- **端点**: `DELETE /api/v1/books/{book_id}`
- **描述**: 删除书籍（仅管理员）
- **认证**: JWT Token

**查询参数**:
- `delete_files`: 是否删除文件（默认false）

### 4.6 下载书籍
- **端点**: `GET /api/v1/books/{book_id}/download`
- **描述**: 下载书籍文件，会记录下载次数
- **认证**: JWT Token

### 4.7 获取书籍封面
- **端点**: `GET /api/v1/books/{book_id}/cover`
- **描述**: 获取书籍封面
- **认证**: JWT Token

**查询参数**:
- `size`: 封面尺寸（可选，支持thumbnail）

### 4.8 阅读统计概览
- **端点**: `GET /api/v1/books/stats/overview`
- **描述**: 获取阅读统计概览数据
- **认证**: JWT Token

**响应**:
```json
{
  "total_books": 150,
  "completed_books": 45,
  "reading_books": 5,
  "completion_rate": 30.0,
  "total_reading_hours": 120.5,
  "avg_reading_time": 4800,
  "devices_count": 3,
  "recent_activity_count": 2
}
```

### 4.9 公开阅读统计 ⭐
- **端点**: `GET /api/v1/books/stats/public`
- **描述**: 获取公开的阅读统计数据，无需认证（博客嵌入专用）
- **认证**: 无需认证

**查询参数**:
- `user_id`: 特定用户ID（可选）
- `username`: 特定用户名（可选）

**响应**:
```json
{
  "overview": {
    "total_books": 150,
    "completed_books": 45,
    "reading_books": 5,
    "completion_rate": 30.0,
    "total_reading_hours": 120.5
  },
  "recent_books": [
    {
      "title": "书籍标题",
      "author": "作者",
      "progress": 75.5,
      "last_read": "2024-01-01T00:00:00Z"
    }
  ],
  "completed_books": [
    {
      "title": "已完成的书",
      "author": "作者",
      "completed_at": "2024-01-01T00:00:00Z"
    }
  ],
  "reading_progress": [
    {
      "title": "正在阅读",
      "progress": 45.2,
      "percentage": "45.2%"
    }
  ]
}
```

## 5. WebDAV服务 (`/api/v1/webdav`)

### 5.1 WebDAV PROPFIND
- **端点**: `PROPFIND /api/v1/webdav/{path}`
- **描述**: 获取资源属性信息，支持目录列表
- **认证**: HTTP Basic Auth

### 5.2 WebDAV GET
- **端点**: `GET /api/v1/webdav/{path}`
- **描述**: 下载指定的文件
- **认证**: HTTP Basic Auth

### 5.3 WebDAV PUT
- **端点**: `PUT /api/v1/webdav/{path}`
- **描述**: 上传文件到指定路径，主要用于KOReader统计文件上传
- **认证**: HTTP Basic Auth

### 5.4 WebDAV DELETE
- **端点**: `DELETE /api/v1/webdav/{path}`
- **描述**: 删除指定的文件或目录
- **认证**: HTTP Basic Auth

### 5.5 WebDAV MKCOL
- **端点**: `MKCOL /api/v1/webdav/{path}`
- **描述**: 创建目录
- **认证**: HTTP Basic Auth

### 5.6 WebDAV OPTIONS
- **端点**: `OPTIONS /api/v1/webdav/{path}`
- **描述**: 返回支持的WebDAV方法
- **认证**: 无需认证

### 5.7 WebDAV使用统计
- **端点**: `GET /api/v1/webdav/stats/overview`
- **描述**: 获取WebDAV服务使用统计
- **认证**: JWT Token

### 5.8 KOReader阅读统计
- **端点**: `GET /api/v1/webdav/stats/reading`
- **描述**: 获取通过WebDAV上传的KOReader阅读统计数据
- **认证**: JWT Token

**查询参数**:
- `page`: 页码（默认1）
- `size`: 每页大小（默认20，最大100）
- `device_name`: 设备名称过滤
- `book_title`: 书籍标题过滤

## 6. Web界面 (`/api/v1/web`) - Streamlit前端专用

### 6.1 登录页面
- **端点**: `GET /api/v1/web/login`
- **描述**: 登录页面（HTML）
- **认证**: 无需认证

### 6.2 管理仪表板
- **端点**: `GET /api/v1/web/dashboard`
- **描述**: 管理仪表板页面（HTML）
- **认证**: JWT Token

### 6.3 用户管理
- **端点**: `GET /api/v1/web/users`
- **描述**: 用户管理页面（HTML，仅管理员）
- **认证**: JWT Token

### 6.4 书籍管理
- **端点**: `GET /api/v1/web/books`
- **描述**: 书籍管理页面（HTML）
- **认证**: JWT Token

### 6.5 统计信息
- **端点**: `GET /api/v1/web/statistics`
- **描述**: 统计信息页面（HTML）
- **认证**: JWT Token

### 6.6 设备管理
- **端点**: `GET /api/v1/web/devices`
- **描述**: 设备管理页面（HTML）
- **认证**: JWT Token

### 6.7 系统设置
- **端点**: `GET /api/v1/web/settings`
- **描述**: 系统设置页面（HTML，仅管理员）
- **认证**: JWT Token

### 6.8 设备列表JSON ⭐
- **端点**: `GET /api/v1/web/devices/json`
- **描述**: 获取设备列表JSON数据（专门为Streamlit前端提供）
- **认证**: JWT Token

**查询参数**:
- `page`: 页码（默认1）
- `size`: 每页大小（默认20，最大100）

**响应**:
```json
{
  "total": 5,
  "items": [
    {
      "id": 1,
      "user_id": 1,
      "device_name": "KOReader Device",
      "device_id": "unique_device_id",
      "model": "Kindle Paperwhite",
      "firmware_version": "5.14.2",
      "app_version": "2023.10",
      "last_sync_at": "2024-01-01T00:00:00Z",
      "sync_count": 50,
      "is_active": true,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "page": 1,
  "size": 20
}
```

### 6.9 阅读统计JSON ⭐
- **端点**: `GET /api/v1/web/statistics/json`
- **描述**: 获取阅读统计JSON数据（专门为Streamlit前端提供）
- **认证**: JWT Token

**查询参数**:
- `page`: 页码（默认1）
- `size`: 每页大小（默认20，最大100）
- `device_filter`: 设备过滤

**响应**:
```json
{
  "total": 100,
  "items": [
    {
      "book_title": "书籍标题",
      "book_author": "作者",
      "device_name": "设备名称",
      "progress": 75.5,
      "percentage": "75.5%",
      "reading_time": 3600,
      "last_read": "2024-01-01T00:00:00Z",
      "is_finished": false
    }
  ],
  "summary": {
    "total_books": 150,
    "completed_books": 45,
    "total_reading_time": 120.5,
    "avg_progress": 65.2
  }
}
```

## 7. 系统端点

### 7.1 健康检查
- **端点**: `GET /health`
- **描述**: 应用健康检查
- **认证**: 无需认证

**响应**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "database": "connected",
  "cache": "connected",
  "version": "1.0.0"
}
```

### 7.2 性能指标
- **端点**: `GET /metrics`
- **描述**: 获取Prometheus格式的性能指标
- **认证**: 无需认证

### 7.3 安全状态
- **端点**: `GET /security/status`
- **描述**: 获取安全状态信息
- **认证**: 无需认证

## 8. 兼容性端点 (`/webdav`)

为了完全兼容KOReader，系统还提供了不带`/api/v1`前缀的WebDAV端点：

- `PROPFIND /webdav/{path}`
- `GET /webdav/{path}`
- `PUT /webdav/{path}`
- `DELETE /webdav/{path}`
- `MKCOL /webdav/{path}`
- `OPTIONS /webdav/{path}`

## 错误码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求错误 |
| 401 | 未认证 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 422 | 参数验证错误 |
| 429 | 请求过于频繁 |
| 500 | 服务器内部错误 |

## 使用示例

### 完整的认证和同步流程

```bash
# 1. 获取JWT Token
TOKEN=$(curl -s -X POST "http://localhost:8080/api/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}' | jq -r '.access_token')

# 2. 获取阅读统计概览
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/v1/books/stats/overview"

# 3. 获取同步进度列表
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/v1/syncs/progress?page=1&size=10"

# 4. 上传阅读进度
curl -X PUT "http://localhost:8080/api/v1/syncs/progress" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "document=mybook.pdf&progress=75.5&percentage=75.5&device=my_device"

# 5. 获取公开统计（无需认证）
curl "http://localhost:8080/api/v1/books/stats/public?username=admin"
```

### KOReader配置示例

在KOReader中配置kosync：

```
服务器: http://your-server:8080
用户名: your_username
密码: your_password
```

KOReader会自动使用以下端点：
- 用户认证: `/api/v1/auth/users/auth`
- 进度上传: `/api/v1/syncs/progress`
- 进度获取: `/api/v1/syncs/progress/{document}`

### WebDAV配置示例

对于统计文件上传，可以配置：

```
WebDAV URL: http://your-server:8080/webdav/
用户名: your_username
密码: your_password
```

## 特色功能

### 1. 公开阅读统计API
这是Kompanion的独创功能，允许无需认证即可获取用户的阅读统计数据，非常适合：
- 个人博客展示
- 读书年报制作
- 社交媒体分享
- 阅读习惯分析

### 2. Streamlit前端专用JSON端点
专门为现代化前端设计的JSON API：
- `/api/v1/web/devices/json` - 设备管理数据
- `/api/v1/web/statistics/json` - 阅读统计数据

### 3. 完整的KOReader兼容性
100%兼容KOReader kosync协议，无需修改任何KOReader设置即可使用。

### 4. 现代化安全机制
- JWT Token认证
- 速率限制
- SQL注入防护
- 安全头设置
- 审计日志

## 开发与测试

### 测试API连通性
使用项目提供的测试脚本：

```bash
python test_api_endpoints.py
```

### API文档访问
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc
- OpenAPI JSON: http://localhost:8080/openapi.json

### 前端界面
- 传统Web界面: http://localhost:8080/web
- 现代Streamlit界面: http://localhost:8501

---

**更新时间**: 2024年1月
**版本**: 1.0.0
**维护者**: Kompanion开发团队 