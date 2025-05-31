"""
Alembic环境配置

支持异步数据库连接的Alembic迁移环境。
"""

import asyncio
import logging
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 导入应用配置和模型
from app.core.config import settings
from app.core.database import Base

# 这是Alembic配置对象，提供对.ini文件中值的访问
config = context.config

# 设置数据库URL
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# 解释配置文件以供Python日志记录使用
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 为自动生成迁移设置目标元数据
target_metadata = Base.metadata

# 其他在此处的值通过env.py调用
# 来自Alembic配置文件，由用户编辑的config/alembic.ini文件定义


def run_migrations_offline() -> None:
    """在"离线"模式下运行迁移。

    这会配置上下文只有一个URL，而不是Engine，
    尽管在这里Engine也是可以接受的。通过跳过Engine创建，
    我们甚至不需要DBAPI可用。

    对SQL脚本的调用发生在"事务"中，该上下文提供单个连接context。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """运行迁移的核心函数"""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在"在线"模式下运行异步迁移。

    在这种情况下，我们需要创建一个Engine
    并将连接与上下文关联。
    """
    # 为异步迁移创建配置
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.database_url_async
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在"在线"模式下运行迁移。"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online() 