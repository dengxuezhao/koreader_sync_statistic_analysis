"""
API依赖项

提供FastAPI路由的依赖注入功能，包括数据库会话、用户认证等。
遵循FastAPI安全最佳实践。
"""

from typing import Optional, Generator, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_async_session
from app.core.security import security
from app.models import User, Device
from app.schemas.auth import TokenData


# 安全方案定义
security_scheme = HTTPBearer(auto_error=False)


async def get_db() -> Generator[AsyncSession, None, None]:
    """获取数据库会话依赖"""
    async for session in get_async_session():
        yield session


async def get_current_user_from_token(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Optional[User]:
    """从JWT令牌获取当前用户"""
    if not credentials:
        return None
    
    # 验证令牌
    username = security.verify_token(credentials.credentials)
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
    device_info = security.verify_device_token(credentials.credentials)
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