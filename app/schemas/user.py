"""
用户数据模式

定义用户和设备管理的数据结构。
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class UserBase(BaseModel):
    """用户基础信息"""
    username: str = Field(..., description="用户名")
    email: Optional[str] = Field(None, description="邮箱地址")
    is_active: bool = Field(default=True, description="是否激活")


class UserResponse(UserBase):
    """用户响应数据"""
    id: int = Field(..., description="用户ID")
    is_admin: bool = Field(..., description="是否为管理员")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    last_login_at: Optional[datetime] = Field(None, description="最后登录时间")
    device_count: int = Field(..., description="设备数量")
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """用户更新数据"""
    email: Optional[str] = Field(None, description="邮箱地址")
    is_active: Optional[bool] = Field(None, description="是否激活")
    is_admin: Optional[bool] = Field(None, description="是否为管理员")


class DeviceCreate(BaseModel):
    """设备创建请求"""
    device_name: str = Field(..., description="设备名称")
    device_id: Optional[str] = Field(None, description="设备ID")
    model: Optional[str] = Field(None, description="设备型号")
    firmware_version: Optional[str] = Field(None, description="固件版本")
    app_version: Optional[str] = Field(None, description="应用版本")


class DeviceResponse(BaseModel):
    """设备响应数据"""
    id: int = Field(..., description="设备ID")
    device_name: str = Field(..., description="设备名称")
    device_id: Optional[str] = Field(None, description="设备ID")
    user_id: int = Field(..., description="用户ID")
    model: Optional[str] = Field(None, description="设备型号")
    firmware_version: Optional[str] = Field(None, description="固件版本")
    app_version: Optional[str] = Field(None, description="应用版本")
    is_active: bool = Field(..., description="是否激活")
    sync_enabled: bool = Field(..., description="是否启用同步")
    auto_sync: bool = Field(..., description="是否自动同步")
    last_sync_at: Optional[datetime] = Field(None, description="最后同步时间")
    sync_count: int = Field(..., description="同步次数")
    sync_progress_count: int = Field(..., description="同步进度数量")
    is_recently_active: bool = Field(..., description="是否最近活跃")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class DeviceUpdate(BaseModel):
    """设备更新数据"""
    device_name: Optional[str] = Field(None, description="设备名称")
    model: Optional[str] = Field(None, description="设备型号")
    firmware_version: Optional[str] = Field(None, description="固件版本")
    app_version: Optional[str] = Field(None, description="应用版本")
    is_active: Optional[bool] = Field(None, description="是否激活")
    sync_enabled: Optional[bool] = Field(None, description="是否启用同步")
    auto_sync: Optional[bool] = Field(None, description="是否自动同步")


class UserDeviceList(BaseModel):
    """用户设备列表"""
    user: UserResponse
    devices: List[DeviceResponse]
    
    class Config:
        from_attributes = True 