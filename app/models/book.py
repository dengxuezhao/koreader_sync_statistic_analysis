"""
书籍模型

定义书籍表结构，用于管理电子书文件和元数据。
支持多种格式和OPDS目录服务。
"""

import hashlib
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, LargeBinary, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Book(Base):
    """书籍模型 - 电子书文件和元数据管理"""
    
    __tablename__ = "books"
    
    # 主键
    id = Column(Integer, primary_key=True, index=True)
    
    # 基本信息
    title = Column(String(500), nullable=False, index=True)
    author = Column(String(300), nullable=True, index=True)
    isbn = Column(String(13), nullable=True, index=True)  # ISBN-13
    
    # 文件信息
    filename = Column(String(500), nullable=False)
    file_format = Column(String(10), nullable=False, index=True)  # epub, pdf, mobi等
    file_size = Column(Integer, nullable=False)  # 文件大小（字节）
    file_hash = Column(String(64), nullable=False, index=True)  # SHA-256哈希
    
    # 元数据
    description = Column(Text, nullable=True)
    publisher = Column(String(200), nullable=True)
    published_date = Column(DateTime, nullable=True)
    language = Column(String(10), nullable=True)  # ISO 639-1语言代码
    genre = Column(String(100), nullable=True)
    series = Column(String(200), nullable=True)
    series_index = Column(Integer, nullable=True)
    
    # 封面
    cover_image = Column(LargeBinary, nullable=True)  # 封面图片二进制数据
    cover_mime_type = Column(String(50), nullable=True)  # 封面MIME类型
    
    # 存储信息
    storage_path = Column(String(1000), nullable=True)  # 文件存储路径
    storage_type = Column(String(20), nullable=False, default="database")  # database, filesystem
    
    # 状态
    is_available = Column(Boolean, default=True)  # 是否可用
    download_count = Column(Integer, default=0)  # 下载次数
    
    # OPDS相关
    opds_category = Column(String(100), nullable=True)  # OPDS分类
    opds_tags = Column(Text, nullable=True)  # OPDS标签（JSON数组）
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 外键
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # 关系
    uploaded_by = relationship("User", back_populates="uploaded_books")
    sync_progress = relationship("SyncProgress", back_populates="book", cascade="all, delete-orphan")
    reading_statistics = relationship("ReadingStatistics", back_populates="book", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Book(id={self.id}, title='{self.title}', author='{self.author}')>"
    
    def calculate_file_hash(self, file_content: bytes) -> str:
        """计算文件SHA-256哈希"""
        return hashlib.sha256(file_content).hexdigest()
    
    def update_file_info(self, filename: str, file_content: bytes, file_format: str) -> None:
        """更新文件信息"""
        self.filename = filename
        self.file_format = file_format.lower()
        self.file_size = len(file_content)
        self.file_hash = self.calculate_file_hash(file_content)
        self.updated_at = datetime.utcnow()
    
    def increment_download_count(self) -> None:
        """增加下载次数"""
        self.download_count += 1
        self.updated_at = datetime.utcnow()
    
    @property
    def file_size_mb(self) -> float:
        """获取文件大小（MB）"""
        return round(self.file_size / (1024 * 1024), 2)
    
    @property
    def display_title(self) -> str:
        """获取显示标题（包含系列信息）"""
        if self.series and self.series_index:
            return f"{self.series} #{self.series_index}: {self.title}"
        return self.title
    
    @property
    def has_cover(self) -> bool:
        """检查是否有封面"""
        return self.cover_image is not None
    
    def get_opds_identifier(self) -> str:
        """获取OPDS标识符"""
        return f"urn:uuid:book-{self.id}"
    
    def get_download_url(self, base_url: str) -> str:
        """获取下载URL"""
        return f"{base_url}/api/v1/books/{self.id}/download"
    
    def get_cover_url(self, base_url: str) -> Optional[str]:
        """获取封面URL"""
        if self.has_cover:
            return f"{base_url}/api/v1/books/{self.id}/cover"
        return None
    
    def to_dict(self, include_content: bool = False) -> dict:
        """转换为字典，用于API响应"""
        result = {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "isbn": self.isbn,
            "filename": self.filename,
            "file_format": self.file_format,
            "file_size": self.file_size,
            "file_size_mb": self.file_size_mb,
            "file_hash": self.file_hash,
            "description": self.description,
            "publisher": self.publisher,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "language": self.language,
            "genre": self.genre,
            "series": self.series,
            "series_index": self.series_index,
            "display_title": self.display_title,
            "storage_type": self.storage_type,
            "is_available": self.is_available,
            "download_count": self.download_count,
            "opds_category": self.opds_category,
            "opds_tags": self.opds_tags,
            "has_cover": self.has_cover,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_content:
            result["storage_path"] = self.storage_path
            result["cover_mime_type"] = self.cover_mime_type
        
        return result 