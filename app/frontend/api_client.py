"""
API 客户端 - 与 FastAPI 后端通信
"""

import requests
import streamlit as st
from typing import Dict, Any, Optional, List
import logging
from app.frontend.config import API_BASE_URL, API_TIMEOUT

logger = logging.getLogger(__name__)

class APIClient:
    """API 客户端类"""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = API_TIMEOUT
        
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # 如果有认证 token，添加到请求头
        if 'auth_token' in st.session_state:
            headers["Authorization"] = f"Bearer {st.session_state.auth_token}"
            
        return headers
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """处理 API 响应"""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                # 清除认证状态
                if 'auth_token' in st.session_state:
                    del st.session_state.auth_token
                if 'user_info' in st.session_state:
                    del st.session_state.user_info
                st.error("认证已过期，请重新登录")
                st.rerun()
            else:
                error_msg = f"API 请求失败: {response.status_code}"
                try:
                    error_detail = response.json().get('detail', str(e))
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {str(e)}"
                raise Exception(error_msg)
        except requests.exceptions.RequestException as e:
            raise Exception(f"网络请求失败: {str(e)}")
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET 请求"""
        url = f"{self.base_url}{endpoint}"
        response = self.session.get(url, headers=self._get_headers(), params=params)
        return self._handle_response(response)
    
    def post(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """POST 请求"""
        url = f"{self.base_url}{endpoint}"
        response = self.session.post(url, headers=self._get_headers(), json=data)
        return self._handle_response(response)
    
    def put(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """PUT 请求"""
        url = f"{self.base_url}{endpoint}"
        response = self.session.put(url, headers=self._get_headers(), json=data)
        return self._handle_response(response)
    
    def delete(self, endpoint: str) -> Dict[str, Any]:
        """DELETE 请求"""
        url = f"{self.base_url}{endpoint}"
        response = self.session.delete(url, headers=self._get_headers())
        return self._handle_response(response)

# 全局 API 客户端实例
api_client = APIClient()

class AuthAPI:
    """认证相关 API"""
    
    @staticmethod
    def login(username: str, password: str) -> Dict[str, Any]:
        """用户登录 - 获取JWT token"""
        return api_client.post("/api/v1/auth/token", {
            "username": username,
            "password": password
        })
    
    @staticmethod
    def get_current_user() -> Dict[str, Any]:
        """获取当前用户信息"""
        return api_client.get("/api/v1/auth/me")

class DashboardAPI:
    """仪表板相关 API"""
    
    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """获取仪表板统计数据"""
        return api_client.get("/api/v1/web/dashboard")
    
    @staticmethod
    def get_overview_data() -> Dict[str, Any]:
        """获取概览数据（模拟接口，基于现有数据构建）"""
        try:
            # 这里我们需要调用多个现有接口来构建概览数据
            stats_data = api_client.get("/api/v1/books/stats/overview")
            return {
                "kpis": {
                    "total_books": stats_data.get("total_books", 0),
                    "total_downloads": stats_data.get("total_downloads", 0),
                    "active_users": 0,  # 需要从用户 API 获取
                    "reading_sessions": 0  # 需要从统计 API 获取
                },
                "trends": {
                    "books_growth": 12.5,
                    "downloads_growth": 8.3,
                    "users_growth": 15.2,
                    "sessions_growth": 6.7
                }
            }
        except Exception as e:
            logger.error(f"获取概览数据失败: {e}")
            return {
                "kpis": {"total_books": 0, "total_downloads": 0, "active_users": 0, "reading_sessions": 0},
                "trends": {"books_growth": 0, "downloads_growth": 0, "users_growth": 0, "sessions_growth": 0}
            }

class BooksAPI:
    """书籍相关 API"""
    
    @staticmethod
    def get_books(page: int = 1, size: int = 20, search: str = None) -> Dict[str, Any]:
        """获取书籍列表"""
        params = {"page": page, "size": size}
        if search:
            params["search"] = search
        return api_client.get("/api/v1/books/", params)
    
    @staticmethod
    def get_reading_stats_overview() -> Dict[str, Any]:
        """获取阅读统计概览"""
        return api_client.get("/api/v1/books/stats/overview")
    
    @staticmethod
    def get_public_reading_stats(username: str = None, user_id: int = None) -> Dict[str, Any]:
        """获取公开阅读统计数据"""
        params = {}
        if username:
            params["username"] = username
        if user_id:
            params["user_id"] = user_id
        return api_client.get("/api/v1/books/stats/public", params)
    
    @staticmethod
    def upload_book(file_data: bytes, filename: str, **metadata) -> Dict[str, Any]:
        """上传书籍文件"""
        # 注意：这需要特殊处理文件上传
        # 暂时返回模拟数据
        return {"message": "文件上传功能需要特殊实现"}

class UsersAPI:
    """用户相关 API"""
    
    @staticmethod
    def get_users(page: int = 1, size: int = 20) -> Dict[str, Any]:
        """获取用户列表"""
        return api_client.get("/api/v1/web/users", {"page": page, "size": size})

class DevicesAPI:
    """设备相关 API"""
    
    @staticmethod
    def get_devices(page: int = 1, size: int = 20) -> Dict[str, Any]:
        """获取设备列表"""
        return api_client.get("/api/v1/web/devices/json", {"page": page, "size": size})
    
    @staticmethod
    def get_device_sync_status() -> Dict[str, Any]:
        """获取设备同步状态"""
        return api_client.get("/api/v1/syncs/devices/status")

class StatisticsAPI:
    """统计相关 API"""
    
    @staticmethod
    def get_reading_statistics(page: int = 1, size: int = 20) -> Dict[str, Any]:
        """获取阅读统计数据"""
        return api_client.get("/api/v1/web/statistics/json", {"page": page, "size": size})

# 健康检查
def check_api_health() -> bool:
    """检查 API 服务健康状态"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False 