"""
认证API端点

实现KOReader kosync兼容的用户注册和认证功能。
严格遵循kosync协议以确保KOReader兼容性。
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status, Form
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, authenticate_kosync_user
from app.core.security import security
from app.models import User, Device
from app.schemas.auth import (
    UserCreate, 
    UserLogin, 
    KosyncUserRegisterResponse,
    KosyncUserAuthResponse,
    Token,
    DeviceAuth
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=KosyncUserRegisterResponse, summary="用户注册")
async def register_user(
    user_data: UserCreate,
    db: DbSession
) -> Any:
    """
    用户注册端点 - KOReader kosync兼容
    
    支持KOReader kosync插件的用户注册。
    """
    try:
        # 检查用户名是否已存在
        result = await db.execute(select(User).where(User.username == user_data.username))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        
        # 检查邮箱是否已存在（如果提供）
        if user_data.email:
            result = await db.execute(select(User).where(User.email == user_data.email))
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱地址已被使用"
                )
        
        # 创建新用户
        user = User(
            username=user_data.username,
            email=user_data.email,
            is_active=True,
            is_admin=False
        )
        user.set_password(user_data.password)  # 使用MD5哈希
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"新用户注册成功: {user.username}")
        
        return KosyncUserRegisterResponse(username=user.username)
        
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或邮箱已存在"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"用户注册失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册过程中发生错误"
        )


@router.post("/login", response_model=KosyncUserAuthResponse, summary="用户登录")
async def login_user(
    user_data: UserLogin,
    db: DbSession
) -> Any:
    """
    用户登录端点 - KOReader kosync兼容
    
    支持KOReader kosync插件的用户认证。
    返回用户密钥（实际上是密码的MD5哈希）以保持兼容性。
    """
    # 认证用户
    user = await authenticate_kosync_user(user_data.username, user_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 更新最后登录时间
    user.update_last_login()
    await db.commit()
    
    logger.info(f"用户登录成功: {user.username}")
    
    # 返回kosync兼容的响应（userkey是密码的MD5哈希）
    return KosyncUserAuthResponse(
        username=user.username,
        userkey=user.password_hash  # MD5哈希作为userkey
    )


# KOReader kosync兼容的端点（使用Form数据）
@router.post("/users/create", response_model=KosyncUserRegisterResponse, summary="kosync用户创建")
async def kosync_create_user(
    username: str = Form(...),
    password: str = Form(...),
    db: DbSession = None
) -> Any:
    """
    KOReader kosync用户创建端点
    
    完全兼容kosync API格式，使用Form数据。
    """
    user_data = UserCreate(username=username, password=password)
    return await register_user(user_data, db)


@router.post("/users/auth", response_model=KosyncUserAuthResponse, summary="kosync用户认证") 
async def kosync_auth_user(
    username: str = Form(...),
    password: str = Form(...),
    db: DbSession = None
) -> Any:
    """
    KOReader kosync用户认证端点
    
    完全兼容kosync API格式，使用Form数据。
    """
    user_data = UserLogin(username=username, password=password)
    return await login_user(user_data, db)


# 现代化JWT令牌认证（用于Web界面等）
@router.post("/token", response_model=Token, summary="获取访问令牌")
async def login_for_access_token(
    user_data: UserLogin,
    db: DbSession
) -> Any:
    """
    现代化JWT令牌认证
    
    用于Web界面和API访问的JWT令牌获取。
    """
    # 认证用户
    user = await authenticate_kosync_user(user_data.username, user_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建访问令牌
    access_token = security.create_access_token(data={"sub": user.username})
    
    # 更新最后登录时间
    user.update_last_login()
    await db.commit()
    
    logger.info(f"用户获取访问令牌: {user.username}")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=security.access_token_expire_minutes * 60
    )


@router.post("/device/register", summary="设备注册")
async def register_device(
    device_data: DeviceAuth,
    user_data: UserLogin,
    db: DbSession
) -> Any:
    """
    设备注册端点
    
    为KOReader设备注册并获取设备专用令牌。
    """
    # 认证用户
    user = await authenticate_kosync_user(user_data.username, user_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 检查设备是否已存在
    result = await db.execute(
        select(Device).where(
            Device.user_id == user.id,
            Device.device_name == device_data.device_name
        )
    )
    device = result.scalar_one_or_none()
    
    if device:
        # 更新现有设备信息
        device.update_device_info(
            model=device_data.model,
            firmware_version=device_data.firmware_version,
            app_version=device_data.app_version
        )
        if device_data.device_id:
            device.device_id = device_data.device_id
    else:
        # 创建新设备
        device = Device(
            user_id=user.id,
            device_name=device_data.device_name,
            device_id=device_data.device_id or security.generate_device_id(),
            model=device_data.model,
            firmware_version=device_data.firmware_version,
            app_version=device_data.app_version,
            is_active=True,
            sync_enabled=True,
            auto_sync=True
        )
        db.add(device)
    
    await db.commit()
    await db.refresh(device)
    
    # 生成设备专用令牌
    device_token = security.create_device_token(user.id, device.device_name)
    
    logger.info(f"设备注册成功: {device.device_name} (用户: {user.username})")
    
    return {
        "device_id": device.device_id,
        "device_name": device.device_name,
        "device_token": device_token,
        "user_id": user.id,
        "username": user.username
    } 