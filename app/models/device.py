"""
设备模型

定义设备表结构，用于管理用户的KOReader设备。
支持设备认证和同步状态跟踪。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Device(Base):
    """设备模型 - KOReader设备管理"""
    
    __tablename__ = "devices"
    
    # 主键
    id = Column(Integer, primary_key=True, index=True)
    
    # 设备标识
    device_name = Column(String(100), nullable=False, index=True)
    device_id = Column(String(100), nullable=True, index=True)  # 设备唯一标识
    
    # 关联用户
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 设备信息
    model = Column(String(50), nullable=True)  # 设备型号
    firmware_version = Column(String(50), nullable=True)  # 固件版本
    app_version = Column(String(50), nullable=True)  # KOReader版本
    
    # 设备状态
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime, nullable=True)  # 最后同步时间
    sync_count = Column(Integer, default=0)  # 同步次数
    
    # 设备配置
    sync_enabled = Column(Boolean, default=True)  # 是否启用同步
    auto_sync = Column(Boolean, default=True)  # 是否自动同步
    settings = Column(Text, nullable=True)  # 设备特定设置（JSON）
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="devices")
    sync_progress = relationship("SyncProgress", back_populates="device", cascade="all, delete-orphan")
    reading_statistics = relationship("ReadingStatistics", back_populates="device", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Device(id={self.id}, name='{self.device_name}', user_id={self.user_id})>"
    
    def update_sync_info(self) -> None:
        """更新同步信息"""
        self.last_sync_at = datetime.utcnow()
        self.sync_count += 1
        self.updated_at = datetime.utcnow()
    
    def update_device_info(self, model: Optional[str] = None, 
                          firmware_version: Optional[str] = None,
                          app_version: Optional[str] = None) -> None:
        """更新设备信息"""
        if model is not None:
            self.model = model
        if firmware_version is not None:
            self.firmware_version = firmware_version
        if app_version is not None:
            self.app_version = app_version
        self.updated_at = datetime.utcnow()
    
    @property
    def sync_progress_count(self) -> int:
        """获取设备的同步进度数量"""
        return len(self.sync_progress) if self.sync_progress else 0
    
    @property
    def is_recently_active(self) -> bool:
        """检查设备是否最近活跃（7天内有同步）"""
        if not self.last_sync_at:
            return False
        delta = datetime.utcnow() - self.last_sync_at
        return delta.days <= 7
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """转换为字典，用于API响应"""
        result = {
            "id": self.id,
            "device_name": self.device_name,
            "device_id": self.device_id,
            "user_id": self.user_id,
            "model": self.model,
            "firmware_version": self.firmware_version,
            "app_version": self.app_version,
            "is_active": self.is_active,
            "sync_enabled": self.sync_enabled,
            "auto_sync": self.auto_sync,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "sync_count": self.sync_count,
            "sync_progress_count": self.sync_progress_count,
            "is_recently_active": self.is_recently_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_sensitive:
            result["settings"] = self.settings
        
        return result 