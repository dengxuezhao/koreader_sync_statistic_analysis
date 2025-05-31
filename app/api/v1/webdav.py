"""
WebDAV服务端点

实现WebDAV (Web Distributed Authoring and Versioning) 协议的核心操作。
专门为KOReader统计插件提供兼容的文件上传和管理功能。
"""

import logging
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict, List
from xml.etree.ElementTree import Element, SubElement, tostring
from urllib.parse import unquote, quote

from fastapi import APIRouter, HTTPException, status, Request, Response, Depends, Query
from fastapi.responses import PlainTextResponse, FileResponse
from sqlalchemy import select, and_, func
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, CurrentUser, OptionalCurrentUser
from app.core.config import settings
from app.models import User, Device, Book, ReadingStatistics

router = APIRouter()
logger = logging.getLogger(__name__)


class WebDAVService:
    """WebDAV服务核心功能"""
    
    @staticmethod
    def ensure_webdav_dirs():
        """确保WebDAV目录存在"""
        webdav_root = Path(settings.WEBDAV_ROOT_PATH)
        stats_dir = webdav_root / "statistics"
        
        webdav_root.mkdir(parents=True, exist_ok=True)
        stats_dir.mkdir(parents=True, exist_ok=True)
        
        return webdav_root, stats_dir
    
    @staticmethod
    def get_file_info(file_path: Path) -> Dict[str, Any]:
        """获取文件信息"""
        if not file_path.exists():
            return None
            
        stat = file_path.stat()
        is_dir = file_path.is_dir()
        
        return {
            "name": file_path.name,
            "path": str(file_path),
            "is_directory": is_dir,
            "size": stat.st_size if not is_dir else 0,
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "created": datetime.fromtimestamp(stat.st_ctime),
            "content_type": "httpd/unix-directory" if is_dir else "application/octet-stream"
        }
    
    @staticmethod
    def generate_propfind_response(path: str, depth: str = "0") -> str:
        """生成PROPFIND响应XML"""
        # WebDAV PROPFIND XML响应
        multistatus = Element("D:multistatus", {"xmlns:D": "DAV:"})
        
        webdav_root, _ = WebDAVService.ensure_webdav_dirs()
        requested_path = webdav_root / unquote(path.lstrip('/'))
        
        # 处理根目录或不存在的路径
        if not requested_path.exists():
            requested_path = webdav_root
            
        # 添加请求的资源
        response = SubElement(multistatus, "D:response")
        href = SubElement(response, "D:href")
        href.text = f"/api/v1/webdav/{quote(path.lstrip('/'))}"
        
        propstat = SubElement(response, "D:propstat")
        prop = SubElement(propstat, "D:prop")
        
        file_info = WebDAVService.get_file_info(requested_path)
        if file_info:
            # 资源类型
            resourcetype = SubElement(prop, "D:resourcetype")
            if file_info["is_directory"]:
                SubElement(resourcetype, "D:collection")
            
            # 内容长度
            if not file_info["is_directory"]:
                getcontentlength = SubElement(prop, "D:getcontentlength")
                getcontentlength.text = str(file_info["size"])
            
            # 最后修改时间
            getlastmodified = SubElement(prop, "D:getlastmodified")
            getlastmodified.text = file_info["modified"].strftime("%a, %d %b %Y %H:%M:%S GMT")
            
            # 创建时间
            creationdate = SubElement(prop, "D:creationdate")
            creationdate.text = file_info["created"].isoformat() + "Z"
        
        # 状态
        status_elem = SubElement(propstat, "D:status")
        status_elem.text = "HTTP/1.1 200 OK"
        
        # 如果深度为1，添加子资源
        if depth == "1" and file_info and file_info["is_directory"]:
            try:
                for child_path in requested_path.iterdir():
                    child_response = SubElement(multistatus, "D:response")
                    child_href = SubElement(child_response, "D:href")
                    relative_path = child_path.relative_to(webdav_root)
                    child_href.text = f"/api/v1/webdav/{quote(str(relative_path))}"
                    
                    child_propstat = SubElement(child_response, "D:propstat")
                    child_prop = SubElement(child_propstat, "D:prop")
                    
                    child_info = WebDAVService.get_file_info(child_path)
                    if child_info:
                        # 资源类型
                        child_resourcetype = SubElement(child_prop, "D:resourcetype")
                        if child_info["is_directory"]:
                            SubElement(child_resourcetype, "D:collection")
                        
                        # 内容长度
                        if not child_info["is_directory"]:
                            child_getcontentlength = SubElement(child_prop, "D:getcontentlength")
                            child_getcontentlength.text = str(child_info["size"])
                        
                        # 最后修改时间
                        child_getlastmodified = SubElement(child_prop, "D:getlastmodified")
                        child_getlastmodified.text = child_info["modified"].strftime("%a, %d %b %Y %H:%M:%S GMT")
                    
                    # 状态
                    child_status = SubElement(child_propstat, "D:status")
                    child_status.text = "HTTP/1.1 200 OK"
                    
            except PermissionError:
                pass
        
        return tostring(multistatus, encoding="unicode")
    
    @staticmethod
    def parse_koreader_statistics(file_content: bytes) -> Optional[Dict[str, Any]]:
        """解析KOReader统计文件"""
        try:
            # KOReader统计文件通常是JSON格式
            stats_data = json.loads(file_content.decode('utf-8'))
            
            # 提取关键统计信息
            parsed_stats = {
                "device_id": stats_data.get("device_id"),
                "book_title": stats_data.get("title"),
                "book_author": stats_data.get("authors"),
                "book_path": stats_data.get("file"),
                "total_pages": stats_data.get("pages"),
                "read_pages": stats_data.get("page"),
                "reading_time": stats_data.get("time_spent_reading", 0),
                "last_read": stats_data.get("last_time"),
                "progress": stats_data.get("percentage", 0.0),
                "statistics": stats_data,
                "updated_at": datetime.utcnow()
            }
            
            return parsed_stats
            
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"KOReader统计文件解析失败: {e}")
            return None


# WebDAV PROPFIND 方法
@router.api_route("/{path:path}", methods=["PROPFIND"], summary="WebDAV PROPFIND")
async def webdav_propfind(
    path: str,
    request: Request,
    user: OptionalCurrentUser,
    db: DbSession
) -> Response:
    """
    WebDAV PROPFIND方法
    
    返回资源属性信息，支持目录列表。
    """
    try:
        # 获取Depth头部
        depth = request.headers.get("Depth", "0")
        
        # 生成PROPFIND响应
        xml_response = WebDAVService.generate_propfind_response(path, depth)
        
        logger.info(f"WebDAV PROPFIND: {path} (深度: {depth}, 用户: {user.username if user else '匿名'})")
        
        return Response(
            content=xml_response,
            media_type="application/xml; charset=utf-8",
            status_code=207,  # Multi-Status
            headers={
                "DAV": "1, 2",
                "MS-Author-Via": "DAV"
            }
        )
        
    except Exception as e:
        logger.error(f"WebDAV PROPFIND错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WebDAV PROPFIND操作失败"
        )


# WebDAV GET 方法
@router.get("/{path:path}", summary="WebDAV GET文件")
async def webdav_get_file(
    path: str,
    user: OptionalCurrentUser,
    db: DbSession
) -> FileResponse:
    """
    WebDAV GET方法
    
    下载指定的文件。
    """
    try:
        webdav_root, _ = WebDAVService.ensure_webdav_dirs()
        file_path = webdav_root / unquote(path.lstrip('/'))
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在"
            )
        
        if file_path.is_dir():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法下载目录"
            )
        
        logger.info(f"WebDAV GET: {path} (用户: {user.username if user else '匿名'})")
        
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            headers={
                "DAV": "1, 2",
                "MS-Author-Via": "DAV"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WebDAV GET错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件下载失败"
        )


# WebDAV PUT 方法
@router.put("/{path:path}", summary="WebDAV PUT上传文件")
async def webdav_put_file(
    path: str,
    request: Request,
    user: OptionalCurrentUser,
    db: DbSession
) -> Response:
    """
    WebDAV PUT方法
    
    上传文件到指定路径，主要用于KOReader统计文件上传。
    """
    try:
        webdav_root, stats_dir = WebDAVService.ensure_webdav_dirs()
        file_path = webdav_root / unquote(path.lstrip('/'))
        
        # 确保父目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 读取请求体
        file_content = await request.body()
        
        # 检查是否是KOReader统计文件
        is_stats_file = "statistics" in path.lower() or path.endswith('.lua') or path.endswith('.json')
        
        # 保存文件
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # 如果是统计文件，尝试解析
        if is_stats_file:
            stats_data = WebDAVService.parse_koreader_statistics(file_content)
            if stats_data:
                logger.info(f"KOReader统计文件上传: {stats_data.get('book_title', 'Unknown')} "
                           f"(用户: {user.username if user else '匿名'})")
                
                # 将统计数据保存到数据库
                try:
                    # 查找或创建统计记录
                    stats_record = None
                    if stats_data.get('book_title') and stats_data.get('device_id'):
                        # 尝试找到现有记录
                        result = await db.execute(
                            select(ReadingStatistics).where(
                                and_(
                                    ReadingStatistics.book_title == stats_data['book_title'],
                                    ReadingStatistics.device_name == stats_data['device_id']
                                )
                            )
                        )
                        stats_record = result.scalar_one_or_none()
                    
                    if not stats_record:
                        # 创建新记录
                        stats_record = ReadingStatistics()
                        if user:
                            stats_record.user_id = user.id
                        db.add(stats_record)
                    
                    # 更新统计数据
                    stats_record.update_from_koreader_data(stats_data)
                    stats_record.webdav_file_path = path
                    stats_record.webdav_uploaded_at = datetime.utcnow()
                    
                    # 尝试关联书籍
                    if stats_data.get('book_title'):
                        book_result = await db.execute(
                            select(Book).where(Book.title.ilike(f"%{stats_data['book_title']}%"))
                        )
                        book = book_result.scalar_one_or_none()
                        if book:
                            stats_record.book_id = book.id
                    
                    await db.commit()
                    
                    logger.info(f"KOReader统计数据已保存到数据库: {stats_record.id}")
                    
                except Exception as e:
                    await db.rollback()
                    logger.error(f"保存统计数据失败: {e}")
                    # 不影响文件上传，继续处理
        
        file_existed = file_path.exists()
        status_code = 200 if file_existed else 201
        
        logger.info(f"WebDAV PUT: {path} ({len(file_content)}字节, 用户: {user.username if user else '匿名'})")
        
        return Response(
            status_code=status_code,
            headers={
                "DAV": "1, 2",
                "MS-Author-Via": "DAV",
                "Location": f"/api/v1/webdav/{quote(path.lstrip('/'))}"
            }
        )
        
    except Exception as e:
        logger.error(f"WebDAV PUT错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件上传失败"
        )


# WebDAV DELETE 方法
@router.delete("/{path:path}", summary="WebDAV DELETE删除文件")
async def webdav_delete_file(
    path: str,
    user: OptionalCurrentUser,
    db: DbSession
) -> Response:
    """
    WebDAV DELETE方法
    
    删除指定的文件或目录。
    """
    try:
        webdav_root, _ = WebDAVService.ensure_webdav_dirs()
        file_path = webdav_root / unquote(path.lstrip('/'))
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件或目录不存在"
            )
        
        if file_path.is_dir():
            # 删除目录（如果为空）
            try:
                file_path.rmdir()
            except OSError:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="目录不为空，无法删除"
                )
        else:
            # 删除文件
            file_path.unlink()
        
        logger.info(f"WebDAV DELETE: {path} (用户: {user.username if user else '匿名'})")
        
        return Response(
            status_code=204,  # No Content
            headers={
                "DAV": "1, 2",
                "MS-Author-Via": "DAV"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WebDAV DELETE错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除操作失败"
        )


# WebDAV MKCOL 方法
@router.api_route("/{path:path}", methods=["MKCOL"], summary="WebDAV MKCOL创建目录")
async def webdav_mkcol(
    path: str,
    user: OptionalCurrentUser,
    db: DbSession
) -> Response:
    """
    WebDAV MKCOL方法
    
    创建新的目录。
    """
    try:
        webdav_root, _ = WebDAVService.ensure_webdav_dirs()
        dir_path = webdav_root / unquote(path.lstrip('/'))
        
        if dir_path.exists():
            raise HTTPException(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                detail="目录已存在"
            )
        
        # 确保父目录存在
        if not dir_path.parent.exists():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="父目录不存在"
            )
        
        # 创建目录
        dir_path.mkdir()
        
        logger.info(f"WebDAV MKCOL: {path} (用户: {user.username if user else '匿名'})")
        
        return Response(
            status_code=201,  # Created
            headers={
                "DAV": "1, 2",
                "MS-Author-Via": "DAV",
                "Location": f"/api/v1/webdav/{quote(path.lstrip('/'))}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WebDAV MKCOL错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="目录创建失败"
        )


# WebDAV OPTIONS 方法
@router.options("/{path:path}", summary="WebDAV OPTIONS")
async def webdav_options(path: str) -> Response:
    """
    WebDAV OPTIONS方法
    
    返回支持的WebDAV方法。
    """
    return Response(
        status_code=200,
        headers={
            "Allow": "OPTIONS, GET, PUT, DELETE, PROPFIND, MKCOL",
            "DAV": "1, 2",
            "MS-Author-Via": "DAV",
            "Accept-Ranges": "bytes"
        }
    )


# 根目录OPTIONS（处理无路径的情况）
@router.options("/", summary="WebDAV根目录OPTIONS")
async def webdav_root_options() -> Response:
    """
    WebDAV根目录OPTIONS方法
    """
    return Response(
        status_code=200,
        headers={
            "Allow": "OPTIONS, GET, PUT, DELETE, PROPFIND, MKCOL",
            "DAV": "1, 2",
            "MS-Author-Via": "DAV",
            "Accept-Ranges": "bytes"
        }
    )


# 获取WebDAV统计信息
@router.get("/stats/overview", summary="获取WebDAV使用统计")
async def get_webdav_stats(
    current_user: CurrentUser,
    db: DbSession
) -> Any:
    """
    获取WebDAV服务使用统计
    """
    try:
        webdav_root, stats_dir = WebDAVService.ensure_webdav_dirs()
        
        # 统计文件数量和大小
        total_files = 0
        total_size = 0
        stats_files = 0
        
        def count_files(directory: Path):
            nonlocal total_files, total_size, stats_files
            try:
                for item in directory.rglob("*"):
                    if item.is_file():
                        total_files += 1
                        total_size += item.stat().st_size
                        
                        # 检查是否是统计文件
                        if "statistics" in str(item).lower() or item.suffix in ['.lua', '.json']:
                            stats_files += 1
            except PermissionError:
                pass
        
        count_files(webdav_root)
        
        return {
            "total_files": total_files,
            "total_size": total_size,
            "statistics_files": stats_files,
            "webdav_root": str(webdav_root),
            "disk_usage": {
                "used": total_size,
                "formatted": f"{total_size / (1024 * 1024):.2f} MB" if total_size > 0 else "0 MB"
            }
        }
        
    except Exception as e:
        logger.error(f"获取WebDAV统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取WebDAV统计失败"
        )


# 获取KOReader统计数据
@router.get("/stats/reading", summary="获取KOReader阅读统计")
async def get_reading_stats(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=20, ge=1, le=100, description="每页大小"),
    device_name: Optional[str] = Query(None, description="设备名称过滤"),
    book_title: Optional[str] = Query(None, description="书籍标题过滤")
) -> Any:
    """
    获取KOReader阅读统计数据
    """
    try:
        # 构建查询
        query = select(ReadingStatistics)
        
        # 用户过滤（仅显示当前用户的统计）
        if not current_user.is_admin:
            query = query.where(ReadingStatistics.user_id == current_user.id)
        
        # 添加过滤条件
        if device_name:
            query = query.where(ReadingStatistics.device_name.ilike(f"%{device_name}%"))
        if book_title:
            query = query.where(ReadingStatistics.book_title.ilike(f"%{book_title}%"))
        
        # 计算总数
        count_query = select(func.count(ReadingStatistics.id)).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()
        
        # 添加排序和分页
        query = query.order_by(ReadingStatistics.updated_at.desc())
        query = query.offset((page - 1) * size).limit(size)
        
        result = await db.execute(query)
        stats = result.scalars().all()
        
        # 格式化响应
        stats_list = []
        for stat in stats:
            stats_list.append({
                "id": stat.id,
                "book_title": stat.book_title,
                "book_author": stat.book_author,
                "device_name": stat.device_name,
                "reading_progress": stat.reading_progress,
                "total_reading_time": stat.total_reading_time,
                "reading_time_formatted": stat.reading_time_formatted,
                "completion_status": stat.completion_status,
                "current_page": stat.current_page,
                "total_pages": stat.total_pages,
                "last_read_time": stat.last_read_time.isoformat() if stat.last_read_time else None,
                "updated_at": stat.updated_at.isoformat()
            })
        
        return {
            "total": total,
            "page": page,
            "size": size,
            "statistics": stats_list
        }
        
    except Exception as e:
        logger.error(f"获取阅读统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取阅读统计失败"
        ) 