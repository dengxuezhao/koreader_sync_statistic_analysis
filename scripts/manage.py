#!/usr/bin/env python3
"""
Kompanion 系统管理脚本

提供数据库管理、用户管理、系统维护等功能的统一入口。

用法：
    python scripts/manage.py <command> [options]
    
命令：
    db init         - 初始化数据库
    db migrate      - 运行数据库迁移
    db reset        - 重置数据库 (谨慎使用)
    user create     - 创建用户
    user list       - 列出用户
    user delete     - 删除用户
    stats           - 显示系统统计
    cleanup         - 清理临时文件
    backup          - 备份数据库
    restore         - 恢复数据库
"""

import asyncio
import sys
import os
import argparse
import json
import shutil
import subprocess
from datetime import datetime
from typing import Optional, List
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.core.database import async_session_maker, engine, Base
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import User, Device, Book, SyncProgress, ReadingStatistics


class DatabaseManager:
    """数据库管理器"""
    
    @staticmethod
    async def init_database():
        """初始化数据库"""
        print("🔧 初始化数据库...")
        
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print("✅ 数据库初始化成功")
        except Exception as e:
            print(f"❌ 数据库初始化失败: {e}")
            return False
        
        return True
    
    @staticmethod
    async def migrate_database():
        """运行数据库迁移"""
        print("🔧 运行数据库迁移...")
        
        try:
            # 运行Alembic迁移
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            
            if result.returncode == 0:
                print("✅ 数据库迁移成功")
                if result.stdout:
                    print(result.stdout)
                return True
            else:
                print(f"❌ 数据库迁移失败: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ 数据库迁移失败: {e}")
            return False
    
    @staticmethod
    async def reset_database():
        """重置数据库"""
        print("⚠️  警告：这将删除所有数据！")
        confirm = input("确认重置数据库? (yes/no): ").strip().lower()
        
        if confirm != "yes":
            print("❌ 取消重置")
            return False
        
        print("🔧 重置数据库...")
        
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
            print("✅ 数据库重置成功")
            return True
        except Exception as e:
            print(f"❌ 数据库重置失败: {e}")
            return False
    
    @staticmethod
    async def backup_database(backup_path: str):
        """备份数据库"""
        print(f"🔧 备份数据库到 {backup_path}...")
        
        if settings.DATABASE_URL.startswith("postgresql"):
            # PostgreSQL备份
            db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
            cmd = f"pg_dump {db_url} > {backup_path}"
        elif settings.DATABASE_URL.startswith("sqlite"):
            # SQLite备份
            db_file = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
            cmd = f"cp {db_file} {backup_path}"
        else:
            print("❌ 不支持的数据库类型")
            return False
        
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ 数据库备份成功")
                return True
            else:
                print(f"❌ 数据库备份失败: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ 数据库备份失败: {e}")
            return False


class UserManager:
    """用户管理器"""
    
    @staticmethod
    async def create_user(username: str, email: str, password: str, is_admin: bool = False):
        """创建用户"""
        async with async_session_maker() as session:
            # 检查用户是否已存在
            result = await session.execute(
                select(User).where(User.username == username)
            )
            if result.scalar_one_or_none():
                print(f"❌ 用户 '{username}' 已存在")
                return False
            
            # 创建新用户
            user = User(
                username=username,
                email=email,
                hashed_password=get_password_hash(password),
                is_active=True,
                is_admin=is_admin
            )
            
            session.add(user)
            await session.commit()
            await session.refresh(user)
            
            user_type = "管理员" if is_admin else "普通用户"
            print(f"✅ {user_type} '{username}' 创建成功 (ID: {user.id})")
            return True
    
    @staticmethod
    async def list_users():
        """列出所有用户"""
        async with async_session_maker() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
            
            if not users:
                print("📭 没有用户")
                return
            
            print("👥 用户列表:")
            print("-" * 80)
            print(f"{'ID':<5} {'用户名':<20} {'邮箱':<30} {'类型':<10} {'状态':<8} {'创建时间'}")
            print("-" * 80)
            
            for user in users:
                user_type = "管理员" if user.is_admin else "普通用户"
                status = "活跃" if user.is_active else "禁用"
                created_at = user.created_at.strftime("%Y-%m-%d %H:%M")
                
                print(f"{user.id:<5} {user.username:<20} {user.email:<30} {user_type:<10} {status:<8} {created_at}")
    
    @staticmethod
    async def delete_user(username: str):
        """删除用户"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                print(f"❌ 用户 '{username}' 不存在")
                return False
            
            if user.is_admin:
                print(f"⚠️  警告：'{username}' 是管理员用户")
                confirm = input("确认删除管理员用户? (yes/no): ").strip().lower()
                if confirm != "yes":
                    print("❌ 取消删除")
                    return False
            
            await session.delete(user)
            await session.commit()
            
            print(f"✅ 用户 '{username}' 删除成功")
            return True


class SystemManager:
    """系统管理器"""
    
    @staticmethod
    async def show_statistics():
        """显示系统统计信息"""
        async with async_session_maker() as session:
            # 用户统计
            user_count = await session.scalar(select(func.count(User.id)))
            admin_count = await session.scalar(
                select(func.count(User.id)).where(User.is_admin == True)
            )
            active_user_count = await session.scalar(
                select(func.count(User.id)).where(User.is_active == True)
            )
            
            # 设备统计
            device_count = await session.scalar(select(func.count(Device.id)))
            
            # 书籍统计
            book_count = await session.scalar(select(func.count(Book.id)))
            available_book_count = await session.scalar(
                select(func.count(Book.id)).where(Book.is_available == True)
            )
            
            # 同步统计
            sync_count = await session.scalar(select(func.count(SyncProgress.id)))
            
            # 阅读统计
            reading_stats_count = await session.scalar(select(func.count(ReadingStatistics.id)))
            
            # 存储统计
            total_size = await session.scalar(select(func.sum(Book.file_size))) or 0
            
            print("📊 Kompanion 系统统计")
            print("=" * 50)
            print(f"👥 用户信息:")
            print(f"   总用户数: {user_count}")
            print(f"   管理员数: {admin_count}")
            print(f"   活跃用户: {active_user_count}")
            print()
            print(f"📱 设备信息:")
            print(f"   注册设备: {device_count}")
            print()
            print(f"📚 书籍信息:")
            print(f"   总书籍数: {book_count}")
            print(f"   可用书籍: {available_book_count}")
            print(f"   存储大小: {total_size / 1024 / 1024:.2f} MB")
            print()
            print(f"🔄 同步信息:")
            print(f"   同步记录: {sync_count}")
            print()
            print(f"📈 阅读统计:")
            print(f"   统计记录: {reading_stats_count}")
    
    @staticmethod
    def cleanup_temp_files():
        """清理临时文件"""
        print("🔧 清理临时文件...")
        
        temp_dirs = [
            "/tmp/kompanion",
            "./temp",
            "./__pycache__",
            "./app/__pycache__",
        ]
        
        cleaned_count = 0
        
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    cleaned_count += 1
                    print(f"   删除: {temp_dir}")
                except Exception as e:
                    print(f"   警告: 无法删除 {temp_dir}: {e}")
        
        # 清理日志文件
        log_files = [
            "./app.log",
            "./error.log",
            "./access.log"
        ]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    os.remove(log_file)
                    cleaned_count += 1
                    print(f"   删除: {log_file}")
                except Exception as e:
                    print(f"   警告: 无法删除 {log_file}: {e}")
        
        print(f"✅ 清理完成，共清理 {cleaned_count} 个项目")
    
    @staticmethod
    def check_system_health():
        """检查系统健康状态"""
        print("🩺 系统健康检查")
        print("-" * 30)
        
        # 检查Python版本
        python_version = sys.version_info
        if python_version >= (3, 12):
            print("✅ Python 版本: OK")
        else:
            print(f"⚠️  Python 版本: {python_version.major}.{python_version.minor} (推荐 3.12+)")
        
        # 检查必需目录
        required_dirs = [
            settings.BOOK_STORAGE_PATH,
            settings.COVER_STORAGE_PATH,
            settings.WEBDAV_ROOT_PATH
        ]
        
        for dir_path in required_dirs:
            if os.path.exists(dir_path):
                print(f"✅ 目录存在: {dir_path}")
            else:
                print(f"⚠️  目录不存在: {dir_path}")
                try:
                    os.makedirs(dir_path, exist_ok=True)
                    print(f"   自动创建: {dir_path}")
                except Exception as e:
                    print(f"   创建失败: {e}")
        
        # 检查数据库连接
        try:
            import asyncio
            async def test_db():
                async with engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
            
            asyncio.run(test_db())
            print("✅ 数据库连接: OK")
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
        
        print("🩺 健康检查完成")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Kompanion 系统管理工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 数据库命令
    db_parser = subparsers.add_parser("db", help="数据库管理")
    db_subparsers = db_parser.add_subparsers(dest="db_action")
    
    db_subparsers.add_parser("init", help="初始化数据库")
    db_subparsers.add_parser("migrate", help="运行数据库迁移")
    db_subparsers.add_parser("reset", help="重置数据库")
    
    backup_parser = db_subparsers.add_parser("backup", help="备份数据库")
    backup_parser.add_argument("--path", "-p", default=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql", help="备份文件路径")
    
    # 用户命令
    user_parser = subparsers.add_parser("user", help="用户管理")
    user_subparsers = user_parser.add_subparsers(dest="user_action")
    
    create_user_parser = user_subparsers.add_parser("create", help="创建用户")
    create_user_parser.add_argument("--username", "-u", required=True, help="用户名")
    create_user_parser.add_argument("--email", "-e", required=True, help="邮箱")
    create_user_parser.add_argument("--password", "-p", required=True, help="密码")
    create_user_parser.add_argument("--admin", action="store_true", help="创建管理员用户")
    
    user_subparsers.add_parser("list", help="列出用户")
    
    delete_user_parser = user_subparsers.add_parser("delete", help="删除用户")
    delete_user_parser.add_argument("username", help="要删除的用户名")
    
    # 系统命令
    subparsers.add_parser("stats", help="显示系统统计")
    subparsers.add_parser("cleanup", help="清理临时文件")
    subparsers.add_parser("health", help="系统健康检查")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == "db":
            if args.db_action == "init":
                await DatabaseManager.init_database()
            elif args.db_action == "migrate":
                await DatabaseManager.migrate_database()
            elif args.db_action == "reset":
                await DatabaseManager.reset_database()
            elif args.db_action == "backup":
                await DatabaseManager.backup_database(args.path)
            else:
                db_parser.print_help()
        
        elif args.command == "user":
            if args.user_action == "create":
                await UserManager.create_user(
                    args.username, 
                    args.email, 
                    args.password, 
                    args.admin
                )
            elif args.user_action == "list":
                await UserManager.list_users()
            elif args.user_action == "delete":
                await UserManager.delete_user(args.username)
            else:
                user_parser.print_help()
        
        elif args.command == "stats":
            await SystemManager.show_statistics()
        
        elif args.command == "cleanup":
            SystemManager.cleanup_temp_files()
        
        elif args.command == "health":
            SystemManager.check_system_health()
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n❌ 操作被用户中断")
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 