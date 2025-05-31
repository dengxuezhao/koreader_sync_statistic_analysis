"""
WebDAV服务测试

测试WebDAV协议兼容性、KOReader统计文件处理和文件操作功能。
"""

import json
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from xml.etree import ElementTree as ET

from app.models import ReadingStatistics


class TestWebDAVBasicOperations:
    """WebDAV基本操作测试"""
    
    @pytest.mark.asyncio
    async def test_webdav_options(self, client: AsyncClient, auth_headers: dict):
        """测试WebDAV OPTIONS方法"""
        response = await client.request("OPTIONS", "/api/v1/webdav/", headers=auth_headers)
        
        assert response.status_code == 200
        
        # 验证支持的方法
        allow_header = response.headers.get("Allow", "")
        required_methods = ["GET", "PUT", "DELETE", "PROPFIND", "MKCOL", "OPTIONS"]
        
        for method in required_methods:
            assert method in allow_header
        
        # 验证DAV头
        dav_header = response.headers.get("DAV", "")
        assert "1" in dav_header
    
    @pytest.mark.asyncio
    async def test_webdav_propfind_root(self, client: AsyncClient, auth_headers: dict, temp_storage_dir):
        """测试根目录PROPFIND"""
        propfind_headers = {
            **auth_headers,
            "Depth": "1",
            "Content-Type": "application/xml"
        }
        
        propfind_body = '''<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <resourcetype/>
        <getcontentlength/>
        <getlastmodified/>
        <creationdate/>
        <displayname/>
    </prop>
</propfind>'''
        
        response = await client.request(
            "PROPFIND", 
            "/api/v1/webdav/", 
            headers=propfind_headers,
            content=propfind_body
        )
        
        assert response.status_code == 207  # Multi-Status
        assert response.headers["content-type"].startswith("application/xml")
        
        # 解析响应XML
        root = ET.fromstring(response.content)
        assert root.tag.endswith("}multistatus")
        
        responses = root.findall(".//{DAV:}response")
        assert len(responses) >= 1  # 至少包含根目录
    
    @pytest.mark.asyncio
    async def test_webdav_mkcol(self, client: AsyncClient, auth_headers: dict, temp_storage_dir):
        """测试创建目录"""
        response = await client.request(
            "MKCOL", 
            "/api/v1/webdav/test_folder/", 
            headers=auth_headers
        )
        
        assert response.status_code == 201
        
        # 验证目录是否创建
        propfind_response = await client.request(
            "PROPFIND",
            "/api/v1/webdav/test_folder/",
            headers={**auth_headers, "Depth": "0"}
        )
        
        assert propfind_response.status_code == 207
    
    @pytest.mark.asyncio
    async def test_webdav_put_file(self, client: AsyncClient, auth_headers: dict, temp_storage_dir):
        """测试上传文件"""
        file_content = b"Test file content"
        
        response = await client.request(
            "PUT",
            "/api/v1/webdav/test_file.txt",
            headers=auth_headers,
            content=file_content
        )
        
        assert response.status_code == 201
        
        # 验证文件是否上传
        get_response = await client.request(
            "GET",
            "/api/v1/webdav/test_file.txt",
            headers=auth_headers
        )
        
        assert get_response.status_code == 200
        assert get_response.content == file_content
    
    @pytest.mark.asyncio
    async def test_webdav_delete_file(self, client: AsyncClient, auth_headers: dict, temp_storage_dir):
        """测试删除文件"""
        # 先上传一个文件
        await client.request(
            "PUT",
            "/api/v1/webdav/delete_me.txt",
            headers=auth_headers,
            content=b"Delete this file"
        )
        
        # 删除文件
        response = await client.request(
            "DELETE",
            "/api/v1/webdav/delete_me.txt",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        
        # 验证文件已删除
        get_response = await client.request(
            "GET",
            "/api/v1/webdav/delete_me.txt",
            headers=auth_headers
        )
        
        assert get_response.status_code == 404


class TestKOReaderStatistics:
    """KOReader统计处理测试"""
    
    @pytest.mark.asyncio
    async def test_upload_koreader_statistics(self, client: AsyncClient, auth_headers: dict, koreader_stats_data: dict, temp_storage_dir):
        """测试上传KOReader统计文件"""
        stats_json = json.dumps(koreader_stats_data)
        
        response = await client.request(
            "PUT",
            "/api/v1/webdav/statistics/test_book.json",
            headers=auth_headers,
            content=stats_json.encode()
        )
        
        assert response.status_code == 201
        
        # 验证文件已上传
        get_response = await client.request(
            "GET",
            "/api/v1/webdav/statistics/test_book.json",
            headers=auth_headers
        )
        
        assert get_response.status_code == 200
        uploaded_data = json.loads(get_response.content)
        assert uploaded_data["title"] == koreader_stats_data["title"]
    
    @pytest.mark.asyncio
    async def test_koreader_statistics_parsing(self, client: AsyncClient, auth_headers: dict, koreader_stats_data: dict, test_db: AsyncSession, temp_storage_dir):
        """测试KOReader统计文件解析"""
        stats_json = json.dumps(koreader_stats_data)
        
        # 上传统计文件
        response = await client.request(
            "PUT",
            "/api/v1/webdav/statistics/parsed_book.json",
            headers=auth_headers,
            content=stats_json.encode()
        )
        
        assert response.status_code == 201
        
        # 检查是否创建了统计记录
        from sqlalchemy import select
        result = await test_db.execute(
            select(ReadingStatistics).where(
                ReadingStatistics.title == koreader_stats_data["title"]
            )
        )
        statistics = result.scalar_one_or_none()
        
        assert statistics is not None
        assert statistics.title == koreader_stats_data["title"]
        assert statistics.authors == koreader_stats_data["authors"]
        assert statistics.current_page == koreader_stats_data["performance_in_pages"]["current_page"]
        assert statistics.total_pages == koreader_stats_data["performance_in_pages"]["total_pages"]
        assert statistics.reading_percentage == koreader_stats_data["performance_in_pages"]["percentage"]
        assert statistics.total_reading_time == koreader_stats_data["total_time_in_sec"]
        assert statistics.highlights_count == koreader_stats_data["highlights"]
        assert statistics.notes_count == koreader_stats_data["notes"]
    
    @pytest.mark.asyncio
    async def test_invalid_json_statistics(self, client: AsyncClient, auth_headers: dict, temp_storage_dir):
        """测试无效JSON统计文件"""
        invalid_json = "{ invalid json content"
        
        response = await client.request(
            "PUT",
            "/api/v1/webdav/statistics/invalid.json",
            headers=auth_headers,
            content=invalid_json.encode()
        )
        
        # 应该还是成功上传，但不会解析
        assert response.status_code == 201
    
    @pytest.mark.asyncio
    async def test_statistics_update(self, client: AsyncClient, auth_headers: dict, test_db: AsyncSession, temp_storage_dir):
        """测试统计数据更新"""
        # 第一次上传
        initial_stats = {
            "title": "Update Test Book",
            "authors": "Test Author",
            "performance_in_pages": {
                "current_page": 10,
                "total_pages": 100,
                "percentage": 10.0
            },
            "total_time_in_sec": 600,
            "highlights": 1,
            "notes": 0,
            "md5": "updatetesthash"
        }
        
        response = await client.request(
            "PUT",
            "/api/v1/webdav/statistics/update_test.json",
            headers=auth_headers,
            content=json.dumps(initial_stats).encode()
        )
        
        assert response.status_code == 201
        
        # 第二次上传更新的数据
        updated_stats = {
            **initial_stats,
            "performance_in_pages": {
                "current_page": 50,
                "total_pages": 100,
                "percentage": 50.0
            },
            "total_time_in_sec": 1800,
            "highlights": 3,
            "notes": 2
        }
        
        response = await client.request(
            "PUT",
            "/api/v1/webdav/statistics/update_test.json",
            headers=auth_headers,
            content=json.dumps(updated_stats).encode()
        )
        
        assert response.status_code == 201
        
        # 验证数据已更新
        from sqlalchemy import select
        result = await test_db.execute(
            select(ReadingStatistics).where(
                ReadingStatistics.title == "Update Test Book"
            )
        )
        statistics = result.scalar_one_or_none()
        
        assert statistics is not None
        assert statistics.current_page == 50
        assert statistics.reading_percentage == 50.0
        assert statistics.total_reading_time == 1800
        assert statistics.highlights_count == 3
        assert statistics.notes_count == 2


class TestWebDAVAuthentication:
    """WebDAV认证测试"""
    
    @pytest.mark.asyncio
    async def test_webdav_unauthorized_access(self, client: AsyncClient):
        """测试未认证访问"""
        response = await client.request("PROPFIND", "/api/v1/webdav/")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_webdav_invalid_token(self, client: AsyncClient):
        """测试无效令牌"""
        headers = {"Authorization": "Bearer invalid_token"}
        
        response = await client.request("PROPFIND", "/api/v1/webdav/", headers=headers)
        
        assert response.status_code == 401


class TestWebDAVPathSecurity:
    """WebDAV路径安全测试"""
    
    @pytest.mark.asyncio
    async def test_path_traversal_protection(self, client: AsyncClient, auth_headers: dict):
        """测试路径遍历攻击防护"""
        # 尝试路径遍历攻击
        malicious_paths = [
            "/api/v1/webdav/../../../etc/passwd",
            "/api/v1/webdav/..%2F..%2F..%2Fetc%2Fpasswd",
            "/api/v1/webdav/./../../config.py"
        ]
        
        for path in malicious_paths:
            response = await client.request("GET", path, headers=auth_headers)
            
            # 应该返回404或400，不应该访问到系统文件
            assert response.status_code in [400, 404]
    
    @pytest.mark.asyncio
    async def test_null_byte_protection(self, client: AsyncClient, auth_headers: dict):
        """测试空字节攻击防护"""
        malicious_path = "/api/v1/webdav/test\x00.txt"
        
        response = await client.request("GET", malicious_path, headers=auth_headers)
        
        assert response.status_code in [400, 404]


class TestWebDAVStatisticsViewing:
    """WebDAV统计查看测试"""
    
    @pytest.mark.asyncio
    async def test_webdav_usage_stats(self, client: AsyncClient, auth_headers: dict, temp_storage_dir):
        """测试WebDAV使用统计"""
        # 先上传一些文件
        await client.request(
            "PUT",
            "/api/v1/webdav/stats_test1.txt",
            headers=auth_headers,
            content=b"test content 1"
        )
        
        await client.request(
            "PUT",
            "/api/v1/webdav/stats_test2.txt",
            headers=auth_headers,
            content=b"test content 2"
        )
        
        response = await client.get("/api/v1/webdav/stats/overview", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_files" in data
        assert "total_size" in data
        assert "file_types" in data
        assert data["total_files"] >= 2
    
    @pytest.mark.asyncio
    async def test_reading_statistics_view(self, client: AsyncClient, auth_headers: dict, test_db: AsyncSession):
        """测试阅读统计查看"""
        # 创建一些阅读统计记录
        stats1 = ReadingStatistics(
            title="View Test Book 1",
            authors="View Author 1",
            current_page=25,
            total_pages=100,
            reading_percentage=25.0,
            total_reading_time=1200
        )
        
        stats2 = ReadingStatistics(
            title="View Test Book 2", 
            authors="View Author 2",
            current_page=75,
            total_pages=150,
            reading_percentage=50.0,
            total_reading_time=2400
        )
        
        test_db.add_all([stats1, stats2])
        await test_db.commit()
        
        response = await client.get("/api/v1/webdav/stats/reading", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "items" in data
        assert data["total"] >= 2
        assert len(data["items"]) >= 2
    
    @pytest.mark.asyncio
    async def test_reading_statistics_pagination(self, client: AsyncClient, auth_headers: dict, test_db: AsyncSession):
        """测试阅读统计分页"""
        # 创建多个统计记录
        for i in range(15):
            stats = ReadingStatistics(
                title=f"Pagination Book {i:02d}",
                authors=f"Author {i}",
                current_page=i * 10,
                total_pages=200,
                reading_percentage=(i * 10) / 200 * 100,
                total_reading_time=i * 300
            )
            test_db.add(stats)
        
        await test_db.commit()
        
        # 测试第一页
        response = await client.get(
            "/api/v1/webdav/stats/reading?page=1&size=10", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] >= 15
        assert len(data["items"]) == 10
        assert "pagination" in data
        
        # 测试第二页
        response = await client.get(
            "/api/v1/webdav/stats/reading?page=2&size=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 5


class TestWebDAVErrorHandling:
    """WebDAV错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_webdav_nonexistent_file(self, client: AsyncClient, auth_headers: dict):
        """测试访问不存在的文件"""
        response = await client.request(
            "GET",
            "/api/v1/webdav/nonexistent.txt",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_webdav_delete_nonexistent(self, client: AsyncClient, auth_headers: dict):
        """测试删除不存在的文件"""
        response = await client.request(
            "DELETE",
            "/api/v1/webdav/nonexistent.txt",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_webdav_invalid_method(self, client: AsyncClient, auth_headers: dict):
        """测试不支持的HTTP方法"""
        response = await client.request(
            "PATCH",
            "/api/v1/webdav/test.txt",
            headers=auth_headers
        )
        
        assert response.status_code == 405


class TestWebDAVPerformance:
    """WebDAV性能测试"""
    
    @pytest.mark.asyncio
    async def test_large_file_upload(self, client: AsyncClient, auth_headers: dict, temp_storage_dir):
        """测试大文件上传"""
        # 创建1MB的测试文件
        large_content = b"x" * (1024 * 1024)
        
        response = await client.request(
            "PUT",
            "/api/v1/webdav/large_file.bin",
            headers=auth_headers,
            content=large_content
        )
        
        assert response.status_code == 201
        
        # 验证文件大小
        get_response = await client.request(
            "GET",
            "/api/v1/webdav/large_file.bin",
            headers=auth_headers
        )
        
        assert get_response.status_code == 200
        assert len(get_response.content) == len(large_content)
    
    @pytest.mark.asyncio
    async def test_directory_listing_performance(self, client: AsyncClient, auth_headers: dict, temp_storage_dir):
        """测试目录列表性能"""
        import time
        
        # 创建多个文件
        for i in range(50):
            await client.request(
                "PUT",
                f"/api/v1/webdav/perf_file_{i:03d}.txt",
                headers=auth_headers,
                content=f"Content {i}".encode()
            )
        
        # 测试PROPFIND性能
        start_time = time.time()
        
        response = await client.request(
            "PROPFIND",
            "/api/v1/webdav/",
            headers={**auth_headers, "Depth": "1"}
        )
        
        end_time = time.time()
        
        assert response.status_code == 207
        
        # 应该在1秒内完成
        response_time = end_time - start_time
        assert response_time < 1.0, f"Directory listing took too long: {response_time}s" 