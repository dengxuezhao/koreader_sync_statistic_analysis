"""
认证API端点

实现KOReader kosync兼容的用户注册和认证功能。
严格遵循kosync协议以确保KOReader兼容性。
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status, Form, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, authenticate_kosync_user, CurrentUser
from app.core.security import security, create_access_token, create_device_token
from app.core.config import settings
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
    db: DbSession,
    username: str = Form(...),
    password: str = Form(...)
) -> Any:
    """
    KOReader kosync用户创建端点
    
    完全兼容kosync API格式，使用Form数据。
    """
    user_data = UserCreate(username=username, password=password)
    return await register_user(user_data, db)


@router.post("/users/auth", response_model=KosyncUserAuthResponse, summary="kosync用户认证") 
async def kosync_auth_user(
    db: DbSession,
    username: str = Form(...),
    password: str = Form(...)
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
    access_token = create_access_token(data={"sub": user.username})
    
    # 更新最后登录时间
    user.update_last_login()
    await db.commit()
    
    logger.info(f"用户获取访问令牌: {user.username}")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", summary="获取当前用户信息")
async def get_current_user_info(current_user: CurrentUser) -> Any:
    """
    获取当前认证用户的信息
    
    需要有效的JWT token进行访问。
    """
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "is_admin": current_user.is_admin,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login_at": current_user.last_login_at.isoformat() if current_user.last_login_at else None,
        "device_count": current_user.device_count
    }


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
    device_token = create_device_token(user.id, device.device_name)
    
    logger.info(f"设备注册成功: {device.device_name} (用户: {user.username})")
    
    return {
        "device_id": device.device_id,
        "device_name": device.device_name,
        "device_token": device_token,
        "user_id": user.id,
        "username": user.username
    }


# Web表单登录端点（处理HTML表单提交）
@router.post("/form-login", summary="表单登录")
async def form_login(
    db: DbSession,
    username: str = Form(..., description="用户名"),
    password: str = Form(..., description="密码")
) -> RedirectResponse:
    """
    Web表单登录端点
    
    处理HTML表单提交的登录请求，成功后重定向到仪表板。
    """
    try:
        # 认证用户 - 直接查询而不使用依赖注入
        logger.info(f"尝试表单登录: 用户名={username}")
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"用户不存在: {username}")
            return RedirectResponse(
                url="/api/v1/web/login?message=用户名或密码错误",
                status_code=302
            )
        
        if not user.is_active:
            logger.warning(f"用户未激活: {username}")
            return RedirectResponse(
                url="/api/v1/web/login?message=用户名或密码错误",
                status_code=302
            )
        
        if not user.check_password(password):
            logger.warning(f"密码错误: {username}")
            return RedirectResponse(
                url="/api/v1/web/login?message=用户名或密码错误",
                status_code=302
            )
        
        logger.info(f"用户认证成功: {username}")
        
        # 更新最后登录时间
        try:
            user.update_last_login()
            await db.commit()
            logger.info(f"更新最后登录时间成功: {username}")
        except Exception as commit_error:
            logger.error(f"更新最后登录时间失败: {commit_error}")
            await db.rollback()
        
        # 创建访问令牌
        try:
            access_token = create_access_token(data={"sub": user.username})
            logger.info(f"访问令牌创建成功: {username}")
        except Exception as token_error:
            logger.error(f"访问令牌创建失败: {token_error}")
            return RedirectResponse(
                url="/api/v1/web/login?message=令牌创建失败",
                status_code=302
            )
        
        logger.info(f"用户表单登录成功: {user.username}")
        
        # 创建重定向响应并设置cookie
        redirect_response = RedirectResponse(
            url="/api/v1/web/dashboard",
            status_code=302
        )
        
        # 设置认证cookie（HttpOnly for security）
        redirect_response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            httponly=True,
            secure=False,  # 在开发环境中设为False，生产环境应为True
            samesite="lax"
        )
        
        logger.info(f"重定向到仪表板: {username}")
        return redirect_response
        
    except Exception as e:
        logger.error(f"表单登录失败: {e}")
        return RedirectResponse(
            url="/api/v1/web/login?message=登录过程中发生错误",
            status_code=302
        ) 