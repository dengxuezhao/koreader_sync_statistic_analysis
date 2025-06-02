"""
Kompanion Python - 主应用程序

KOReader兼容的书籍库管理Web应用程序，使用FastAPI构建。
"""

import logging
from contextlib import asynccontextmanager
import time
import os

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uvicorn

from app.core.config import settings
from app.core.database import init_database, check_database_health
from app.core.cache import cache_manager, warm_cache
from app.api.v1 import api_router, auth, sync, opds, books, webdav, web
from app.core.security import (
    rate_limiter, 
    security_headers, 
    security_audit,
    check_sql_injection,
    SecurityError
)

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用程序生命周期管理"""
    # 启动时执行
    logger.info("启动Kompanion应用程序...")
    
    # 检查数据库连接
    try:
        logger.info("检查数据库连接...")
        is_healthy = await check_database_health()
        if not is_healthy:
            logger.error("数据库连接检查失败")
        else:
            logger.info("数据库连接正常")
            
            # 初始化数据库（如果需要）
            logger.info("初始化数据库...")
            await init_database()
            logger.info("数据库初始化完成")
            
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
    
    logger.info(f"Kompanion启动完成，运行在 http://{settings.HOST}:{settings.PORT}")
    
    # 初始化缓存
    await cache_manager.init()
    
    # 缓存预热（可选）
    if settings.CACHE_WARMUP_ON_STARTUP:
        await warm_cache()
    
    yield
    
    # 关闭时执行
    logger.info("关闭Kompanion应用程序...")
    
    # 关闭缓存连接
    await cache_manager.close()
    
    logger.info("应用关闭完成")


# 创建FastAPI应用实例
app = FastAPI(
    title="Kompanion Python",
    description="KOReader兼容的书籍管理和同步服务器",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    swagger_ui_parameters={
        "deepLinking": True,
        "displayRequestDuration": True,
        "filter": True,
        "showExtensions": True,
        "showCommonExtensions": True,
        "tryItOutEnabled": True,
        "requestSnippetsEnabled": True,
        "persistAuthorization": True,
        "docExpansion": "list",
        "defaultModelRendering": "model",
        "preauthorizeApiKey": False
    }
)

# 添加静态文件服务
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    # 如果static目录不存在，创建它
    os.makedirs("static", exist_ok=True)
    app.mount("/static", StaticFiles(directory="static"), name="static")

# 根路径重定向到web界面
@app.get("/", response_class=RedirectResponse)
async def root():
    """重定向到web管理界面"""
    return RedirectResponse(url="/api/v1/web/", status_code=302)

# 信任主机中间件
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # 生产环境中应该限制为具体的域名
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# 安全中间件
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """综合安全中间件"""
    start_time = time.time()
    client_ip = request.client.host
    
    try:
        # 1. 速率限制检查
        if not rate_limiter.is_allowed(client_ip):
            security_audit.log_security_event(
                "rate_limit_exceeded",
                None,
                client_ip,
                {"path": str(request.url.path)}
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"}
            )
        
        # 2. SQL注入检查
        query_params = dict(request.query_params)
        if await check_sql_injection(query_params):
            security_audit.log_security_event(
                "sql_injection_attempt",
                None,
                client_ip,
                {"path": str(request.url.path), "params": query_params}
            )
            return JSONResponse(
                status_code=400,
                content={"detail": "请求包含非法参数"}
            )
        
        # 3. 处理请求
        response = await call_next(request)
        
        # 4. 添加安全头
        headers = security_headers.get_security_headers()
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value
        
        # 5. 性能监控
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # 6. 记录请求日志
        logger.info(
            f"{request.method} {request.url.path} - "
            f"{response.status_code} - {process_time:.3f}s - {client_ip}"
        )
        
        return response
        
    except SecurityError as e:
        security_audit.log_security_event(
            "security_error",
            None,
            client_ip,
            {"path": str(request.url.path), "error": str(e)}
        )
        return JSONResponse(
            status_code=400,
            content={"detail": str(e)}
        )
    except Exception as e:
        logger.error(f"安全中间件错误: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误"}
        )

# 注册API路由
app.include_router(api_router, prefix="/api/v1")

# 直接WebDAV路由支持（KOReader兼容）
from app.api.v1 import webdav
app.include_router(webdav.router, prefix="/webdav", tags=["WebDAV兼容"])

# 健康检查端点
@app.get("/health", tags=["健康检查"])
async def health_check():
    """
    应用健康检查
    
    返回服务状态、数据库连接状态、缓存状态等信息。
    """
    try:
        from app.core.database import check_database_health
        from app.utils.performance import get_performance_metrics
        
        # 检查数据库连接
        db_healthy = await check_database_health()
        
        # 获取缓存状态
        cache_stats = await cache_manager.get_stats()
        
        # 获取基础性能指标
        try:
            perf_metrics = await get_performance_metrics()
            system_stats = perf_metrics.get('system', {})
        except Exception:
            system_stats = {}
        
        health_status = {
            "status": "healthy" if db_healthy else "unhealthy",
            "timestamp": time.time(),
            "version": "1.0.0",
            "database": {
                "status": "connected" if db_healthy else "disconnected",
                "type": settings.DATABASE_TYPE
            },
            "cache": cache_stats,
            "system": {
                "cpu_percent": system_stats.get('cpu', {}).get('percent', 0),
                "memory_percent": system_stats.get('memory', {}).get('percent', 0),
            }
        }
        
        status_code = 200 if db_healthy else 503
        return JSONResponse(content=health_status, status_code=status_code)
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return JSONResponse(
            content={
                "status": "error",
                "timestamp": time.time(),
                "error": str(e)
            },
            status_code=503
        )

# 性能监控端点
@app.get("/metrics", tags=["监控"])
async def metrics():
    """
    获取应用性能指标
    
    返回Prometheus格式的性能指标数据。
    """
    try:
        from app.utils.performance import get_performance_metrics, REGISTRY
        from prometheus_client import generate_latest
        
        # 获取Prometheus指标
        metrics_data = generate_latest(REGISTRY).decode('utf-8')
        
        return Response(
            content=metrics_data,
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )
        
    except Exception as e:
        logger.error(f"获取性能指标失败: {e}")
        return JSONResponse(
            content={"error": "无法获取性能指标"},
            status_code=500
        )

# 安全状态端点
@app.get("/security/status", tags=["安全"])
async def security_status():
    """
    获取安全状态信息
    
    返回安全配置和防护状态。
    """
    try:
        from app.core.security import SECURITY_CONFIG
        
        return {
            "security_config": {
                "rate_limiting": {
                    "enabled": True,
                    "requests_per_minute": SECURITY_CONFIG["RATE_LIMIT_REQUESTS"],
                    "window_seconds": SECURITY_CONFIG["RATE_LIMIT_WINDOW"]
                },
                "authentication": {
                    "jwt_enabled": True,
                    "koreader_compatible": True,
                    "session_timeout": SECURITY_CONFIG["SESSION_TIMEOUT"]
                },
                "file_security": {
                    "max_file_size": SECURITY_CONFIG["MAX_FILE_SIZE"],
                    "allowed_mime_types_count": len(SECURITY_CONFIG["ALLOWED_MIME_TYPES"])
                },
                "password_policy": {
                    "min_length": SECURITY_CONFIG["PASSWORD_MIN_LENGTH"],
                    "require_special": SECURITY_CONFIG["PASSWORD_REQUIRE_SPECIAL"],
                    "require_numbers": SECURITY_CONFIG["PASSWORD_REQUIRE_NUMBERS"],
                    "require_uppercase": SECURITY_CONFIG["PASSWORD_REQUIRE_UPPERCASE"]
                }
            },
            "protections": {
                "sql_injection": "enabled",
                "xss_protection": "enabled",
                "csrf_protection": "enabled",
                "security_headers": "enabled",
                "input_validation": "enabled"
            }
        }
        
    except Exception as e:
        logger.error(f"获取安全状态失败: {e}")
        return JSONResponse(
            content={"error": "无法获取安全状态"},
            status_code=500
        )

# CLI入口点（可选）
def cli():
    """命令行接口入口点"""
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    cli() 