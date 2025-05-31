"""
同步数据模式

定义KOReader同步API的数据结构，兼容kosync协议。
"""

from datetime import datetime
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator


class SyncProgressCreate(BaseModel):
    """同步进度创建请求 - KOReader kosync兼容"""
    document: str = Field(..., description="文档名称/路径")
    progress: Union[str, float] = Field(..., description="阅读进度")
    percentage: float = Field(..., description="百分比")
    device: Optional[str] = Field(None, description="设备标识")
    device_id: Optional[str] = Field(None, description="设备ID")
    page: Optional[int] = Field(None, description="页码")
    pos: Optional[str] = Field(None, description="位置信息")
    chapter: Optional[str] = Field(None, description="章节信息")
    timestamp: Optional[int] = Field(None, description="时间戳")
    
    @validator("progress")
    def validate_progress(cls, v):
        """验证并转换进度值"""
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                raise ValueError("进度值必须是有效的数字")
        return float(v)
    
    @validator("percentage")
    def validate_percentage(cls, v):
        """验证百分比"""
        if not 0 <= v <= 100:
            raise ValueError("百分比必须在0-100之间")
        return v


class SyncProgressUpdate(BaseModel):
    """同步进度更新请求"""
    progress: Optional[float] = Field(None, description="阅读进度")
    percentage: Optional[float] = Field(None, description="百分比")
    page: Optional[int] = Field(None, description="页码")
    pos: Optional[str] = Field(None, description="位置信息")
    chapter: Optional[str] = Field(None, description="章节信息")


class SyncProgressResponse(BaseModel):
    """同步进度响应数据"""
    id: int = Field(..., description="进度ID")
    user_id: int = Field(..., description="用户ID")
    device_id: Optional[int] = Field(None, description="设备ID")
    book_id: Optional[int] = Field(None, description="书籍ID")
    document: str = Field(..., description="文档名称")
    document_hash: Optional[str] = Field(None, description="文档哈希")
    progress: float = Field(..., description="阅读进度")
    percentage: float = Field(..., description="百分比")
    reading_percentage: str = Field(..., description="格式化百分比")
    device_name: Optional[str] = Field(None, description="设备名称")
    device: Optional[str] = Field(None, description="设备标识")
    page: Optional[int] = Field(None, description="页码")
    pos: Optional[str] = Field(None, description="位置信息")
    chapter: Optional[str] = Field(None, description="章节信息")
    book_title: Optional[str] = Field(None, description="书籍标题")
    book_author: Optional[str] = Field(None, description="书籍作者")
    last_sync_at: datetime = Field(..., description="最后同步时间")
    sync_count: int = Field(..., description="同步次数")
    is_finished: bool = Field(..., description="是否完成阅读")
    is_recently_synced: bool = Field(..., description="是否最近同步")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class KosyncProgress(BaseModel):
    """KOReader kosync格式的进度数据"""
    document: str = Field(..., description="文档名称")
    progress: str = Field(..., description="进度字符串")
    percentage: float = Field(..., description="百分比")
    device: Optional[str] = Field(None, description="设备标识")
    device_id: Optional[str] = Field(None, description="设备ID")
    timestamp: Optional[int] = Field(None, description="时间戳")
    page: Optional[int] = Field(None, description="页码")
    pos: Optional[str] = Field(None, description="位置")
    chapter: Optional[str] = Field(None, description="章节")
    
    class Config:
        # 允许额外字段以保持kosync兼容性
        extra = "allow"


class SyncProgressList(BaseModel):
    """同步进度列表"""
    total: int = Field(..., description="总数")
    items: list[SyncProgressResponse] = Field(..., description="进度列表")
    page: int = Field(default=1, description="页码")
    size: int = Field(default=20, description="每页大小")
    
    class Config:
        from_attributes = True


# KOReader kosync API兼容响应
class KosyncProgressResponse(BaseModel):
    """kosync进度响应 - 完全兼容KOReader"""
    document: str
    progress: str
    percentage: float
    device: Optional[str] = None
    device_id: Optional[str] = None
    timestamp: Optional[int] = None
    
    @classmethod
    def from_sync_progress(cls, sync_progress) -> "KosyncProgressResponse":
        """从SyncProgress模型转换"""
        return cls(
            document=sync_progress.document,
            progress=str(sync_progress.progress),
            percentage=sync_progress.percentage,
            device=sync_progress.device or sync_progress.device_name,
            device_id=str(sync_progress.device_id) if sync_progress.device_id else None,
            timestamp=int(sync_progress.last_sync_at.timestamp()) if sync_progress.last_sync_at else None,
        )


class KosyncErrorResponse(BaseModel):
    """kosync错误响应"""
    message: str = Field(..., description="错误信息")
    code: Optional[int] = Field(None, description="错误代码") 