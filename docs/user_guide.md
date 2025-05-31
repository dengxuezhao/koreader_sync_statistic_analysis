# Kompanion Python 用户指南

## 目录
- [简介](#简介)
- [快速开始](#快速开始)
- [安装指南](#安装指南)
- [配置说明](#配置说明)
- [KOReader 配置](#koreader-配置)
- [Web 管理界面](#web-管理界面)
- [故障排除](#故障排除)
- [API 使用](#api-使用)
- [常见问题](#常见问题)

## 简介

Kompanion Python 是为 KOReader 设计的书籍库管理 Web 应用程序，提供以下核心功能：

- 📚 **书籍管理**: 上传、分类、搜索电子书
- 🔄 **同步服务**: 与 KOReader 同步阅读进度
- 📡 **OPDS 目录**: 兼容标准 OPDS 协议的书籍目录
- 📂 **WebDAV 服务**: 支持 KOReader 统计文件上传
- 🌐 **Web 界面**: 现代化的管理界面

### 兼容性

- **KOReader**: 完全兼容 kosync 插件
- **OPDS 客户端**: 支持 OPDS 1.2 标准
- **WebDAV 客户端**: 标准 WebDAV 协议支持

---

## 快速开始

### 使用 Docker Compose (推荐)

1. **克隆项目**:
```bash
git clone https://github.com/your-repo/kompanion-python.git
cd kompanion-python
```

2. **配置环境变量**:
```bash
cp env.example .env
# 编辑 .env 文件，设置数据库连接和管理员账户
```

3. **启动服务**:
```bash
docker-compose up -d
```

4. **访问应用**:
- Web 界面: http://localhost:8000
- API 文档: http://localhost:8000/docs
- OPDS 目录: http://localhost:8000/api/v1/opds/

### 本地开发安装

1. **安装依赖**:
```bash
# 使用 uv (推荐)
pip install uv
uv sync

# 或使用 pip
pip install -r requirements.txt
```

2. **初始化数据库**:
```bash
python scripts/manage.py db init
```

3. **创建管理员用户**:
```bash
python scripts/create_admin.py --username admin --email admin@example.com --password yourpassword
```

4. **启动应用**:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 安装指南

### 系统要求

- **Python**: 3.12 或更高版本
- **数据库**: PostgreSQL 12+ (推荐) 或 SQLite 3.35+
- **内存**: 最少 1GB RAM
- **存储**: 根据书籍库大小确定

### 生产环境部署

#### 使用 Docker

1. **准备 Docker 环境**:
```bash
# 安装 Docker 和 Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

2. **配置生产环境**:
```bash
# 复制并编辑环境配置
cp env.example .env.production

# 编辑生产环境配置
nano .env.production
```

3. **启动生产服务**:
```bash
docker-compose -f docker-compose.yml --profile production up -d
```

#### 手动部署

1. **安装系统依赖**:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.12 python3.12-venv postgresql-client

# CentOS/RHEL
sudo yum install python3.12 python3.12-venv postgresql
```

2. **创建虚拟环境**:
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install uv
uv sync --frozen
```

3. **配置数据库**:
```bash
# PostgreSQL
sudo -u postgres psql
CREATE DATABASE kompanion;
CREATE USER kompanion_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE kompanion TO kompanion_user;
\q
```

4. **配置环境变量**:
```bash
export DATABASE_URL="postgresql+asyncpg://kompanion_user:your_password@localhost/kompanion"
export SECRET_KEY="your-secret-key-here"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="your-admin-password"
```

5. **初始化应用**:
```bash
python scripts/manage.py db init
python scripts/create_admin.py --username "$ADMIN_USERNAME" --email admin@example.com --password "$ADMIN_PASSWORD"
```

6. **启动服务**:
```bash
# 开发服务器
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 生产服务器 (使用 Gunicorn)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## 配置说明

### 环境变量配置

创建 `.env` 文件配置应用参数：

```bash
# 数据库配置
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/kompanion
# 或使用 SQLite
# DATABASE_URL=sqlite+aiosqlite:///./data/kompanion.db

# 应用配置
SECRET_KEY=your-very-secret-key-here
DEBUG=false
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# 管理员配置
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-admin-password
ADMIN_EMAIL=admin@your-domain.com

# 文件存储配置
BOOK_STORAGE_PATH=./storage/books
COVER_STORAGE_PATH=./storage/covers
WEBDAV_ROOT_PATH=./storage/webdav

# 上传限制
MAX_UPLOAD_SIZE=500  # MB
ALLOWED_EXTENSIONS=epub,pdf,mobi,azw,azw3,fb2,txt

# 服务器配置
HOST=0.0.0.0
PORT=8000
WORKERS=4

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log

# KOReader 兼容配置
ENABLE_MD5_AUTH=true
KOSYNC_COMPATIBLE=true

# OPDS 配置
OPDS_TITLE=Kompanion 书籍库
OPDS_DESCRIPTION=个人电子书籍管理系统
OPDS_AUTHOR=Your Name
OPDS_EMAIL=your@email.com

# WebDAV 配置
WEBDAV_ENABLED=true
WEBDAV_AUTH_REQUIRED=true
```

### 详细配置说明

#### 数据库配置
- **PostgreSQL** (推荐生产环境):
  ```
  DATABASE_URL=postgresql+asyncpg://username:password@host:port/database
  ```
- **SQLite** (适合小型部署):
  ```
  DATABASE_URL=sqlite+aiosqlite:///./data/kompanion.db
  ```

#### 安全配置
- `SECRET_KEY`: 用于 JWT 令牌加密，必须保密且足够复杂
- `ALLOWED_HOSTS`: 允许访问的主机名列表
- `ENABLE_MD5_AUTH`: 是否启用 MD5 认证 (KOReader 兼容)

#### 存储配置
- `BOOK_STORAGE_PATH`: 书籍文件存储路径
- `COVER_STORAGE_PATH`: 封面图片存储路径
- `WEBDAV_ROOT_PATH`: WebDAV 文件存储路径

#### 性能配置
- `WORKERS`: Gunicorn 工作进程数量
- `MAX_UPLOAD_SIZE`: 最大上传文件大小 (MB)
- `ALLOWED_EXTENSIONS`: 允许上传的文件扩展名

---

## KOReader 配置

### 同步插件配置

1. **启用同步插件**:
   - 打开 KOReader
   - 进入 "工具" → "插件管理器"
   - 启用 "同步" 插件

2. **配置同步服务器**:
   - 进入 "工具" → "同步"
   - 选择 "自定义同步服务器"
   - 设置服务器地址: `http://your-server:8000/api/v1`
   - 输入用户名和密码

3. **同步设置**:
   - 启用 "自动同步"
   - 设置同步间隔
   - 选择同步内容（阅读进度、书签等）

### 统计插件配置

1. **启用统计插件**:
   - 进入 "工具" → "插件管理器"
   - 启用 "统计" 插件

2. **配置 WebDAV 上传**:
   - 进入 "工具" → "统计"
   - 选择 "设置" → "云存储"
   - 配置 WebDAV 服务器:
     - 服务器: `http://your-server:8000/api/v1/webdav/`
     - 用户名: 你的用户名
     - 密码: 你的密码

### OPDS 目录配置

1. **添加 OPDS 目录**:
   - 打开 KOReader
   - 进入 "工具" → "OPDS 目录"
   - 添加新目录: `http://your-server:8000/api/v1/opds/`

2. **浏览和下载**:
   - 在 OPDS 目录中浏览书籍
   - 直接下载到 KOReader

---

## Web 管理界面

### 登录管理界面

访问 `http://your-server:8000/web/dashboard` 使用管理员账户登录。

### 仪表板

仪表板显示系统概览信息：
- 用户统计
- 书籍统计
- 同步活动
- 存储使用情况
- 最近活动

### 书籍管理

**上传书籍**:
1. 点击 "上传书籍" 按钮
2. 选择电子书文件 (支持 EPUB、PDF、MOBI 等)
3. 系统自动提取元数据和封面
4. 确认信息后上传

**管理书籍**:
- 搜索和筛选书籍
- 编辑书籍信息
- 查看下载统计
- 删除书籍

### 用户管理

**查看用户**:
- 用户列表
- 登录状态
- 设备信息
- 同步统计

**管理用户**:
- 创建新用户
- 重置密码
- 禁用/启用用户
- 删除用户

### 统计查看

**阅读统计**:
- 查看 KOReader 上传的阅读数据
- 阅读进度分析
- 时间统计
- 设备使用情况

**系统统计**:
- 存储使用情况
- API 调用统计
- 错误日志
- 性能指标

---

## 故障排除

### 常见问题

#### 1. 数据库连接失败
**症状**: 应用启动时出现数据库连接错误

**解决方案**:
```bash
# 检查数据库服务状态
sudo systemctl status postgresql

# 检查连接配置
python scripts/manage.py health

# 重新初始化数据库
python scripts/manage.py db reset
```

#### 2. KOReader 同步失败
**症状**: KOReader 无法连接同步服务器

**解决方案**:
1. 检查服务器地址配置
2. 验证用户名和密码
3. 检查网络连接
4. 查看服务器日志:
   ```bash
   tail -f logs/app.log
   ```

#### 3. 文件上传失败
**症状**: 书籍上传时出现错误

**解决方案**:
1. 检查文件大小限制
2. 验证文件格式支持
3. 检查存储空间
4. 查看权限设置:
   ```bash
   chmod -R 755 storage/
   ```

#### 4. OPDS 目录无法访问
**症状**: OPDS 客户端无法加载目录

**解决方案**:
1. 检查 OPDS 端点是否可访问
2. 验证 XML 格式正确性
3. 检查权限配置

### 日志查看

**应用日志**:
```bash
# 查看应用日志
tail -f logs/app.log

# 查看错误日志
tail -f logs/error.log

# 使用管理脚本查看系统状态
python scripts/manage.py stats
```

**Docker 日志**:
```bash
# 查看容器日志
docker-compose logs -f kompanion

# 查看特定服务日志
docker-compose logs -f postgres
```

### 性能优化

**数据库优化**:
```bash
# 重建索引
python scripts/manage.py db migrate

# 清理临时文件
python scripts/manage.py cleanup
```

**存储优化**:
```bash
# 检查存储使用情况
du -sh storage/*

# 清理未使用的封面文件
find storage/covers -name "*.jpg" -mtime +30 -delete
```

---

## API 使用

### 获取访问令牌

```bash
curl -X POST "http://your-server:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "your_password"
  }'
```

### 使用 API

```bash
# 设置令牌
TOKEN="your_access_token"

# 获取书籍列表
curl -X GET "http://your-server:8000/api/v1/books/" \
  -H "Authorization: Bearer $TOKEN"

# 上传同步进度 (KOReader 格式)
curl -X PUT "http://your-server:8000/api/v1/syncs/progress" \
  -d "document=book.epub&progress=0.25&device=KOReader&user=username"

# 获取 OPDS 目录
curl -X GET "http://your-server:8000/api/v1/opds/"
```

### Python 客户端示例

```python
import requests

class KompanionClient:
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.token = self._login(username, password)
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def _login(self, username, password):
        response = requests.post(f"{self.base_url}/auth/login", json={
            "username": username,
            "password": password
        })
        return response.json()["access_token"]
    
    def get_books(self):
        response = requests.get(f"{self.base_url}/books/", headers=self.headers)
        return response.json()
    
    def upload_progress(self, document, progress):
        data = {
            "document": document,
            "progress": progress,
            "device": "Python Client",
            "user": "username"
        }
        response = requests.put(f"{self.base_url}/syncs/progress", data=data)
        return response.json()

# 使用示例
client = KompanionClient("http://localhost:8000/api/v1", "admin", "password")
books = client.get_books()
print(f"Total books: {books['total']}")
```

---

## 常见问题

### Q: 如何更改管理员密码？
A: 使用管理脚本重新创建管理员用户：
```bash
python scripts/create_admin.py --username admin --email admin@example.com --password newpassword --force
```

### Q: 如何备份数据？
A: 使用管理脚本进行备份：
```bash
python scripts/manage.py db backup --path backup.sql
```

### Q: 如何升级到新版本？
A: 
1. 备份数据库和文件
2. 更新代码
3. 运行数据库迁移：
   ```bash
   python scripts/manage.py db migrate
   ```

### Q: 如何配置 HTTPS？
A: 推荐使用 Nginx 反向代理：
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Q: 如何迁移到新服务器？
A:
1. 在新服务器安装 Kompanion
2. 导出旧服务器数据：
   ```bash
   python scripts/manage.py db backup --path export.sql
   ```
3. 复制存储文件：
   ```bash
   rsync -av storage/ new-server:/path/to/storage/
   ```
4. 在新服务器导入数据
5. 更新 KOReader 配置中的服务器地址

### Q: 如何监控系统状态？
A: 使用管理脚本查看系统统计：
```bash
python scripts/manage.py stats
python scripts/manage.py health
```

---

## 技术支持

如果遇到问题，请：

1. 查看应用日志
2. 运行系统健康检查
3. 参考故障排除章节
4. 在 GitHub 项目页面提交 Issue

**项目地址**: https://github.com/your-repo/kompanion-python
**文档地址**: https://kompanion-python.readthedocs.io/ 