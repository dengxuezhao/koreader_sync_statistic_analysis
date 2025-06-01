"""
API依赖项

提供FastAPI路由的依赖注入功能，包括数据库会话、用户认证等。
遵循FastAPI安全最佳实践。
"""

from typing import Optional, Generator, Annotated
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import base64

from app.core.database import get_session
from app.core.security import security, verify_token, verify_device_token
from app.models import User, Device
from app.schemas.auth import TokenData


# 安全方案定义
security_scheme = HTTPBearer(auto_error=False)
basic_security = HTTPBasic(auto_error=False)


async def get_db() -> Generator[AsyncSession, None, None]:
    """获取数据库会话依赖"""
    async for session in get_session():
        yield session


async def get_current_user_from_token(
    request: Request,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Optional[User]:
    """从JWT令牌获取当前用户（支持Header和Cookie）"""
    token = None
    
    # 首先尝试从Authorization header获取token
    if credentials:
        token = credentials.credentials
    else:
        # 然后尝试从cookie获取token
        cookie_token = request.cookies.get("access_token")
        if cookie_token and cookie_token.startswith("Bearer "):
            token = cookie_token[7:]  # 移除"Bearer "前缀
    
    if not token:
        return None
    
    # 验证令牌
    token_data = verify_token(token)
    if not token_data:
        return None
    
    username = token_data.get("sub")
    if not username:
        return None
    
    # 查找用户
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        return None
    
    return user


async def get_current_user(
    current_user: Annotated[Optional[User], Depends(get_current_user_from_token)]
) -> User:
    """获取当前认证用户（必需）"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供有效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="用户账户已禁用"
        )
    return current_user


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    """获取当前管理员用户"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


# KOReader设备认证相关依赖
async def get_current_user_from_device_token(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Optional[tuple[User, Device]]:
    """从设备令牌获取用户和设备信息"""
    if not credentials:
        return None
    
    # 验证设备令牌
    device_info = verify_device_token(credentials.credentials)
    if not device_info:
        return None
    
    user_id, device_name = device_info
    
    # 查找用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        return None
    
    # 查找设备
    result = await db.execute(
        select(Device).where(
            Device.user_id == user_id,
            Device.device_name == device_name
        )
    )
    device = result.scalar_one_or_none()
    
    if not device or not device.is_active:
        return None
    
    return user, device


async def get_current_device_user(
    user_device: Annotated[Optional[tuple[User, Device]], Depends(get_current_user_from_device_token)]
) -> tuple[User, Device]:
    """获取当前设备用户（必需）"""
    if not user_device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供有效的设备认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_device


# KOReader kosync兼容的用户名密码认证
async def authenticate_kosync_user(
    username: str, 
    password: str,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Optional[User]:
    """KOReader kosync用户名密码认证"""
    # 查找用户
    result = await db.execute(select(User).where(User.username == username.lower()))
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    
    # 验证MD5密码
    if not user.check_password(password):
        return None
    
    if not user.is_active:
        return None
    
    return user


# 可选认证依赖（不强制要求认证）
async def get_optional_current_user(
    current_user: Annotated[Optional[User], Depends(get_current_user_from_token)]
) -> Optional[User]:
    """获取可选的当前用户（允许未认证访问）"""
    return current_user


# 通用认证依赖（支持多种认证方式）
async def get_user_by_any_auth(
    user_from_token: Annotated[Optional[User], Depends(get_current_user_from_token)],
    user_device_from_token: Annotated[Optional[tuple[User, Device]], Depends(get_current_user_from_device_token)]
) -> Optional[User]:
    """通过任意有效认证方式获取用户"""
    if user_from_token:
        return user_from_token
    elif user_device_from_token:
        return user_device_from_token[0]
    return None


# 类型注解快捷方式
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]
CurrentAdminUser = Annotated[User, Depends(get_current_admin_user)]
OptionalCurrentUser = Annotated[Optional[User], Depends(get_optional_current_user)]
CurrentDeviceUser = Annotated[tuple[User, Device], Depends(get_current_device_user)]


# WebDAV HTTP基本认证
async def get_webdav_user(
    request: Request,
    credentials: Annotated[Optional[HTTPBasicCredentials], Depends(basic_security)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Optional[User]:
    """
    WebDAV HTTP基本认证
    
    支持KOReader的HTTP基本认证访问WebDAV服务
    """
    # 首先尝试HTTP基本认证
    if credentials:
        # 验证用户名密码
        result = await db.execute(select(User).where(User.username == credentials.username))
        user = result.scalar_one_or_none()
        
        if user and user.check_password(credentials.password) and user.is_active:
            return user
    
    # 然后尝试从Authorization header手动解析
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Basic "):
        try:
            # 解码Base64编码的用户名:密码
            encoded_credentials = auth_header[6:]  # 移除"Basic "
            decoded_bytes = base64.b64decode(encoded_credentials)
            decoded_string = decoded_bytes.decode('utf-8')
            username, password = decoded_string.split(':', 1)
            
            # 验证用户名密码
            result = await db.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()
            
            if user and user.check_password(password) and user.is_active:
                return user
                
        except Exception:
            pass  # 忽略解析错误
    
    return None


# WebDAV认证类型注解
WebDAVUser = Annotated[Optional[User], Depends(get_webdav_user)] 