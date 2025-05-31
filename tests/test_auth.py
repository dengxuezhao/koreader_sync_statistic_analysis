"""
认证系统测试

测试用户注册、登录、JWT令牌验证和KOReader兼容性。
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password, verify_md5_password, create_access_token
from app.models import User


class TestUserRegistration:
    """用户注册测试"""
    
    @pytest.mark.asyncio
    async def test_register_user_success(self, client: AsyncClient):
        """测试用户注册成功"""
        user_data = {
            "username": "newuser",
            "password": "password123",
            "email": "newuser@example.com"
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert data["is_active"] is True
        assert data["is_admin"] is False
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient, test_user: User):
        """测试注册重复用户名"""
        user_data = {
            "username": test_user.username,
            "password": "password123",
            "email": "different@example.com"
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """测试无效邮箱注册"""
        user_data = {
            "username": "newuser",
            "password": "password123",
            "email": "invalid-email"
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 422


class TestUserLogin:
    """用户登录测试"""
    
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User):
        """测试登录成功"""
        login_data = {
            "username": test_user.username,
            "password": "hello"  # MD5 hash matches test user
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == test_user.username
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient, test_user: User):
        """测试无效凭据登录"""
        login_data = {
            "username": test_user.username,
            "password": "wrongpassword"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "认证失败" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client: AsyncClient, test_db: AsyncSession):
        """测试非活跃用户登录"""
        # 创建非活跃用户
        inactive_user = User(
            username="inactive",
            hashed_password="5d41402abc4b2a76b9719d911017c592",
            is_active=False
        )
        test_db.add(inactive_user)
        await test_db.commit()
        
        login_data = {
            "username": "inactive",
            "password": "hello"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "用户未激活" in response.json()["detail"]


class TestKOReaderCompatibility:
    """KOReader兼容性测试"""
    
    @pytest.mark.asyncio
    async def test_kosync_user_create(self, client: AsyncClient):
        """测试kosync用户创建端点"""
        user_data = {
            "username": "koreader_user",
            "password": "koreader_pass"
        }
        
        response = await client.post("/api/v1/users/create", data=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "koreader_user"
        assert data["authorized"] == "OK"
    
    @pytest.mark.asyncio
    async def test_kosync_user_auth(self, client: AsyncClient, test_user: User):
        """测试kosync用户认证端点"""
        auth_data = {
            "username": test_user.username,
            "password": "hello"
        }
        
        response = await client.post("/api/v1/users/auth", data=auth_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username
        assert data["authorized"] == "OK"
    
    @pytest.mark.asyncio
    async def test_kosync_auth_invalid(self, client: AsyncClient):
        """测试kosync认证失败"""
        auth_data = {
            "username": "nonexistent",
            "password": "wrong"
        }
        
        response = await client.post("/api/v1/users/auth", data=auth_data)
        
        assert response.status_code == 401
        data = response.json()
        assert data["authorized"] == "FAIL"


class TestDeviceRegistration:
    """设备注册测试"""
    
    @pytest.mark.asyncio
    async def test_device_register_success(self, client: AsyncClient, auth_headers: dict):
        """测试设备注册成功"""
        device_data = {
            "device_id": "koreader-123",
            "device_name": "My KOReader",
            "device_type": "koreader"
        }
        
        response = await client.post(
            "/api/v1/auth/device-register", 
            json=device_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["device_id"] == "koreader-123"
        assert data["device_name"] == "My KOReader"
        assert data["device_type"] == "koreader"
    
    @pytest.mark.asyncio
    async def test_device_register_duplicate(self, client: AsyncClient, auth_headers: dict, test_device):
        """测试重复设备注册"""
        device_data = {
            "device_id": test_device.device_id,
            "device_name": "Duplicate Device",
            "device_type": "koreader"
        }
        
        response = await client.post(
            "/api/v1/auth/device-register", 
            json=device_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_device_register_unauthorized(self, client: AsyncClient):
        """测试未认证设备注册"""
        device_data = {
            "device_id": "unauthorized",
            "device_name": "Unauthorized Device",
            "device_type": "koreader"
        }
        
        response = await client.post("/api/v1/auth/device-register", json=device_data)
        
        assert response.status_code == 401


class TestPasswordSecurity:
    """密码安全测试"""
    
    def test_md5_password_verification(self):
        """测试MD5密码验证（KOReader兼容）"""
        password = "hello"
        md5_hash = "5d41402abc4b2a76b9719d911017c592"
        
        # 测试正确密码
        assert verify_md5_password(password, md5_hash) is True
        
        # 测试错误密码
        assert verify_md5_password("wrong", md5_hash) is False
    
    def test_bcrypt_password_verification(self):
        """测试bcrypt密码验证（现代安全）"""
        from app.core.security import get_password_hash
        
        password = "securepassword"
        bcrypt_hash = get_password_hash(password)
        
        # 测试正确密码
        assert verify_password(password, bcrypt_hash) is True
        
        # 测试错误密码
        assert verify_password("wrong", bcrypt_hash) is False


class TestJWTTokens:
    """JWT令牌测试"""
    
    def test_create_access_token(self):
        """测试JWT令牌创建"""
        data = {"sub": "testuser"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 10
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_with_token(self, client: AsyncClient, auth_headers: dict):
        """测试受保护端点的令牌访问"""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "username" in data
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_without_token(self, client: AsyncClient):
        """测试无令牌访问受保护端点"""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_invalid_token(self, client: AsyncClient):
        """测试无效令牌访问受保护端点"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401


class TestUserProfile:
    """用户资料测试"""
    
    @pytest.mark.asyncio
    async def test_get_current_user(self, client: AsyncClient, auth_headers: dict, test_user: User):
        """测试获取当前用户信息"""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username
        assert data["email"] == test_user.email
        assert data["is_active"] == test_user.is_active
        assert data["is_admin"] == test_user.is_admin
    
    @pytest.mark.asyncio
    async def test_update_profile(self, client: AsyncClient, auth_headers: dict):
        """测试更新用户资料"""
        update_data = {
            "email": "updated@example.com"
        }
        
        response = await client.put(
            "/api/v1/auth/profile", 
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "updated@example.com"
    
    @pytest.mark.asyncio
    async def test_change_password(self, client: AsyncClient, auth_headers: dict):
        """测试修改密码"""
        password_data = {
            "current_password": "hello",
            "new_password": "newpassword123"
        }
        
        response = await client.put(
            "/api/v1/auth/change-password", 
            json=password_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "密码修改成功"
    
    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, client: AsyncClient, auth_headers: dict):
        """测试错误当前密码修改"""
        password_data = {
            "current_password": "wrongpassword",
            "new_password": "newpassword123"
        }
        
        response = await client.put(
            "/api/v1/auth/change-password", 
            json=password_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "当前密码错误" in response.json()["detail"] 