# Kompanion Python 部署运维指南

## 目录
- [快速部署](#快速部署)
- [生产环境部署](#生产环境部署)
- [容器化部署](#容器化部署)
- [系统配置](#系统配置)
- [性能优化](#性能优化)
- [监控和日志](#监控和日志)
- [备份恢复](#备份恢复)
- [故障排除](#故障排除)
- [安全加固](#安全加固)
- [版本升级](#版本升级)

---

## 快速部署

### 自动安装脚本

最简单的部署方式是使用自动安装脚本：

```bash
# 下载并运行安装脚本
curl -sSL https://raw.githubusercontent.com/your-repo/kompanion-python/main/scripts/install.sh | bash

# 或者手动下载后运行
wget https://raw.githubusercontent.com/your-repo/kompanion-python/main/scripts/install.sh
chmod +x install.sh
./install.sh
```

安装脚本将自动：
- 检测操作系统类型
- 安装系统依赖
- 配置Python环境
- 创建数据库
- 设置服务和反向代理
- 创建管理员用户

### Docker Compose 部署

```bash
# 克隆项目
git clone https://github.com/your-repo/kompanion-python.git
cd kompanion-python

# 配置环境变量
cp env.example .env
vim .env

# 启动服务
docker-compose up -d
```

---

## 生产环境部署

### 系统要求

**最低配置**:
- CPU: 2核心
- 内存: 4GB RAM
- 存储: 50GB (根据书籍库大小调整)
- 操作系统: Ubuntu 20.04+ / CentOS 8+ / Debian 11+

**推荐配置**:
- CPU: 4核心
- 内存: 8GB RAM
- 存储: 500GB SSD
- 网络: 稳定的互联网连接

### 手动部署步骤

#### 1. 准备系统环境

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip \
    postgresql-14 nginx supervisor git curl build-essential \
    libpq-dev libffi-dev libssl-dev libjpeg-dev libpng-dev

# CentOS/RHEL
sudo yum update -y
sudo yum install -y python3.12 python3.12-venv python3-pip \
    postgresql14-server nginx supervisor git curl gcc gcc-c++ \
    postgresql14-devel libffi-devel openssl-devel libjpeg-devel
```

#### 2. 配置PostgreSQL数据库

```bash
# 初始化PostgreSQL
sudo postgresql-setup --initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 创建数据库和用户
sudo -u postgres psql << EOF
CREATE DATABASE kompanion;
CREATE USER kompanion_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE kompanion TO kompanion_user;
ALTER DATABASE kompanion OWNER TO kompanion_user;
\q
EOF

# 配置PostgreSQL认证
sudo vim /var/lib/pgsql/data/pg_hba.conf
# 添加或修改：
# local   kompanion    kompanion_user                  md5
# host    kompanion    kompanion_user    127.0.0.1/32  md5

sudo systemctl restart postgresql
```

#### 3. 创建应用用户和目录

```bash
# 创建应用用户
sudo useradd -m -s /bin/bash kompanion
sudo mkdir -p /opt/kompanion
sudo chown kompanion:kompanion /opt/kompanion

# 切换到应用用户
sudo -u kompanion -i
```

#### 4. 部署应用代码

```bash
cd /opt/kompanion

# 克隆代码
git clone https://github.com/your-repo/kompanion-python.git app
cd app

# 创建虚拟环境
python3.12 -m venv venv
source venv/bin/activate

# 安装依赖
pip install --upgrade pip uv
uv sync --frozen
```

#### 5. 配置应用

```bash
# 创建配置文件
cp env.example /opt/kompanion/.env
vim /opt/kompanion/.env
```

配置示例：
```bash
# 数据库配置
DATABASE_URL=postgresql+asyncpg://kompanion_user:your_secure_password@localhost:5432/kompanion

# 应用配置
SECRET_KEY=your-very-secure-secret-key-here
DEBUG=false
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# 存储配置
BOOK_STORAGE_PATH=/opt/kompanion/storage/books
COVER_STORAGE_PATH=/opt/kompanion/storage/covers
WEBDAV_ROOT_PATH=/opt/kompanion/storage/webdav

# 管理员配置
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_admin_password
ADMIN_EMAIL=admin@yourdomain.com

# 性能配置
WORKERS=4
MAX_UPLOAD_SIZE=1000
```

#### 6. 初始化数据库

```bash
cd /opt/kompanion/app
source venv/bin/activate

# 初始化数据库
python scripts/manage.py db init

# 创建管理员用户
python scripts/create_admin.py \
    --username admin \
    --email admin@yourdomain.com \
    --password your_admin_password
```

#### 7. 配置系统服务

**Systemd 服务配置**:
```bash
sudo tee /etc/systemd/system/kompanion.service > /dev/null << 'EOF'
[Unit]
Description=Kompanion Python Web Application
After=network.target postgresql.service

[Service]
Type=exec
User=kompanion
Group=kompanion
WorkingDirectory=/opt/kompanion/app
Environment="PATH=/opt/kompanion/app/venv/bin"
EnvironmentFile=/opt/kompanion/.env
ExecStart=/opt/kompanion/app/venv/bin/gunicorn \
    app.main:app \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --max-requests 1000 \
    --max-requests-jitter 100
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable kompanion
sudo systemctl start kompanion
```

#### 8. 配置Nginx反向代理

```bash
sudo tee /etc/nginx/sites-available/kompanion > /dev/null << 'EOF'
# 强制HTTPS重定向
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS主配置
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL证书配置
    ssl_certificate /etc/ssl/certs/kompanion.crt;
    ssl_certificate_key /etc/ssl/private/kompanion.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # 安全头
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # 文件上传大小限制
    client_max_body_size 1G;
    client_body_timeout 120s;
    
    # 主要代理配置
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_buffering off;
    }
    
    # 静态文件服务
    location /static/ {
        alias /opt/kompanion/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        gzip_static on;
    }
    
    # 书籍封面和文件
    location /storage/ {
        alias /opt/kompanion/storage/;
        expires 30d;
        add_header Cache-Control "public";
    }
    
    # WebDAV优化
    location /api/v1/webdav/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_request_buffering off;
        proxy_buffering off;
        client_max_body_size 100M;
    }
    
    # 限制访问敏感文件
    location ~ /\. {
        deny all;
    }
    
    location ~* \.(log|env)$ {
        deny all;
    }
}
EOF

# 启用站点
sudo ln -sf /etc/nginx/sites-available/kompanion /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 测试配置
sudo nginx -t
sudo systemctl restart nginx
```

---

## 容器化部署

### Docker Compose 生产配置

```yaml
version: '3.8'

services:
  kompanion:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    container_name: kompanion-app
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql+asyncpg://kompanion:${DB_PASSWORD}@postgres:5432/kompanion
      - SECRET_KEY=${SECRET_KEY}
      - ADMIN_USERNAME=${ADMIN_USERNAME}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - ADMIN_EMAIL=${ADMIN_EMAIL}
    volumes:
      - ./storage:/app/storage
      - ./logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - kompanion-network

  postgres:
    image: postgres:15-alpine
    container_name: kompanion-db
    restart: unless-stopped
    environment:
      - POSTGRES_DB=kompanion
      - POSTGRES_USER=kompanion
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_postgres.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kompanion"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - kompanion-network

  redis:
    image: redis:7-alpine
    container_name: kompanion-cache
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - kompanion-network

  nginx:
    image: nginx:alpine
    container_name: kompanion-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx.conf:/etc/nginx/nginx.conf
      - ./docker/ssl:/etc/ssl/certs
      - ./storage:/var/www/storage:ro
    depends_on:
      - kompanion
    networks:
      - kompanion-network

volumes:
  postgres_data:
  redis_data:

networks:
  kompanion-network:
    driver: bridge
```

### Kubernetes 部署

```yaml
# kompanion-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kompanion
  labels:
    app: kompanion
spec:
  replicas: 3
  selector:
    matchLabels:
      app: kompanion
  template:
    metadata:
      labels:
        app: kompanion
    spec:
      containers:
      - name: kompanion
        image: kompanion:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: kompanion-secrets
              key: database-url
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: kompanion-secrets
              key: secret-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        volumeMounts:
        - name: storage
          mountPath: /app/storage
      volumes:
      - name: storage
        persistentVolumeClaim:
          claimName: kompanion-storage

---
apiVersion: v1
kind: Service
metadata:
  name: kompanion-service
spec:
  selector:
    app: kompanion
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

## 系统配置

### 操作系统优化

```bash
# 增加文件描述符限制
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 调整内核参数
cat >> /etc/sysctl.conf << EOF
# 网络优化
net.core.somaxconn = 1024
net.core.netdev_max_backlog = 5000
net.core.rmem_default = 262144
net.core.rmem_max = 16777216
net.core.wmem_default = 262144
net.core.wmem_max = 16777216

# TCP优化
net.ipv4.tcp_wmem = 4096 65536 16777216
net.ipv4.tcp_rmem = 4096 65536 16777216
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_tw_reuse = 1

# 文件系统优化
fs.file-max = 2097152
vm.swappiness = 10
vm.dirty_ratio = 60
vm.dirty_background_ratio = 2
EOF

sysctl -p
```

### PostgreSQL 优化

```bash
# 编辑PostgreSQL配置
sudo vim /var/lib/pgsql/data/postgresql.conf
```

关键配置参数：
```bash
# 内存配置
shared_buffers = 256MB                # 系统内存的25%
effective_cache_size = 1GB            # 系统内存的75%
work_mem = 4MB                        # 每个查询的工作内存
maintenance_work_mem = 64MB           # 维护操作内存

# 连接配置
max_connections = 200                 # 最大连接数
listen_addresses = 'localhost'       # 监听地址

# 性能配置
random_page_cost = 1.1               # SSD优化
effective_io_concurrency = 200      # 并发IO
max_worker_processes = 8             # 工作进程数
max_parallel_workers_per_gather = 2 # 并行查询

# WAL配置
wal_buffers = 16MB
checkpoint_completion_target = 0.9
wal_compression = on

# 日志配置
logging_collector = on
log_directory = 'pg_log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_min_duration_statement = 1000
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on
```

### Nginx 优化

```nginx
# /etc/nginx/nginx.conf
user nginx;
worker_processes auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    # 基础优化
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    server_tokens off;
    
    # 缓冲区优化
    client_body_buffer_size 128k;
    client_max_body_size 1G;
    client_header_buffer_size 1k;
    large_client_header_buffers 4 4k;
    output_buffers 1 32k;
    postpone_output 1460;
    
    # Gzip压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;
    
    # 日志格式
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    '$request_time $upstream_response_time';
    
    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log;
    
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
}
```

---

## 性能优化

### 应用层优化

1. **数据库连接池**:
```python
# app/core/database.py
from sqlalchemy import create_engine

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,           # 连接池大小
    max_overflow=30,        # 最大溢出连接
    pool_pre_ping=True,     # 连接前ping检查
    pool_recycle=3600,      # 连接回收时间
)
```

2. **缓存配置**:
```python
# 使用Redis缓存
import redis
from functools import wraps

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_result(expire=3600):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            result = await func(*args, **kwargs)
            redis_client.setex(cache_key, expire, json.dumps(result))
            return result
        return wrapper
    return decorator
```

3. **异步任务队列**:
```python
# 使用Celery处理异步任务
from celery import Celery

celery_app = Celery(
    'kompanion',
    broker='redis://localhost:6379/1',
    backend='redis://localhost:6379/2'
)

@celery_app.task
def process_book_metadata(book_id):
    # 异步处理书籍元数据提取
    pass
```

### 数据库优化

1. **索引优化**:
```sql
-- 为常用查询添加索引
CREATE INDEX idx_books_title ON books (title);
CREATE INDEX idx_books_author ON books (author);
CREATE INDEX idx_books_format ON books (file_format);
CREATE INDEX idx_sync_progress_user_document ON sync_progress (user_id, document);
CREATE INDEX idx_reading_stats_user_device ON reading_statistics (user_id, device_id);

-- 复合索引
CREATE INDEX idx_books_available_created ON books (is_available, created_at);
CREATE INDEX idx_sync_progress_timestamp ON sync_progress (user_id, timestamp DESC);
```

2. **查询优化**:
```python
# 使用预加载减少N+1查询
from sqlalchemy.orm import selectinload

# 优化前
users = await session.execute(select(User))
for user in users.scalars():
    devices = await session.execute(select(Device).where(Device.user_id == user.id))

# 优化后
users = await session.execute(
    select(User).options(selectinload(User.devices))
)
```

### 静态文件优化

1. **CDN配置**:
```nginx
# 配置CDN缓存头
location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    add_header Vary Accept-Encoding;
}
```

2. **图片优化**:
```python
from PIL import Image
import io

def optimize_image(image_data, max_size=(800, 600), quality=85):
    """优化图片大小和质量"""
    img = Image.open(io.BytesIO(image_data))
    
    # 调整大小
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    # 压缩质量
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality, optimize=True)
    return output.getvalue()
```

---

## 监控和日志

### 应用监控

1. **Prometheus 指标**:
```python
from prometheus_client import Counter, Histogram, generate_latest

# 定义指标
request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    request_count.labels(method=request.method, endpoint=request.url.path).inc()
    request_duration.observe(duration)
    
    return response

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

2. **健康检查端点**:
```python
@app.get("/health")
async def health_check():
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
        "storage": check_storage(),
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        content={"status": "healthy" if all_healthy else "unhealthy", "checks": checks},
        status_code=status_code
    )
```

### 日志配置

1. **结构化日志**:
```python
import structlog

# 配置结构化日志
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# 使用示例
logger.info("User logged in", user_id=123, ip_address="192.168.1.1")
```

2. **日志轮转配置**:
```bash
# /etc/logrotate.d/kompanion
/opt/kompanion/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 kompanion kompanion
    postrotate
        systemctl reload kompanion
    endscript
}
```

### 监控告警

1. **Grafana 仪表板**:
```json
{
  "dashboard": {
    "title": "Kompanion Monitoring",
    "panels": [
      {
        "title": "HTTP Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      }
    ]
  }
}
```

2. **告警规则**:
```yaml
# prometheus-alerts.yml
groups:
- name: kompanion
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate detected"
      
  - alert: DatabaseDown
    expr: up{job="postgres"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "PostgreSQL database is down"
```

---

## 备份恢复

### 自动化备份脚本

```bash
#!/bin/bash
# /opt/kompanion/scripts/backup.sh

BACKUP_DIR="/opt/kompanion/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 数据库备份
pg_dump -h localhost -U kompanion_user kompanion | gzip > "$BACKUP_DIR/db_backup_$TIMESTAMP.sql.gz"

# 文件备份
tar -czf "$BACKUP_DIR/files_backup_$TIMESTAMP.tar.gz" -C /opt/kompanion storage

# 配置备份
cp /opt/kompanion/.env "$BACKUP_DIR/config_backup_$TIMESTAMP.env"

# 清理旧备份
find "$BACKUP_DIR" -name "*backup*" -mtime +$RETENTION_DAYS -delete

# 备份到远程存储
if command -v aws &> /dev/null; then
    aws s3 sync "$BACKUP_DIR" s3://your-backup-bucket/kompanion/
fi

echo "Backup completed: $TIMESTAMP"
```

### 恢复流程

```bash
#!/bin/bash
# 数据库恢复脚本

BACKUP_FILE="$1"
if [[ -z "$BACKUP_FILE" ]]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

# 停止应用
sudo systemctl stop kompanion

# 恢复数据库
gunzip < "$BACKUP_FILE" | psql -h localhost -U kompanion_user kompanion

# 重启应用
sudo systemctl start kompanion

echo "Database restored from $BACKUP_FILE"
```

### 灾难恢复计划

1. **备份策略**:
   - 每日数据库备份
   - 每周完整文件备份
   - 实时配置备份
   - 异地存储备份

2. **恢复时间目标(RTO)**:
   - 数据库恢复: < 30分钟
   - 完整系统恢复: < 2小时

3. **恢复点目标(RPO)**:
   - 数据损失: < 1小时

---

## 故障排除

### 常见问题

1. **应用启动失败**:
```bash
# 检查服务状态
sudo systemctl status kompanion

# 查看日志
sudo journalctl -u kompanion -f

# 检查配置
cd /opt/kompanion/app
source venv/bin/activate
python scripts/manage.py health
```

2. **数据库连接问题**:
```bash
# 检查PostgreSQL状态
sudo systemctl status postgresql

# 测试连接
psql -h localhost -U kompanion_user -d kompanion

# 检查连接数
psql -h localhost -U kompanion_user -d kompanion -c "SELECT count(*) FROM pg_stat_activity;"
```

3. **性能问题**:
```bash
# 检查系统资源
top
htop
iotop

# 检查数据库性能
psql -h localhost -U kompanion_user -d kompanion -c "
SELECT query, state, query_start, now() - query_start AS duration
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;
"
```

### 调试工具

1. **应用调试**:
```python
# 启用调试模式
DEBUG=true uvicorn app.main:app --reload --log-level debug

# 使用pdb调试
import pdb; pdb.set_trace()
```

2. **性能分析**:
```bash
# 使用py-spy进行性能分析
pip install py-spy
py-spy top --pid $(pgrep -f gunicorn)
py-spy record -o profile.svg --pid $(pgrep -f gunicorn)
```

---

## 安全加固

### 应用安全

1. **依赖安全扫描**:
```bash
# 使用safety检查依赖漏洞
pip install safety
safety check

# 使用bandit进行代码安全扫描
pip install bandit
bandit -r app/
```

2. **API安全**:
```python
# 启用CORS保护
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# 添加安全头
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

### 系统安全

1. **防火墙配置**:
```bash
# Ubuntu UFW
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# CentOS firewalld
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

2. **SSL/TLS配置**:
```bash
# 使用Let's Encrypt获取证书
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com

# 或者使用现有证书
sudo cp your-cert.crt /etc/ssl/certs/kompanion.crt
sudo cp your-key.key /etc/ssl/private/kompanion.key
sudo chmod 644 /etc/ssl/certs/kompanion.crt
sudo chmod 600 /etc/ssl/private/kompanion.key
```

3. **访问控制**:
```nginx
# 限制管理界面访问
location /web/ {
    allow 192.168.1.0/24;  # 内网IP段
    allow 10.0.0.0/8;      # VPN IP段
    deny all;
    
    proxy_pass http://127.0.0.1:8000;
}

# 限制API访问频率
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

location /api/ {
    limit_req zone=api burst=20 nodelay;
    proxy_pass http://127.0.0.1:8000;
}
```

---

## 版本升级

### 升级流程

1. **使用自动升级脚本**:
```bash
# 检查可用更新
/opt/kompanion/scripts/update.sh --check

# 执行升级
/opt/kompanion/scripts/update.sh

# 升级到指定版本
/opt/kompanion/scripts/update.sh v1.2.0
```

2. **手动升级步骤**:
```bash
# 1. 备份当前版本
/opt/kompanion/scripts/backup.sh

# 2. 停止服务
sudo systemctl stop kompanion

# 3. 更新代码
cd /opt/kompanion/app
git stash
git pull origin main

# 4. 更新依赖
source venv/bin/activate
uv sync --frozen

# 5. 运行迁移
python scripts/manage.py db migrate

# 6. 重启服务
sudo systemctl start kompanion

# 7. 验证升级
curl -f http://localhost:8000/health
```

### 回滚策略

```bash
# 自动回滚
/opt/kompanion/scripts/update.sh --rollback

# 手动回滚到备份
BACKUP_PATH="/opt/kompanion/backups/update_backup_20240131_180000"

# 停止服务
sudo systemctl stop kompanion

# 恢复代码
rm -rf /opt/kompanion/app
cp -r "$BACKUP_PATH/app" /opt/kompanion/

# 恢复数据库
cd /opt/kompanion/app
source venv/bin/activate
python scripts/manage.py db restore --path "$BACKUP_PATH/database.sql"

# 恢复配置
cp "$BACKUP_PATH/.env" /opt/kompanion/

# 重启服务
sudo systemctl start kompanion
```

---

通过遵循本部署指南，您可以安全、高效地部署和运维 Kompanion Python 应用程序。记住定期备份数据、监控系统性能，并保持软件更新以确保最佳的安全性和稳定性。 