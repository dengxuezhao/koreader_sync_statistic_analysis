"""
Web管理界面端点

提供基于HTML的管理界面，包括仪表板、用户管理、书籍管理、统计查看等功能。
使用Jinja2模板引擎渲染响应式Web界面。
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Dict
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, Request, Response, Form, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, and_, func, or_, desc
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, CurrentUser, CurrentAdminUser, OptionalCurrentUser
from app.core.config import settings
from app.models import User, Device, Book, SyncProgress, ReadingStatistics

router = APIRouter()
logger = logging.getLogger(__name__)

# 初始化模板引擎
templates_dir = Path(__file__).parent.parent.parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))


class WebService:
    """Web管理界面服务"""
    
    @staticmethod
    async def get_dashboard_stats(db: DbSession) -> Dict[str, Any]:
        """获取仪表板统计数据"""
        # 用户统计
        users_count = await db.execute(select(func.count(User.id)))
        total_users = users_count.scalar_one()
        
        active_users_count = await db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        active_users = active_users_count.scalar_one()
        
        # 设备统计
        devices_count = await db.execute(select(func.count(Device.id)))
        total_devices = devices_count.scalar_one()
        
        # 书籍统计
        books_count = await db.execute(
            select(func.count(Book.id)).where(Book.is_available == True)
        )
        total_books = books_count.scalar_one()
        
        # 下载统计
        downloads_count = await db.execute(
            select(func.sum(Book.download_count)).where(Book.is_available == True)
        )
        total_downloads = downloads_count.scalar_one() or 0
        
        # 同步进度统计
        sync_count = await db.execute(select(func.count(SyncProgress.id)))
        total_syncs = sync_count.scalar_one()
        
        # 阅读统计
        reading_stats_count = await db.execute(select(func.count(ReadingStatistics.id)))
        total_reading_stats = reading_stats_count.scalar_one()
        
        # 最近活动
        recent_date = datetime.utcnow() - timedelta(days=7)
        recent_users = await db.execute(
            select(func.count(User.id)).where(User.last_login_at >= recent_date)
        )
        recent_active_users = recent_users.scalar_one()
        
        recent_books = await db.execute(
            select(func.count(Book.id)).where(Book.created_at >= recent_date)
        )
        recent_book_uploads = recent_books.scalar_one()
        
        return {
            "users": {
                "total": total_users,
                "active": active_users,
                "recent_active": recent_active_users
            },
            "devices": {
                "total": total_devices
            },
            "books": {
                "total": total_books,
                "recent_uploads": recent_book_uploads
            },
            "activity": {
                "total_downloads": total_downloads,
                "total_syncs": total_syncs,
                "total_reading_stats": total_reading_stats
            }
        }
    
    @staticmethod
    async def get_recent_activities(db: DbSession, limit: int = 10) -> Dict[str, Any]:
        """获取最近活动"""
        # 最新书籍
        recent_books_result = await db.execute(
            select(Book)
            .where(Book.is_available == True)
            .order_by(Book.created_at.desc())
            .limit(limit)
        )
        recent_books = recent_books_result.scalars().all()
        
        # 最新用户
        recent_users_result = await db.execute(
            select(User)
            .where(User.is_active == True)
            .order_by(User.created_at.desc())
            .limit(limit)
        )
        recent_users = recent_users_result.scalars().all()
        
        # 最新阅读统计
        recent_stats_result = await db.execute(
            select(ReadingStatistics)
            .order_by(ReadingStatistics.updated_at.desc())
            .limit(limit)
        )
        recent_stats = recent_stats_result.scalars().all()
        
        return {
            "books": recent_books,
            "users": recent_users,
            "reading_stats": recent_stats
        }


# 根页面重定向到仪表板
@router.get("/", response_class=RedirectResponse)
async def web_root():
    """重定向到仪表板"""
    return RedirectResponse(url="/api/v1/web/dashboard", status_code=302)


# 仪表板页面
@router.get("/dashboard", response_class=HTMLResponse, summary="管理仪表板")
async def dashboard(
    request: Request,
    current_user: CurrentUser,
    db: DbSession
):
    """
    管理仪表板 - 显示系统概览和统计信息
    """
    try:
        # 获取统计数据
        stats = await WebService.get_dashboard_stats(db)
        activities = await WebService.get_recent_activities(db, limit=5)
        
        context = {
            "request": request,
            "user": current_user,
            "stats": stats,
            "activities": activities,
            "page_title": "管理仪表板"
        }
        
        return templates.TemplateResponse("dashboard.html", context)
        
    except Exception as e:
        logger.error(f"仪表板加载失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="仪表板加载失败"
        )


# 用户管理页面
@router.get("/users", response_class=HTMLResponse, summary="用户管理")
async def users_management(
    request: Request,
    current_user: CurrentAdminUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="页码"),
    search: Optional[str] = Query(None, description="搜索关键词")
):
    """
    用户管理页面 - 仅管理员可访问
    """
    try:
        # 构建查询
        query = select(User)
        
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term)
                )
            )
        
        # 计算总数
        count_query = select(func.count(User.id)).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()
        
        # 分页
        size = 20
        query = query.order_by(User.created_at.desc())
        query = query.offset((page - 1) * size).limit(size)
        
        result = await db.execute(query)
        users = result.scalars().all()
        
        # 分页信息
        total_pages = (total + size - 1) // size
        
        context = {
            "request": request,
            "user": current_user,
            "users": users,
            "search": search,
            "page": page,
            "total_pages": total_pages,
            "total_users": total,
            "page_title": "用户管理"
        }
        
        return templates.TemplateResponse("users.html", context)
        
    except Exception as e:
        logger.error(f"用户管理页面加载失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="用户管理页面加载失败"
        )


# 书籍管理页面
@router.get("/books", response_class=HTMLResponse, summary="书籍管理")
async def books_management(
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="页码"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    format_filter: Optional[str] = Query(None, description="格式过滤")
):
    """
    书籍管理页面
    """
    try:
        # 构建查询
        query = select(Book).where(Book.is_available == True)
        
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Book.title.ilike(search_term),
                    Book.author.ilike(search_term),
                    Book.publisher.ilike(search_term)
                )
            )
        
        if format_filter:
            query = query.where(Book.file_format == format_filter.lower())
        
        # 计算总数
        count_query = select(func.count(Book.id)).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()
        
        # 分页
        size = 20
        query = query.order_by(Book.created_at.desc())
        query = query.offset((page - 1) * size).limit(size)
        
        result = await db.execute(query)
        books = result.scalars().all()
        
        # 获取可用格式
        formats_result = await db.execute(
            select(Book.file_format, func.count(Book.id))
            .where(Book.is_available == True)
            .group_by(Book.file_format)
        )
        available_formats = dict(formats_result.fetchall())
        
        # 分页信息
        total_pages = (total + size - 1) // size
        
        context = {
            "request": request,
            "user": current_user,
            "books": books,
            "search": search,
            "format_filter": format_filter,
            "available_formats": available_formats,
            "page": page,
            "total_pages": total_pages,
            "total_books": total,
            "page_title": "书籍管理"
        }
        
        return templates.TemplateResponse("books.html", context)
        
    except Exception as e:
        logger.error(f"书籍管理页面加载失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="书籍管理页面加载失败"
        )


# 统计页面
@router.get("/statistics", response_class=HTMLResponse, summary="统计信息")
async def statistics_page(
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="页码"),
    device_filter: Optional[str] = Query(None, description="设备过滤")
):
    """
    统计信息页面 - 显示阅读统计
    """
    try:
        # 构建查询
        query = select(ReadingStatistics)
        
        # 非管理员只能查看自己的统计
        if not current_user.is_admin:
            query = query.where(ReadingStatistics.user_id == current_user.id)
        
        if device_filter:
            query = query.where(ReadingStatistics.device_name.ilike(f"%{device_filter}%"))
        
        # 计算总数
        count_query = select(func.count(ReadingStatistics.id)).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()
        
        # 分页
        size = 20
        query = query.order_by(ReadingStatistics.updated_at.desc())
        query = query.offset((page - 1) * size).limit(size)
        
        result = await db.execute(query)
        statistics = result.scalars().all()
        
        # 获取可用设备
        devices_query = select(ReadingStatistics.device_name, func.count(ReadingStatistics.id))
        if not current_user.is_admin:
            devices_query = devices_query.where(ReadingStatistics.user_id == current_user.id)
        devices_query = devices_query.group_by(ReadingStatistics.device_name)
        
        devices_result = await db.execute(devices_query)
        available_devices = dict(devices_result.fetchall())
        
        # 统计汇总
        summary_query = select(
            func.count(ReadingStatistics.id),
            func.avg(ReadingStatistics.reading_progress),
            func.sum(ReadingStatistics.total_reading_time)
        )
        if not current_user.is_admin:
            summary_query = summary_query.where(ReadingStatistics.user_id == current_user.id)
        
        summary_result = await db.execute(summary_query)
        stats_count, avg_progress, total_time = summary_result.fetchone()
        
        # 分页信息
        total_pages = (total + size - 1) // size
        
        context = {
            "request": request,
            "user": current_user,
            "statistics": statistics,
            "device_filter": device_filter,
            "available_devices": available_devices,
            "page": page,
            "total_pages": total_pages,
            "total_stats": total,
            "summary": {
                "count": stats_count or 0,
                "avg_progress": round(avg_progress or 0, 1),
                "total_time": int(total_time or 0)
            },
            "page_title": "阅读统计"
        }
        
        return templates.TemplateResponse("statistics.html", context)
        
    except Exception as e:
        logger.error(f"统计页面加载失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="统计页面加载失败"
        )


# 设备管理页面
@router.get("/devices", response_class=HTMLResponse, summary="设备管理")
async def devices_management(
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="页码")
):
    """
    设备管理页面
    """
    try:
        # 构建查询
        query = select(Device).options(selectinload(Device.user))
        
        # 非管理员只能查看自己的设备
        if not current_user.is_admin:
            query = query.where(Device.user_id == current_user.id)
        
        # 计算总数
        count_query = select(func.count(Device.id)).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()
        
        # 分页
        size = 20
        query = query.order_by(Device.last_sync_at.desc().nullslast())
        query = query.offset((page - 1) * size).limit(size)
        
        result = await db.execute(query)
        devices = result.scalars().all()
        
        # 分页信息
        total_pages = (total + size - 1) // size
        
        context = {
            "request": request,
            "user": current_user,
            "devices": devices,
            "page": page,
            "total_pages": total_pages,
            "total_devices": total,
            "page_title": "设备管理"
        }
        
        return templates.TemplateResponse("devices.html", context)
        
    except Exception as e:
        logger.error(f"设备管理页面加载失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="设备管理页面加载失败"
        )


# 系统设置页面
@router.get("/settings", response_class=HTMLResponse, summary="系统设置")
async def system_settings(
    request: Request,
    current_user: CurrentAdminUser,
    db: DbSession
):
    """
    系统设置页面 - 仅管理员可访问
    """
    try:
        # 系统信息
        system_info = {
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "debug_mode": settings.DEBUG,
            "database_type": settings.DATABASE_TYPE,
            "book_storage_path": settings.BOOK_STORAGE_PATH,
            "webdav_enabled": settings.WEBDAV_ENABLED,
            "webdav_root_path": settings.WEBDAV_ROOT_PATH,
            "log_level": settings.LOG_LEVEL
        }
        
        context = {
            "request": request,
            "user": current_user,
            "system_info": system_info,
            "page_title": "系统设置"
        }
        
        return templates.TemplateResponse("settings.html", context)
        
    except Exception as e:
        logger.error(f"系统设置页面加载失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统设置页面加载失败"
        )


# API文档页面
@router.get("/api-docs", response_class=HTMLResponse, summary="API文档")
async def api_documentation(
    request: Request,
    current_user: CurrentUser
):
    """
    API文档页面 - 显示API使用说明
    """
    try:
        # API端点信息
        api_endpoints = {
            "认证API": [
                {"method": "POST", "path": "/api/v1/auth/login", "description": "用户登录"},
                {"method": "POST", "path": "/api/v1/auth/register", "description": "用户注册"},
                {"method": "POST", "path": "/api/v1/auth/device-register", "description": "设备注册"}
            ],
            "同步API": [
                {"method": "PUT", "path": "/api/v1/syncs/progress", "description": "上传同步进度（kosync兼容）"},
                {"method": "GET", "path": "/api/v1/syncs/progress/{document}", "description": "获取同步进度（kosync兼容）"},
                {"method": "POST", "path": "/api/v1/syncs/progress", "description": "双向同步进度"}
            ],
            "OPDS目录": [
                {"method": "GET", "path": "/api/v1/opds/", "description": "OPDS根目录"},
                {"method": "GET", "path": "/api/v1/opds/catalog/recent", "description": "最新书籍"},
                {"method": "GET", "path": "/api/v1/opds/search", "description": "搜索书籍"}
            ],
            "书籍管理": [
                {"method": "POST", "path": "/api/v1/books/upload", "description": "上传书籍文件"},
                {"method": "GET", "path": "/api/v1/books/{book_id}/download", "description": "下载书籍"},
                {"method": "GET", "path": "/api/v1/books/{book_id}/cover", "description": "获取封面"}
            ],
            "WebDAV服务": [
                {"method": "PROPFIND", "path": "/api/v1/webdav/{path}", "description": "获取资源属性"},
                {"method": "PUT", "path": "/api/v1/webdav/{path}", "description": "上传文件"},
                {"method": "GET", "path": "/api/v1/webdav/{path}", "description": "下载文件"}
            ]
        }
        
        context = {
            "request": request,
            "user": current_user,
            "api_endpoints": api_endpoints,
            "page_title": "API文档"
        }
        
        return templates.TemplateResponse("api_docs.html", context)
        
    except Exception as e:
        logger.error(f"API文档页面加载失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API文档页面加载失败"
        ) 