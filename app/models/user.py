"""
用户模型

定义用户表结构，兼容KOReader的kosync认证系统。
支持MD5密码哈希以保证向后兼容性。
"""

import hashlib
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """用户模型 - 兼容KOReader的kosync用户系统"""
    
    __tablename__ = "users"
    
    # 主键
    id = Column(Integer, primary_key=True, index=True)
    
    # 用户认证信息
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(32), nullable=False)  # MD5哈希，32字符
    
    # 用户信息
    email = Column(String(100), unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    
    # 用户配置（JSON存储）
    settings = Column(Text, nullable=True)  # 存储JSON格式的用户设置
    
    # 关系
    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    sync_progress = relationship("SyncProgress", back_populates="user", cascade="all, delete-orphan")
    uploaded_books = relationship("Book", back_populates="uploaded_by", cascade="all, delete-orphan")
    reading_statistics = relationship("ReadingStatistics", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', is_admin={self.is_admin})>"
    
    def set_password(self, password: str) -> None:
        """设置密码 - 使用MD5哈希保证KOReader兼容性
        
        注意：MD5被认为不安全，但为了与KOReader的kosync插件兼容，
        我们必须使用MD5哈希（无盐）。在未来KOReader更新认证方式后，
        可以考虑迁移到更安全的哈希算法。
        """
        # KOReader kosync使用简单的MD5哈希（无盐）
        self.password_hash = hashlib.md5(password.encode('utf-8')).hexdigest()
    
    def check_password(self, password: str) -> bool:
        """验证密码"""
        return self.password_hash == hashlib.md5(password.encode('utf-8')).hexdigest()
    
    def update_last_login(self) -> None:
        """更新最后登录时间"""
        self.last_login_at = datetime.utcnow()
    
    @property
    def device_count(self) -> int:
        """获取用户的设备数量"""
        return len(self.devices) if self.devices else 0
    
    def get_device_by_name(self, device_name: str) -> Optional["Device"]:
        """根据设备名称获取设备"""
        for device in self.devices:
            if device.device_name == device_name:
                return device
        return None
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """转换为字典，用于API响应"""
        result = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "device_count": self.device_count,
        }
        
        if include_sensitive:
            result["password_hash"] = self.password_hash
            result["settings"] = self.settings
        
        return result 