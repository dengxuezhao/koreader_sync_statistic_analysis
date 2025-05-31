"""
pytest配置文件

定义通用的测试fixtures和配置。
"""

import asyncio
import os
import tempfile
from typing import AsyncGenerator, Dict, Any
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import settings
from app.core.database import get_db, Base
from app.core.security import create_access_token
from app.models import User, Device, Book
from app.api.deps import get_current_user, get_current_admin_user


# 测试数据库配置
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def event_loop():
    """创建测试事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """创建测试数据库会话"""
    # 创建测试引擎
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建会话
    TestSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with TestSessionLocal() as session:
        yield session
    
    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """创建测试HTTP客户端"""
    
    def override_get_db():
        return test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(test_db: AsyncSession) -> User:
    """创建测试用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="5d41402abc4b2a76b9719d911017c592",  # MD5 of "hello"
        is_active=True,
        is_admin=False
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin_user(test_db: AsyncSession) -> User:
    """创建测试管理员用户"""
    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password="5d41402abc4b2a76b9719d911017c592",  # MD5 of "hello"
        is_active=True,
        is_admin=True
    )
    test_db.add(admin)
    await test_db.commit()
    await test_db.refresh(admin)
    return admin


@pytest_asyncio.fixture
async def test_device(test_db: AsyncSession, test_user: User) -> Device:
    """创建测试设备"""
    device = Device(
        device_id="test-device-123",
        device_name="Test KOReader",
        device_type="koreader",
        user_id=test_user.id
    )
    test_db.add(device)
    await test_db.commit()
    await test_db.refresh(device)
    return device


@pytest_asyncio.fixture
async def test_book(test_db: AsyncSession) -> Book:
    """创建测试书籍"""
    book = Book(
        title="Test Book",
        author="Test Author",
        isbn="1234567890123",
        publisher="Test Publisher",
        language="en",
        file_path="/test/path/book.epub",
        file_name="book.epub",
        file_size=1024000,
        file_hash="testhash123",
        file_format="epub",
        is_available=True,
        download_count=0
    )
    test_db.add(book)
    await test_db.commit()
    await test_db.refresh(book)
    return book


@pytest.fixture
def auth_headers(test_user: User) -> Dict[str, str]:
    """创建认证头"""
    token = create_access_token(data={"sub": test_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(test_admin_user: User) -> Dict[str, str]:
    """创建管理员认证头"""
    token = create_access_token(data={"sub": test_admin_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_current_user(test_user: User):
    """模拟当前用户依赖"""
    def override_get_current_user():
        return test_user
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield test_user
    app.dependency_overrides.clear()


@pytest.fixture
def mock_current_admin_user(test_admin_user: User):
    """模拟当前管理员用户依赖"""
    def override_get_current_admin_user():
        return test_admin_user
    
    app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user
    yield test_admin_user
    app.dependency_overrides.clear()


@pytest.fixture
def temp_storage_dir():
    """创建临时存储目录"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # 设置临时存储路径
        original_book_path = settings.BOOK_STORAGE_PATH
        original_cover_path = settings.COVER_STORAGE_PATH
        original_webdav_path = settings.WEBDAV_ROOT_PATH
        
        settings.BOOK_STORAGE_PATH = os.path.join(temp_dir, "books")
        settings.COVER_STORAGE_PATH = os.path.join(temp_dir, "covers")
        settings.WEBDAV_ROOT_PATH = os.path.join(temp_dir, "webdav")
        
        # 创建目录
        os.makedirs(settings.BOOK_STORAGE_PATH, exist_ok=True)
        os.makedirs(settings.COVER_STORAGE_PATH, exist_ok=True)
        os.makedirs(settings.WEBDAV_ROOT_PATH, exist_ok=True)
        
        yield temp_dir
        
        # 恢复原始设置
        settings.BOOK_STORAGE_PATH = original_book_path
        settings.COVER_STORAGE_PATH = original_cover_path
        settings.WEBDAV_ROOT_PATH = original_webdav_path


@pytest.fixture
def sample_epub_content() -> bytes:
    """生成简单的EPUB文件内容"""
    import zipfile
    import io
    
    # 创建简单的EPUB文件
    epub_buffer = io.BytesIO()
    with zipfile.ZipFile(epub_buffer, 'w', zipfile.ZIP_DEFLATED) as epub:
        # mimetype文件
        epub.writestr('mimetype', 'application/epub+zip')
        
        # META-INF/container.xml
        container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>'''
        epub.writestr('META-INF/container.xml', container_xml)
        
        # OEBPS/content.opf
        content_opf = '''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">test-book-123</dc:identifier>
    <dc:title>Test Book</dc:title>
    <dc:creator>Test Author</dc:creator>
    <dc:language>en</dc:language>
    <dc:publisher>Test Publisher</dc:publisher>
  </metadata>
  <manifest>
    <item id="chapter1" href="chapter1.html" media-type="application/xhtml+xml"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="chapter1"/>
  </spine>
</package>'''
        epub.writestr('OEBPS/content.opf', content_opf)
        
        # OEBPS/chapter1.html
        chapter1 = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>Chapter 1</title>
</head>
<body>
  <h1>Chapter 1</h1>
  <p>This is a test chapter.</p>
</body>
</html>'''
        epub.writestr('OEBPS/chapter1.html', chapter1)
        
        # OEBPS/toc.ncx
        toc_ncx = '''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="test-book-123"/>
  </head>
  <docTitle>
    <text>Test Book</text>
  </docTitle>
  <navMap>
    <navPoint id="chapter1">
      <navLabel>
        <text>Chapter 1</text>
      </navLabel>
      <content src="chapter1.html"/>
    </navPoint>
  </navMap>
</ncx>'''
        epub.writestr('OEBPS/toc.ncx', toc_ncx)
    
    epub_buffer.seek(0)
    return epub_buffer.read()


@pytest.fixture
def koreader_stats_data() -> Dict[str, Any]:
    """KOReader统计数据示例"""
    return {
        "title": "Test Book",
        "authors": "Test Author",
        "language": "en",
        "series": "",
        "performance_in_pages": {
            "current_page": 15,
            "total_pages": 100,
            "percentage": 15.0
        },
        "total_time_in_sec": 3600,
        "highlights": 5,
        "notes": 2,
        "pages": 100,
        "md5": "testhash123"
    } 