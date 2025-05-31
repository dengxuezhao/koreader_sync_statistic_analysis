"""
数据模式定义

包含所有Pydantic数据模式，用于API请求和响应验证。
"""

from app.schemas.auth import *
from app.schemas.user import *
from app.schemas.sync import *
from app.schemas.opds import *

__all__ = [
    # 认证相关
    "UserCreate",
    "UserLogin", 
    "Token",
    "TokenData",
    "UserAuth",
    
    # 用户相关
    "UserBase",
    "UserResponse",
    "UserUpdate",
    "DeviceCreate",
    "DeviceResponse",
    
    # 同步相关
    "SyncProgressCreate",
    "SyncProgressUpdate", 
    "SyncProgressResponse",
    "KosyncProgress",
    
    # OPDS相关
    "OPDSEntry",
    "OPDSFeed",
] 