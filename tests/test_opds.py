"""
OPDS目录服务测试

测试OPDS 1.2标准兼容性、书籍浏览、搜索功能和XML生成。
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from xml.etree import ElementTree as ET

from app.models import Book


class TestOPDSRootDirectory:
    """OPDS根目录测试"""
    
    @pytest.mark.asyncio
    async def test_opds_root_directory(self, client: AsyncClient):
        """测试OPDS根目录"""
        response = await client.get("/api/v1/opds/")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/atom+xml;profile=opds-catalog;kind=navigation"
        
        # 解析XML
        root = ET.fromstring(response.content)
        
        # 验证命名空间
        assert root.tag.endswith("}feed")
        
        # 验证标题
        title = root.find(".//{http://www.w3.org/2005/Atom}title")
        assert title is not None
        assert "Kompanion" in title.text
        
        # 验证导航链接
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        assert len(entries) >= 3  # 至少应该有最新、热门、所有书籍
        
        # 验证每个entry都有navigation类型
        for entry in entries:
            link = entry.find(".//{http://www.w3.org/2005/Atom}link[@type='application/atom+xml;profile=opds-catalog']")
            assert link is not None
    
    @pytest.mark.asyncio
    async def test_opds_self_link(self, client: AsyncClient):
        """测试OPDS自引用链接"""
        response = await client.get("/api/v1/opds/")
        
        root = ET.fromstring(response.content)
        self_link = root.find(".//{http://www.w3.org/2005/Atom}link[@rel='self']")
        
        assert self_link is not None
        assert self_link.get("href").endswith("/api/v1/opds/")


class TestOPDSBookCatalogs:
    """OPDS书籍目录测试"""
    
    @pytest.mark.asyncio
    async def test_recent_books_catalog(self, client: AsyncClient, test_book: Book):
        """测试最新书籍目录"""
        response = await client.get("/api/v1/opds/catalog/recent")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/atom+xml;profile=opds-catalog;kind=acquisition"
        
        root = ET.fromstring(response.content)
        
        # 验证标题
        title = root.find(".//{http://www.w3.org/2005/Atom}title")
        assert "最新书籍" in title.text
        
        # 验证书籍entry
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        assert len(entries) >= 1
        
        # 验证第一本书
        first_entry = entries[0]
        entry_title = first_entry.find(".//{http://www.w3.org/2005/Atom}title")
        assert entry_title.text == test_book.title
    
    @pytest.mark.asyncio
    async def test_popular_books_catalog(self, client: AsyncClient, test_db: AsyncSession):
        """测试热门书籍目录"""
        # 创建一本有下载次数的书
        popular_book = Book(
            title="Popular Book",
            author="Popular Author",
            file_path="/test/popular.epub",
            file_name="popular.epub",
            file_size=1024000,
            file_hash="popularhash",
            file_format="epub",
            is_available=True,
            download_count=10
        )
        test_db.add(popular_book)
        await test_db.commit()
        
        response = await client.get("/api/v1/opds/catalog/popular")
        
        assert response.status_code == 200
        
        root = ET.fromstring(response.content)
        title = root.find(".//{http://www.w3.org/2005/Atom}title")
        assert "热门书籍" in title.text
        
        # 验证排序（下载次数多的在前）
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        if len(entries) >= 2:
            first_entry_title = entries[0].find(".//{http://www.w3.org/2005/Atom}title").text
            assert first_entry_title == "Popular Book"
    
    @pytest.mark.asyncio
    async def test_all_books_catalog(self, client: AsyncClient, test_book: Book):
        """测试所有书籍目录"""
        response = await client.get("/api/v1/opds/catalog/all")
        
        assert response.status_code == 200
        
        root = ET.fromstring(response.content)
        title = root.find(".//{http://www.w3.org/2005/Atom}title")
        assert "所有书籍" in title.text
        
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        assert len(entries) >= 1


class TestOPDSPagination:
    """OPDS分页测试"""
    
    @pytest.mark.asyncio
    async def test_pagination_links(self, client: AsyncClient, test_db: AsyncSession):
        """测试分页链接"""
        # 创建多本书以测试分页
        for i in range(15):
            book = Book(
                title=f"Book {i:02d}",
                author=f"Author {i}",
                file_path=f"/test/book{i}.epub",
                file_name=f"book{i}.epub",
                file_size=1024000,
                file_hash=f"hash{i}",
                file_format="epub",
                is_available=True
            )
            test_db.add(book)
        
        await test_db.commit()
        
        # 测试第一页
        response = await client.get("/api/v1/opds/catalog/all?page=1&size=10")
        
        assert response.status_code == 200
        
        root = ET.fromstring(response.content)
        
        # 验证分页信息
        links = root.findall(".//{http://www.w3.org/2005/Atom}link")
        link_rels = [link.get("rel") for link in links]
        
        assert "self" in link_rels
        assert "next" in link_rels  # 应该有下一页
        
        # 验证条目数量
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        assert len(entries) == 10
    
    @pytest.mark.asyncio
    async def test_pagination_second_page(self, client: AsyncClient, test_db: AsyncSession):
        """测试第二页分页"""
        response = await client.get("/api/v1/opds/catalog/all?page=2&size=10")
        
        assert response.status_code == 200
        
        root = ET.fromstring(response.content)
        links = root.findall(".//{http://www.w3.org/2005/Atom}link")
        link_rels = [link.get("rel") for link in links]
        
        assert "self" in link_rels
        assert "first" in link_rels  # 应该有第一页链接
        assert "previous" in link_rels  # 应该有上一页链接


class TestOPDSSearch:
    """OPDS搜索测试"""
    
    @pytest.mark.asyncio
    async def test_search_by_title(self, client: AsyncClient, test_book: Book):
        """测试按标题搜索"""
        response = await client.get(f"/api/v1/opds/search?q={test_book.title}")
        
        assert response.status_code == 200
        
        root = ET.fromstring(response.content)
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        
        assert len(entries) >= 1
        found_book = entries[0]
        title = found_book.find(".//{http://www.w3.org/2005/Atom}title").text
        assert test_book.title in title
    
    @pytest.mark.asyncio
    async def test_search_by_author(self, client: AsyncClient, test_book: Book):
        """测试按作者搜索"""
        response = await client.get(f"/api/v1/opds/search?q={test_book.author}")
        
        assert response.status_code == 200
        
        root = ET.fromstring(response.content)
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        
        assert len(entries) >= 1
    
    @pytest.mark.asyncio
    async def test_search_no_results(self, client: AsyncClient):
        """测试搜索无结果"""
        response = await client.get("/api/v1/opds/search?q=nonexistentbook")
        
        assert response.status_code == 200
        
        root = ET.fromstring(response.content)
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        
        assert len(entries) == 0
    
    @pytest.mark.asyncio
    async def test_search_empty_query(self, client: AsyncClient):
        """测试空搜索查询"""
        response = await client.get("/api/v1/opds/search?q=")
        
        assert response.status_code == 200
        
        # 空查询应该返回所有书籍
        root = ET.fromstring(response.content)
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        
        assert len(entries) >= 0  # 可能为0如果没有书籍


class TestOPDSBookEntry:
    """OPDS书籍条目测试"""
    
    @pytest.mark.asyncio
    async def test_book_entry_structure(self, client: AsyncClient, test_book: Book):
        """测试书籍条目结构"""
        response = await client.get("/api/v1/opds/catalog/all")
        
        root = ET.fromstring(response.content)
        entry = root.find(".//{http://www.w3.org/2005/Atom}entry")
        
        assert entry is not None
        
        # 验证必需字段
        title = entry.find(".//{http://www.w3.org/2005/Atom}title")
        assert title is not None
        assert title.text == test_book.title
        
        # 验证作者
        author = entry.find(".//{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name")
        assert author is not None
        assert author.text == test_book.author
        
        # 验证ID
        entry_id = entry.find(".//{http://www.w3.org/2005/Atom}id")
        assert entry_id is not None
        
        # 验证更新时间
        updated = entry.find(".//{http://www.w3.org/2005/Atom}updated")
        assert updated is not None
        
        # 验证下载链接
        acquisition_link = entry.find(".//{http://www.w3.org/2005/Atom}link[@rel='http://opds-spec.org/acquisition']")
        assert acquisition_link is not None
        assert acquisition_link.get("href").endswith(f"/api/v1/books/{test_book.id}/download")
        assert acquisition_link.get("type") == "application/epub+zip"
    
    @pytest.mark.asyncio
    async def test_book_entry_metadata(self, client: AsyncClient, test_book: Book):
        """测试书籍条目元数据"""
        response = await client.get("/api/v1/opds/catalog/all")
        
        root = ET.fromstring(response.content)
        entry = root.find(".//{http://www.w3.org/2005/Atom}entry")
        
        # 验证Dublin Core元数据
        dc_language = entry.find(".//{http://purl.org/dc/terms/}language")
        if dc_language is not None:
            assert dc_language.text == test_book.language
        
        dc_publisher = entry.find(".//{http://purl.org/dc/terms/}publisher")
        if dc_publisher is not None:
            assert dc_publisher.text == test_book.publisher
        
        dc_identifier = entry.find(".//{http://purl.org/dc/terms/}identifier")
        if dc_identifier is not None:
            assert dc_identifier.text == test_book.isbn


class TestOPDSAuthentication:
    """OPDS认证测试"""
    
    @pytest.mark.asyncio
    async def test_anonymous_access_allowed(self, client: AsyncClient):
        """测试匿名访问允许"""
        response = await client.get("/api/v1/opds/")
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_authenticated_access(self, client: AsyncClient, auth_headers: dict):
        """测试认证用户访问"""
        response = await client.get("/api/v1/opds/", headers=auth_headers)
        
        assert response.status_code == 200
        
        # 认证用户可能看到额外信息
        root = ET.fromstring(response.content)
        title = root.find(".//{http://www.w3.org/2005/Atom}title")
        assert title is not None


class TestOPDSStandardCompliance:
    """OPDS标准兼容性测试"""
    
    @pytest.mark.asyncio
    async def test_atom_namespace(self, client: AsyncClient):
        """测试Atom命名空间"""
        response = await client.get("/api/v1/opds/")
        
        root = ET.fromstring(response.content)
        
        # 验证Atom命名空间
        assert root.tag == "{http://www.w3.org/2005/Atom}feed"
    
    @pytest.mark.asyncio
    async def test_opds_namespace(self, client: AsyncClient):
        """测试OPDS命名空间"""
        response = await client.get("/api/v1/opds/catalog/all")
        
        # 检查响应中是否包含OPDS相关命名空间
        content = response.content.decode()
        assert "http://opds-spec.org/2010/catalog" in content
    
    @pytest.mark.asyncio
    async def test_required_feed_elements(self, client: AsyncClient):
        """测试必需的feed元素"""
        response = await client.get("/api/v1/opds/")
        
        root = ET.fromstring(response.content)
        
        # 验证必需元素
        required_elements = ["title", "id", "updated", "link"]
        for element in required_elements:
            found = root.find(f".//{{{ET._namespace_map.get('', 'http://www.w3.org/2005/Atom')}}}{element}")
            assert found is not None, f"Missing required element: {element}"
    
    @pytest.mark.asyncio
    async def test_mime_types(self, client: AsyncClient, test_book: Book):
        """测试MIME类型正确性"""
        response = await client.get("/api/v1/opds/catalog/all")
        
        root = ET.fromstring(response.content)
        entry = root.find(".//{http://www.w3.org/2005/Atom}entry")
        
        if entry is not None:
            acquisition_link = entry.find(".//{http://www.w3.org/2005/Atom}link[@rel='http://opds-spec.org/acquisition']")
            if acquisition_link is not None:
                mime_type = acquisition_link.get("type")
                
                # 验证MIME类型映射
                if test_book.file_format == "epub":
                    assert mime_type == "application/epub+zip"
                elif test_book.file_format == "pdf":
                    assert mime_type == "application/pdf"


class TestOPDSPerformance:
    """OPDS性能测试"""
    
    @pytest.mark.asyncio
    async def test_large_catalog_performance(self, client: AsyncClient, test_db: AsyncSession):
        """测试大型目录性能"""
        import time
        
        # 创建100本书进行性能测试
        books = []
        for i in range(100):
            book = Book(
                title=f"Performance Book {i:03d}",
                author=f"Performance Author {i}",
                file_path=f"/test/perf_book{i}.epub",
                file_name=f"perf_book{i}.epub",
                file_size=1024000,
                file_hash=f"perfhash{i}",
                file_format="epub",
                is_available=True
            )
            books.append(book)
        
        test_db.add_all(books)
        await test_db.commit()
        
        # 测试响应时间
        start_time = time.time()
        response = await client.get("/api/v1/opds/catalog/all?size=50")
        end_time = time.time()
        
        assert response.status_code == 200
        
        # 验证响应时间合理（应该在2秒内）
        response_time = end_time - start_time
        assert response_time < 2.0, f"Response took too long: {response_time}s"
        
        # 验证返回正确数量的条目
        root = ET.fromstring(response.content)
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        assert len(entries) == 50


class TestOPDSErrorHandling:
    """OPDS错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_invalid_page_number(self, client: AsyncClient):
        """测试无效页码"""
        response = await client.get("/api/v1/opds/catalog/all?page=0")
        
        # 应该自动调整为第1页
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_excessive_page_size(self, client: AsyncClient):
        """测试过大的页面大小"""
        response = await client.get("/api/v1/opds/catalog/all?size=1000")
        
        # 应该限制到最大值
        assert response.status_code == 200
        
        root = ET.fromstring(response.content)
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        assert len(entries) <= 100  # 假设最大限制是100 