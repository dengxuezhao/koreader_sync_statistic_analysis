"""
书籍管理API端点

提供书籍文件上传、下载、元数据管理和封面处理功能。
支持多种电子书格式，包括EPUB、PDF、MOBI等。
"""

import logging
import os
import hashlib
import mimetypes
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, List, BinaryIO, Dict
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
from app.models import Book, User, ReadingStatistics
from app.schemas.opds import BookEntry
from app.core.database import get_session
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
            filename=file.filename,
            file_format=file_format,
            file_size=file_size,
            storage_path=str(file_path),
            file_hash=file_hash,
            uploaded_by_id=current_user.id,
            is_available=True,
            download_count=0
        )
        
        db.add(book)
        await db.flush()  # 获取book.id
        
        # 处理封面
        cover_data = metadata.get('cover_data')
        if cover_data:
            try:
                # 处理封面图片
                img = Image.open(BytesIO(cover_data))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 调整封面大小
                img = ImageOps.fit(img, (400, 600), Image.Resampling.LANCZOS)
                
                # 保存为二进制数据
                img_buffer = BytesIO()
                img.save(img_buffer, format='JPEG', quality=85)
                
                book.cover_image = img_buffer.getvalue()
                book.cover_mime_type = 'image/jpeg'
                
                logger.info(f"封面处理成功: {book.title}")
            except Exception as e:
                logger.warning(f"封面处理失败: {e}")
        
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
    
    if not os.path.exists(book.storage_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍文件不存在"
        )
    
    try:
        # 更新下载次数
        book.download_count += 1
        await db.commit()
        
        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(book.storage_path)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        logger.info(f"书籍下载: {book.title} (用户: {user.username if user else '匿名'})")
        
        # 返回文件
        return FileResponse(
            path=book.storage_path,
            filename=book.filename,
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{book.filename}",
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
    
    if not book.cover_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="封面数据不存在"
        )
    
    # 返回封面图片流
    return StreamingResponse(
        BytesIO(book.cover_image),
        media_type=book.cover_mime_type or "image/jpeg",
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
        "filename": book.filename,
        "has_cover": book.has_cover,
        "is_available": book.is_available,
        "download_count": book.download_count,
        "last_downloaded_at": book.last_downloaded_at.isoformat() if book.last_downloaded_at else None,
        "uploaded_by_id": book.uploaded_by_id,
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
            if book.storage_path and os.path.exists(book.storage_path):
                os.remove(book.storage_path)
        
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


# 公开阅读统计API (无需认证)
@router.get("/stats/public", summary="公开阅读统计", description="获取公开的阅读统计数据，无需认证")
async def get_public_reading_stats(
    db: DbSession,
    user_id: Optional[int] = Query(None, description="特定用户ID"),
    username: Optional[str] = Query(None, description="特定用户名")
) -> Any:
    """
    获取公开的阅读统计数据
    
    此端点无需认证，用于博客等公开展示场景。
    只返回已设置为公开的用户数据。
    """
    try:
        # 构建用户查询
        user_query = select(User)
        
        if user_id:
            user_query = user_query.where(User.id == user_id)
        elif username:
            user_query = user_query.where(User.username == username)
        else:
            # 如果没有指定用户，返回第一个管理员用户的公开数据（默认展示）
            user_query = user_query.where(User.is_admin == True).limit(1)
        
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 获取用户的阅读统计
        stats_query = (
            select(ReadingStatistics)
            .where(ReadingStatistics.user_id == user.id)
            .order_by(ReadingStatistics.updated_at.desc())
        )
        
        stats_result = await db.execute(stats_query)
        statistics = stats_result.scalars().all()
        
        # 计算统计汇总
        total_books = len(statistics)
        completed_books = len([s for s in statistics if s.reading_progress >= 100])
        total_reading_time = sum(s.total_reading_time or 0 for s in statistics)
        avg_progress = sum(s.reading_progress or 0 for s in statistics) / total_books if total_books > 0 else 0
        
        # 准备公开展示的数据
        public_stats = []
        for stat in statistics:
            public_stats.append({
                "book_title": stat.book_title,
                "book_author": stat.book_author, 
                "reading_progress": stat.reading_progress,
                "completion_status": stat.completion_status,
                "total_reading_time": stat.total_reading_time,
                "reading_time_formatted": stat.reading_time_formatted,
                "last_read_time": stat.last_read_time.isoformat() if stat.last_read_time else None,
                "device_name": stat.device_name,
                "current_page": stat.current_page,
                "total_pages": stat.total_pages
            })
        
        # 最近阅读的书籍（取前10本）
        recent_books = sorted(
            [s for s in public_stats if s["last_read_time"]],
            key=lambda x: x["last_read_time"],
            reverse=True
        )[:10]
        
        # 已完成的书籍
        completed_books_list = [s for s in public_stats if s["reading_progress"] >= 100]
        
        # 正在阅读的书籍
        reading_books = [
            s for s in public_stats 
            if 0 < s["reading_progress"] < 100
        ][:10]
        
        return {
            "user": {
                "username": user.username,
                "total_books": total_books,
                "completed_books": len(completed_books_list),
                "reading_books": len(reading_books),
                "total_reading_time": total_reading_time,
                "total_reading_hours": total_reading_time // 3600,
                "avg_progress": round(avg_progress, 1)
            },
            "summary": {
                "total_books": total_books,
                "completed_count": len(completed_books_list),
                "reading_count": len(reading_books),
                "completion_rate": round(len(completed_books_list) / total_books * 100, 1) if total_books > 0 else 0,
                "total_reading_time": total_reading_time,
                "avg_progress": round(avg_progress, 1)
            },
            "recent_books": recent_books,
            "completed_books": completed_books_list,
            "reading_books": reading_books,
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取公开阅读统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取公开阅读统计失败"
        )


@router.get("/stats/overview", summary="阅读统计概览")
async def get_reading_stats_overview(
    current_user: CurrentUser,
    db: DbSession
) -> Any:
    """
    获取阅读统计概览数据
    
    需要认证，用于前端概览页面
    """
    try:
        # 构建查询
        query = select(ReadingStatistics)
        
        # 非管理员只能查看自己的统计
        if not current_user.is_admin:
            query = query.where(ReadingStatistics.user_id == current_user.id)
        
        result = await db.execute(query)
        statistics = result.scalars().all()
        
        # 计算统计数据
        total_books = len(statistics)
        completed_books = len([s for s in statistics if s.reading_progress >= 100])
        reading_books = len([s for s in statistics if 0 < s.reading_progress < 100])
        total_reading_time = sum(s.total_reading_time or 0 for s in statistics)
        
        # 最近阅读的书籍
        recent_stats = [
            s for s in statistics 
            if s.last_read_time and s.last_read_time >= datetime.utcnow() - timedelta(days=30)
        ]
        
        return {
            "total_books": total_books,
            "completed_books": completed_books,
            "reading_books": reading_books,
            "completion_rate": round(completed_books / total_books * 100, 1) if total_books > 0 else 0,
            "total_reading_time": total_reading_time,
            "total_reading_hours": total_reading_time // 3600,
            "avg_reading_time": total_reading_time // total_books if total_books > 0 else 0,
            "recent_activity_count": len(recent_stats),
            "devices_count": len(set(s.device_name for s in statistics if s.device_name))
        }
        
    except Exception as e:
        logger.error(f"获取阅读统计概览失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取阅读统计概览失败"
        )


@router.get("/stats/enhanced", summary="增强阅读统计分析")
async def get_enhanced_reading_stats(
    current_user: CurrentUser,
    db: DbSession
) -> Any:
    """
    获取增强的阅读统计分析，包含四个维度：
    A. 整体阅读总结
    B. 单书统计数据  
    C. 阅读时间模式分析
    D. 类型、作者与语言分析
    """
    
    try:
        # 获取用户的阅读统计数据
        statistics_query = select(ReadingStatistics).where(
            ReadingStatistics.user_id == current_user.id
        ).order_by(ReadingStatistics.last_read_time.desc())
        
        result = await db.execute(statistics_query)
        statistics = result.scalars().all()
        
        if not statistics:
            return {
                "overall_summary": {"message": "暂无阅读数据"},
                "per_book_stats": [],
                "time_patterns": {"message": "暂无时间模式数据"},
                "metadata_analysis": {"message": "暂无元数据分析"},
                "total_records": 0,
                "generated_at": datetime.utcnow().isoformat()
            }
        
        # A. 整体阅读总结
        overall_summary = calculate_overall_summary(statistics)
        
        # B. 单书统计数据
        per_book_stats = calculate_per_book_stats(statistics)
        
        # C. 阅读时间模式分析 (基于现有数据的估算)
        time_patterns = calculate_time_patterns(statistics)
        
        # D. 类型、作者与语言分析
        metadata_analysis = await calculate_metadata_analysis(statistics, db)
        
        return {
            "overall_summary": overall_summary,
            "per_book_stats": per_book_stats,
            "time_patterns": time_patterns,
            "metadata_analysis": metadata_analysis,
            "total_records": len(statistics),
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取增强阅读统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取增强阅读统计失败"
        )


def calculate_overall_summary(statistics: List[ReadingStatistics]) -> Dict[str, Any]:
    """计算整体阅读总结 (A)"""
    
    total_books = len(statistics)
    total_reading_time = sum(s.total_reading_time or 0 for s in statistics)
    total_reading_hours = total_reading_time / 3600
    
    # 计算独立页数 (基于已读页数估算)
    total_unique_pages = sum(s.read_pages or s.current_page or 0 for s in statistics)
    
    # 完成度分析
    completed_books = len([s for s in statistics if s.reading_progress >= 100])
    nearly_completed = len([s for s in statistics if 80 <= s.reading_progress < 100])
    in_progress = len([s for s in statistics if 0 < s.reading_progress < 80])
    
    # 时间分析 (基于记录时间估算)
    now = datetime.utcnow()
    this_year_books = len([s for s in statistics if s.created_at and s.created_at.year == now.year])
    this_month_books = len([s for s in statistics if s.created_at and s.created_at.year == now.year and s.created_at.month == now.month])
    
    # 阅读会话分析 (基于现有数据估算)
    reading_sessions = sum(1 for s in statistics if s.total_reading_time and s.total_reading_time > 0)
    avg_session_duration = (total_reading_time / reading_sessions / 60) if reading_sessions > 0 else 0  # 分钟
    
    # 平均每日/周/月阅读时长 (基于创建时间范围估算)
    if statistics:
        date_range = (now - min(s.created_at for s in statistics if s.created_at)).days or 1
        avg_daily_minutes = (total_reading_time / 60) / date_range if date_range > 0 else 0
        avg_weekly_hours = avg_daily_minutes * 7 / 60
        avg_monthly_hours = avg_daily_minutes * 30 / 60
    else:
        avg_daily_minutes = avg_weekly_hours = avg_monthly_hours = 0
    
    return {
        "total_interactive_books": total_books,
        "total_reading_time_hours": round(total_reading_hours, 2),
        "total_reading_time_seconds": total_reading_time,
        "total_unique_pages": total_unique_pages,
        "completed_books": completed_books,
        "nearly_completed_books": nearly_completed,
        "in_progress_books": in_progress,
        "completion_rate": round(completed_books / total_books * 100, 1) if total_books > 0 else 0,
        "avg_daily_reading_minutes": round(avg_daily_minutes, 1),
        "avg_weekly_reading_hours": round(avg_weekly_hours, 1),
        "avg_monthly_reading_hours": round(avg_monthly_hours, 1),
        "avg_session_duration_minutes": round(avg_session_duration, 1),
        "this_year_books": this_year_books,
        "this_month_books": this_month_books,
        "reading_sessions_count": reading_sessions,
        "key_metrics": {
            "总互动书籍数量": f"{total_books} 本",
            "总阅读时长": f"{total_reading_hours:.1f} 小时",
            "总阅读独立页数": f"{total_unique_pages:,} 页",
            "平均单次阅读会话时长": f"{avg_session_duration:.0f} 分钟",
            "本年度已读/互动书籍数量": f"{this_year_books} 本",
            "本月已读/互动书籍数量": f"{this_month_books} 本"
        }
    }


def calculate_per_book_stats(statistics: List[ReadingStatistics]) -> List[Dict[str, Any]]:
    """计算单书统计数据 (B)"""
    
    books_stats = []
    
    for stat in statistics:
        # 基础信息
        book_stat = {
            "book_title": stat.book_title or "未知书籍",
            "book_author": stat.book_author or "未知作者",
            "total_pages": stat.total_pages or 0,
            "read_pages": stat.read_pages or stat.current_page or 0,
            "current_page": stat.current_page or 0,
            "reading_progress": round(stat.reading_progress or 0, 1),
            "completion_percentage": round(stat.reading_progress or 0, 1),
            "total_reading_time_hours": round((stat.total_reading_time or 0) / 3600, 3),
            "total_reading_time_seconds": stat.total_reading_time or 0,
            "highlights_count": stat.highlights_count or 0,
            "notes_count": stat.notes_count or 0,
            "bookmarks_count": stat.bookmarks_count or 0,
            "device_name": stat.device_name or "未知设备",
            "last_read_time": stat.last_read_time.isoformat() if stat.last_read_time else None,
            "first_read_time": stat.first_read_time.isoformat() if stat.first_read_time else None,
            "completion_status": stat.completion_status
        }
        
        # 计算阅读速度 (页/小时)
        if stat.total_reading_time and stat.total_reading_time > 0:
            hours = stat.total_reading_time / 3600
            read_pages = stat.read_pages or stat.current_page or 0
            book_stat["reading_speed_pages_per_hour"] = round(read_pages / hours, 1) if hours > 0 else 0
        else:
            book_stat["reading_speed_pages_per_hour"] = 0
        
        # 阅读会话次数 (基于现有数据估算)
        book_stat["reading_sessions"] = 1 if stat.total_reading_time and stat.total_reading_time > 0 else 0
        
        # 完成度计算 (两种方式)
        if stat.total_pages and stat.total_pages > 0:
            # 方式1: 最大页码比例
            max_page_percentage = (stat.current_page or 0) / stat.total_pages * 100
            # 方式2: 已读页数比例  
            read_pages_percentage = (stat.read_pages or 0) / stat.total_pages * 100
            book_stat["completion_by_max_page"] = round(max_page_percentage, 1)
            book_stat["completion_by_read_pages"] = round(read_pages_percentage, 1)
        else:
            book_stat["completion_by_max_page"] = 0
            book_stat["completion_by_read_pages"] = 0
        
        books_stats.append(book_stat)
    
    # 按阅读时间排序
    books_stats.sort(key=lambda x: x["total_reading_time_seconds"], reverse=True)
    
    return books_stats


def calculate_time_patterns(statistics: List[ReadingStatistics]) -> Dict[str, Any]:
    """计算阅读时间模式分析 (C) - 基于现有数据估算"""
    
    # 由于缺乏详细的page_stat_data，我们基于现有的时间戳进行分析
    time_data = []
    
    for stat in statistics:
        # 使用last_read_time作为阅读时间参考
        if stat.last_read_time:
            time_data.append({
                "datetime": stat.last_read_time,
                "reading_time": stat.total_reading_time or 0,
                "hour": stat.last_read_time.hour,
                "weekday": stat.last_read_time.weekday(),  # 0=Monday, 6=Sunday
                "month": stat.last_read_time.month
            })
    
    if not time_data:
        return {
            "hourly_distribution": {},
            "weekday_distribution": {},
            "monthly_distribution": {},
            "reading_heatmap_data": [],
            "peak_reading_hours": [],
            "message": "暂无时间模式数据"
        }
    
    # 按小时分布
    hourly_dist = {}
    for i in range(24):
        hourly_dist[i] = {
            "count": len([d for d in time_data if d["hour"] == i]),
            "total_time": sum(d["reading_time"] for d in time_data if d["hour"] == i),
            "avg_session_time": 0
        }
        if hourly_dist[i]["count"] > 0:
            hourly_dist[i]["avg_session_time"] = hourly_dist[i]["total_time"] / hourly_dist[i]["count"]
    
    # 按星期分布
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday_dist = {}
    for i in range(7):
        weekday_dist[weekday_names[i]] = {
            "count": len([d for d in time_data if d["weekday"] == i]),
            "total_time": sum(d["reading_time"] for d in time_data if d["weekday"] == i),
            "avg_session_time": 0
        }
        if weekday_dist[weekday_names[i]]["count"] > 0:
            weekday_dist[weekday_names[i]]["avg_session_time"] = weekday_dist[weekday_names[i]]["total_time"] / weekday_dist[weekday_names[i]]["count"]
    
    # 按月份分布
    month_names = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]
    monthly_dist = {}
    for i in range(1, 13):
        month_key = month_names[i-1]
        monthly_dist[month_key] = {
            "count": len([d for d in time_data if d["month"] == i]),
            "total_time": sum(d["reading_time"] for d in time_data if d["month"] == i),
            "avg_session_time": 0
        }
        if monthly_dist[month_key]["count"] > 0:
            monthly_dist[month_key]["avg_session_time"] = monthly_dist[month_key]["total_time"] / monthly_dist[month_key]["count"]
    
    # 生成热力图数据 (hour vs weekday)
    heatmap_data = []
    for hour in range(24):
        for weekday in range(7):
            count = len([d for d in time_data if d["hour"] == hour and d["weekday"] == weekday])
            total_time = sum(d["reading_time"] for d in time_data if d["hour"] == hour and d["weekday"] == weekday)
            heatmap_data.append({
                "hour": hour,
                "weekday": weekday,
                "weekday_name": weekday_names[weekday],
                "count": count,
                "total_time": total_time,
                "intensity": total_time / 3600  # 转换为小时
            })
    
    # 找出阅读高峰时段
    peak_hours = sorted(hourly_dist.items(), key=lambda x: x[1]["total_time"], reverse=True)[:5]
    peak_reading_hours = [{"hour": hour, "total_time": data["total_time"], "count": data["count"]} for hour, data in peak_hours]
    
    return {
        "hourly_distribution": hourly_dist,
        "weekday_distribution": weekday_dist,
        "monthly_distribution": monthly_dist,
        "reading_heatmap_data": heatmap_data,
        "peak_reading_hours": peak_reading_hours,
        "total_time_entries": len(time_data)
    }


async def calculate_metadata_analysis(statistics: List[ReadingStatistics], db) -> Dict[str, Any]:
    """计算类型、作者与语言分析 (D)"""
    
    # 作者分析
    author_stats = {}
    for stat in statistics:
        author = stat.book_author or "未知作者"
        if author not in author_stats:
            author_stats[author] = {
                "books_count": 0,
                "total_reading_time": 0,
                "completed_books": 0,
                "avg_progress": 0
            }
        
        author_stats[author]["books_count"] += 1
        author_stats[author]["total_reading_time"] += stat.total_reading_time or 0
        if stat.reading_progress >= 100:
            author_stats[author]["completed_books"] += 1
    
    # 计算作者平均进度
    for author in author_stats:
        author_books = [s for s in statistics if (s.book_author or "未知作者") == author]
        author_stats[author]["avg_progress"] = sum(s.reading_progress or 0 for s in author_books) / len(author_books)
    
    # 按阅读书籍数量排序
    top_authors = sorted(author_stats.items(), key=lambda x: x[1]["books_count"], reverse=True)[:10]
    
    # 语言分析 (基于现有book数据)
    language_stats = {}
    try:
        # 从关联的书籍表获取语言信息
        book_ids = [s.book_id for s in statistics if s.book_id]
        if book_ids:
            from app.models.book import Book
            books_query = select(Book.language, func.count(Book.id)).where(Book.id.in_(book_ids)).group_by(Book.language)
            books_result = await db.execute(books_query)
            language_data = books_result.fetchall()
            
            for lang, count in language_data:
                lang_key = lang or "未知语言"
                # 计算该语言书籍的阅读统计
                lang_books = [s for s in statistics if s.book_id and any(book_id for book_id in book_ids)]
                total_time = sum(s.total_reading_time or 0 for s in lang_books)
                avg_speed = 0  # 需要更复杂的计算
                
                language_stats[lang_key] = {
                    "books_count": count,
                    "total_reading_time": total_time,
                    "avg_reading_speed": avg_speed
                }
    except Exception as e:
        logger.warning(f"语言分析失败: {e}")
        language_stats = {"未知语言": {"books_count": len(statistics), "total_reading_time": sum(s.total_reading_time or 0 for s in statistics), "avg_reading_speed": 0}}
    
    # 设备分析
    device_stats = {}
    for stat in statistics:
        device = stat.device_name or "未知设备"
        if device not in device_stats:
            device_stats[device] = {
                "books_count": 0,
                "total_reading_time": 0,
                "avg_session_duration": 0
            }
        
        device_stats[device]["books_count"] += 1
        device_stats[device]["total_reading_time"] += stat.total_reading_time or 0
    
    # 计算设备平均会话时长
    for device in device_stats:
        device_books = [s for s in statistics if (s.device_name or "未知设备") == device]
        sessions = len([s for s in device_books if s.total_reading_time and s.total_reading_time > 0])
        if sessions > 0:
            device_stats[device]["avg_session_duration"] = device_stats[device]["total_reading_time"] / sessions
    
    return {
        "author_analysis": {
            "top_authors": [{"author": author, **stats} for author, stats in top_authors],
            "total_authors": len(author_stats)
        },
        "language_analysis": language_stats,
        "device_analysis": device_stats,
        "data_quality": {
            "books_with_author": len([s for s in statistics if s.book_author and s.book_author != "未知作者"]),
            "books_without_author": len([s for s in statistics if not s.book_author or s.book_author == "未知作者"]),
            "total_books": len(statistics)
        }
    }


# 缓存清理函数
async def invalidate_books_cache():
    """清除书籍相关缓存"""
    await invalidate_cache_pattern("books:*")
    await invalidate_cache_pattern("opds:*")  # OPDS也依赖书籍数据
    await invalidate_cache_pattern("stats:*")  # 统计数据也需要更新 