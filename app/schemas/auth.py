"""
认证数据模式

定义KOReader兼容的认证API数据结构。
"""

from typing import Optional
from pydantic import BaseModel, Field, validator


class UserCreate(BaseModel):
    """用户注册请求 - KOReader kosync兼容"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, description="密码")
    email: Optional[str] = Field(None, description="邮箱地址")
    
    @validator("username")
    def validate_username(cls, v):
        """验证用户名格式"""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名只能包含字母、数字、下划线和连字符")
        return v.lower()
    
    @validator("email")
    def validate_email(cls, v):
        """验证邮箱格式"""
        if v and "@" not in v:
            raise ValueError("邮箱格式不正确")
        return v


class UserLogin(BaseModel):
    """用户登录请求 - KOReader kosync兼容"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    
    @validator("username")
    def validate_username(cls, v):
        """标准化用户名"""
        return v.lower()


class UserAuth(BaseModel):
    """用户认证响应 - KOReader kosync兼容"""
    username: str = Field(..., description="用户名")
    userkey: str = Field(..., description="用户密钥")
    
    class Config:
        json_encoders = {
            # 确保与KOReader兼容的字段名
        }


class Token(BaseModel):
    """JWT令牌响应"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: Optional[int] = Field(None, description="过期时间（秒）")


class TokenData(BaseModel):
    """令牌数据"""
    username: Optional[str] = None
    user_id: Optional[int] = None
    device_name: Optional[str] = None


class DeviceAuth(BaseModel):
    """设备认证请求"""
    device_name: str = Field(..., description="设备名称")
    device_id: Optional[str] = Field(None, description="设备ID")
    model: Optional[str] = Field(None, description="设备型号")
    firmware_version: Optional[str] = Field(None, description="固件版本")
    app_version: Optional[str] = Field(None, description="应用版本")


class AuthError(BaseModel):
    """认证错误响应"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误信息")
    
    
# KOReader kosync兼容的响应格式
class KosyncUserRegisterResponse(BaseModel):
    """KOReader用户注册响应"""
    username: str
    
    
class KosyncUserAuthResponse(BaseModel):
    """KOReader用户认证响应"""
    username: str
    userkey: str  # 实际上是用户密码的MD5哈希 