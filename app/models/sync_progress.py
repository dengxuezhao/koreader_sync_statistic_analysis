"""
同步进度模型

定义同步进度表结构，用于管理KOReader的阅读进度同步。
兼容kosync协议的进度数据存储。
"""

from datetime import datetime
from typing import Optional, Dict, Any
import json

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.orm import relationship

from app.core.database import Base


class SyncProgress(Base):
    """同步进度模型 - KOReader阅读进度同步"""
    
    __tablename__ = "sync_progress"
    
    # 主键
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)  # 可选，有些同步可能不包含设备信息
    book_id = Column(Integer, ForeignKey("books.id"), nullable=True)  # 可选，书籍可能不在库中
    
    # 文档标识 - KOReader使用文档名称作为标识
    document = Column(String(500), nullable=False, index=True)  # 文档名称/路径
    document_hash = Column(String(64), nullable=True, index=True)  # 文档哈希（如果有）
    
    # 进度信息
    progress = Column(Float, nullable=False)  # 阅读进度 (0.0 - 1.0)
    percentage = Column(Float, nullable=False)  # 百分比 (0.0 - 100.0)
    
    # KOReader特定数据
    device_name = Column(String(100), nullable=True)  # 设备名称
    device = Column(String(100), nullable=True)  # 设备标识
    
    # 位置信息（KOReader专用字段）
    page = Column(Integer, nullable=True)  # 页码
    pos = Column(String(200), nullable=True)  # 位置信息
    chapter = Column(String(500), nullable=True)  # 章节信息
    
    # 元数据
    book_title = Column(String(500), nullable=True)  # 书籍标题
    book_author = Column(String(300), nullable=True)  # 书籍作者
    
    # 同步信息
    last_sync_at = Column(DateTime, default=datetime.utcnow)  # 最后同步时间
    sync_count = Column(Integer, default=1)  # 同步次数
    
    # 额外数据（JSON格式存储其他kosync字段）
    extra_data = Column(Text, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="sync_progress")
    device_rel = relationship("Device", back_populates="sync_progress")
    book = relationship("Book", back_populates="sync_progress")
    
    def __repr__(self) -> str:
        return f"<SyncProgress(id={self.id}, document='{self.document}', progress={self.progress})>"
    
    def update_progress(self, progress: float, percentage: float, 
                       page: Optional[int] = None, pos: Optional[str] = None,
                       chapter: Optional[str] = None) -> None:
        """更新阅读进度"""
        self.progress = progress
        self.percentage = percentage
        if page is not None:
            self.page = page
        if pos is not None:
            self.pos = pos
        if chapter is not None:
            self.chapter = chapter
        
        self.last_sync_at = datetime.utcnow()
        self.sync_count += 1
        self.updated_at = datetime.utcnow()
    
    def set_extra_data(self, data: Dict[str, Any]) -> None:
        """设置额外数据"""
        self.extra_data = json.dumps(data, ensure_ascii=False)
        self.updated_at = datetime.utcnow()
    
    def get_extra_data(self) -> Dict[str, Any]:
        """获取额外数据"""
        if self.extra_data:
            try:
                return json.loads(self.extra_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    @property
    def reading_percentage(self) -> str:
        """获取格式化的阅读百分比"""
        return f"{self.percentage:.1f}%"
    
    @property
    def is_finished(self) -> bool:
        """检查是否已完成阅读"""
        return self.percentage >= 100.0
    
    @property
    def is_recently_synced(self) -> bool:
        """检查是否最近同步过（24小时内）"""
        if not self.last_sync_at:
            return False
        delta = datetime.utcnow() - self.last_sync_at
        return delta.total_seconds() < 24 * 3600  # 24小时
    
    def to_kosync_format(self) -> Dict[str, Any]:
        """转换为kosync兼容格式"""
        result = {
            "document": self.document,
            "progress": str(self.progress),
            "percentage": self.percentage,
            "device": self.device or self.device_name,
            "device_id": str(self.device_id) if self.device_id else None,
            "timestamp": int(self.last_sync_at.timestamp()) if self.last_sync_at else None,
        }
        
        # 添加可选字段
        if self.page is not None:
            result["page"] = self.page
        if self.pos:
            result["pos"] = self.pos
        if self.chapter:
            result["chapter"] = self.chapter
        
        # 合并额外数据
        extra = self.get_extra_data()
        result.update(extra)
        
        return result
    
    def to_dict(self, include_kosync: bool = False) -> Dict[str, Any]:
        """转换为字典，用于API响应"""
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "book_id": self.book_id,
            "document": self.document,
            "document_hash": self.document_hash,
            "progress": self.progress,
            "percentage": self.percentage,
            "reading_percentage": self.reading_percentage,
            "device_name": self.device_name,
            "device": self.device,
            "page": self.page,
            "pos": self.pos,
            "chapter": self.chapter,
            "book_title": self.book_title,
            "book_author": self.book_author,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "sync_count": self.sync_count,
            "is_finished": self.is_finished,
            "is_recently_synced": self.is_recently_synced,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_kosync:
            result["kosync_format"] = self.to_kosync_format()
        
        return result 