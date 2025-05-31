"""
KOReader 兼容性测试

测试与实际 KOReader 设备和插件的兼容性，确保完全符合 kosync 协议。
"""

import json
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import hash_password_md5


class TestKOReaderCompatibility:
    """KOReader 设备兼容性测试套件"""
    
    @pytest.fixture
    def koreader_user_data(self):
        """模拟 KOReader 用户数据"""
        return {
            "username": "koreader_user",
            "password": "test123",
            "password_md5": hash_password_md5("test123")
        }
    
    @pytest.fixture
    def koreader_device_data(self):
        """模拟 KOReader 设备数据"""
        return {
            "device": "Kindle Paperwhite",
            "device_id": "kpw_001",
            "koreader_version": "2023.10"
        }
    
    @pytest.fixture
    def koreader_sync_data(self):
        """模拟 KOReader 同步数据"""
        return {
            "document": "test_book.epub",
            "progress": "0.45",
            "percentage": 45.0,
            "device": "Kindle Paperwhite",
            "device_id": "kpw_001",
            "timestamp": int(datetime.now().timestamp())
        }

    def test_kosync_user_registration(self, client: TestClient, koreader_user_data):
        """测试 kosync 兼容的用户注册
        
        KOReader kosync 插件使用此端点注册新用户
        """
        # 模拟 KOReader kosync 插件的注册请求
        registration_data = {
            "username": koreader_user_data["username"],
            "password": koreader_user_data["password"]
        }
        
        response = client.post("/users/create", data=registration_data)
        
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["username"] == registration_data["username"]
        assert "password" not in response_data  # 不应返回密码
        assert response_data["created_at"] is not None
        
        # 验证用户确实创建成功
        auth_response = client.post("/users/auth", data=registration_data)
        assert auth_response.status_code == 200

    def test_kosync_user_authentication(self, client: TestClient, test_user):
        """测试 kosync 兼容的用户认证
        
        KOReader kosync 插件使用此端点进行用户认证
        """
        # 模拟 KOReader kosync 插件的认证请求
        auth_data = {
            "username": test_user.username,
            "password": "test123"  # 明文密码，服务器端会进行MD5哈希
        }
        
        response = client.post("/users/auth", data=auth_data)
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["authorized"] == "OK"
        assert "username" in response_data

    def test_kosync_progress_upload_form_data(self, client: TestClient, auth_headers, koreader_sync_data):
        """测试 kosync 兼容的进度上传（Form数据格式）
        
        KOReader kosync 插件使用 application/x-www-form-urlencoded 格式上传进度
        """
        # 模拟 KOReader kosync 插件的进度上传请求
        form_data = {
            "document": koreader_sync_data["document"],
            "progress": str(koreader_sync_data["progress"]),
            "percentage": str(koreader_sync_data["percentage"]),
            "device": koreader_sync_data["device"],
            "device_id": koreader_sync_data["device_id"]
        }
        
        response = client.put("/syncs/progress", data=form_data, headers=auth_headers)
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["document"] == koreader_sync_data["document"]
        assert float(response_data["progress"]) == koreader_sync_data["progress"]
        assert response_data["device"] == koreader_sync_data["device"]

    def test_kosync_progress_retrieval(self, client: TestClient, auth_headers, koreader_sync_data):
        """测试 kosync 兼容的进度获取
        
        KOReader kosync 插件使用此端点获取同步进度
        """
        # 先上传一个进度
        form_data = {
            "document": koreader_sync_data["document"],
            "progress": str(koreader_sync_data["progress"]),
            "device": koreader_sync_data["device"]
        }
        client.put("/syncs/progress", data=form_data, headers=auth_headers)
        
        # 获取进度
        response = client.get(f"/syncs/progress/{koreader_sync_data['document']}", headers=auth_headers)
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["document"] == koreader_sync_data["document"]
        assert float(response_data["progress"]) == koreader_sync_data["progress"]
        assert response_data["device"] == koreader_sync_data["device"]

    def test_kosync_progress_sync_post(self, client: TestClient, auth_headers, koreader_sync_data):
        """测试 kosync 兼容的进度同步（POST方法）
        
        KOReader kosync 插件也支持使用 POST 方法进行进度同步
        """
        form_data = {
            "document": koreader_sync_data["document"],
            "progress": str(koreader_sync_data["progress"]),
            "device": koreader_sync_data["device"]
        }
        
        response = client.post("/syncs/progress", data=form_data, headers=auth_headers)
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["document"] == koreader_sync_data["document"]
        assert float(response_data["progress"]) == koreader_sync_data["progress"]

    def test_multiple_device_sync(self, client: TestClient, auth_headers):
        """测试多设备同步兼容性
        
        模拟同一用户在不同设备上的阅读进度同步
        """
        document = "multi_device_test.pdf"
        devices = ["Kindle Paperwhite", "Kobo Clara", "Android Phone"]
        
        # 在不同设备上上传不同的阅读进度
        for i, device in enumerate(devices):
            progress = 0.1 * (i + 1)  # 0.1, 0.2, 0.3
            form_data = {
                "document": document,
                "progress": str(progress),
                "device": device,
                "device_id": f"device_{i+1}"
            }
            response = client.put("/syncs/progress", data=form_data, headers=auth_headers)
            assert response.status_code == 200
        
        # 获取最新进度（应该是最后更新的设备）
        response = client.get(f"/syncs/progress/{document}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert float(data["progress"]) == 0.3  # 最后更新的进度
        assert data["device"] == "Android Phone"

    def test_document_hash_matching(self, client: TestClient, auth_headers):
        """测试文档哈希匹配功能
        
        KOReader 支持基于文件哈希的文档匹配
        """
        # 创建测试文档内容
        document_content = b"This is a test book content for hash testing"
        document_hash = hashlib.md5(document_content).hexdigest()
        
        # 使用哈希作为文档标识符
        form_data = {
            "document": f"hash:{document_hash}",
            "progress": "0.75",
            "device": "Test Device"
        }
        
        response = client.put("/syncs/progress", data=form_data, headers=auth_headers)
        assert response.status_code == 200
        
        # 验证可以通过哈希获取进度
        response = client.get(f"/syncs/progress/hash:{document_hash}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert float(data["progress"]) == 0.75

    def test_opds_koreader_compatibility(self, client: TestClient):
        """测试 OPDS 与 KOReader 的兼容性
        
        KOReader 支持 OPDS 目录浏览和下载
        """
        # 获取 OPDS 根目录
        response = client.get("/opds/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/atom+xml")
        
        # 解析 XML 内容
        root = ET.fromstring(response.content)
        
        # 验证 OPDS 命名空间
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'opds': 'http://opds-spec.org/2010/catalog'
        }
        
        # 验证必需的 OPDS 元素
        assert root.find('.//atom:id', namespaces) is not None
        assert root.find('.//atom:title', namespaces) is not None
        assert root.find('.//atom:updated', namespaces) is not None
        assert root.find('.//atom:link[@type="application/atom+xml;profile=opds-catalog"]', namespaces) is not None

    def test_opds_search_koreader_format(self, client: TestClient):
        """测试 OPDS 搜索功能的 KOReader 兼容性"""
        # 获取搜索端点
        response = client.get("/opds/search?q=test")
        assert response.status_code == 200
        
        # 解析搜索结果
        root = ET.fromstring(response.content)
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'opds': 'http://opds-spec.org/2010/catalog'
        }
        
        # 验证搜索结果格式
        assert root.tag.endswith('feed')
        assert root.find('.//atom:id', namespaces) is not None

    def test_webdav_koreader_statistics(self, client: TestClient, auth_headers):
        """测试 WebDAV 与 KOReader 统计插件的兼容性
        
        KOReader 统计插件会通过 WebDAV 上传阅读统计文件
        """
        # 模拟 KOReader 统计文件内容
        stats_data = {
            "title": "Test Book Statistics",
            "authors": "Test Author",
            "language": "en",
            "series": "",
            "md5": "abc123def456",
            "total_pages": 200,
            "current_page": 100,
            "percentage_read": 50.0,
            "total_time_seconds": 3600,
            "start_reading": "2023-01-01 10:00:00",
            "last_reading": "2023-01-01 11:00:00",
            "highlights": [],
            "notes": [],
            "bookmarks": []
        }
        
        stats_json = json.dumps(stats_data, indent=2)
        
        # 上传统计文件到 WebDAV
        file_path = "/statistics/2023/01/test_book_stats.json"
        response = client.put(
            f"/webdav{file_path}",
            content=stats_json,
            headers={
                **auth_headers,
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code in [201, 204]  # Created or No Content
        
        # 验证可以下载统计文件
        response = client.get(f"/webdav{file_path}", headers=auth_headers)
        assert response.status_code == 200
        assert json.loads(response.content) == stats_data

    def test_webdav_propfind_koreader_compatibility(self, client: TestClient, auth_headers):
        """测试 WebDAV PROPFIND 与 KOReader 的兼容性"""
        # 测试根目录 PROPFIND
        response = client.request(
            "PROPFIND",
            "/webdav/",
            headers={
                **auth_headers,
                "Depth": "1",
                "Content-Type": "text/xml"
            }
        )
        
        assert response.status_code == 207  # Multi-Status
        assert response.headers["content-type"].startswith("text/xml")
        
        # 解析 WebDAV 响应
        root = ET.fromstring(response.content)
        
        # 验证 WebDAV 命名空间
        assert 'DAV:' in root.tag or 'multistatus' in root.tag.lower()

    def test_error_handling_koreader_compatibility(self, client: TestClient, auth_headers):
        """测试错误处理的 KOReader 兼容性
        
        确保错误响应格式与 KOReader 期望的格式兼容
        """
        # 测试不存在的文档
        response = client.get("/syncs/progress/nonexistent_document", headers=auth_headers)
        assert response.status_code == 404
        
        # 测试无效的进度值
        invalid_data = {
            "document": "test.epub",
            "progress": "invalid_progress",
            "device": "Test Device"
        }
        response = client.put("/syncs/progress", data=invalid_data, headers=auth_headers)
        assert response.status_code == 422  # Validation error

    def test_large_sync_data_handling(self, client: TestClient, auth_headers):
        """测试大量同步数据的处理能力
        
        模拟用户有大量书籍和同步记录的情况
        """
        # 创建大量同步记录
        documents = [f"book_{i:03d}.epub" for i in range(100)]
        
        for i, document in enumerate(documents):
            form_data = {
                "document": document,
                "progress": str((i + 1) / 100.0),  # 0.01 到 1.00
                "device": "Bulk Test Device"
            }
            response = client.put("/syncs/progress", data=form_data, headers=auth_headers)
            assert response.status_code == 200
        
        # 验证可以获取所有记录
        response = client.get("/api/v1/syncs/progress?limit=200", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 100

    def test_concurrent_sync_requests(self, client: TestClient, auth_headers):
        """测试并发同步请求的处理
        
        模拟多个 KOReader 设备同时同步的情况
        """
        import threading
        import time
        
        results = []
        
        def sync_worker(device_id: int):
            """并发同步工作线程"""
            local_client = TestClient(app)
            form_data = {
                "document": "concurrent_test.epub",
                "progress": str(0.5 + device_id * 0.01),
                "device": f"Device_{device_id}"
            }
            response = local_client.put("/syncs/progress", data=form_data, headers=auth_headers)
            results.append(response.status_code)
        
        # 启动多个并发线程
        threads = []
        for i in range(10):
            thread = threading.Thread(target=sync_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证所有请求都成功处理
        assert all(status == 200 for status in results)
        assert len(results) == 10

    def test_koreader_specific_headers(self, client: TestClient, auth_headers):
        """测试 KOReader 特定的 HTTP 头处理"""
        # 模拟 KOReader 发送的典型请求头
        koreader_headers = {
            **auth_headers,
            "User-Agent": "KOReader/2023.10",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }
        
        # 测试同步请求
        form_data = {
            "document": "header_test.epub",
            "progress": "0.33",
            "device": "KOReader Device"
        }
        
        response = client.put("/syncs/progress", data=form_data, headers=koreader_headers)
        assert response.status_code == 200
        
        # 验证响应头
        assert "Content-Type" in response.headers
        assert response.headers["Content-Type"] == "application/json"


class TestKOReaderDeviceSimulation:
    """真实 KOReader 设备行为模拟测试"""
    
    def test_complete_sync_workflow(self, client: TestClient):
        """测试完整的 KOReader 同步工作流程
        
        模拟从用户注册到阅读进度同步的完整流程
        """
        # 1. 用户注册（首次使用 kosync）
        user_data = {
            "username": "koreader_workflow_test",
            "password": "workflow123"
        }
        
        response = client.post("/users/create", data=user_data)
        assert response.status_code == 201
        
        # 2. 用户认证
        response = client.post("/users/auth", data=user_data)
        assert response.status_code == 200
        auth_data = response.json()
        
        # 3. 模拟设备注册（如果需要）
        device_data = {
            "device_name": "Kindle Paperwhite 11th Gen",
            "device_id": "kpw11_workflow_test"
        }
        
        # 4. 开始阅读，上传初始进度
        initial_progress = {
            "document": "workflow_test_book.epub",
            "progress": "0.05",
            "percentage": 5.0,
            "device": device_data["device_name"],
            "device_id": device_data["device_id"]
        }
        
        # 使用基本认证头
        auth_headers = {"Authorization": f"Bearer {auth_data.get('token', '')}"}
        if not auth_data.get('token'):
            # 如果没有token，使用用户名密码进行基本认证
            import base64
            credentials = base64.b64encode(f"{user_data['username']}:{user_data['password']}".encode()).decode()
            auth_headers = {"Authorization": f"Basic {credentials}"}
        
        response = client.put("/syncs/progress", data=initial_progress, headers=auth_headers)
        assert response.status_code == 200
        
        # 5. 模拟阅读进度更新
        progress_updates = [0.15, 0.35, 0.50, 0.75, 0.90]
        
        for progress in progress_updates:
            update_data = {
                "document": "workflow_test_book.epub",
                "progress": str(progress),
                "device": device_data["device_name"]
            }
            response = client.put("/syncs/progress", data=update_data, headers=auth_headers)
            assert response.status_code == 200
        
        # 6. 验证最终进度
        response = client.get("/syncs/progress/workflow_test_book.epub", headers=auth_headers)
        assert response.status_code == 200
        final_data = response.json()
        assert float(final_data["progress"]) == 0.90

    def test_offline_sync_simulation(self, client: TestClient, auth_headers):
        """测试离线阅读后的同步模拟
        
        模拟用户离线阅读后重新连接网络进行同步的情况
        """
        document = "offline_sync_test.pdf"
        
        # 模拟离线期间累积的多个进度更新
        offline_updates = [
            {"progress": "0.10", "timestamp": "2023-01-01T10:00:00"},
            {"progress": "0.25", "timestamp": "2023-01-01T10:30:00"},
            {"progress": "0.40", "timestamp": "2023-01-01T11:00:00"},
            {"progress": "0.55", "timestamp": "2023-01-01T11:30:00"},
        ]
        
        # 重新连接后，按时间顺序同步所有进度
        for update in offline_updates:
            sync_data = {
                "document": document,
                "progress": update["progress"],
                "device": "Offline Test Device",
                "timestamp": update["timestamp"]
            }
            response = client.put("/syncs/progress", data=sync_data, headers=auth_headers)
            assert response.status_code == 200
        
        # 验证最终进度是最新的
        response = client.get(f"/syncs/progress/{document}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert float(data["progress"]) == 0.55


@pytest.mark.integration
class TestRealWorldKOReaderIntegration:
    """真实世界 KOReader 集成测试
    
    这些测试需要实际的 KOReader 设备或模拟器环境
    """
    
    def test_koreader_kosync_plugin_integration(self):
        """测试与真实 KOReader kosync 插件的集成
        
        注意：此测试需要真实的 KOReader 环境
        """
        pytest.skip("需要真实 KOReader 环境进行测试")
    
    def test_koreader_opds_client_integration(self):
        """测试与 KOReader OPDS 客户端的集成
        
        注意：此测试需要真实的 KOReader 环境
        """
        pytest.skip("需要真实 KOReader 环境进行测试")
    
    def test_koreader_statistics_plugin_integration(self):
        """测试与 KOReader 统计插件的集成
        
        注意：此测试需要真实的 KOReader 环境
        """
        pytest.skip("需要真实 KOReader 环境进行测试")


# 兼容性测试工具函数

def create_sample_koreader_statistics():
    """创建示例 KOReader 统计文件数据"""
    return {
        "title": "Sample Book for Testing",
        "authors": "Test Author",
        "language": "en",
        "series": "",
        "md5": hashlib.md5(b"sample book content").hexdigest(),
        "total_pages": 250,
        "current_page": 125,
        "percentage_read": 50.0,
        "total_time_seconds": 7200,  # 2 hours
        "start_reading": "2023-01-01 09:00:00",
        "last_reading": "2023-01-01 11:00:00",
        "highlights": [
            {
                "text": "This is a highlighted text.",
                "page": 45,
                "chapter": "Chapter 3",
                "datetime": "2023-01-01 09:30:00"
            }
        ],
        "notes": [
            {
                "text": "Interesting point about the topic.",
                "note": "My personal note here.",
                "page": 67,
                "chapter": "Chapter 4",
                "datetime": "2023-01-01 10:15:00"
            }
        ],
        "bookmarks": [
            {
                "page": 100,
                "datetime": "2023-01-01 10:45:00",
                "notes": "Important section to remember"
            }
        ]
    }


def validate_opds_xml_structure(xml_content: bytes) -> bool:
    """验证 OPDS XML 结构是否符合规范"""
    try:
        root = ET.fromstring(xml_content)
        
        # 定义命名空间
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'opds': 'http://opds-spec.org/2010/catalog'
        }
        
        # 检查必需元素
        required_elements = ['id', 'title', 'updated']
        for element in required_elements:
            if root.find(f'.//atom:{element}', namespaces) is None:
                return False
        
        return True
        
    except ET.ParseError:
        return False


def simulate_koreader_request(client: TestClient, endpoint: str, method: str = "GET", **kwargs):
    """模拟 KOReader 发送的 HTTP 请求"""
    koreader_headers = {
        "User-Agent": "KOReader/2023.10",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive"
    }
    
    # 合并用户提供的头部
    if "headers" in kwargs:
        koreader_headers.update(kwargs["headers"])
        kwargs["headers"] = koreader_headers
    else:
        kwargs["headers"] = koreader_headers
    
    return client.request(method, endpoint, **kwargs) 