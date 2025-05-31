#!/bin/bash

# Kompanion Python 更新升级脚本
# 支持版本更新、数据库迁移、配置升级

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置参数
APP_DIR="/opt/kompanion/app"
BACKUP_DIR="/opt/kompanion/backups"
SERVICE_NAME="kompanion"

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

# 检查更新权限
check_permissions() {
    if [[ ! -d "$APP_DIR" ]]; then
        log_error "应用目录不存在: $APP_DIR"
        exit 1
    fi
    
    if [[ ! -w "$APP_DIR" ]]; then
        log_error "没有写入权限: $APP_DIR"
        exit 1
    fi
}

# 获取当前版本
get_current_version() {
    cd "$APP_DIR"
    if [[ -f "pyproject.toml" ]]; then
        CURRENT_VERSION=$(grep -E '^version = ' pyproject.toml | cut -d'"' -f2)
    else
        CURRENT_VERSION="unknown"
    fi
    log_info "当前版本: $CURRENT_VERSION"
}

# 检查新版本
check_latest_version() {
    log_info "检查最新版本..."
    
    # 从Git获取最新标签
    cd "$APP_DIR"
    git fetch --tags
    LATEST_VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "main")
    
    log_info "最新版本: $LATEST_VERSION"
    
    if [[ "$CURRENT_VERSION" == "$LATEST_VERSION" ]]; then
        log_success "已是最新版本"
        return 1
    fi
    
    return 0
}

# 创建备份
create_backup() {
    log_info "创建备份..."
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="$BACKUP_DIR/update_backup_$TIMESTAMP"
    
    mkdir -p "$BACKUP_PATH"
    
    # 备份应用代码
    log_info "备份应用代码..."
    cp -r "$APP_DIR" "$BACKUP_PATH/"
    
    # 备份数据库
    log_info "备份数据库..."
    cd "$APP_DIR"
    source venv/bin/activate
    python scripts/manage.py db backup --path "$BACKUP_PATH/database.sql"
    
    # 备份配置文件
    log_info "备份配置文件..."
    cp /opt/kompanion/.env "$BACKUP_PATH/"
    
    # 备份存储文件
    log_info "备份存储文件..."
    tar -czf "$BACKUP_PATH/storage.tar.gz" -C /opt/kompanion storage
    
    log_success "备份完成: $BACKUP_PATH"
    echo "$BACKUP_PATH" > /tmp/kompanion_backup_path
}

# 停止服务
stop_services() {
    log_info "停止服务..."
    
    # 停止应用服务
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        sudo systemctl stop "$SERVICE_NAME"
        log_info "Kompanion服务已停止"
    fi
    
    # 停止Nginx (可选)
    if [[ "$1" == "--nginx" ]]; then
        sudo systemctl stop nginx
        log_info "Nginx服务已停止"
    fi
}

# 启动服务
start_services() {
    log_info "启动服务..."
    
    # 启动应用服务
    sudo systemctl start "$SERVICE_NAME"
    log_info "Kompanion服务已启动"
    
    # 启动Nginx (如果之前停止了)
    if [[ "$1" == "--nginx" ]]; then
        sudo systemctl start nginx
        log_info "Nginx服务已启动"
    fi
}

# 下载新版本
download_update() {
    log_info "下载新版本代码..."
    
    cd "$APP_DIR"
    
    # 保存本地修改
    git stash push -m "Pre-update stash $(date)"
    
    # 拉取最新代码
    if [[ "$1" == "main" ]] || [[ -z "$1" ]]; then
        git pull origin main
    else
        git checkout "$1"
    fi
    
    log_success "代码更新完成"
}

# 更新依赖
update_dependencies() {
    log_info "更新Python依赖..."
    
    cd "$APP_DIR"
    source venv/bin/activate
    
    # 更新uv
    pip install --upgrade uv
    
    # 同步依赖
    uv sync --frozen
    
    log_success "依赖更新完成"
}

# 运行数据库迁移
run_migrations() {
    log_info "运行数据库迁移..."
    
    cd "$APP_DIR"
    source venv/bin/activate
    
    # 检查是否需要迁移
    if python scripts/manage.py db migrate --dry-run 2>/dev/null; then
        log_info "发现数据库迁移，正在执行..."
        python scripts/manage.py db migrate
        log_success "数据库迁移完成"
    else
        log_info "无需数据库迁移"
    fi
}

# 更新配置文件
update_config() {
    log_info "检查配置文件..."
    
    CONFIG_FILE="/opt/kompanion/.env"
    CONFIG_EXAMPLE="$APP_DIR/env.example"
    
    if [[ -f "$CONFIG_EXAMPLE" ]]; then
        # 检查新的配置项
        log_info "检查新的配置项..."
        
        # 提取示例配置中的所有键
        EXAMPLE_KEYS=$(grep -E '^[A-Z_]+=.*' "$CONFIG_EXAMPLE" | cut -d'=' -f1 | sort)
        CURRENT_KEYS=$(grep -E '^[A-Z_]+=.*' "$CONFIG_FILE" | cut -d'=' -f1 | sort)
        
        # 找出缺失的键
        MISSING_KEYS=$(comm -23 <(echo "$EXAMPLE_KEYS") <(echo "$CURRENT_KEYS"))
        
        if [[ -n "$MISSING_KEYS" ]]; then
            log_warning "发现新的配置项:"
            echo "$MISSING_KEYS"
            
            read -p "是否自动添加默认值? (y/N): " ADD_CONFIG
            if [[ "$ADD_CONFIG" =~ ^[Yy]$ ]]; then
                # 添加缺失的配置项
                for key in $MISSING_KEYS; do
                    DEFAULT_VALUE=$(grep "^$key=" "$CONFIG_EXAMPLE" | cut -d'=' -f2-)
                    echo "$key=$DEFAULT_VALUE" >> "$CONFIG_FILE"
                    log_info "添加配置项: $key"
                done
            fi
        else
            log_info "配置文件无需更新"
        fi
    fi
}

# 清理缓存
clear_cache() {
    log_info "清理缓存..."
    
    cd "$APP_DIR"
    
    # 清理Python缓存
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    
    # 清理日志文件 (可选)
    if [[ "$1" == "--logs" ]]; then
        find /opt/kompanion/logs -name "*.log" -mtime +7 -delete 2>/dev/null || true
        log_info "清理旧日志文件"
    fi
    
    log_success "缓存清理完成"
}

# 验证更新
verify_update() {
    log_info "验证更新..."
    
    # 等待服务启动
    sleep 5
    
    # 检查服务状态
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_success "服务运行正常"
    else
        log_error "服务启动失败"
        return 1
    fi
    
    # 检查HTTP响应
    if curl -f -s http://localhost:8000/health > /dev/null; then
        log_success "HTTP服务正常"
    else
        log_error "HTTP服务异常"
        return 1
    fi
    
    # 检查API
    if curl -f -s http://localhost:8000/api/v1/health > /dev/null; then
        log_success "API服务正常"
    else
        log_error "API服务异常"
        return 1
    fi
    
    # 运行健康检查
    cd "$APP_DIR"
    source venv/bin/activate
    if python scripts/manage.py health > /dev/null 2>&1; then
        log_success "系统健康检查通过"
    else
        log_warning "系统健康检查发现问题"
    fi
    
    log_success "更新验证完成"
}

# 回滚更新
rollback_update() {
    log_error "更新失败，正在回滚..."
    
    if [[ -f "/tmp/kompanion_backup_path" ]]; then
        BACKUP_PATH=$(cat /tmp/kompanion_backup_path)
        
        if [[ -d "$BACKUP_PATH" ]]; then
            # 停止服务
            stop_services
            
            # 恢复应用代码
            log_info "恢复应用代码..."
            rm -rf "$APP_DIR"
            mv "$BACKUP_PATH/app" "$APP_DIR"
            
            # 恢复配置文件
            log_info "恢复配置文件..."
            cp "$BACKUP_PATH/.env" /opt/kompanion/
            
            # 恢复数据库
            log_info "恢复数据库..."
            cd "$APP_DIR"
            source venv/bin/activate
            python scripts/manage.py db restore --path "$BACKUP_PATH/database.sql"
            
            # 启动服务
            start_services
            
            log_success "回滚完成"
        else
            log_error "备份目录不存在: $BACKUP_PATH"
        fi
    else
        log_error "无法找到备份路径"
    fi
}

# 显示帮助信息
show_help() {
    echo "Kompanion Python 更新脚本"
    echo ""
    echo "用法:"
    echo "  $0 [选项] [版本]"
    echo ""
    echo "选项:"
    echo "  --check         仅检查更新，不执行"
    echo "  --force         强制更新，跳过版本检查"
    echo "  --no-backup     跳过备份步骤"
    echo "  --nginx         同时重启Nginx服务"
    echo "  --clear-logs    清理旧日志文件"
    echo "  --dry-run       模拟运行，不实际执行"
    echo "  --rollback      回滚到上次备份"
    echo "  --help          显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                    # 更新到最新版本"
    echo "  $0 v1.2.0            # 更新到指定版本"
    echo "  $0 --check           # 检查是否有新版本"
    echo "  $0 --rollback        # 回滚更新"
}

# 主更新流程
main() {
    local VERSION=""
    local CHECK_ONLY=false
    local FORCE_UPDATE=false
    local NO_BACKUP=false
    local RESTART_NGINX=false
    local CLEAR_LOGS=false
    local DRY_RUN=false
    local ROLLBACK=false
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --check)
                CHECK_ONLY=true
                shift
                ;;
            --force)
                FORCE_UPDATE=true
                shift
                ;;
            --no-backup)
                NO_BACKUP=true
                shift
                ;;
            --nginx)
                RESTART_NGINX=true
                shift
                ;;
            --clear-logs)
                CLEAR_LOGS=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --rollback)
                ROLLBACK=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            -*)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
            *)
                VERSION="$1"
                shift
                ;;
        esac
    done
    
    echo "🔄 Kompanion Python 更新脚本"
    echo "=============================="
    
    check_permissions
    get_current_version
    
    # 处理回滚
    if [[ "$ROLLBACK" == true ]]; then
        rollback_update
        exit 0
    fi
    
    # 检查更新
    if ! check_latest_version && [[ "$FORCE_UPDATE" != true ]]; then
        exit 0
    fi
    
    # 仅检查模式
    if [[ "$CHECK_ONLY" == true ]]; then
        log_info "可更新到版本: $LATEST_VERSION"
        exit 0
    fi
    
    # 模拟运行模式
    if [[ "$DRY_RUN" == true ]]; then
        log_info "模拟运行模式 - 将执行以下步骤:"
        echo "1. 创建备份"
        echo "2. 停止服务"
        echo "3. 下载更新"
        echo "4. 更新依赖"
        echo "5. 运行迁移"
        echo "6. 更新配置"
        echo "7. 启动服务"
        echo "8. 验证更新"
        exit 0
    fi
    
    # 确认更新
    log_info "准备从 $CURRENT_VERSION 更新到 ${VERSION:-$LATEST_VERSION}"
    read -p "确认继续? (y/N): " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        log_info "更新已取消"
        exit 0
    fi
    
    # 执行更新
    trap 'rollback_update' ERR
    
    # 创建备份
    if [[ "$NO_BACKUP" != true ]]; then
        create_backup
    fi
    
    # 停止服务
    if [[ "$RESTART_NGINX" == true ]]; then
        stop_services --nginx
    else
        stop_services
    fi
    
    # 下载更新
    download_update "${VERSION:-$LATEST_VERSION}"
    
    # 更新依赖
    update_dependencies
    
    # 运行迁移
    run_migrations
    
    # 更新配置
    update_config
    
    # 清理缓存
    if [[ "$CLEAR_LOGS" == true ]]; then
        clear_cache --logs
    else
        clear_cache
    fi
    
    # 启动服务
    if [[ "$RESTART_NGINX" == true ]]; then
        start_services --nginx
    else
        start_services
    fi
    
    # 验证更新
    if verify_update; then
        log_success "🎉 更新完成！"
        log_info "新版本: ${VERSION:-$LATEST_VERSION}"
        
        # 清理备份路径记录
        rm -f /tmp/kompanion_backup_path
    else
        log_error "更新验证失败"
        exit 1
    fi
}

# 执行更新
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 