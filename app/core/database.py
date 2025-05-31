"""
数据库连接管理

使用SQLAlchemy 2.0的异步引擎管理数据库连接，支持PostgreSQL和SQLite。
"""

import logging
from typing import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import StaticPool

from app.core.config import settings

logger = logging.getLogger(__name__)

# 数据库元数据和基础模型
metadata = MetaData()
Base = declarative_base(metadata=metadata)

# 异步数据库引擎
engine = None
async_session_maker = None


def create_engine():
    """创建数据库引擎"""
    global engine, async_session_maker
    
    # 根据数据库类型配置引擎参数
    engine_kwargs = {
        "echo": settings.LOG_LEVEL == "DEBUG",
    }
    
    if settings.DATABASE_TYPE == "sqlite":
        # SQLite特殊配置
        engine_kwargs.update({
            "poolclass": StaticPool,
            "connect_args": {
                "check_same_thread": False,
            },
        })
    else:
        # PostgreSQL配置
        engine_kwargs.update({
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_recycle": settings.DB_POOL_RECYCLE,
            "pool_pre_ping": settings.DB_POOL_PRE_PING,
            "pool_timeout": 30,
            "connect_args": {
                "command_timeout": 60,
                "server_settings": {
                    "application_name": "kompanion",
                    "jit": "off",
                },
            },
        })
    
    # 创建异步引擎
    engine = create_async_engine(
        settings.database_url_async,
        **engine_kwargs
    )
    
    # 创建异步会话工厂
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    logger.info(f"数据库引擎已创建: {settings.DATABASE_TYPE}")
    return engine


async def create_tables():
    """创建数据库表"""
    if engine is None:
        create_engine()
    
    # 导入所有模型以确保表被创建
    # 注意：这里需要导入所有模型类
    try:
        from app.models import user, book, sync_progress, device  # noqa
        logger.info("数据库模型已导入")
    except ImportError as e:
        logger.warning(f"导入数据库模型时出现问题: {e}")
    
    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表创建完成")


async def drop_tables():
    """删除所有数据库表（谨慎使用）"""
    if engine is None:
        create_engine()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        logger.warning("所有数据库表已删除")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话
    
    用作FastAPI的依赖注入，自动管理数据库会话的生命周期。
    """
    if async_session_maker is None:
        create_engine()
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_database():
    """初始化数据库
    
    创建表并执行初始数据设置。
    """
    await create_tables()
    
    # 创建默认管理员用户（如果配置了）
    if settings.AUTH_USERNAME and settings.AUTH_PASSWORD:
        try:
            from app.services.auth_service import AuthService
            
            async with async_session_maker() as session:
                auth_service = AuthService(session)
                await auth_service.create_admin_user(
                    username=settings.AUTH_USERNAME,
                    password=settings.AUTH_PASSWORD
                )
                await session.commit()
                logger.info("默认管理员用户已创建")
        except Exception as e:
            logger.error(f"创建默认管理员用户失败: {e}")


async def check_database_health() -> bool:
    """检查数据库连接健康状态"""
    try:
        if engine is None:
            create_engine()
        
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        return False


# 初始化引擎（在模块导入时）
if engine is None:
    create_engine() 