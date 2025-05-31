# Kompanion Python

**KOReader兼容的图书管理Web应用** - Go版本kompanion的Python重新实现

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 功能特性

- ✅ **KOReader同步API** - 完全兼容KOReader的kosync插件
- ✅ **OPDS目录服务** - 支持OPDS 1.2协议，提供书籍浏览和下载
- ✅ **WebDAV统计上传** - 支持KOReader统计插件的数据上传
- ✅ **现代化Web界面** - 用户和书籍管理的Web界面
- ✅ **多数据库支持** - PostgreSQL和SQLite
- ✅ **异步高性能** - 基于FastAPI和SQLAlchemy 2.0
- ✅ **Docker部署** - 容器化部署支持
- ✅ **类型安全** - 完整的Python类型提示

## 快速开始

### 环境要求

- Python 3.8+
- uv包管理器（推荐）或pip

### 安装

1. **克隆项目**
```bash
git clone https://github.com/koreader/kompanion-python.git
cd kompanion-python
```

2. **安装依赖（使用uv）**
```bash
# 安装uv（如果还没有）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

uv sync
```

3. **配置环境变量**
```bash
# 复制示例配置文件
cp .env.example .env

# 编辑配置文件
nano .env
```

4. **初始化数据库**
```bash
# 使用SQLite（默认）
uv run python scripts/init_db.py

# 或使用PostgreSQL
export KOMPANION_DB_TYPE=postgresql
export KOMPANION_PG_URL=postgresql+asyncpg://user:pass@localhost/kompanion
uv run python scripts/init_db.py
```

5. **启动服务**
```bash
# 开发模式
uv run python -m app.main --reload

# 生产模式
uv run python -m app.main
```

服务启动后访问 [http://localhost:8080](http://localhost:8080)

## 配置说明

### 核心环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `KOMPANION_HTTP_PORT` | `8080` | 服务端口 |
| `KOMPANION_HOST` | `0.0.0.0` | 绑定地址 |
| `KOMPANION_DEBUG` | `false` | 调试模式 |
| `KOMPANION_LOG_LEVEL` | `INFO` | 日志级别 |

### 数据库配置

```bash
# SQLite（默认）
KOMPANION_DB_TYPE=sqlite
KOMPANION_SQLITE_PATH=./kompanion.db

# PostgreSQL
KOMPANION_DB_TYPE=postgresql
KOMPANION_PG_URL=postgresql+asyncpg://user:pass@localhost/kompanion
```

### 认证配置

```bash
# 管理员账户
KOMPANION_AUTH_USERNAME=admin
KOMPANION_AUTH_PASSWORD=your_secure_password

# JWT密钥（生产环境中必须更改）
KOMPANION_SECRET_KEY=your-secret-key
```

### 存储配置

```bash
# 书籍存储
KOMPANION_BSTORAGE_TYPE=database  # 或 filesystem
KOMPANION_BSTORAGE_PATH=./books

# 统计文件存储
KOMPANION_STATS_PATH=./stats
```

## KOReader集成

### 同步配置

在KOReader中配置同步服务器：

1. 进入 **设置 → 网络 → 进度同步**
2. 选择 **自定义同步服务器**
3. 配置服务器信息：
   - **服务器地址**: `http://your-server:8080`
   - **用户名**: 在应用中注册的用户名
   - **密码**: 用户密码

### OPDS目录

在KOReader中添加OPDS目录：

1. 进入 **设置 → 网络 → OPDS目录**
2. 添加新目录：
   - **名称**: Kompanion书库
   - **URL**: `http://your-server:8080/opds`
   - **认证**: 如需要，输入用户名和密码

### 统计上传

配置WebDAV统计上传：

1. 进入 **设置 → 统计 → 历史记录**
2. 启用 **上传到WebDAV**
3. 配置WebDAV信息：
   - **地址**: `http://your-server:8080/webdav`
   - **用户名**: 你的用户名
   - **密码**: 你的密码

## API文档

启动服务后，访问以下URL获取API文档：

- **Swagger UI**: [http://localhost:8080/api/docs](http://localhost:8080/api/docs)
- **ReDoc**: [http://localhost:8080/api/redoc](http://localhost:8080/api/redoc)

### 主要API端点

- `POST /api/v1/users/create` - 用户注册
- `POST /api/v1/users/auth` - 用户认证
- `PUT /api/v1/syncs/progress` - 上传阅读进度
- `GET /api/v1/syncs/progress/{document}` - 获取阅读进度
- `GET /opds` - OPDS目录根
- `/webdav/*` - WebDAV接口

## Docker部署

### 使用Docker Compose

```bash
# 启动服务（包含PostgreSQL）
docker-compose up -d

# 查看日志
docker-compose logs -f kompanion

# 停止服务
docker-compose down
```

### 单独Docker容器

```bash
# 构建镜像
docker build -t kompanion-python .

# 运行容器
docker run -d \
  --name kompanion \
  -p 8080:8080 \
  -e KOMPANION_DB_TYPE=sqlite \
  -v ./data:/app/data \
  kompanion-python
```

## 开发

### 环境设置

```bash
# 安装开发依赖
uv sync --extra dev

# 安装pre-commit钩子
pre-commit install
```

### 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/test_auth.py

# 生成覆盖率报告
uv run pytest --cov=app --cov-report=html
```

### 代码质量

```bash
# 代码格式化
uv run black app tests
uv run isort app tests

# 类型检查
uv run mypy app

# 代码检查
uv run flake8 app tests
```

## 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 贡献

欢迎提交Issue和Pull Request！请确保：

1. 代码遵循项目的代码规范
2. 添加必要的测试
3. 更新相关文档

## 致谢

- 原版 [kompanion](https://github.com/vanadium23/kompanion) 项目
- [KOReader](https://github.com/koreader/koreader) 社区
- [FastAPI](https://fastapi.tiangolo.com/) 框架

## 支持

如果遇到问题，请：

1. 查看 [文档](https://kompanion-python.readthedocs.io/)
2. 搜索现有的 [Issues](https://github.com/koreader/kompanion-python/issues)
3. 创建新的Issue并提供详细信息 