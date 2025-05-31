#!/usr/bin/env python3
"""
数据库初始化脚本

创建数据库表并初始化基础数据，包括创建管理员用户。
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import settings
from app.core.database import init_database, check_database_health
from app.models import User, Device, Book, SyncProgress

logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    print("正在初始化Kompanion数据库...")
    print(f"数据库类型: {settings.DATABASE_TYPE}")
    
    if settings.DATABASE_TYPE == "postgresql":
        print(f"PostgreSQL URL: {settings.database_url_async}")
    else:
        print(f"SQLite路径: {settings.SQLITE_DB_PATH}")
    
    try:
        # 检查数据库连接
        print("检查数据库连接...")
        is_healthy = await check_database_health()
        if not is_healthy:
            print("❌ 数据库连接失败！请检查配置。")
            return False
        
        print("✅ 数据库连接正常")
        
        # 初始化数据库
        print("创建数据库表...")
        await init_database()
        print("✅ 数据库表创建完成")
        
        # 显示配置信息
        if settings.AUTH_USERNAME and settings.AUTH_PASSWORD:
            print(f"✅ 管理员用户已创建: {settings.AUTH_USERNAME}")
            print("💡 可以使用此账户登录Web界面和API")
        else:
            print("⚠️  未配置默认管理员账户")
            print("   请设置 KOMPANION_AUTH_USERNAME 和 KOMPANION_AUTH_PASSWORD 环境变量")
        
        print("\n🎉 数据库初始化完成！")
        print(f"服务将在 http://{settings.HOST}:{settings.PORT} 启动")
        return True
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        print(f"❌ 数据库初始化失败: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 