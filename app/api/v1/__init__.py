"""
API v1版本

包含所有v1版本的API端点。
"""

from fastapi import APIRouter

from app.api.v1 import auth, sync, users, devices, opds, books, webdav, web

api_router = APIRouter()

# 注册路由
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])  
api_router.include_router(devices.router, prefix="/devices", tags=["设备管理"])
api_router.include_router(sync.router, prefix="/syncs", tags=["同步API"])
api_router.include_router(opds.router, prefix="/opds", tags=["OPDS目录"])
api_router.include_router(books.router, prefix="/books", tags=["书籍管理"])
api_router.include_router(webdav.router, prefix="/webdav", tags=["WebDAV服务"])
api_router.include_router(web.router, prefix="/web", tags=["Web界面"]) 