"""
书籍管理功能测试

测试文件上传、元数据提取、封面处理、搜索和下载功能。
"""

import io
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Book


class TestBookUpload:
    """书籍上传测试"""
    
    @pytest.mark.asyncio
    async def test_upload_epub_book(self, client: AsyncClient, admin_auth_headers: dict, sample_epub_content: bytes, temp_storage_dir):
        """测试上传EPUB书籍"""
        files = {
            "file": ("test_book.epub", io.BytesIO(sample_epub_content), "application/epub+zip")
        }
        
        response = await client.post("/api/v1/books/upload", files=files, headers=admin_auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["title"] == "Test Book"
        assert data["author"] == "Test Author"
        assert data["file_format"] == "epub"
        assert data["file_size"] > 0
        assert data["is_available"] is True
        assert "file_hash" in data
    
    @pytest.mark.asyncio
    async def test_upload_duplicate_book(self, client: AsyncClient, admin_auth_headers: dict, sample_epub_content: bytes, temp_storage_dir):
        """测试上传重复书籍"""
        files = {
            "file": ("duplicate.epub", io.BytesIO(sample_epub_content), "application/epub+zip")
        }
        
        # 第一次上传
        response1 = await client.post("/api/v1/books/upload", files=files, headers=admin_auth_headers)
        assert response1.status_code == 201
        
        # 第二次上传相同文件
        files = {
            "file": ("duplicate2.epub", io.BytesIO(sample_epub_content), "application/epub+zip")
        }
        response2 = await client.post("/api/v1/books/upload", files=files, headers=admin_auth_headers)
        
        # 应该检测到重复并返回现有书籍信息
        assert response2.status_code == 200
        assert "已存在" in response2.json()["message"]
    
    @pytest.mark.asyncio
    async def test_upload_invalid_file_format(self, client: AsyncClient, admin_auth_headers: dict):
        """测试上传无效文件格式"""
        files = {
            "file": ("invalid.txt", io.BytesIO(b"Invalid content"), "text/plain")
        }
        
        response = await client.post("/api/v1/books/upload", files=files, headers=admin_auth_headers)
        
        assert response.status_code == 400
        assert "不支持的文件格式" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_upload_oversized_file(self, client: AsyncClient, admin_auth_headers: dict):
        """测试上传超大文件"""
        # 创建超过限制的文件（假设限制是500MB）
        large_content = b"x" * (600 * 1024 * 1024)  # 600MB
        
        files = {
            "file": ("large.epub", io.BytesIO(large_content), "application/epub+zip")
        }
        
        response = await client.post("/api/v1/books/upload", files=files, headers=admin_auth_headers)
        
        assert response.status_code == 400
        assert "文件过大" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_upload_unauthorized(self, client: AsyncClient, auth_headers: dict, sample_epub_content: bytes):
        """测试非管理员上传"""
        files = {
            "file": ("unauthorized.epub", io.BytesIO(sample_epub_content), "application/epub+zip")
        }
        
        response = await client.post("/api/v1/books/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 403


class TestBookDownload:
    """书籍下载测试"""
    
    @pytest.mark.asyncio
    async def test_download_book_authenticated(self, client: AsyncClient, auth_headers: dict, test_book: Book, temp_storage_dir):
        """测试认证用户下载书籍"""
        response = await client.get(f"/api/v1/books/{test_book.id}/download", headers=auth_headers)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/epub+zip"
        assert "attachment" in response.headers["content-disposition"]
        assert test_book.file_name in response.headers["content-disposition"]
    
    @pytest.mark.asyncio
    async def test_download_book_anonymous(self, client: AsyncClient, test_book: Book, temp_storage_dir):
        """测试匿名用户下载书籍"""
        response = await client.get(f"/api/v1/books/{test_book.id}/download")
        
        # 匿名下载应该被允许（根据OPDS兼容性）
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_download_nonexistent_book(self, client: AsyncClient, auth_headers: dict):
        """测试下载不存在的书籍"""
        response = await client.get("/api/v1/books/99999/download", headers=auth_headers)
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_download_unavailable_book(self, client: AsyncClient, auth_headers: dict, test_db: AsyncSession, temp_storage_dir):
        """测试下载不可用的书籍"""
        # 创建一本不可用的书
        unavailable_book = Book(
            title="Unavailable Book",
            author="Test Author",
            file_path="/test/unavailable.epub",
            file_name="unavailable.epub",
            file_size=1024000,
            file_hash="unavailablehash",
            file_format="epub",
            is_available=False
        )
        test_db.add(unavailable_book)
        await test_db.commit()
        await test_db.refresh(unavailable_book)
        
        response = await client.get(f"/api/v1/books/{unavailable_book.id}/download", headers=auth_headers)
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_download_count_increment(self, client: AsyncClient, test_book: Book, test_db: AsyncSession, temp_storage_dir):
        """测试下载次数增加"""
        initial_count = test_book.download_count
        
        response = await client.get(f"/api/v1/books/{test_book.id}/download")
        
        assert response.status_code == 200
        
        # 刷新数据库中的对象
        await test_db.refresh(test_book)
        
        assert test_book.download_count == initial_count + 1


class TestBookCover:
    """书籍封面测试"""
    
    @pytest.mark.asyncio
    async def test_get_book_cover(self, client: AsyncClient, test_book: Book, temp_storage_dir):
        """测试获取书籍封面"""
        # 假设书籍有封面文件
        response = await client.get(f"/api/v1/books/{test_book.id}/cover")
        
        # 如果没有封面文件，应该返回默认封面或404
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            # 验证是图片内容
            content_type = response.headers.get("content-type", "")
            assert content_type.startswith("image/")
    
    @pytest.mark.asyncio
    async def test_get_book_cover_thumbnail(self, client: AsyncClient, test_book: Book, temp_storage_dir):
        """测试获取书籍封面缩略图"""
        response = await client.get(f"/api/v1/books/{test_book.id}/cover?thumbnail=true")
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            assert content_type.startswith("image/")
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_cover(self, client: AsyncClient):
        """测试获取不存在书籍的封面"""
        response = await client.get("/api/v1/books/99999/cover")
        
        assert response.status_code == 404


class TestBookListing:
    """书籍列表测试"""
    
    @pytest.mark.asyncio
    async def test_get_books_list(self, client: AsyncClient, test_book: Book):
        """测试获取书籍列表"""
        response = await client.get("/api/v1/books/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "items" in data
        assert "pagination" in data
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        
        # 验证书籍信息
        book_item = data["items"][0]
        assert "id" in book_item
        assert "title" in book_item
        assert "author" in book_item
        assert "file_format" in book_item
    
    @pytest.mark.asyncio
    async def test_search_books_by_title(self, client: AsyncClient, test_book: Book):
        """测试按标题搜索书籍"""
        response = await client.get(f"/api/v1/books/?search={test_book.title}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] >= 1
        found_book = next((book for book in data["items"] if book["id"] == test_book.id), None)
        assert found_book is not None
    
    @pytest.mark.asyncio
    async def test_search_books_by_author(self, client: AsyncClient, test_book: Book):
        """测试按作者搜索书籍"""
        response = await client.get(f"/api/v1/books/?search={test_book.author}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] >= 1
    
    @pytest.mark.asyncio
    async def test_filter_books_by_format(self, client: AsyncClient, test_db: AsyncSession):
        """测试按格式过滤书籍"""
        # 创建不同格式的书籍
        pdf_book = Book(
            title="PDF Book",
            author="PDF Author",
            file_path="/test/pdf_book.pdf",
            file_name="pdf_book.pdf",
            file_size=2048000,
            file_hash="pdfhash123",
            file_format="pdf",
            is_available=True
        )
        test_db.add(pdf_book)
        await test_db.commit()
        
        response = await client.get("/api/v1/books/?format=pdf")
        
        assert response.status_code == 200
        data = response.json()
        
        # 所有返回的书籍都应该是PDF格式
        for book in data["items"]:
            assert book["file_format"] == "pdf"
    
    @pytest.mark.asyncio
    async def test_sort_books_by_title(self, client: AsyncClient, test_db: AsyncSession):
        """测试按标题排序书籍"""
        # 创建多本书用于排序测试
        books = []
        for i, title in enumerate(["Z Book", "A Book", "M Book"]):
            book = Book(
                title=title,
                author=f"Author {i}",
                file_path=f"/test/sort{i}.epub",
                file_name=f"sort{i}.epub",
                file_size=1024000,
                file_hash=f"sorthash{i}",
                file_format="epub",
                is_available=True
            )
            books.append(book)
        
        test_db.add_all(books)
        await test_db.commit()
        
        response = await client.get("/api/v1/books/?sort=title&order=asc")
        
        assert response.status_code == 200
        data = response.json()
        
        # 验证排序
        titles = [book["title"] for book in data["items"]]
        assert titles == sorted(titles)
    
    @pytest.mark.asyncio
    async def test_books_pagination(self, client: AsyncClient, test_db: AsyncSession):
        """测试书籍分页"""
        # 创建足够多的书籍用于分页测试
        books = []
        for i in range(15):
            book = Book(
                title=f"Pagination Book {i:02d}",
                author=f"Author {i}",
                file_path=f"/test/page{i}.epub",
                file_name=f"page{i}.epub",
                file_size=1024000,
                file_hash=f"pagehash{i}",
                file_format="epub",
                is_available=True
            )
            books.append(book)
        
        test_db.add_all(books)
        await test_db.commit()
        
        # 测试第一页
        response = await client.get("/api/v1/books/?page=1&size=10")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 10
        assert data["pagination"]["current_page"] == 1
        assert data["pagination"]["total_pages"] >= 2


class TestBookCRUD:
    """书籍CRUD操作测试"""
    
    @pytest.mark.asyncio
    async def test_get_book_detail(self, client: AsyncClient, test_book: Book):
        """测试获取书籍详情"""
        response = await client.get(f"/api/v1/books/{test_book.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == test_book.id
        assert data["title"] == test_book.title
        assert data["author"] == test_book.author
        assert data["file_format"] == test_book.file_format
        assert data["file_size"] == test_book.file_size
        assert "created_at" in data
        assert "updated_at" in data
    
    @pytest.mark.asyncio
    async def test_update_book(self, client: AsyncClient, admin_auth_headers: dict, test_book: Book):
        """测试更新书籍信息"""
        update_data = {
            "title": "Updated Title",
            "author": "Updated Author",
            "description": "Updated description"
        }
        
        response = await client.put(
            f"/api/v1/books/{test_book.id}",
            json=update_data,
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["title"] == "Updated Title"
        assert data["author"] == "Updated Author"
        assert data["description"] == "Updated description"
    
    @pytest.mark.asyncio
    async def test_update_book_unauthorized(self, client: AsyncClient, auth_headers: dict, test_book: Book):
        """测试非管理员更新书籍"""
        update_data = {
            "title": "Unauthorized Update"
        }
        
        response = await client.put(
            f"/api/v1/books/{test_book.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_delete_book(self, client: AsyncClient, admin_auth_headers: dict, test_db: AsyncSession, temp_storage_dir):
        """测试删除书籍"""
        # 创建一本书用于删除
        delete_book = Book(
            title="Delete Me",
            author="Delete Author",
            file_path="/test/delete.epub",
            file_name="delete.epub",
            file_size=1024000,
            file_hash="deletehash",
            file_format="epub",
            is_available=True
        )
        test_db.add(delete_book)
        await test_db.commit()
        await test_db.refresh(delete_book)
        
        response = await client.delete(f"/api/v1/books/{delete_book.id}", headers=admin_auth_headers)
        
        assert response.status_code == 200
        
        # 验证书籍已删除
        result = await test_db.execute(select(Book).where(Book.id == delete_book.id))
        deleted_book = result.scalar_one_or_none()
        assert deleted_book is None
    
    @pytest.mark.asyncio
    async def test_delete_book_unauthorized(self, client: AsyncClient, auth_headers: dict, test_book: Book):
        """测试非管理员删除书籍"""
        response = await client.delete(f"/api/v1/books/{test_book.id}", headers=auth_headers)
        
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_book(self, client: AsyncClient):
        """测试获取不存在的书籍"""
        response = await client.get("/api/v1/books/99999")
        
        assert response.status_code == 404


class TestBookStatistics:
    """书籍统计测试"""
    
    @pytest.mark.asyncio
    async def test_get_book_statistics(self, client: AsyncClient, admin_auth_headers: dict, test_db: AsyncSession):
        """测试获取书籍统计信息"""
        # 创建一些书籍数据
        for i in range(5):
            book = Book(
                title=f"Stats Book {i}",
                author=f"Stats Author {i}",
                file_path=f"/test/stats{i}.epub",
                file_name=f"stats{i}.epub",
                file_size=1024000 * (i + 1),
                file_hash=f"statshash{i}",
                file_format="epub" if i % 2 == 0 else "pdf",
                is_available=True,
                download_count=i * 10
            )
            test_db.add(book)
        
        await test_db.commit()
        
        response = await client.get("/api/v1/books/stats/overview", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_books" in data
        assert "total_size" in data
        assert "format_distribution" in data
        assert "top_downloads" in data
        assert "recent_uploads" in data
        
        assert data["total_books"] >= 5
        assert data["total_size"] > 0
    
    @pytest.mark.asyncio
    async def test_book_statistics_unauthorized(self, client: AsyncClient, auth_headers: dict):
        """测试非管理员访问统计"""
        response = await client.get("/api/v1/books/stats/overview", headers=auth_headers)
        
        assert response.status_code == 403


class TestBookMetadataExtraction:
    """书籍元数据提取测试"""
    
    @pytest.mark.asyncio
    async def test_epub_metadata_extraction(self, client: AsyncClient, admin_auth_headers: dict, sample_epub_content: bytes, temp_storage_dir):
        """测试EPUB元数据提取"""
        files = {
            "file": ("metadata_test.epub", io.BytesIO(sample_epub_content), "application/epub+zip")
        }
        
        response = await client.post("/api/v1/books/upload", files=files, headers=admin_auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        
        # 验证从EPUB中提取的元数据
        assert data["title"] == "Test Book"
        assert data["author"] == "Test Author"
        assert data["language"] == "en"
        assert data["publisher"] == "Test Publisher"
    
    @pytest.mark.asyncio
    async def test_file_hash_calculation(self, client: AsyncClient, admin_auth_headers: dict, sample_epub_content: bytes, temp_storage_dir):
        """测试文件哈希计算"""
        files = {
            "file": ("hash_test.epub", io.BytesIO(sample_epub_content), "application/epub+zip")
        }
        
        response = await client.post("/api/v1/books/upload", files=files, headers=admin_auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        
        # 验证文件哈希已计算
        assert "file_hash" in data
        assert len(data["file_hash"]) == 32  # MD5 hash length
        assert data["file_hash"] != ""


class TestBookValidation:
    """书籍验证测试"""
    
    @pytest.mark.asyncio
    async def test_corrupted_epub_upload(self, client: AsyncClient, admin_auth_headers: dict):
        """测试上传损坏的EPUB文件"""
        corrupted_content = b"This is not a valid EPUB file"
        
        files = {
            "file": ("corrupted.epub", io.BytesIO(corrupted_content), "application/epub+zip")
        }
        
        response = await client.post("/api/v1/books/upload", files=files, headers=admin_auth_headers)
        
        # 应该能够上传但元数据提取可能失败
        assert response.status_code in [201, 400]
    
    @pytest.mark.asyncio
    async def test_empty_file_upload(self, client: AsyncClient, admin_auth_headers: dict):
        """测试上传空文件"""
        files = {
            "file": ("empty.epub", io.BytesIO(b""), "application/epub+zip")
        }
        
        response = await client.post("/api/v1/books/upload", files=files, headers=admin_auth_headers)
        
        assert response.status_code == 400
        assert "文件为空" in response.json()["detail"] 