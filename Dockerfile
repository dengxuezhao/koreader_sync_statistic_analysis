# 构建阶段
FROM python:3.12-slim as builder

# 设置工作目录
WORKDIR /build

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装uv包管理器
RUN pip install uv

# 复制项目配置文件
COPY pyproject.toml ./

# 使用uv安装依赖到虚拟环境
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install --no-cache-dir -e .

# 生产阶段
FROM python:3.12-slim as production

# 创建非root用户
RUN groupadd -r kompanion && useradd -r -g kompanion kompanion

# 安装运行时系统依赖
RUN apt-get update && apt-get install -y \
    libpq5 \
    libffi8 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get purge -y --auto-remove

# 复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 设置工作目录
WORKDIR /app

# 复制应用代码
COPY --chown=kompanion:kompanion . .

# 创建必要的目录
RUN mkdir -p /app/storage/books /app/storage/covers /app/storage/webdav \
    && chown -R kompanion:kompanion /app/storage

# 切换到非root用户
USER kompanion

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 