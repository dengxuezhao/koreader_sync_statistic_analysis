"""
书籍管理API端点

提供书籍文件上传、下载、元数据管理和封面处理功能。
支持多种电子书格式，包括EPUB、PDF、MOBI等。
"""

import logging
import os
import hashlib
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List, BinaryIO
from io import BytesIO

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Query, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select, and_, func, or_
from sqlalchemy.exc import IntegrityError
from PIL import Image, ImageOps
import zipfile
import fitz  # PyMuPDF
import ebooklib
from ebooklib import epub

from app.api.deps import DbSession, CurrentUser, CurrentAdminUser, OptionalCurrentUser
from app.core.config import settings
from app.models import Book, User
from app.schemas.opds import BookEntry
from app.core.database import get_async_session
from app.core.cache import cache_books, cache_stats, invalidate_cache_pattern
from app.api.deps import get_current_user, get_current_admin_user

router = APIRouter()
logger = logging.getLogger(__name__)


class BookService:
    """书籍管理服务"""
    
    @staticmethod
    def ensure_storage_dirs():
        """确保存储目录存在"""
        storage_path = Path(settings.BOOK_STORAGE_PATH)
        covers_path = storage_path / "covers"
        uploads_path = storage_path / "uploads"
        
        storage_path.mkdir(parents=True, exist_ok=True)
        covers_path.mkdir(parents=True, exist_ok=True)
        uploads_path.mkdir(parents=True, exist_ok=True)
        
        return storage_path, covers_path, uploads_path
    
    @staticmethod
    def calculate_file_hash(file_content: bytes) -> str:
        """计算文件哈希值"""
        return hashlib.md5(file_content).hexdigest()
    
    @staticmethod
    def get_file_format(filename: str) -> str:
        """获取文件格式"""
        ext = Path(filename).suffix.lower()
        format_map = {
            '.epub': 'epub',
            '.pdf': 'pdf',
            '.mobi': 'mobi',
            '.azw': 'azw',
            '.azw3': 'azw3',
            '.fb2': 'fb2',
            '.txt': 'txt',
            '.rtf': 'rtf',
            '.djvu': 'djvu',
            '.cbz': 'cbz',
            '.cbr': 'cbr'
        }
        return format_map.get(ext, 'unknown')
    
    @staticmethod
    def extract_epub_metadata(file_content: bytes) -> dict:
        """提取EPUB元数据"""
        try:
            # 使用ebooklib解析EPUB
            book = epub.read_epub(BytesIO(file_content))
            
            metadata = {
                'title': None,
                'author': None,
                'description': None,
                'publisher': None,
                'language': None,
                'published_date': None,
                'cover_data': None
            }
            
            # 提取基础元数据
            title = book.get_metadata('DC', 'title')
            if title:
                metadata['title'] = title[0][0]
            
            creator = book.get_metadata('DC', 'creator')
            if creator:
                metadata['author'] = creator[0][0]
            
            description = book.get_metadata('DC', 'description')
            if description:
                metadata['description'] = description[0][0]
            
            publisher = book.get_metadata('DC', 'publisher')
            if publisher:
                metadata['publisher'] = publisher[0][0]
            
            language = book.get_metadata('DC', 'language')
            if language:
                metadata['language'] = language[0][0]
            
            date = book.get_metadata('DC', 'date')
            if date:
                try:
                    # 尝试解析日期
                    date_str = date[0][0]
                    if date_str:
                        metadata['published_date'] = datetime.strptime(date_str[:10], '%Y-%m-%d').date()
                except:
                    pass
            
            # 提取封面
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_COVER:
                    metadata['cover_data'] = item.get_content()
                    break
                elif 'cover' in item.get_name().lower() and item.get_type() == ebooklib.ITEM_IMAGE:
                    metadata['cover_data'] = item.get_content()
                    break
            
            return metadata
            
        except Exception as e:
            logger.warning(f"EPUB元数据提取失败: {e}")
            return {}
    
    @staticmethod
    def extract_pdf_metadata(file_content: bytes) -> dict:
        """提取PDF元数据"""
        try:
            # 使用PyMuPDF解析PDF
            doc = fitz.open(stream=file_content, filetype="pdf")
            
            metadata = {
                'title': None,
                'author': None,
                'description': None,
                'publisher': None,
                'language': None,
                'published_date': None,
                'cover_data': None
            }
            
            # 提取文档元数据
            meta = doc.metadata
            if meta.get('title'):
                metadata['title'] = meta['title']
            if meta.get('author'):
                metadata['author'] = meta['author']
            if meta.get('subject'):
                metadata['description'] = meta['subject']
            if meta.get('producer'):
                metadata['publisher'] = meta['producer']
            
            # 提取第一页作为封面
            if doc.page_count > 0:
                page = doc.load_page(0)
                pix = page.get_pixmap()
                img_data = pix.pil_tobytes(format="PNG")
                metadata['cover_data'] = img_data
            
            doc.close()
            return metadata
            
        except Exception as e:
            logger.warning(f"PDF元数据提取失败: {e}")
            return {}
    
    @staticmethod
    def extract_metadata(file_content: bytes, file_format: str, filename: str) -> dict:
        """提取书籍元数据"""
        metadata = {
            'title': Path(filename).stem,  # 默认使用文件名作为标题
            'author': None,
            'description': None,
            'publisher': None,
            'language': None,
            'published_date': None,
            'cover_data': None
        }
        
        try:
            if file_format == 'epub':
                extracted = BookService.extract_epub_metadata(file_content)
                metadata.update({k: v for k, v in extracted.items() if v is not None})
            elif file_format == 'pdf':
                extracted = BookService.extract_pdf_metadata(file_content)
                metadata.update({k: v for k, v in extracted.items() if v is not None})
            # 其他格式可以在这里添加
            
        except Exception as e:
            logger.warning(f"元数据提取失败 ({file_format}): {e}")
        
        return metadata
    
    @staticmethod
    def save_cover(cover_data: bytes, book_id: int) -> str:
        """保存封面图片"""
        try:
            _, covers_path, _ = BookService.ensure_storage_dirs()
            
            # 转换为PIL图像
            img = Image.open(BytesIO(cover_data))
            
            # 转换为RGB模式
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 调整大小（保持长宽比）
            img = ImageOps.fit(img, (400, 600), Image.Resampling.LANCZOS)
            
            # 保存封面
            cover_filename = f"cover_{book_id}.jpg"
            cover_path = covers_path / cover_filename
            img.save(cover_path, 'JPEG', quality=85)
            
            return str(cover_path)
            
        except Exception as e:
            logger.error(f"封面保存失败: {e}")
            return None
    
    @staticmethod
    def generate_thumbnail(cover_path: str, book_id: int) -> str:
        """生成缩略图"""
        try:
            _, covers_path, _ = BookService.ensure_storage_dirs()
            
            # 打开原始封面
            img = Image.open(cover_path)
            
            # 生成缩略图
            img.thumbnail((150, 225), Image.Resampling.LANCZOS)
            
            # 保存缩略图
            thumbnail_filename = f"thumb_{book_id}.jpg"
            thumbnail_path = covers_path / thumbnail_filename
            img.save(thumbnail_path, 'JPEG', quality=80)
            
            return str(thumbnail_path)
            
        except Exception as e:
            logger.error(f"缩略图生成失败: {e}")
            return None


# 书籍上传端点
@router.post("/upload", summary="上传书籍文件")
@cache_books(ttl=settings.CACHE_TTL_BOOKS)
async def upload_book(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(..., description="书籍文件"),
    title: Optional[str] = Form(None, description="书籍标题"),
    author: Optional[str] = Form(None, description="作者"),
    description: Optional[str] = Form(None, description="描述"),
    publisher: Optional[str] = Form(None, description="出版商"),
    genre: Optional[str] = Form(None, description="类型"),
    series: Optional[str] = Form(None, description="系列"),
    series_index: Optional[int] = Form(None, description="系列索引"),
    language: Optional[str] = Form(None, description="语言"),
    extract_metadata: bool = Form(True, description="是否自动提取元数据")
) -> Any:
    """
    上传书籍文件
    
    支持自动元数据提取和封面提取。
    """
    try:
        # 验证文件类型
        file_format = BookService.get_file_format(file.filename)
        if file_format == 'unknown':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的文件格式"
            )
        
        # 读取文件内容
        file_content = await file.read()
        file_size = len(file_content)
        
        # 计算文件哈希
        file_hash = BookService.calculate_file_hash(file_content)
        
        # 检查文件是否已存在
        result = await db.execute(select(Book).where(Book.file_hash == file_hash))
        existing_book = result.scalar_one_or_none()
        if existing_book:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该书籍文件已存在"
            )
        
        # 确保存储目录存在
        storage_path, covers_path, uploads_path = BookService.ensure_storage_dirs()
        
        # 保存文件
        file_filename = f"{file_hash}_{file.filename}"
        file_path = uploads_path / file_filename
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # 提取元数据
        metadata = {}
        if extract_metadata:
            metadata = BookService.extract_metadata(file_content, file_format, file.filename)
        
        # 使用提供的元数据覆盖自动提取的元数据
        book_title = title or metadata.get('title') or Path(file.filename).stem
        book_author = author or metadata.get('author')
        book_description = description or metadata.get('description')
        book_publisher = publisher or metadata.get('publisher')
        book_language = language or metadata.get('language')
        book_published_date = metadata.get('published_date')
        
        # 创建书籍记录
        book = Book(
            title=book_title,
            author=book_author,
            description=book_description,
            publisher=book_publisher,
            genre=genre,
            series=series,
            series_index=series_index,
            language=book_language,
            published_date=book_published_date,
            file_format=file_format,
            file_size=file_size,
            file_path=str(file_path),
            file_hash=file_hash,
            original_filename=file.filename,
            uploaded_by_user_id=current_user.id,
            is_available=True,
            has_cover=False,
            download_count=0
        )
        
        db.add(book)
        await db.flush()  # 获取book.id
        
        # 处理封面
        cover_data = metadata.get('cover_data')
        if cover_data:
            cover_path = BookService.save_cover(cover_data, book.id)
            if cover_path:
                book.cover_path = cover_path
                book.has_cover = True
                
                # 生成缩略图
                thumbnail_path = BookService.generate_thumbnail(cover_path, book.id)
                if thumbnail_path:
                    book.thumbnail_path = thumbnail_path
        
        await db.commit()
        await db.refresh(book)
        
        logger.info(f"书籍上传成功: {book.title} ({current_user.username})")
        
        # 清除相关缓存
        await invalidate_books_cache()
        
        return {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "file_format": book.file_format,
            "file_size": book.file_size,
            "has_cover": book.has_cover,
            "message": "书籍上传成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        # 清理已保存的文件
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        
        logger.error(f"书籍上传失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="书籍上传失败"
        )


# 书籍下载端点
@router.get("/{book_id}/download", summary="下载书籍文件")
async def download_book(
    book_id: int,
    user: OptionalCurrentUser,
    db: DbSession
) -> FileResponse:
    """
    下载书籍文件
    
    支持匿名下载，会记录下载次数。
    """
    # 查找书籍
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    if not book.is_available:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="书籍暂时不可用"
        )
    
    if not os.path.exists(book.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍文件不存在"
        )
    
    try:
        # 更新下载次数
        book.download_count += 1
        book.last_downloaded_at = datetime.utcnow()
        await db.commit()
        
        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(book.file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        logger.info(f"书籍下载: {book.title} (用户: {user.username if user else '匿名'})")
        
        # 返回文件
        return FileResponse(
            path=book.file_path,
            filename=book.original_filename,
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{book.original_filename}",
                "Cache-Control": "no-cache"
            }
        )
        
    except Exception as e:
        logger.error(f"书籍下载失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="书籍下载失败"
        )


# 书籍封面端点
@router.get("/{book_id}/cover", summary="获取书籍封面")
async def get_book_cover(
    book_id: int,
    user: OptionalCurrentUser,
    db: DbSession,
    size: Optional[str] = Query(None, description="封面尺寸 (thumbnail)")
) -> FileResponse:
    """
    获取书籍封面
    
    支持原图和缩略图。
    """
    # 查找书籍
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    if not book.has_cover:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍没有封面"
        )
    
    # 选择封面文件
    if size == "thumbnail" and book.thumbnail_path and os.path.exists(book.thumbnail_path):
        cover_path = book.thumbnail_path
    elif book.cover_path and os.path.exists(book.cover_path):
        cover_path = book.cover_path
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="封面文件不存在"
        )
    
    return FileResponse(
        path=cover_path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=86400"  # 缓存1天
        }
    )


# 书籍列表端点
@router.get("/", summary="获取书籍列表")
@cache_books(ttl=settings.CACHE_TTL_BOOKS)
async def get_books(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=20, ge=1, le=100, description="每页大小"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    author: Optional[str] = Query(None, description="作者过滤"),
    genre: Optional[str] = Query(None, description="类型过滤"),
    format: Optional[str] = Query(None, description="格式过滤"),
    sort_by: str = Query(default="created_at", description="排序字段"),
    sort_order: str = Query(default="desc", description="排序方向")
) -> Any:
    """
    获取书籍列表
    
    支持搜索、过滤和排序。
    """
    try:
        # 构建查询
        query = select(Book).where(Book.is_available == True)
        
        # 添加搜索条件
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Book.title.ilike(search_term),
                    Book.author.ilike(search_term),
                    Book.description.ilike(search_term),
                    Book.publisher.ilike(search_term),
                    Book.series.ilike(search_term)
                )
            )
        
        # 添加过滤条件
        if author:
            query = query.where(Book.author.ilike(f"%{author}%"))
        if genre:
            query = query.where(Book.genre.ilike(f"%{genre}%"))
        if format:
            query = query.where(Book.file_format == format.lower())
        
        # 计算总数
        count_query = select(func.count(Book.id)).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()
        
        # 添加排序
        sort_column = getattr(Book, sort_by, Book.created_at)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # 应用分页
        query = query.offset((page - 1) * size).limit(size)
        result = await db.execute(query)
        books = result.scalars().all()
        
        # 转换为响应格式
        book_list = []
        for book in books:
            book_list.append({
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "description": book.description,
                "publisher": book.publisher,
                "genre": book.genre,
                "series": book.series,
                "series_index": book.series_index,
                "language": book.language,
                "published_date": book.published_date.isoformat() if book.published_date else None,
                "file_format": book.file_format,
                "file_size": book.file_size,
                "has_cover": book.has_cover,
                "download_count": book.download_count,
                "created_at": book.created_at.isoformat(),
                "updated_at": book.updated_at.isoformat()
            })
        
        logger.info(f"获取书籍列表: {len(books)}本书 ({current_user.username})")
        
        return {
            "total": total,
            "page": page,
            "size": size,
            "books": book_list
        }
        
    except Exception as e:
        logger.error(f"获取书籍列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取书籍列表失败"
        )


# 书籍详情端点
@router.get("/{book_id}", summary="获取书籍详情")
@cache_books(ttl=settings.CACHE_TTL_BOOKS)
async def get_book_detail(
    book_id: int,
    current_user: CurrentUser,
    db: DbSession
) -> Any:
    """
    获取书籍详细信息
    """
    # 查找书籍
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "description": book.description,
        "publisher": book.publisher,
        "genre": book.genre,
        "series": book.series,
        "series_index": book.series_index,
        "language": book.language,
        "published_date": book.published_date.isoformat() if book.published_date else None,
        "file_format": book.file_format,
        "file_size": book.file_size,
        "file_hash": book.file_hash,
        "original_filename": book.original_filename,
        "has_cover": book.has_cover,
        "is_available": book.is_available,
        "download_count": book.download_count,
        "last_downloaded_at": book.last_downloaded_at.isoformat() if book.last_downloaded_at else None,
        "uploaded_by_user_id": book.uploaded_by_user_id,
        "created_at": book.created_at.isoformat(),
        "updated_at": book.updated_at.isoformat()
    }


# 书籍更新端点
@router.put("/{book_id}", summary="更新书籍信息")
@cache_books(ttl=settings.CACHE_TTL_BOOKS)
async def update_book(
    book_id: int,
    current_user: CurrentAdminUser,
    db: DbSession,
    title: Optional[str] = Form(None, description="书籍标题"),
    author: Optional[str] = Form(None, description="作者"),
    description: Optional[str] = Form(None, description="描述"),
    publisher: Optional[str] = Form(None, description="出版商"),
    genre: Optional[str] = Form(None, description="类型"),
    series: Optional[str] = Form(None, description="系列"),
    series_index: Optional[int] = Form(None, description="系列索引"),
    language: Optional[str] = Form(None, description="语言"),
    is_available: Optional[bool] = Form(None, description="是否可用")
) -> Any:
    """
    更新书籍信息
    
    仅管理员可操作。
    """
    # 查找书籍
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    try:
        # 更新字段
        if title is not None:
            book.title = title
        if author is not None:
            book.author = author
        if description is not None:
            book.description = description
        if publisher is not None:
            book.publisher = publisher
        if genre is not None:
            book.genre = genre
        if series is not None:
            book.series = series
        if series_index is not None:
            book.series_index = series_index
        if language is not None:
            book.language = language
        if is_available is not None:
            book.is_available = is_available
        
        book.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(book)
        
        logger.info(f"书籍信息更新: {book.title} ({current_user.username})")
        
        # 清除相关缓存
        await invalidate_books_cache()
        
        return {"message": "书籍信息更新成功"}
        
    except Exception as e:
        await db.rollback()
        logger.error(f"书籍信息更新失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="书籍信息更新失败"
        )


# 书籍删除端点
@router.delete("/{book_id}", summary="删除书籍")
@cache_books(ttl=settings.CACHE_TTL_BOOKS)
async def delete_book(
    book_id: int,
    current_user: CurrentAdminUser,
    db: DbSession,
    delete_files: bool = Query(default=False, description="是否删除文件")
) -> Any:
    """
    删除书籍
    
    仅管理员可操作。可选择是否删除关联文件。
    """
    # 查找书籍
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    try:
        # 删除关联文件
        if delete_files:
            if book.file_path and os.path.exists(book.file_path):
                os.remove(book.file_path)
            if book.cover_path and os.path.exists(book.cover_path):
                os.remove(book.cover_path)
            if book.thumbnail_path and os.path.exists(book.thumbnail_path):
                os.remove(book.thumbnail_path)
        
        # 删除数据库记录
        await db.delete(book)
        await db.commit()
        
        logger.info(f"书籍删除: {book.title} ({current_user.username})")
        
        # 清除相关缓存
        await invalidate_books_cache()
        
        return {"message": "书籍删除成功"}
        
    except Exception as e:
        await db.rollback()
        logger.error(f"书籍删除失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="书籍删除失败"
        )


# 书籍统计端点
@router.get("/stats/overview", summary="获取书籍统计信息")
@cache_stats(ttl=settings.CACHE_TTL_STATS)
async def get_books_stats(
    current_user: CurrentUser,
    db: DbSession
) -> Any:
    """
    获取书籍库统计信息
    """
    try:
        # 总书籍数
        total_books_result = await db.execute(
            select(func.count(Book.id)).where(Book.is_available == True)
        )
        total_books = total_books_result.scalar_one()
        
        # 总下载次数
        total_downloads_result = await db.execute(
            select(func.sum(Book.download_count)).where(Book.is_available == True)
        )
        total_downloads = total_downloads_result.scalar_one() or 0
        
        # 文件格式统计
        format_stats_result = await db.execute(
            select(Book.file_format, func.count(Book.id))
            .where(Book.is_available == True)
            .group_by(Book.file_format)
        )
        format_stats = dict(format_stats_result.fetchall())
        
        # 作者统计（前10名）
        author_stats_result = await db.execute(
            select(Book.author, func.count(Book.id))
            .where(and_(Book.is_available == True, Book.author.isnot(None)))
            .group_by(Book.author)
            .order_by(func.count(Book.id).desc())
            .limit(10)
        )
        author_stats = dict(author_stats_result.fetchall())
        
        # 类型统计
        genre_stats_result = await db.execute(
            select(Book.genre, func.count(Book.id))
            .where(and_(Book.is_available == True, Book.genre.isnot(None)))
            .group_by(Book.genre)
        )
        genre_stats = dict(genre_stats_result.fetchall())
        
        return {
            "total_books": total_books,
            "total_downloads": total_downloads,
            "format_stats": format_stats,
            "author_stats": author_stats,
            "genre_stats": genre_stats
        }
        
    except Exception as e:
        logger.error(f"获取书籍统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取书籍统计失败"
        )


# 缓存清理函数
async def invalidate_books_cache():
    """清除书籍相关缓存"""
    await invalidate_cache_pattern("books:*")
    await invalidate_cache_pattern("opds:*")  # OPDS也依赖书籍数据
    await invalidate_cache_pattern("stats:*")  # 统计数据也需要更新 