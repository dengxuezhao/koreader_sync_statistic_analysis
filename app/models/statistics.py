"""
统计数据模型

存储KOReader设备上传的阅读统计数据。
"""

from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class ReadingStatistics(Base):
    """阅读统计模型
    
    存储KOReader上传的详细阅读统计数据。
    """
    __tablename__ = "reading_statistics"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联信息
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=True, index=True)
    
    # 设备和文件信息
    device_name = Column(String(100), nullable=True, index=True)
    file_path = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=True)
    
    # 书籍信息
    book_title = Column(String(500), nullable=True)
    book_author = Column(String(255), nullable=True)
    book_format = Column(String(20), nullable=True)
    
    # 阅读进度统计
    total_pages = Column(Integer, nullable=True)
    read_pages = Column(Integer, nullable=True)
    current_page = Column(Integer, nullable=True)
    reading_progress = Column(Float, default=0.0)  # 百分比 0.0-100.0
    
    # 时间统计
    total_reading_time = Column(Integer, default=0)  # 秒
    session_reading_time = Column(Integer, default=0)  # 当前会话时间
    last_read_time = Column(DateTime, nullable=True)
    first_read_time = Column(DateTime, nullable=True)
    
    # 阅读行为统计
    page_turns = Column(Integer, default=0)
    highlights_count = Column(Integer, default=0)
    notes_count = Column(Integer, default=0)
    bookmarks_count = Column(Integer, default=0)
    
    # 原始统计数据
    raw_statistics = Column(JSON, nullable=True)  # 存储完整的原始统计数据
    
    # WebDAV文件信息
    webdav_file_path = Column(String(500), nullable=True)  # WebDAV中的文件路径
    webdav_uploaded_at = Column(DateTime, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 关系
    user = relationship("User", back_populates="reading_statistics")
    device = relationship("Device", back_populates="reading_statistics") 
    book = relationship("Book", back_populates="reading_statistics")
    
    def __repr__(self) -> str:
        return f"<ReadingStatistics(id={self.id}, book='{self.book_title}', progress={self.reading_progress}%)>"
    
    @property
    def reading_time_formatted(self) -> str:
        """格式化阅读时间"""
        if not self.total_reading_time:
            return "0分钟"
        
        hours = self.total_reading_time // 3600
        minutes = (self.total_reading_time % 3600) // 60
        
        if hours > 0:
            return f"{hours}小时{minutes}分钟"
        else:
            return f"{minutes}分钟"
    
    @property
    def completion_status(self) -> str:
        """获取完成状态"""
        if self.reading_progress >= 100:
            return "已完成"
        elif self.reading_progress >= 80:
            return "接近完成"
        elif self.reading_progress >= 50:
            return "进行中"
        elif self.reading_progress > 0:
            return "已开始"
        else:
            return "未开始"
    
    def update_from_koreader_data(self, stats_data: Dict[str, Any]) -> None:
        """从KOReader统计数据更新记录"""
        # 书籍信息
        if stats_data.get("title"):
            self.book_title = stats_data["title"]
        if stats_data.get("authors"):
            self.book_author = stats_data["authors"]
        if stats_data.get("file"):
            self.file_path = stats_data["file"]
            self.file_name = stats_data["file"].split("/")[-1] if "/" in stats_data["file"] else stats_data["file"]
        
        # 进度信息
        if stats_data.get("pages"):
            self.total_pages = stats_data["pages"]
        if stats_data.get("page"):
            self.current_page = stats_data["page"]
            self.read_pages = stats_data["page"]
        if stats_data.get("percentage"):
            self.reading_progress = stats_data["percentage"]
        
        # 时间信息
        if stats_data.get("time_spent_reading"):
            self.total_reading_time = stats_data["time_spent_reading"]
        if stats_data.get("last_time"):
            try:
                # 尝试解析时间戳
                if isinstance(stats_data["last_time"], (int, float)):
                    self.last_read_time = datetime.fromtimestamp(stats_data["last_time"])
                elif isinstance(stats_data["last_time"], str):
                    self.last_read_time = datetime.fromisoformat(stats_data["last_time"].replace("Z", "+00:00"))
            except:
                pass
        
        # 设备信息
        if stats_data.get("device_id"):
            self.device_name = stats_data["device_id"]
        
        # 保存原始数据
        self.raw_statistics = stats_data
        self.updated_at = datetime.utcnow() 