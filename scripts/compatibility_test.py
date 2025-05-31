#!/usr/bin/env python3
"""
KOReader 兼容性自动化测试脚本

独立运行的测试脚本，验证 Kompanion Python 与 KOReader 的兼容性。
可用于持续集成、部署验证或日常检查。
"""

import asyncio
import json
import hashlib
import time
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import xml.etree.ElementTree as ET

import httpx
import pytest

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from app.core.security import hash_password_md5
    APP_AVAILABLE = True
except ImportError:
    APP_AVAILABLE = False


class KOReaderCompatibilityTester:
    """KOReader 兼容性测试器"""
    
    def __init__(self, base_url: str, username: str = None, password: str = None):
        self.base_url = base_url.rstrip('/')
        self.username = username or "test_koreader_user"
        self.password = password or "test123"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.auth_token = None
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "base_url": base_url,
            "tests": {},
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0
            }
        }
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def log_test_result(self, test_name: str, passed: bool, message: str = "", details: Dict = None):
        """记录测试结果"""
        self.test_results["tests"][test_name] = {
            "passed": passed,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        
        self.test_results["summary"]["total"] += 1
        if passed:
            self.test_results["summary"]["passed"] += 1
            print(f"✅ {test_name}: {message}")
        else:
            self.test_results["summary"]["failed"] += 1
            print(f"❌ {test_name}: {message}")
    
    def skip_test(self, test_name: str, reason: str):
        """跳过测试"""
        self.test_results["tests"][test_name] = {
            "passed": None,
            "message": f"跳过: {reason}",
            "skipped": True,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results["summary"]["skipped"] += 1
        print(f"⏭️  {test_name}: 跳过 - {reason}")
    
    async def test_server_connectivity(self):
        """测试服务器连接"""
        test_name = "服务器连接测试"
        try:
            response = await self.client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                self.log_test_result(
                    test_name, True, 
                    f"服务器响应正常，状态: {data.get('status', 'unknown')}",
                    {"status_code": response.status_code, "response": data}
                )
                return True
            else:
                self.log_test_result(
                    test_name, False,
                    f"服务器响应异常，状态码: {response.status_code}",
                    {"status_code": response.status_code}
                )
                return False
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"无法连接到服务器: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    async def test_user_registration(self):
        """测试 kosync 用户注册"""
        test_name = "kosync用户注册"
        try:
            # 使用时间戳确保用户名唯一
            unique_username = f"{self.username}_{int(time.time())}"
            
            registration_data = {
                "username": unique_username,
                "password": self.password
            }
            
            response = await self.client.post(
                f"{self.base_url}/users/create",
                data=registration_data
            )
            
            if response.status_code == 201:
                data = response.json()
                self.log_test_result(
                    test_name, True,
                    f"用户注册成功: {unique_username}",
                    {"username": unique_username, "response": data}
                )
                # 更新用户名供后续测试使用
                self.username = unique_username
                return True
            else:
                self.log_test_result(
                    test_name, False,
                    f"用户注册失败，状态码: {response.status_code}",
                    {"status_code": response.status_code, "response": response.text}
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"用户注册异常: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    async def test_user_authentication(self):
        """测试 kosync 用户认证"""
        test_name = "kosync用户认证"
        try:
            auth_data = {
                "username": self.username,
                "password": self.password
            }
            
            response = await self.client.post(
                f"{self.base_url}/users/auth",
                data=auth_data
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("authorized") == "OK":
                    self.log_test_result(
                        test_name, True,
                        "用户认证成功",
                        {"response": data}
                    )
                    return True
                else:
                    self.log_test_result(
                        test_name, False,
                        f"认证响应格式错误: {data}",
                        {"response": data}
                    )
                    return False
            else:
                self.log_test_result(
                    test_name, False,
                    f"用户认证失败，状态码: {response.status_code}",
                    {"status_code": response.status_code, "response": response.text}
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"用户认证异常: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    async def get_auth_headers(self):
        """获取认证头"""
        if not self.auth_token:
            # 尝试获取JWT令牌
            try:
                auth_data = {
                    "username": self.username,
                    "password": self.password
                }
                response = await self.client.post(
                    f"{self.base_url}/api/v1/auth/login",
                    json=auth_data
                )
                if response.status_code == 200:
                    data = response.json()
                    self.auth_token = data.get("access_token")
            except:
                pass
        
        if self.auth_token:
            return {"Authorization": f"Bearer {self.auth_token}"}
        else:
            # 使用基本认证
            import base64
            credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            return {"Authorization": f"Basic {credentials}"}
    
    async def test_sync_progress_upload(self):
        """测试同步进度上传"""
        test_name = "同步进度上传"
        try:
            auth_headers = await self.get_auth_headers()
            
            # 测试数据
            sync_data = {
                "document": "test_compatibility_book.epub",
                "progress": "0.45",
                "percentage": "45.0",
                "device": "Test KOReader Device",
                "device_id": "test_device_001"
            }
            
            response = await self.client.put(
                f"{self.base_url}/syncs/progress",
                data=sync_data,
                headers=auth_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("document") == sync_data["document"] and \
                   float(data.get("progress", 0)) == float(sync_data["progress"]):
                    self.log_test_result(
                        test_name, True,
                        f"进度上传成功: {sync_data['document']} -> {sync_data['progress']}",
                        {"sync_data": sync_data, "response": data}
                    )
                    return True
                else:
                    self.log_test_result(
                        test_name, False,
                        f"进度上传响应数据不匹配: {data}",
                        {"expected": sync_data, "actual": data}
                    )
                    return False
            else:
                self.log_test_result(
                    test_name, False,
                    f"进度上传失败，状态码: {response.status_code}",
                    {"status_code": response.status_code, "response": response.text}
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"进度上传异常: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    async def test_sync_progress_retrieval(self):
        """测试同步进度获取"""
        test_name = "同步进度获取"
        try:
            auth_headers = await self.get_auth_headers()
            document = "test_compatibility_book.epub"
            
            # 先上传一个进度
            sync_data = {
                "document": document,
                "progress": "0.67",
                "device": "Test Retrieval Device"
            }
            
            await self.client.put(
                f"{self.base_url}/syncs/progress",
                data=sync_data,
                headers=auth_headers
            )
            
            # 获取进度
            response = await self.client.get(
                f"{self.base_url}/syncs/progress/{document}",
                headers=auth_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("document") == document and \
                   float(data.get("progress", 0)) == float(sync_data["progress"]):
                    self.log_test_result(
                        test_name, True,
                        f"进度获取成功: {document} -> {data['progress']}",
                        {"document": document, "response": data}
                    )
                    return True
                else:
                    self.log_test_result(
                        test_name, False,
                        f"进度获取数据不匹配: {data}",
                        {"expected": sync_data, "actual": data}
                    )
                    return False
            else:
                self.log_test_result(
                    test_name, False,
                    f"进度获取失败，状态码: {response.status_code}",
                    {"status_code": response.status_code, "response": response.text}
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"进度获取异常: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    async def test_multi_device_sync(self):
        """测试多设备同步"""
        test_name = "多设备同步"
        try:
            auth_headers = await self.get_auth_headers()
            document = "multi_device_test.pdf"
            devices = ["Kindle Paperwhite", "Kobo Clara", "Android Phone"]
            
            # 在不同设备上上传不同进度
            for i, device in enumerate(devices):
                progress = 0.2 + (i * 0.1)  # 0.2, 0.3, 0.4
                sync_data = {
                    "document": document,
                    "progress": str(progress),
                    "device": device,
                    "device_id": f"device_{i+1}"
                }
                
                response = await self.client.put(
                    f"{self.base_url}/syncs/progress",
                    data=sync_data,
                    headers=auth_headers
                )
                
                if response.status_code != 200:
                    self.log_test_result(
                        test_name, False,
                        f"设备 {device} 同步失败",
                        {"device": device, "status_code": response.status_code}
                    )
                    return False
            
            # 获取最终进度
            response = await self.client.get(
                f"{self.base_url}/syncs/progress/{document}",
                headers=auth_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                final_progress = float(data.get("progress", 0))
                if final_progress == 0.4:  # 最后更新的进度
                    self.log_test_result(
                        test_name, True,
                        f"多设备同步成功，最终进度: {final_progress} (设备: {data.get('device')})",
                        {"devices": devices, "final_progress": final_progress, "response": data}
                    )
                    return True
                else:
                    self.log_test_result(
                        test_name, False,
                        f"多设备同步进度不正确: {final_progress} (期望: 0.4)",
                        {"expected": 0.4, "actual": final_progress}
                    )
                    return False
            else:
                self.log_test_result(
                    test_name, False,
                    f"获取最终进度失败，状态码: {response.status_code}",
                    {"status_code": response.status_code}
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"多设备同步异常: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    async def test_opds_root_catalog(self):
        """测试 OPDS 根目录"""
        test_name = "OPDS根目录"
        try:
            response = await self.client.get(f"{self.base_url}/opds/")
            
            if response.status_code == 200:
                # 验证Content-Type
                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("application/atom+xml"):
                    self.log_test_result(
                        test_name, False,
                        f"OPDS Content-Type 不正确: {content_type}",
                        {"content_type": content_type}
                    )
                    return False
                
                # 验证XML格式
                try:
                    root = ET.fromstring(response.content)
                    
                    # 验证OPDS命名空间
                    namespaces = {
                        'atom': 'http://www.w3.org/2005/Atom',
                        'opds': 'http://opds-spec.org/2010/catalog'
                    }
                    
                    # 检查必需元素
                    if (root.find('.//atom:id', namespaces) is not None and
                        root.find('.//atom:title', namespaces) is not None and
                        root.find('.//atom:updated', namespaces) is not None):
                        
                        self.log_test_result(
                            test_name, True,
                            "OPDS 根目录格式正确",
                            {"content_type": content_type}
                        )
                        return True
                    else:
                        self.log_test_result(
                            test_name, False,
                            "OPDS XML 缺少必需元素",
                            {"content": response.text[:500]}
                        )
                        return False
                        
                except ET.ParseError as e:
                    self.log_test_result(
                        test_name, False,
                        f"OPDS XML 解析失败: {str(e)}",
                        {"content": response.text[:500]}
                    )
                    return False
            else:
                self.log_test_result(
                    test_name, False,
                    f"OPDS 根目录访问失败，状态码: {response.status_code}",
                    {"status_code": response.status_code, "response": response.text}
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"OPDS 根目录测试异常: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    async def test_opds_search(self):
        """测试 OPDS 搜索功能"""
        test_name = "OPDS搜索功能"
        try:
            response = await self.client.get(f"{self.base_url}/opds/search?q=test")
            
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if content_type.startswith("application/atom+xml"):
                    # 验证XML格式
                    try:
                        root = ET.fromstring(response.content)
                        if root.tag.endswith('feed'):
                            self.log_test_result(
                                test_name, True,
                                "OPDS 搜索功能正常",
                                {"query": "test", "content_type": content_type}
                            )
                            return True
                        else:
                            self.log_test_result(
                                test_name, False,
                                f"OPDS 搜索 XML 格式不正确: {root.tag}",
                                {"root_tag": root.tag}
                            )
                            return False
                    except ET.ParseError as e:
                        self.log_test_result(
                            test_name, False,
                            f"OPDS 搜索 XML 解析失败: {str(e)}",
                            {"content": response.text[:500]}
                        )
                        return False
                else:
                    self.log_test_result(
                        test_name, False,
                        f"OPDS 搜索 Content-Type 不正确: {content_type}",
                        {"content_type": content_type}
                    )
                    return False
            else:
                self.log_test_result(
                    test_name, False,
                    f"OPDS 搜索失败，状态码: {response.status_code}",
                    {"status_code": response.status_code, "response": response.text}
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"OPDS 搜索测试异常: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    async def test_webdav_propfind(self):
        """测试 WebDAV PROPFIND 操作"""
        test_name = "WebDAV PROPFIND"
        try:
            auth_headers = await self.get_auth_headers()
            auth_headers.update({
                "Depth": "1",
                "Content-Type": "text/xml"
            })
            
            response = await self.client.request(
                "PROPFIND",
                f"{self.base_url}/webdav/",
                headers=auth_headers
            )
            
            if response.status_code == 207:  # Multi-Status
                content_type = response.headers.get("content-type", "")
                if content_type.startswith("text/xml"):
                    # 验证XML格式
                    try:
                        root = ET.fromstring(response.content)
                        if 'DAV:' in root.tag or 'multistatus' in root.tag.lower():
                            self.log_test_result(
                                test_name, True,
                                "WebDAV PROPFIND 操作成功",
                                {"content_type": content_type}
                            )
                            return True
                        else:
                            self.log_test_result(
                                test_name, False,
                                f"WebDAV XML 格式不正确: {root.tag}",
                                {"root_tag": root.tag}
                            )
                            return False
                    except ET.ParseError as e:
                        self.log_test_result(
                            test_name, False,
                            f"WebDAV XML 解析失败: {str(e)}",
                            {"content": response.text[:500]}
                        )
                        return False
                else:
                    self.log_test_result(
                        test_name, False,
                        f"WebDAV Content-Type 不正确: {content_type}",
                        {"content_type": content_type}
                    )
                    return False
            else:
                self.log_test_result(
                    test_name, False,
                    f"WebDAV PROPFIND 失败，状态码: {response.status_code}",
                    {"status_code": response.status_code, "response": response.text}
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"WebDAV PROPFIND 测试异常: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    async def test_webdav_file_upload(self):
        """测试 WebDAV 文件上传"""
        test_name = "WebDAV文件上传"
        try:
            auth_headers = await self.get_auth_headers()
            
            # 创建测试统计文件
            stats_data = {
                "title": "Compatibility Test Book",
                "authors": "Test Author",
                "language": "en",
                "md5": hashlib.md5(b"test book content").hexdigest(),
                "total_pages": 100,
                "current_page": 50,
                "percentage_read": 50.0,
                "total_time_seconds": 1800,
                "start_reading": "2024-01-01 10:00:00",
                "last_reading": "2024-01-01 10:30:00"
            }
            
            stats_json = json.dumps(stats_data, indent=2)
            file_path = f"/statistics/compatibility_test_{int(time.time())}.json"
            
            auth_headers.update({
                "Content-Type": "application/json"
            })
            
            response = await self.client.put(
                f"{self.base_url}/webdav{file_path}",
                content=stats_json,
                headers=auth_headers
            )
            
            if response.status_code in [201, 204]:  # Created or No Content
                # 验证文件是否可以下载
                download_response = await self.client.get(
                    f"{self.base_url}/webdav{file_path}",
                    headers=await self.get_auth_headers()
                )
                
                if download_response.status_code == 200:
                    downloaded_data = download_response.json()
                    if downloaded_data == stats_data:
                        self.log_test_result(
                            test_name, True,
                            f"WebDAV 文件上传和下载成功: {file_path}",
                            {"file_path": file_path, "stats_data": stats_data}
                        )
                        return True
                    else:
                        self.log_test_result(
                            test_name, False,
                            "WebDAV 文件内容不匹配",
                            {"expected": stats_data, "actual": downloaded_data}
                        )
                        return False
                else:
                    self.log_test_result(
                        test_name, False,
                        f"WebDAV 文件下载失败，状态码: {download_response.status_code}",
                        {"download_status": download_response.status_code}
                    )
                    return False
            else:
                self.log_test_result(
                    test_name, False,
                    f"WebDAV 文件上传失败，状态码: {response.status_code}",
                    {"status_code": response.status_code, "response": response.text}
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"WebDAV 文件上传测试异常: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    async def test_performance_basic(self):
        """测试基本性能"""
        test_name = "基本性能测试"
        try:
            auth_headers = await self.get_auth_headers()
            
            # 测试多个同步请求的性能
            start_time = time.time()
            tasks = []
            
            for i in range(10):
                sync_data = {
                    "document": f"perf_test_book_{i}.epub",
                    "progress": str(0.1 * (i + 1)),
                    "device": "Performance Test Device"
                }
                
                task = self.client.put(
                    f"{self.base_url}/syncs/progress",
                    data=sync_data,
                    headers=auth_headers
                )
                tasks.append(task)
            
            # 等待所有请求完成
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            # 统计结果
            successful = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 200)
            total_time = end_time - start_time
            avg_time = total_time / len(tasks)
            
            if successful == len(tasks) and total_time < 5.0:  # 10个请求在5秒内完成
                self.log_test_result(
                    test_name, True,
                    f"性能测试通过: {successful}/{len(tasks)} 请求成功，总时间: {total_time:.2f}s，平均: {avg_time:.2f}s",
                    {"total_requests": len(tasks), "successful": successful, "total_time": total_time, "avg_time": avg_time}
                )
                return True
            else:
                self.log_test_result(
                    test_name, False,
                    f"性能测试失败: {successful}/{len(tasks)} 请求成功，总时间: {total_time:.2f}s (超过5秒)",
                    {"total_requests": len(tasks), "successful": successful, "total_time": total_time}
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                test_name, False,
                f"性能测试异常: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    async def run_all_tests(self):
        """运行所有兼容性测试"""
        print(f"🚀 开始 KOReader 兼容性测试...")
        print(f"🌐 服务器地址: {self.base_url}")
        print(f"👤 测试用户: {self.username}")
        print("=" * 60)
        
        # 测试列表
        tests = [
            ("服务器连接", self.test_server_connectivity),
            ("用户注册", self.test_user_registration),
            ("用户认证", self.test_user_authentication),
            ("同步进度上传", self.test_sync_progress_upload),
            ("同步进度获取", self.test_sync_progress_retrieval),
            ("多设备同步", self.test_multi_device_sync),
            ("OPDS根目录", self.test_opds_root_catalog),
            ("OPDS搜索", self.test_opds_search),
            ("WebDAV PROPFIND", self.test_webdav_propfind),
            ("WebDAV文件上传", self.test_webdav_file_upload),
            ("基本性能测试", self.test_performance_basic)
        ]
        
        # 运行测试
        for test_name, test_func in tests:
            try:
                await test_func()
            except Exception as e:
                self.log_test_result(
                    test_name, False,
                    f"测试执行异常: {str(e)}",
                    {"error": str(e)}
                )
        
        print("=" * 60)
        self.print_summary()
        return self.test_results
    
    def print_summary(self):
        """打印测试摘要"""
        summary = self.test_results["summary"]
        total = summary["total"]
        passed = summary["passed"]
        failed = summary["failed"]
        skipped = summary["skipped"]
        
        print(f"📊 测试摘要:")
        print(f"   总测试数: {total}")
        print(f"   ✅ 通过: {passed}")
        print(f"   ❌ 失败: {failed}")
        print(f"   ⏭️  跳过: {skipped}")
        
        if total > 0:
            pass_rate = (passed / total) * 100
            print(f"   📈 通过率: {pass_rate:.1f}%")
            
            if pass_rate >= 90:
                print(f"🎉 兼容性测试结果: 优秀")
            elif pass_rate >= 80:
                print(f"👍 兼容性测试结果: 良好")
            elif pass_rate >= 60:
                print(f"⚠️  兼容性测试结果: 一般")
            else:
                print(f"💥 兼容性测试结果: 需要改进")
    
    def save_results(self, output_file: str):
        """保存测试结果"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)
        print(f"📄 测试结果已保存到: {output_file}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="KOReader 兼容性自动化测试")
    parser.add_argument(
        "--url", "-u",
        default="http://localhost:8000",
        help="服务器地址 (默认: http://localhost:8000)"
    )
    parser.add_argument(
        "--username",
        default="test_koreader_user",
        help="测试用户名 (默认: test_koreader_user)"
    )
    parser.add_argument(
        "--password",
        default="test123",
        help="测试密码 (默认: test123)"
    )
    parser.add_argument(
        "--output", "-o",
        default="koreader_compatibility_results.json",
        help="输出文件路径 (默认: koreader_compatibility_results.json)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="请求超时时间（秒） (默认: 30)"
    )
    
    args = parser.parse_args()
    
    # 运行测试
    async with KOReaderCompatibilityTester(args.url, args.username, args.password) as tester:
        results = await tester.run_all_tests()
        tester.save_results(args.output)
        
        # 根据测试结果设置退出码
        summary = results["summary"]
        if summary["failed"] > 0:
            print(f"\n❌ 测试失败: {summary['failed']} 个测试未通过")
            sys.exit(1)
        elif summary["passed"] == 0:
            print(f"\n⚠️  没有测试通过")
            sys.exit(2)
        else:
            print(f"\n✅ 所有测试通过!")
            sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main()) 