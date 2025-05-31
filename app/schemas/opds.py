"""
OPDS数据模式

定义OPDS目录服务的数据结构。
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class OPDSLink(BaseModel):
    """OPDS链接"""
    rel: str = Field(..., description="链接关系")
    href: str = Field(..., description="链接地址")
    type: Optional[str] = Field(None, description="内容类型")
    title: Optional[str] = Field(None, description="链接标题")


class OPDSAuthor(BaseModel):
    """OPDS作者信息"""
    name: str = Field(..., description="作者姓名")
    uri: Optional[str] = Field(None, description="作者URI")


class OPDSCategory(BaseModel):
    """OPDS分类"""
    term: str = Field(..., description="分类标识")
    label: Optional[str] = Field(None, description="分类标签")
    scheme: Optional[str] = Field(None, description="分类方案")


class OPDSEntry(BaseModel):
    """OPDS条目"""
    id: str = Field(..., description="条目ID")
    title: str = Field(..., description="标题")
    updated: datetime = Field(..., description="更新时间")
    summary: Optional[str] = Field(None, description="摘要")
    content: Optional[str] = Field(None, description="内容")
    authors: List[OPDSAuthor] = Field(default_factory=list, description="作者列表")
    categories: List[OPDSCategory] = Field(default_factory=list, description="分类列表")
    links: List[OPDSLink] = Field(default_factory=list, description="链接列表")
    rights: Optional[str] = Field(None, description="版权信息")
    published: Optional[datetime] = Field(None, description="发布时间")
    
    class Config:
        from_attributes = True


class OPDSFeed(BaseModel):
    """OPDS源"""
    id: str = Field(..., description="源ID")
    title: str = Field(..., description="源标题") 
    subtitle: Optional[str] = Field(None, description="源副标题")
    updated: datetime = Field(..., description="更新时间")
    icon: Optional[str] = Field(None, description="图标")
    authors: List[OPDSAuthor] = Field(default_factory=list, description="作者列表")
    links: List[OPDSLink] = Field(default_factory=list, description="链接列表")
    entries: List[OPDSEntry] = Field(default_factory=list, description="条目列表")
    total_results: Optional[int] = Field(None, description="总结果数")
    items_per_page: Optional[int] = Field(None, description="每页条目数")
    start_index: Optional[int] = Field(None, description="起始索引")
    
    class Config:
        from_attributes = True


class BookEntry(BaseModel):
    """书籍条目（用于生成OPDS）"""
    id: int = Field(..., description="书籍ID")
    title: str = Field(..., description="书籍标题")
    author: Optional[str] = Field(None, description="作者")
    description: Optional[str] = Field(None, description="描述")
    publisher: Optional[str] = Field(None, description="出版商")
    published_date: Optional[datetime] = Field(None, description="出版日期")
    language: Optional[str] = Field(None, description="语言")
    genre: Optional[str] = Field(None, description="类型")
    series: Optional[str] = Field(None, description="系列")
    series_index: Optional[int] = Field(None, description="系列索引")
    file_format: str = Field(..., description="文件格式")
    file_size: int = Field(..., description="文件大小")
    has_cover: bool = Field(..., description="是否有封面")
    download_count: int = Field(..., description="下载次数")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class OPDSNavigationEntry(BaseModel):
    """OPDS导航条目"""
    title: str = Field(..., description="标题")
    href: str = Field(..., description="链接")
    content_type: str = Field(default="application/atom+xml;profile=opds-catalog;kind=navigation", description="内容类型")
    summary: Optional[str] = Field(None, description="摘要")


class OPDSCatalogInfo(BaseModel):
    """OPDS目录信息"""
    title: str = Field(..., description="目录标题")
    subtitle: Optional[str] = Field(None, description="目录副标题")
    author: str = Field(..., description="作者")
    icon: Optional[str] = Field(None, description="图标")
    base_url: str = Field(..., description="基础URL") 