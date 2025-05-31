#!/bin/bash

# Kompanion Python Docker 部署设置脚本
# 用于自动化容器化部署流程

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

# 检查必要工具
check_requirements() {
    log_info "检查系统要求..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装。请先安装 Docker。"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装。请先安装 Docker Compose。"
        exit 1
    fi
    
    log_success "系统要求检查通过"
}

# 创建必要目录
create_directories() {
    log_info "创建必要的目录..."
    
    mkdir -p docker/ssl
    mkdir -p storage/{books,covers,webdav}
    mkdir -p logs
    
    log_success "目录创建完成"
}

# 生成自签名SSL证书（开发环境）
generate_ssl_cert() {
    if [ ! -f "docker/ssl/cert.pem" ]; then
        log_info "生成自签名SSL证书..."
        
        openssl req -x509 -newkey rsa:4096 -keyout docker/ssl/key.pem -out docker/ssl/cert.pem -days 365 -nodes \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
        
        log_success "SSL证书生成完成"
    else
        log_info "SSL证书已存在，跳过生成"
    fi
}

# 创建环境配置文件
create_env_file() {
    if [ ! -f ".env" ]; then
        log_info "创建环境配置文件..."
        
        cat > .env << EOF
# Kompanion Python 环境配置

# 数据库配置
KOMPANION_DATABASE_URL=postgresql+asyncpg://kompanion:kompanion123@postgres:5432/kompanion
KOMPANION_DATABASE_TYPE=postgresql

# 应用配置
KOMPANION_DEBUG=false
KOMPANION_APP_NAME=Kompanion Python
KOMPANION_APP_VERSION=1.0.0

# 安全配置（请在生产环境中更改）
KOMPANION_SECRET_KEY=$(openssl rand -hex 32)
KOMPANION_ACCESS_TOKEN_EXPIRE_MINUTES=30
KOMPANION_ALGORITHM=HS256

# 存储配置
KOMPANION_BOOK_STORAGE_PATH=/app/storage/books
KOMPANION_COVER_STORAGE_PATH=/app/storage/covers
KOMPANION_MAX_BOOK_SIZE_MB=500

# WebDAV配置
KOMPANION_WEBDAV_ENABLED=true
KOMPANION_WEBDAV_ROOT_PATH=/app/storage/webdav

# 日志配置
KOMPANION_LOG_LEVEL=INFO

# CORS配置
KOMPANION_ALLOWED_HOSTS=*
KOMPANION_CORS_ORIGINS=*

# PostgreSQL配置
POSTGRES_DB=kompanion
POSTGRES_USER=kompanion
POSTGRES_PASSWORD=kompanion123

# Redis配置
REDIS_PASSWORD=redis123
EOF
        
        log_success "环境配置文件创建完成"
    else
        log_info "环境配置文件已存在，跳过创建"
    fi
}

# 构建Docker镜像
build_images() {
    log_info "构建Docker镜像..."
    
    docker-compose build --no-cache
    
    log_success "Docker镜像构建完成"
}

# 启动服务
start_services() {
    local profile=${1:-""}
    
    log_info "启动服务..."
    
    if [ "$profile" = "production" ]; then
        docker-compose --profile production up -d
        log_info "生产环境服务启动完成（包含 Nginx）"
    else
        docker-compose up -d postgres redis kompanion
        log_info "开发环境服务启动完成"
    fi
    
    log_success "服务启动完成"
}

# 等待服务就绪
wait_for_services() {
    log_info "等待服务就绪..."
    
    # 等待数据库
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose exec -T postgres pg_isready -U kompanion -d kompanion &> /dev/null; then
            break
        fi
        
        log_info "等待数据库就绪... ($attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        log_error "数据库启动超时"
        exit 1
    fi
    
    # 等待应用
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8000/health &> /dev/null; then
            break
        fi
        
        log_info "等待应用就绪... ($attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        log_error "应用启动超时"
        exit 1
    fi
    
    log_success "所有服务已就绪"
}

# 初始化数据库
init_database() {
    log_info "初始化数据库..."
    
    docker-compose exec kompanion python scripts/init_db.py
    
    log_success "数据库初始化完成"
}

# 显示状态
show_status() {
    log_info "服务状态："
    docker-compose ps
    
    echo ""
    log_info "应用访问地址："
    echo "  - Web界面: http://localhost:8000"
    echo "  - API文档: http://localhost:8000/docs"
    echo "  - 健康检查: http://localhost:8000/health"
    echo ""
    log_info "管理命令："
    echo "  - 查看日志: docker-compose logs -f"
    echo "  - 停止服务: docker-compose down"
    echo "  - 重启服务: docker-compose restart"
}

# 清理函数
cleanup() {
    log_info "停止所有服务..."
    docker-compose down -v
    
    log_warning "是否删除所有数据卷？(y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        docker-compose down -v --remove-orphans
        docker volume prune -f
        log_success "数据卷已清理"
    fi
}

# 主函数
main() {
    case "${1:-setup}" in
        "setup")
            log_info "开始 Kompanion Python Docker 部署设置..."
            check_requirements
            create_directories
            generate_ssl_cert
            create_env_file
            build_images
            start_services
            wait_for_services
            init_database
            show_status
            log_success "部署设置完成！"
            ;;
        "production")
            log_info "启动生产环境..."
            check_requirements
            create_directories
            generate_ssl_cert
            create_env_file
            build_images
            start_services "production"
            wait_for_services
            init_database
            show_status
            log_success "生产环境部署完成！"
            ;;
        "cleanup")
            cleanup
            ;;
        "status")
            show_status
            ;;
        *)
            echo "用法: $0 {setup|production|cleanup|status}"
            echo "  setup      - 设置开发环境（默认）"
            echo "  production - 设置生产环境（包含Nginx）"
            echo "  cleanup    - 清理所有容器和卷"
            echo "  status     - 显示服务状态"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@" 