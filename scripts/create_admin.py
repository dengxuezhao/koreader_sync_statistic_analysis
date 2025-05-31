#!/usr/bin/env python3
"""
创建管理员用户脚本

用法：
    python scripts/create_admin.py
    python scripts/create_admin.py --username admin --email admin@example.com
"""

import asyncio
import sys
import os
import argparse
import getpass
from typing import Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import async_session_maker, engine
from app.core.security import get_password_hash
from app.models import User


async def create_admin_user(
    username: str,
    email: str,
    password: str,
    force: bool = False
) -> None:
    """创建管理员用户"""
    
    async with async_session_maker() as session:
        # 检查用户是否已存在
        result = await session.execute(
            select(User).where(User.username == username)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            if not force:
                print(f"❌ 用户 '{username}' 已存在")
                print("使用 --force 参数覆盖现有用户")
                return
            else:
                print(f"⚠️  覆盖现有用户 '{username}'")
                await session.delete(existing_user)
        
        # 创建新的管理员用户
        admin_user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            is_active=True,
            is_admin=True
        )
        
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)
        
        print(f"✅ 管理员用户创建成功")
        print(f"   用户名: {admin_user.username}")
        print(f"   邮箱: {admin_user.email}")
        print(f"   用户ID: {admin_user.id}")
        print(f"   创建时间: {admin_user.created_at}")


async def interactive_create_admin() -> None:
    """交互式创建管理员用户"""
    print("🔧 Kompanion 管理员用户创建工具")
    print("-" * 40)
    
    # 获取用户名
    while True:
        username = input("请输入管理员用户名: ").strip()
        if username:
            break
        print("⚠️  用户名不能为空")
    
    # 获取邮箱
    while True:
        email = input("请输入管理员邮箱: ").strip()
        if email and "@" in email:
            break
        print("⚠️  请输入有效的邮箱地址")
    
    # 获取密码
    while True:
        password = getpass.getpass("请输入管理员密码: ")
        if len(password) >= 6:
            confirm_password = getpass.getpass("请确认密码: ")
            if password == confirm_password:
                break
            else:
                print("⚠️  两次输入的密码不匹配")
        else:
            print("⚠️  密码长度至少为6位")
    
    # 确认创建
    print(f"\n将创建管理员用户:")
    print(f"  用户名: {username}")
    print(f"  邮箱: {email}")
    
    confirm = input("\n确认创建? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ 取消创建")
        return
    
    # 创建用户
    await create_admin_user(username, email, password)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="创建 Kompanion 管理员用户")
    parser.add_argument("--username", "-u", help="管理员用户名")
    parser.add_argument("--email", "-e", help="管理员邮箱")
    parser.add_argument("--password", "-p", help="管理员密码")
    parser.add_argument("--force", "-f", action="store_true", help="强制覆盖现有用户")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互式模式")
    
    args = parser.parse_args()
    
    # 确保数据库已初始化
    try:
        # 测试数据库连接
        async with engine.begin() as conn:
            pass
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("请确保数据库已正确配置并运行")
        print("运行 'python scripts/init_db.py' 初始化数据库")
        sys.exit(1)
    
    if args.interactive or not all([args.username, args.email, args.password]):
        # 交互式模式
        await interactive_create_admin()
    else:
        # 命令行模式
        await create_admin_user(
            username=args.username,
            email=args.email,
            password=args.password,
            force=args.force
        )


if __name__ == "__main__":
    asyncio.run(main()) 