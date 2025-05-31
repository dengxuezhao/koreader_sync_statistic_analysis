#!/bin/bash

# Kompanion Python 自动安装脚本
# 支持 Ubuntu/Debian 和 CentOS/RHEL 系统

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "请不要使用root用户运行此脚本"
        exit 1
    fi
}

# 检测操作系统
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$NAME
        VERSION=$VERSION_ID
    else
        log_error "无法检测操作系统版本"
        exit 1
    fi
    
    log_info "检测到操作系统: $OS $VERSION"
}

# 安装系统依赖
install_system_deps() {
    log_info "安装系统依赖包..."
    
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        sudo apt update
        sudo apt install -y \
            python3.12 \
            python3.12-venv \
            python3.12-dev \
            python3-pip \
            postgresql-client \
            git \
            curl \
            wget \
            build-essential \
            libpq-dev \
            libffi-dev \
            libssl-dev \
            libjpeg-dev \
            libpng-dev \
            supervisor \
            nginx
    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        sudo yum update -y
        sudo yum install -y \
            python3.12 \
            python3.12-venv \
            python3.12-devel \
            postgresql \
            git \
            curl \
            wget \
            gcc \
            gcc-c++ \
            make \
            postgresql-devel \
            libffi-devel \
            openssl-devel \
            libjpeg-devel \
            libpng-devel \
            supervisor \
            nginx
    else
        log_error "不支持的操作系统: $OS"
        exit 1
    fi
    
    log_success "系统依赖安装完成"
}

# 安装Python依赖管理器uv
install_uv() {
    log_info "安装uv包管理器..."
    
    if ! command -v uv &> /dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        source $HOME/.cargo/env
    else
        log_info "uv已安装，跳过"
    fi
    
    log_success "uv安装完成"
}

# 创建应用目录和用户
setup_app_structure() {
    log_info "设置应用目录结构..."
    
    # 创建应用目录
    sudo mkdir -p /opt/kompanion
    sudo chown $USER:$USER /opt/kompanion
    
    # 创建数据目录
    mkdir -p /opt/kompanion/{storage,logs,data}
    mkdir -p /opt/kompanion/storage/{books,covers,webdav}
    
    # 设置权限
    chmod 755 /opt/kompanion
    chmod 755 /opt/kompanion/storage
    
    log_success "应用目录创建完成"
}

# 克隆项目代码
clone_project() {
    log_info "克隆项目代码..."
    
    if [[ ! -d "/opt/kompanion/app" ]]; then
        cd /opt/kompanion
        
        # 如果当前目录已经是项目目录，复制文件
        if [[ -f "$(pwd)/pyproject.toml" ]]; then
            cp -r . /opt/kompanion/app/
        else
            # 否则从GitHub克隆
            git clone https://github.com/your-repo/kompanion-python.git app
        fi
    else
        log_info "项目代码已存在，跳过克隆"
    fi
    
    log_success "项目代码准备完成"
}

# 设置Python虚拟环境
setup_python_env() {
    log_info "设置Python虚拟环境..."
    
    cd /opt/kompanion/app
    
    # 创建虚拟环境
    python3.12 -m venv venv
    source venv/bin/activate
    
    # 升级pip并安装uv
    pip install --upgrade pip
    pip install uv
    
    # 使用uv安装依赖
    uv sync --frozen
    
    log_success "Python环境设置完成"
}

# 配置数据库
setup_database() {
    log_info "配置数据库..."
    
    read -p "选择数据库类型 (postgresql/sqlite) [postgresql]: " DB_TYPE
    DB_TYPE=${DB_TYPE:-postgresql}
    
    if [[ "$DB_TYPE" == "postgresql" ]]; then
        # PostgreSQL配置
        read -p "PostgreSQL主机 [localhost]: " DB_HOST
        DB_HOST=${DB_HOST:-localhost}
        
        read -p "PostgreSQL端口 [5432]: " DB_PORT
        DB_PORT=${DB_PORT:-5432}
        
        read -p "数据库名 [kompanion]: " DB_NAME
        DB_NAME=${DB_NAME:-kompanion}
        
        read -p "数据库用户 [kompanion_user]: " DB_USER
        DB_USER=${DB_USER:-kompanion_user}
        
        read -s -p "数据库密码: " DB_PASS
        echo
        
        DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
    else
        # SQLite配置
        DATABASE_URL="sqlite+aiosqlite:///opt/kompanion/data/kompanion.db"
    fi
    
    echo "DATABASE_URL=\"$DATABASE_URL\"" >> /opt/kompanion/.env
    
    log_success "数据库配置完成"
}

# 生成配置文件
generate_config() {
    log_info "生成应用配置..."
    
    # 生成密钥
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    
    # 获取管理员信息
    read -p "管理员用户名 [admin]: " ADMIN_USER
    ADMIN_USER=${ADMIN_USER:-admin}
    
    read -p "管理员邮箱 [admin@localhost]: " ADMIN_EMAIL
    ADMIN_EMAIL=${ADMIN_EMAIL:-admin@localhost}
    
    read -s -p "管理员密码: " ADMIN_PASS
    echo
    
    # 创建环境配置文件
    cat > /opt/kompanion/.env << EOF
# 数据库配置
DATABASE_URL="$DATABASE_URL"

# 应用配置
SECRET_KEY="$SECRET_KEY"
DEBUG=false
ALLOWED_HOSTS=localhost,127.0.0.1

# 管理员配置
ADMIN_USERNAME="$ADMIN_USER"
ADMIN_PASSWORD="$ADMIN_PASS"
ADMIN_EMAIL="$ADMIN_EMAIL"

# 文件存储配置
BOOK_STORAGE_PATH=/opt/kompanion/storage/books
COVER_STORAGE_PATH=/opt/kompanion/storage/covers
WEBDAV_ROOT_PATH=/opt/kompanion/storage/webdav

# 上传限制
MAX_UPLOAD_SIZE=500
ALLOWED_EXTENSIONS=epub,pdf,mobi,azw,azw3,fb2,txt

# 服务器配置
HOST=127.0.0.1
PORT=8000
WORKERS=4

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=/opt/kompanion/logs/app.log

# KOReader兼容配置
ENABLE_MD5_AUTH=true
KOSYNC_COMPATIBLE=true

# OPDS配置
OPDS_TITLE=Kompanion 书籍库
OPDS_DESCRIPTION=个人电子书籍管理系统
OPDS_AUTHOR=$ADMIN_USER
OPDS_EMAIL=$ADMIN_EMAIL

# WebDAV配置
WEBDAV_ENABLED=true
WEBDAV_AUTH_REQUIRED=true
EOF
    
    log_success "配置文件生成完成"
}

# 初始化数据库
init_database() {
    log_info "初始化数据库..."
    
    cd /opt/kompanion/app
    source venv/bin/activate
    
    # 初始化数据库
    python scripts/manage.py db init
    
    # 创建管理员用户
    python scripts/create_admin.py \
        --username "$ADMIN_USER" \
        --email "$ADMIN_EMAIL" \
        --password "$ADMIN_PASS"
    
    log_success "数据库初始化完成"
}

# 配置Supervisor
setup_supervisor() {
    log_info "配置Supervisor服务..."
    
    sudo tee /etc/supervisor/conf.d/kompanion.conf > /dev/null << EOF
[program:kompanion]
command=/opt/kompanion/app/venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000
directory=/opt/kompanion/app
user=$USER
autostart=true
autorestart=true
startsecs=5
startretries=3
stdout_logfile=/opt/kompanion/logs/supervisor.log
stderr_logfile=/opt/kompanion/logs/supervisor_error.log
environment=PATH="/opt/kompanion/app/venv/bin"
EOF
    
    # 重新加载Supervisor配置
    sudo supervisorctl reread
    sudo supervisorctl update
    
    log_success "Supervisor配置完成"
}

# 配置Nginx反向代理
setup_nginx() {
    log_info "配置Nginx反向代理..."
    
    read -p "配置域名 [localhost]: " DOMAIN
    DOMAIN=${DOMAIN:-localhost}
    
    sudo tee /etc/nginx/sites-available/kompanion > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    client_max_body_size 500M;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    location /static/ {
        alias /opt/kompanion/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location /storage/ {
        alias /opt/kompanion/storage/;
        expires 1y;
        add_header Cache-Control "public";
    }
}
EOF
    
    # 启用站点
    sudo ln -sf /etc/nginx/sites-available/kompanion /etc/nginx/sites-enabled/
    
    # 删除默认站点
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # 测试配置并重启Nginx
    sudo nginx -t
    sudo systemctl restart nginx
    
    log_success "Nginx配置完成"
}

# 设置系统服务
setup_systemd() {
    log_info "配置systemd服务..."
    
    sudo tee /etc/systemd/system/kompanion.service > /dev/null << EOF
[Unit]
Description=Kompanion Python Web Application
After=network.target

[Service]
Type=exec
User=$USER
WorkingDirectory=/opt/kompanion/app
Environment=PATH=/opt/kompanion/app/venv/bin
ExecStart=/opt/kompanion/app/venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
    
    # 重新加载systemd并启用服务
    sudo systemctl daemon-reload
    sudo systemctl enable kompanion
    sudo systemctl start kompanion
    
    log_success "Systemd服务配置完成"
}

# 创建管理脚本
create_management_scripts() {
    log_info "创建管理脚本..."
    
    # 创建启动脚本
    cat > /opt/kompanion/start.sh << 'EOF'
#!/bin/bash
cd /opt/kompanion/app
source venv/bin/activate
exec gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000
EOF
    
    # 创建停止脚本
    cat > /opt/kompanion/stop.sh << 'EOF'
#!/bin/bash
sudo systemctl stop kompanion
EOF
    
    # 创建重启脚本
    cat > /opt/kompanion/restart.sh << 'EOF'
#!/bin/bash
sudo systemctl restart kompanion
sudo systemctl restart nginx
EOF
    
    # 创建状态检查脚本
    cat > /opt/kompanion/status.sh << 'EOF'
#!/bin/bash
echo "=== Kompanion 服务状态 ==="
sudo systemctl status kompanion --no-pager
echo ""
echo "=== Nginx 状态 ==="
sudo systemctl status nginx --no-pager
echo ""
echo "=== 应用统计 ==="
cd /opt/kompanion/app
source venv/bin/activate
python scripts/manage.py stats
EOF
    
    # 创建备份脚本
    cat > /opt/kompanion/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/kompanion/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "开始备份 Kompanion..."

# 备份数据库
cd /opt/kompanion/app
source venv/bin/activate
python scripts/manage.py db backup --path "$BACKUP_DIR/database_$TIMESTAMP.sql"

# 备份存储文件
tar -czf "$BACKUP_DIR/storage_$TIMESTAMP.tar.gz" -C /opt/kompanion storage

# 备份配置文件
cp /opt/kompanion/.env "$BACKUP_DIR/config_$TIMESTAMP.env"

echo "备份完成: $BACKUP_DIR"
EOF
    
    # 设置执行权限
    chmod +x /opt/kompanion/*.sh
    
    log_success "管理脚本创建完成"
}

# 测试安装
test_installation() {
    log_info "测试安装..."
    
    # 等待服务启动
    sleep 5
    
    # 测试HTTP响应
    if curl -f -s http://localhost:8000/health > /dev/null; then
        log_success "HTTP服务正常"
    else
        log_error "HTTP服务异常"
        return 1
    fi
    
    # 测试API
    if curl -f -s http://localhost:8000/api/v1/health > /dev/null; then
        log_success "API服务正常"
    else
        log_error "API服务异常"
        return 1
    fi
    
    log_success "安装测试通过"
}

# 显示安装总结
show_summary() {
    log_success "🎉 Kompanion Python 安装完成！"
    echo ""
    echo "📍 服务信息:"
    echo "   Web界面: http://$DOMAIN"
    echo "   API文档: http://$DOMAIN/docs"
    echo "   OPDS目录: http://$DOMAIN/api/v1/opds/"
    echo ""
    echo "👤 管理员账户:"
    echo "   用户名: $ADMIN_USER"
    echo "   邮箱: $ADMIN_EMAIL"
    echo ""
    echo "📁 重要路径:"
    echo "   应用目录: /opt/kompanion/app"
    echo "   存储目录: /opt/kompanion/storage"
    echo "   配置文件: /opt/kompanion/.env"
    echo "   日志目录: /opt/kompanion/logs"
    echo ""
    echo "🔧 管理命令:"
    echo "   状态检查: /opt/kompanion/status.sh"
    echo "   重启服务: /opt/kompanion/restart.sh"
    echo "   数据备份: /opt/kompanion/backup.sh"
    echo ""
    echo "📖 下一步:"
    echo "   1. 配置KOReader同步服务器: http://$DOMAIN/api/v1"
    echo "   2. 添加OPDS目录: http://$DOMAIN/api/v1/opds/"
    echo "   3. 访问Web管理界面上传书籍"
}

# 主安装流程
main() {
    echo "🚀 Kompanion Python 自动安装脚本"
    echo "=================================="
    
    check_root
    detect_os
    install_system_deps
    install_uv
    setup_app_structure
    clone_project
    setup_python_env
    setup_database
    generate_config
    init_database
    
    # 选择进程管理器
    read -p "选择进程管理器 (supervisor/systemd) [systemd]: " PROCESS_MANAGER
    PROCESS_MANAGER=${PROCESS_MANAGER:-systemd}
    
    if [[ "$PROCESS_MANAGER" == "supervisor" ]]; then
        setup_supervisor
    else
        setup_systemd
    fi
    
    setup_nginx
    create_management_scripts
    test_installation
    show_summary
}

# 执行安装
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 