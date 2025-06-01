"""
应用程序配置管理

使用pydantic-settings管理环境变量配置，支持KOReader兼容的完整配置选项。
"""

import logging
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional, List

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用程序配置类
    
    使用环境变量进行配置，兼容原始kompanion的配置命名。
    """
    
    # 应用基础配置
    APP_NAME: str = "Kompanion Python"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8080, alias="KOMPANION_HTTP_PORT")
    
    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", alias="KOMPANION_LOG_LEVEL")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Optional[str] = None
    
    # 安全配置
    SECRET_KEY: str = Field(default="kompanion-secret-key-change-in-production")
    JWT_SECRET_KEY: str = Field(default="jwt-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天
    
    # 数据库配置
    DATABASE_TYPE: str = "sqlite"  # sqlite 或 postgresql
    
    # PostgreSQL配置
    POSTGRES_URL: Optional[str] = Field(default=None, alias="KOMPANION_PG_URL")
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "kompanion"
    POSTGRES_PASSWORD: str = "kompanion"
    POSTGRES_DB: str = "kompanion"
    
    # SQLite配置
    SQLITE_DB_PATH: str = "data/kompanion.db"
    
    # 认证配置
    AUTH_USERNAME: Optional[str] = Field(default=None, alias="KOMPANION_AUTH_USERNAME")
    AUTH_PASSWORD: Optional[str] = Field(default=None, alias="KOMPANION_AUTH_PASSWORD")
    AUTH_STORAGE: str = Field(default="postgres", alias="KOMPANION_AUTH_STORAGE")
    
    # 书籍存储配置
    BOOK_STORAGE_TYPE: str = Field(default="database", alias="KOMPANION_BSTORAGE_TYPE")
    BOOK_STORAGE_PATH: str = Field(default="./storage", description="书籍存储目录")
    MAX_FILE_SIZE: int = Field(default=500 * 1024 * 1024, description="最大文件大小（字节）")  # 500MB
    SUPPORTED_FORMATS: List[str] = Field(
        default_factory=lambda: ["epub", "pdf", "mobi", "azw", "azw3", "fb2", "txt", "rtf", "djvu", "cbz", "cbr"],
        description="支持的书籍格式"
    )
    
    # OPDS配置
    OPDS_TITLE: str = "Kompanion Library"
    OPDS_SUBTITLE: str = "KOReader Compatible Book Library"
    OPDS_AUTHOR: str = "Kompanion"
    OPDS_ICON: str = "/static/icon.png"
    
    # WebDAV配置
    WEBDAV_ENABLED: bool = True
    WEBDAV_ROOT_PATH: str = Field(default="./data/webdav", description="WebDAV根目录路径")
    WEBDAV_AUTH_REQUIRED: bool = True
    WEBDAV_MAX_FILE_SIZE: int = Field(default=100 * 1024 * 1024, description="WebDAV最大文件大小")  # 100MB
    
    # CORS配置
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"],
        description="允许的CORS源"
    )
    CORS_CREDENTIALS: bool = Field(default=True, description="允许CORS凭据")
    CORS_METHODS: List[str] = Field(default_factory=lambda: ["*"], description="允许的CORS方法")
    CORS_HEADERS: List[str] = Field(default_factory=lambda: ["*"], description="允许的CORS头部")
    
    # 性能配置
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    REQUEST_TIMEOUT: int = 30
    
    # 开发配置
    RELOAD: bool = False
    
    # 封面设置
    COVER_MAX_WIDTH: int = Field(default=400, description="封面最大宽度")
    COVER_MAX_HEIGHT: int = Field(default=600, description="封面最大高度")
    THUMBNAIL_MAX_WIDTH: int = Field(default=150, description="缩略图最大宽度")
    THUMBNAIL_MAX_HEIGHT: int = Field(default=225, description="缩略图最大高度")
    
    # 性能优化配置
    REDIS_URL: str = "redis://localhost:6379/0"
    ENABLE_REDIS_CACHE: bool = False  # 默认禁用，避免连接错误
    CACHE_TTL_DEFAULT: int = 3600  # 默认缓存1小时
    CACHE_TTL_OPDS: int = 1800     # OPDS缓存30分钟
    CACHE_TTL_BOOKS: int = 7200    # 书籍列表缓存2小时
    CACHE_TTL_STATS: int = 300     # 统计数据缓存5分钟
    
    # 数据库性能配置
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True
    DB_ECHO: bool = False
    
    # 并发控制
    GUNICORN_WORKERS: int = 4
    GUNICORN_WORKER_CLASS: str = "uvicorn.workers.UvicornWorker"
    GUNICORN_MAX_REQUESTS: int = 1000
    GUNICORN_MAX_REQUESTS_JITTER: int = 100
    GUNICORN_TIMEOUT: int = 120
    
    # 缓存预热配置
    ENABLE_CACHE_WARMUP: bool = True
    CACHE_WARMUP_ON_STARTUP: bool = False
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """验证日志级别"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"日志级别必须是 {valid_levels} 之一")
        return v.upper()
    
    @validator("DATABASE_TYPE")
    def validate_database_type(cls, v):
        """验证数据库类型"""
        valid_types = ["sqlite", "postgresql"]
        if v.lower() not in valid_types:
            raise ValueError(f"数据库类型必须是 {valid_types} 之一")
        return v.lower()
    
    @validator("BOOK_STORAGE_TYPE")
    def validate_book_storage_type(cls, v):
        """验证书籍存储类型"""
        valid_types = ["database", "filesystem", "memory"]
        if v.lower() not in valid_types:
            raise ValueError(f"书籍存储类型必须是 {valid_types} 之一")
        return v.lower()
    
    @property
    def database_url_async(self) -> str:
        """异步数据库连接URL"""
        if self.DATABASE_TYPE == "postgresql":
            if self.POSTGRES_URL:
                # 将同步URL转换为异步URL
                url = self.POSTGRES_URL
                if url.startswith("postgresql://"):
                    return url.replace("postgresql://", "postgresql+asyncpg://")
                return url
            else:
                return (
                    f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                    f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
                )
        else:
            # SQLite异步连接
            db_path = Path(self.SQLITE_DB_PATH)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{db_path}"
    
    @property 
    def database_url_sync(self) -> str:
        """同步数据库连接URL（用于Alembic迁移）"""
        if self.DATABASE_TYPE == "postgresql":
            if self.POSTGRES_URL:
                return self.POSTGRES_URL
            else:
                return (
                    f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                    f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
                )
        else:
            db_path = Path(self.SQLITE_DB_PATH)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{db_path}"
    
    def setup_logging(self) -> None:
        """配置日志系统"""
        # 配置根日志器
        logging.basicConfig(
            level=getattr(logging, self.LOG_LEVEL),
            format=self.LOG_FORMAT,
            handlers=self._get_log_handlers()
        )
        
        # 设置第三方库日志级别
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
        logging.getLogger("alembic").setLevel(logging.INFO)
        
        # 应用日志器
        app_logger = logging.getLogger("kompanion")
        app_logger.setLevel(getattr(logging, self.LOG_LEVEL))
        
        if self.DEBUG:
            # 开发模式下显示更多调试信息
            logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    
    def _get_log_handlers(self) -> List[logging.Handler]:
        """获取日志处理器"""
        handlers = []
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(self.LOG_FORMAT))
        handlers.append(console_handler)
        
        # 文件处理器（如果配置了日志文件）
        if self.LOG_FILE:
            log_path = Path(self.LOG_FILE)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(self.LOG_FORMAT))
            handlers.append(file_handler)
        
        return handlers
    
    def create_directories(self) -> None:
        """创建必要的目录"""
        directories = []
        
        # 数据目录
        if self.DATABASE_TYPE == "sqlite":
            db_path = Path(self.SQLITE_DB_PATH)
            directories.append(db_path.parent)
        
        # 书籍存储目录
        if self.BOOK_STORAGE_TYPE == "filesystem":
            directories.append(Path(self.BOOK_STORAGE_PATH))
        
        # WebDAV目录
        if self.WEBDAV_ENABLED:
            directories.append(Path(self.WEBDAV_ROOT_PATH))
        
        # 日志目录
        if self.LOG_FILE:
            directories.append(Path(self.LOG_FILE).parent)
        
        # 创建目录
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8", 
        "case_sensitive": True,
        "populate_by_name": True,
        "extra": "allow"  # 允许额外字段
    }


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（带缓存）"""
    settings = Settings()
    
    # 初始化配置
    settings.setup_logging()
    settings.create_directories()
    
    return settings


# 全局配置实例
settings = get_settings()

# 导出常用配置
__all__ = ["settings", "get_settings", "Settings"] 