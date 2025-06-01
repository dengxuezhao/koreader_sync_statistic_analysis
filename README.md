# Kompanion 阅读统计分析系统

现代化的 KOReader 数据分析平台，提供 Web 管理界面和专业数据分析功能。

## ✨ 特色功能

### 🎯 双前端架构
- **传统 Web 界面** - 基于 Jinja2 模板的经典 Web 管理界面
- **现代数据分析界面** - 基于 Streamlit 的专业数据分析平台

### 📊 数据分析能力
- **实时数据监控** - KPI 指标实时展示
- **交互式图表** - 基于 Plotly 的专业图表组件
- **多维度分析** - 用户、内容、设备多角度数据分析

### 🔧 技术栈
- **后端**: FastAPI + SQLAlchemy + PostgreSQL
- **传统前端**: Jinja2 + Bootstrap
- **现代前端**: Streamlit + Plotly + Pandas
- **依赖管理**: uv (统一管理)

## 🏗️ 项目结构

```
├── app/
│   ├── api/                 # API 路由
│   ├── core/                # 核心配置
│   ├── db/                  # 数据库模型
│   ├── services/            # 业务逻辑
│   ├── templates/           # Jinja2 模板 (传统前端)
│   └── frontend/            # Streamlit 前端
│       ├── components/      # UI 组件
│       ├── pages/          # 页面模块
│       ├── config.py       # 前端配置
│       ├── api_client.py   # API 客户端
│       └── main.py         # 前端入口
├── main.py                 # 统一启动脚本
├── pyproject.toml         # 项目配置和依赖
└── uv.lock               # 依赖锁定文件
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装 uv（如果还没有）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装项目依赖
uv sync
```

### 2. 数据库配置

```bash
# 设置环境变量（可选，使用默认 SQLite）
export DATABASE_URL=postgresql://user:password@localhost/koreader_db

# 运行数据库迁移
uv run alembic upgrade head
```

### 3. 启动应用

**方式一：启动完整系统（推荐）**
```bash
uv run python main.py both
```
- 后端 API: http://localhost:8080
- 传统前端: http://localhost:8080/web
- 现代前端: http://localhost:8501

**方式二：分别启动**
```bash
# 仅启动后端服务
uv run python main.py backend

# 仅启动 Streamlit 前端
uv run python main.py frontend
```

**方式三：使用脚本命令**
```bash
# 启动后端
uv run koreader-server

# 启动前端
uv run koreader-streamlit
```

## 📋 功能模块

### 🎯 传统 Web 界面
- **仪表板** - 系统概览和基础统计
- **书籍管理** - 上传、删除、分类管理
- **用户管理** - 用户账号和权限管理
- **设备管理** - 设备注册和状态监控
- **数据统计** - 基础数据统计和报表

### 📊 现代数据分析界面
- **总览仪表板** - KPI 指标和趋势分析
- **用户行为分析** - 活跃度、阅读习惯分析
- **内容表现分析** - 书籍热度、分类分析
- **设备使用分析** - 设备类型、同步状态分析
- **阅读统计分析** - 详细阅读数据和洞察

## 🎨 设计系统

### 现代简约风格
- **主色调**: #0A2A4E (深邃蓝) - 专业可信
- **强调色**: #38B2AC (活力青) - 数据突出
- **辅助色**: #F59E0B (明亮橙) - 状态提示
- **字体**: Inter 无衬线字体家族

### 响应式设计
- **桌面端** - 完整功能布局
- **平板端** - 自适应布局
- **移动端** - 优化触控体验

## 🔧 配置说明

### 环境变量
```bash
# 数据库配置
DATABASE_URL=postgresql://user:password@localhost/dbname

# 服务配置
HOST=0.0.0.0
PORT=8080

# JWT 配置
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Redis 配置（可选）
REDIS_URL=redis://localhost:6379
```

### 主要配置文件
- `app/core/config.py` - 后端核心配置
- `app/frontend/config.py` - 前端界面配置
- `pyproject.toml` - 项目依赖和元数据

## 📱 API 文档

### 自动生成文档
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

### 主要 API 端点
- `POST /api/v1/auth/login` - 用户登录
- `GET /api/v1/books/` - 获取书籍列表
- `GET /api/v1/web/dashboard` - 仪表板数据
- `GET /api/v1/books/stats/overview` - 统计概览

## 🔮 架构优势

### 1. 统一依赖管理
- 使用 uv 统一管理所有依赖
- 避免多个 requirements.txt 的混乱
- 更快的依赖解析和安装

### 2. 模块化设计
- 前后端集成但逻辑分离
- 组件化的 UI 设计
- 易于维护和扩展

### 3. 灵活部署
- 支持独立部署前端或后端
- 支持完整系统一键启动
- 便于开发和生产环境切换

## 🚀 开发指南

### 添加新的 Streamlit 页面
1. 在 `app/frontend/pages/` 创建新页面文件
2. 在 `app/frontend/config.py` 添加导航配置
3. 在 `app/frontend/main.py` 添加路由

### 扩展 API 功能
1. 在 `app/api/v1/` 添加新的路由模块
2. 在 `app/services/` 添加业务逻辑
3. 更新 `app/frontend/api_client.py` 添加客户端方法

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**新架构的优势**：
- ✅ 统一的依赖管理（仅使用 uv）
- ✅ 集成的项目结构
- ✅ 灵活的运行模式
- ✅ 更好的代码复用
- ✅ 简化的部署流程 