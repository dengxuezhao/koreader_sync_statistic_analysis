"""
OPDS目录服务端点

实现OPDS (Open Publication Distribution System) 1.2标准的目录服务。
提供书籍浏览、搜索和下载功能，与KOReader和其他OPDS客户端兼容。
"""

import logging
from datetime import datetime
from typing import Any, Optional, List
from urllib.parse import quote, unquote

from fastapi import APIRouter, HTTPException, status, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, and_, func, or_
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, OptionalCurrentUser, CurrentUser
from app.models import Book, User
from app.schemas.opds import (
    OPDSFeed,
    OPDSEntry,
    OPDSLink,
    OPDSAuthor,
    OPDSCategory,
    OPDSNavigationEntry,
    OPDSCatalogInfo,
    BookEntry
)
from app.core.config import settings
from app.core.database import get_session
from app.core.cache import cache_opds, invalidate_cache_pattern
from app.api.deps import get_optional_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


def generate_opds_xml(feed: OPDSFeed) -> str:
    """
    生成OPDS 1.2标准的XML格式
    """
    # XML头部
    xml_content = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_content.append('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog">')
    
    # Feed基础信息
    xml_content.append(f'<id>{feed.id}</id>')
    xml_content.append(f'<title>{feed.title}</title>')
    if feed.subtitle:
        xml_content.append(f'<subtitle>{feed.subtitle}</subtitle>')
    xml_content.append(f'<updated>{feed.updated.isoformat()}Z</updated>')
    
    # Feed图标
    if feed.icon:
        xml_content.append(f'<icon>{feed.icon}</icon>')
    
    # Feed作者
    for author in feed.authors:
        xml_content.append('<author>')
        xml_content.append(f'<name>{author.name}</name>')
        if author.uri:
            xml_content.append(f'<uri>{author.uri}</uri>')
        xml_content.append('</author>')
    
    # Feed链接
    for link in feed.links:
        link_attrs = [f'rel="{link.rel}"', f'href="{link.href}"']
        if link.type:
            link_attrs.append(f'type="{link.type}"')
        if link.title:
            link_attrs.append(f'title="{link.title}"')
        xml_content.append(f'<link {" ".join(link_attrs)} />')
    
    # 分页信息
    if feed.total_results is not None:
        xml_content.append(f'<opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">{feed.total_results}</opensearch:totalResults>')
    if feed.items_per_page is not None:
        xml_content.append(f'<opensearch:itemsPerPage xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">{feed.items_per_page}</opensearch:itemsPerPage>')
    if feed.start_index is not None:
        xml_content.append(f'<opensearch:startIndex xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">{feed.start_index}</opensearch:startIndex>')
    
    # 条目
    for entry in feed.entries:
        xml_content.append('<entry>')
        xml_content.append(f'<id>{entry.id}</id>')
        xml_content.append(f'<title>{entry.title}</title>')
        xml_content.append(f'<updated>{entry.updated.isoformat()}Z</updated>')
        
        if entry.published:
            xml_content.append(f'<published>{entry.published.isoformat()}Z</published>')
        
        if entry.summary:
            xml_content.append(f'<summary>{entry.summary}</summary>')
        
        if entry.content:
            xml_content.append(f'<content type="text">{entry.content}</content>')
        
        if entry.rights:
            xml_content.append(f'<rights>{entry.rights}</rights>')
        
        # 作者
        for author in entry.authors:
            xml_content.append('<author>')
            xml_content.append(f'<name>{author.name}</name>')
            if author.uri:
                xml_content.append(f'<uri>{author.uri}</uri>')
            xml_content.append('</author>')
        
        # 分类
        for category in entry.categories:
            cat_attrs = [f'term="{category.term}"']
            if category.label:
                cat_attrs.append(f'label="{category.label}"')
            if category.scheme:
                cat_attrs.append(f'scheme="{category.scheme}"')
            xml_content.append(f'<category {" ".join(cat_attrs)} />')
        
        # 链接
        for link in entry.links:
            link_attrs = [f'rel="{link.rel}"', f'href="{link.href}"']
            if link.type:
                link_attrs.append(f'type="{link.type}"')
            if link.title:
                link_attrs.append(f'title="{link.title}"')
            xml_content.append(f'<link {" ".join(link_attrs)} />')
        
        xml_content.append('</entry>')
    
    xml_content.append('</feed>')
    
    return '\n'.join(xml_content)


def get_base_url(request: Request) -> str:
    """获取基础URL"""
    return f"{request.url.scheme}://{request.url.netloc}"


def create_navigation_feed(request: Request, title: str = "Kompanion图书馆") -> OPDSFeed:
    """创建导航目录"""
    base_url = get_base_url(request)
    opds_base = f"{base_url}/api/v1/opds"
    
    # 基础链接
    links = [
        OPDSLink(
            rel="self",
            href=f"{opds_base}/",
            type="application/atom+xml;profile=opds-catalog;kind=navigation"
        ),
        OPDSLink(
            rel="start",
            href=f"{opds_base}/",
            type="application/atom+xml;profile=opds-catalog;kind=navigation"
        ),
        OPDSLink(
            rel="search",
            href=f"{opds_base}/search?q={{searchTerms}}",
            type="application/atom+xml;profile=opds-catalog;kind=acquisition",
            title="搜索书籍"
        )
    ]
    
    # 导航条目
    entries = [
        OPDSEntry(
            id=f"{opds_base}/catalog/recent",
            title="最新书籍",
            updated=datetime.utcnow(),
            summary="浏览最近添加的书籍",
            links=[
                OPDSLink(
                    rel="subsection",
                    href=f"{opds_base}/catalog/recent",
                    type="application/atom+xml;profile=opds-catalog;kind=acquisition"
                )
            ],
            categories=[
                OPDSCategory(term="recent", label="最新")
            ]
        ),
        OPDSEntry(
            id=f"{opds_base}/catalog/popular",
            title="热门书籍",
            updated=datetime.utcnow(),
            summary="浏览下载次数最多的书籍",
            links=[
                OPDSLink(
                    rel="subsection",
                    href=f"{opds_base}/catalog/popular",
                    type="application/atom+xml;profile=opds-catalog;kind=acquisition"
                )
            ],
            categories=[
                OPDSCategory(term="popular", label="热门")
            ]
        ),
        OPDSEntry(
            id=f"{opds_base}/catalog/authors",
            title="按作者浏览",
            updated=datetime.utcnow(),
            summary="按作者分类浏览书籍",
            links=[
                OPDSLink(
                    rel="subsection",
                    href=f"{opds_base}/catalog/authors",
                    type="application/atom+xml;profile=opds-catalog;kind=navigation"
                )
            ],
            categories=[
                OPDSCategory(term="authors", label="作者")
            ]
        ),
        OPDSEntry(
            id=f"{opds_base}/catalog/genres",
            title="按类型浏览",
            updated=datetime.utcnow(),
            summary="按书籍类型分类浏览",
            links=[
                OPDSLink(
                    rel="subsection",
                    href=f"{opds_base}/catalog/genres",
                    type="application/atom+xml;profile=opds-catalog;kind=navigation"
                )
            ],
            categories=[
                OPDSCategory(term="genres", label="类型")
            ]
        ),
        OPDSEntry(
            id=f"{opds_base}/catalog/all",
            title="所有书籍",
            updated=datetime.utcnow(),
            summary="浏览所有可用书籍",
            links=[
                OPDSLink(
                    rel="subsection",
                    href=f"{opds_base}/catalog/all",
                    type="application/atom+xml;profile=opds-catalog;kind=acquisition"
                )
            ],
            categories=[
                OPDSCategory(term="all", label="全部")
            ]
        )
    ]
    
    return OPDSFeed(
        id=f"{opds_base}/",
        title=title,
        subtitle="KOReader兼容的电子书目录服务",
        updated=datetime.utcnow(),
        authors=[
            OPDSAuthor(name="Kompanion", uri=base_url)
        ],
        links=links,
        entries=entries
    )


def book_to_opds_entry(book: Book, request: Request) -> OPDSEntry:
    """将Book模型转换为OPDS Entry"""
    base_url = get_base_url(request)
    opds_base = f"{base_url}/api/v1/opds"
    
    # 基础链接
    links = []
    
    # 下载链接
    if book.storage_path:
        download_url = f"{base_url}/api/v1/books/{book.id}/download"
        links.append(
            OPDSLink(
                rel="http://opds-spec.org/acquisition",
                href=download_url,
                type=get_mime_type(book.file_format),
                title=f"下载 {book.file_format.upper()}"
            )
        )
    
    # 封面链接
    if book.has_cover:
        cover_url = f"{base_url}/api/v1/books/{book.id}/cover"
        links.extend([
            OPDSLink(
                rel="http://opds-spec.org/image",
                href=cover_url,
                type="image/jpeg"
            ),
            OPDSLink(
                rel="http://opds-spec.org/image/thumbnail",
                href=f"{cover_url}?size=thumbnail",
                type="image/jpeg"
            )
        ])
    
    # 作者信息
    authors = []
    if book.author:
        authors.append(OPDSAuthor(name=book.author))
    
    # 分类信息
    categories = []
    if book.genre:
        categories.append(OPDSCategory(term=book.genre.lower(), label=book.genre))
    if book.series:
        categories.append(OPDSCategory(term="series", label=f"系列: {book.series}"))
    
    # 构建描述
    summary_parts = []
    if book.description:
        summary_parts.append(book.description)
    if book.publisher:
        summary_parts.append(f"出版社: {book.publisher}")
    if book.published_date:
        summary_parts.append(f"出版日期: {book.published_date.strftime('%Y-%m-%d')}")
    if book.language:
        summary_parts.append(f"语言: {book.language}")
    
    summary = " | ".join(summary_parts) if summary_parts else f"{book.file_format.upper()}格式电子书"
    
    return OPDSEntry(
        id=f"{opds_base}/books/{book.id}",
        title=book.title,
        updated=book.updated_at,
        published=book.published_date,
        summary=summary,
        authors=authors,
        categories=categories,
        links=links,
        rights=f"文件大小: {format_file_size(book.file_size)} | 下载次数: {book.download_count}"
    )


def get_mime_type(file_format: str) -> str:
    """根据文件格式获取MIME类型"""
    mime_types = {
        'epub': 'application/epub+zip',
        'pdf': 'application/pdf',
        'mobi': 'application/x-mobipocket-ebook',
        'azw': 'application/vnd.amazon.ebook',
        'azw3': 'application/vnd.amazon.ebook',
        'fb2': 'application/x-fictionbook+xml',
        'txt': 'text/plain',
        'rtf': 'application/rtf',
        'djvu': 'image/vnd.djvu',
        'cbz': 'application/vnd.comicbook+zip',
        'cbr': 'application/vnd.comicbook-rar'
    }
    return mime_types.get(file_format.lower(), 'application/octet-stream')


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


# OPDS根目录端点
@router.get("/", summary="OPDS根目录")
@cache_opds(ttl=settings.CACHE_TTL_OPDS)
async def opds_root(
    request: Request,
    user: OptionalCurrentUser,
    db: DbSession
) -> Response:
    """
    OPDS目录根端点
    
    返回OPDS导航目录，提供书籍浏览入口。
    """
    try:
        # 创建导航目录
        feed = create_navigation_feed(request)
        
        # 生成XML
        xml_content = generate_opds_xml(feed)
        
        logger.info(f"OPDS根目录访问 (用户: {user.username if user else '匿名'})")
        
        return Response(
            content=xml_content,
            media_type="application/atom+xml;profile=opds-catalog;kind=navigation;charset=utf-8",
            headers={
                "charset": "utf-8"
            }
        )

    except Exception as e:
        logger.error(f"OPDS根目录错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPDS目录服务暂时不可用"
        )


# OPDS根目录HEAD请求支持
@router.head("/", summary="OPDS根目录 - HEAD请求")
async def opds_root_head(
    request: Request,
    user: OptionalCurrentUser,
    db: DbSession
) -> Response:
    """
    OPDS目录根端点 - HEAD请求
    """
    return Response(
        media_type="application/atom+xml;profile=opds-catalog;kind=navigation;charset=utf-8",
        headers={
            "charset": "utf-8"
        }
    )


@router.get("/catalog/recent", summary="最新书籍")
@cache_opds(ttl=settings.CACHE_TTL_OPDS // 2)  # 最新书籍缓存时间减半
async def opds_recent_books(
    request: Request,
    user: OptionalCurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=20, ge=1, le=100, description="每页大小")
) -> Response:
    """
    最新书籍目录
    """
    try:
        base_url = get_base_url(request)
        opds_base = f"{base_url}/api/v1/opds"
        
        # 查询最新书籍
        query = select(Book).where(Book.is_available == True).order_by(Book.created_at.desc())
        
        # 计算总数
        count_result = await db.execute(select(func.count(Book.id)).where(Book.is_available == True))
        total = count_result.scalar_one()
        
        # 应用分页
        query = query.offset((page - 1) * size).limit(size)
        result = await db.execute(query)
        books = result.scalars().all()
        
        # 生成OPDS条目
        entries = []
        for book in books:
            entries.append(book_to_opds_entry(book, request))
        
        # 分页链接
        links = [
            OPDSLink(
                rel="self",
                href=f"{opds_base}/catalog/recent?page={page}&size={size}",
                type="application/atom+xml;profile=opds-catalog;kind=acquisition"
            ),
            OPDSLink(
                rel="start",
                href=f"{opds_base}/",
                type="application/atom+xml;profile=opds-catalog;kind=navigation"
            ),
            OPDSLink(
                rel="up",
                href=f"{opds_base}/",
                type="application/atom+xml;profile=opds-catalog;kind=navigation"
            )
        ]
        
        # 添加分页导航链接
        if page > 1:
            links.append(
                OPDSLink(
                    rel="prev",
                    href=f"{opds_base}/catalog/recent?page={page-1}&size={size}",
                    type="application/atom+xml;profile=opds-catalog;kind=acquisition"
                )
            )
        
        total_pages = (total + size - 1) // size
        if page < total_pages:
            links.append(
                OPDSLink(
                    rel="next",
                    href=f"{opds_base}/catalog/recent?page={page+1}&size={size}",
                    type="application/atom+xml;profile=opds-catalog;kind=acquisition"
                )
            )
        
        # 创建Feed
        feed = OPDSFeed(
            id=f"{opds_base}/catalog/recent",
            title="最新书籍",
            subtitle=f"最近添加的书籍 (第{page}页，共{total_pages}页)",
            updated=datetime.utcnow(),
            authors=[OPDSAuthor(name="Kompanion")],
            links=links,
            entries=entries,
            total_results=total,
            items_per_page=size,
            start_index=(page - 1) * size + 1
        )
        
        xml_content = generate_opds_xml(feed)
        
        logger.info(f"OPDS最新书籍目录: {len(books)}本书 (用户: {user.username if user else '匿名'})")
        
        return Response(
            content=xml_content,
            media_type="application/atom+xml;profile=opds-catalog;kind=acquisition",
            headers={"charset": "utf-8"}
        )
        
    except Exception as e:
        logger.error(f"OPDS最新书籍目录错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="无法获取最新书籍"
        )


@router.get("/catalog/popular", summary="热门书籍")
@cache_opds(ttl=settings.CACHE_TTL_OPDS)
async def opds_popular_books(
    request: Request,
    user: OptionalCurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=20, ge=1, le=100, description="每页大小")
) -> Response:
    """
    热门书籍目录（按下载次数排序）
    """
    try:
        base_url = get_base_url(request)
        opds_base = f"{base_url}/api/v1/opds"
        
        # 查询热门书籍
        query = select(Book).where(Book.is_available == True).order_by(Book.download_count.desc())
        
        # 计算总数
        count_result = await db.execute(select(func.count(Book.id)).where(Book.is_available == True))
        total = count_result.scalar_one()
        
        # 应用分页
        query = query.offset((page - 1) * size).limit(size)
        result = await db.execute(query)
        books = result.scalars().all()
        
        # 生成OPDS条目
        entries = []
        for book in books:
            entries.append(book_to_opds_entry(book, request))
        
        # 分页链接
        links = [
            OPDSLink(
                rel="self",
                href=f"{opds_base}/catalog/popular?page={page}&size={size}",
                type="application/atom+xml;profile=opds-catalog;kind=acquisition"
            ),
            OPDSLink(
                rel="start",
                href=f"{opds_base}/",
                type="application/atom+xml;profile=opds-catalog;kind=navigation"
            ),
            OPDSLink(
                rel="up",
                href=f"{opds_base}/",
                type="application/atom+xml;profile=opds-catalog;kind=navigation"
            )
        ]
        
        # 添加分页导航链接
        if page > 1:
            links.append(
                OPDSLink(
                    rel="prev",
                    href=f"{opds_base}/catalog/popular?page={page-1}&size={size}",
                    type="application/atom+xml;profile=opds-catalog;kind=acquisition"
                )
            )
        
        total_pages = (total + size - 1) // size
        if page < total_pages:
            links.append(
                OPDSLink(
                    rel="next",
                    href=f"{opds_base}/catalog/popular?page={page+1}&size={size}",
                    type="application/atom+xml;profile=opds-catalog;kind=acquisition"
                )
            )
        
        # 创建Feed
        feed = OPDSFeed(
            id=f"{opds_base}/catalog/popular",
            title="热门书籍",
            subtitle=f"下载次数最多的书籍 (第{page}页，共{total_pages}页)",
            updated=datetime.utcnow(),
            authors=[OPDSAuthor(name="Kompanion")],
            links=links,
            entries=entries,
            total_results=total,
            items_per_page=size,
            start_index=(page - 1) * size + 1
        )
        
        xml_content = generate_opds_xml(feed)
        
        logger.info(f"OPDS热门书籍目录: {len(books)}本书 (用户: {user.username if user else '匿名'})")
        
        return Response(
            content=xml_content,
            media_type="application/atom+xml;profile=opds-catalog;kind=acquisition",
            headers={"charset": "utf-8"}
        )
        
    except Exception as e:
        logger.error(f"OPDS热门书籍目录错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="无法获取热门书籍"
        )


@router.get("/catalog/all", summary="所有书籍")
@cache_opds(ttl=settings.CACHE_TTL_OPDS)
async def opds_all_books(
    request: Request,
    user: OptionalCurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=20, ge=1, le=100, description="每页大小")
) -> Response:
    """
    所有书籍目录
    """
    try:
        base_url = get_base_url(request)
        opds_base = f"{base_url}/api/v1/opds"
        
        # 查询所有书籍
        query = select(Book).where(Book.is_available == True).order_by(Book.title)
        
        # 计算总数
        count_result = await db.execute(select(func.count(Book.id)).where(Book.is_available == True))
        total = count_result.scalar_one()
        
        # 应用分页
        query = query.offset((page - 1) * size).limit(size)
        result = await db.execute(query)
        books = result.scalars().all()
        
        # 生成OPDS条目
        entries = []
        for book in books:
            entries.append(book_to_opds_entry(book, request))
        
        # 分页链接
        links = [
            OPDSLink(
                rel="self",
                href=f"{opds_base}/catalog/all?page={page}&size={size}",
                type="application/atom+xml;profile=opds-catalog;kind=acquisition"
            ),
            OPDSLink(
                rel="start",
                href=f"{opds_base}/",
                type="application/atom+xml;profile=opds-catalog;kind=navigation"
            ),
            OPDSLink(
                rel="up",
                href=f"{opds_base}/",
                type="application/atom+xml;profile=opds-catalog;kind=navigation"
            )
        ]
        
        # 添加分页导航链接
        if page > 1:
            links.append(
                OPDSLink(
                    rel="prev",
                    href=f"{opds_base}/catalog/all?page={page-1}&size={size}",
                    type="application/atom+xml;profile=opds-catalog;kind=acquisition"
                )
            )
        
        total_pages = (total + size - 1) // size
        if page < total_pages:
            links.append(
                OPDSLink(
                    rel="next",
                    href=f"{opds_base}/catalog/all?page={page+1}&size={size}",
                    type="application/atom+xml;profile=opds-catalog;kind=acquisition"
                )
            )
        
        # 创建Feed
        feed = OPDSFeed(
            id=f"{opds_base}/catalog/all",
            title="所有书籍",
            subtitle=f"按标题排序的所有书籍 (第{page}页，共{total_pages}页)",
            updated=datetime.utcnow(),
            authors=[OPDSAuthor(name="Kompanion")],
            links=links,
            entries=entries,
            total_results=total,
            items_per_page=size,
            start_index=(page - 1) * size + 1
        )
        
        xml_content = generate_opds_xml(feed)
        
        logger.info(f"OPDS所有书籍目录: {len(books)}本书 (用户: {user.username if user else '匿名'})")
        
        return Response(
            content=xml_content,
            media_type="application/atom+xml;profile=opds-catalog;kind=acquisition",
            headers={"charset": "utf-8"}
        )
        
    except Exception as e:
        logger.error(f"OPDS所有书籍目录错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="无法获取书籍列表"
        )


@router.get("/search", summary="搜索书籍")
async def opds_search_books(
    request: Request,
    user: OptionalCurrentUser,
    db: DbSession,
    q: str = Query(..., description="搜索关键词"),
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=20, ge=1, le=100, description="每页大小")
) -> Response:
    """
    搜索书籍
    
    支持按标题、作者、描述等字段搜索。
    """
    try:
        base_url = get_base_url(request)
        opds_base = f"{base_url}/api/v1/opds"
        
        # 构建搜索查询
        search_term = f"%{q}%"
        query = select(Book).where(
            and_(
                Book.is_available == True,
                or_(
                    Book.title.ilike(search_term),
                    Book.author.ilike(search_term),
                    Book.description.ilike(search_term),
                    Book.publisher.ilike(search_term),
                    Book.genre.ilike(search_term),
                    Book.series.ilike(search_term)
                )
            )
        ).order_by(Book.title)
        
        # 计算总数
        count_query = select(func.count(Book.id)).where(
            and_(
                Book.is_available == True,
                or_(
                    Book.title.ilike(search_term),
                    Book.author.ilike(search_term),
                    Book.description.ilike(search_term),
                    Book.publisher.ilike(search_term),
                    Book.genre.ilike(search_term),
                    Book.series.ilike(search_term)
                )
            )
        )
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()
        
        # 应用分页
        query = query.offset((page - 1) * size).limit(size)
        result = await db.execute(query)
        books = result.scalars().all()
        
        # 生成OPDS条目
        entries = []
        for book in books:
            entries.append(book_to_opds_entry(book, request))
        
        # 分页链接
        search_url_base = f"{opds_base}/search?q={quote(q)}"
        links = [
            OPDSLink(
                rel="self",
                href=f"{search_url_base}&page={page}&size={size}",
                type="application/atom+xml;profile=opds-catalog;kind=acquisition"
            ),
            OPDSLink(
                rel="start",
                href=f"{opds_base}/",
                type="application/atom+xml;profile=opds-catalog;kind=navigation"
            ),
            OPDSLink(
                rel="up",
                href=f"{opds_base}/",
                type="application/atom+xml;profile=opds-catalog;kind=navigation"
            )
        ]
        
        # 添加分页导航链接
        if page > 1:
            links.append(
                OPDSLink(
                    rel="prev",
                    href=f"{search_url_base}&page={page-1}&size={size}",
                    type="application/atom+xml;profile=opds-catalog;kind=acquisition"
                )
            )
        
        total_pages = (total + size - 1) // size if total > 0 else 1
        if page < total_pages:
            links.append(
                OPDSLink(
                    rel="next",
                    href=f"{search_url_base}&page={page+1}&size={size}",
                    type="application/atom+xml;profile=opds-catalog;kind=acquisition"
                )
            )
        
        # 创建Feed
        feed = OPDSFeed(
            id=f"{opds_base}/search?q={quote(q)}",
            title=f"搜索结果: \"{q}\"",
            subtitle=f"找到 {total} 本相关书籍 (第{page}页，共{total_pages}页)",
            updated=datetime.utcnow(),
            authors=[OPDSAuthor(name="Kompanion")],
            links=links,
            entries=entries,
            total_results=total,
            items_per_page=size,
            start_index=(page - 1) * size + 1
        )
        
        xml_content = generate_opds_xml(feed)
        
        logger.info(f"OPDS搜索: \"{q}\" - {len(books)}本书 (用户: {user.username if user else '匿名'})")
        
        return Response(
            content=xml_content,
            media_type="application/atom+xml;profile=opds-catalog;kind=acquisition",
            headers={"charset": "utf-8"}
        )
        
    except Exception as e:
        logger.error(f"OPDS搜索错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="搜索服务暂时不可用"
        )

# 在书籍相关操作后，清除相关缓存
async def invalidate_opds_cache():
    """清除OPDS相关缓存"""
    await invalidate_cache_pattern("opds:*") 