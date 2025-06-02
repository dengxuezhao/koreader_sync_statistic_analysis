#!/usr/bin/env python3
"""
前端功能测试脚本
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """测试关键模块导入"""
    try:
        print("测试导入...")
        
        # 测试配置导入
        from app.frontend.config import PAGE_CONFIG, NAVIGATION_CONFIG
        print("✅ 配置模块导入成功")
        
        # 测试组件导入
        from app.frontend.components.navigation import check_authentication
        from app.frontend.components.design_system import apply_custom_css
        print("✅ 组件模块导入成功")
        
        # 测试页面导入
        from app.frontend.pages.overview import show_overview_page
        print("✅ 概览页面导入成功")
        
        from app.frontend.pages.statistics import show_statistics_page
        print("✅ 统计页面导入成功")
        
        # 测试API客户端
        from app.frontend.api_client import StatisticsAPI
        print("✅ API客户端导入成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_config():
    """测试配置是否正确"""
    try:
        from app.frontend.config import PAGE_CONFIG, NAVIGATION_CONFIG, API_BASE_URL
        
        print(f"页面配置: {PAGE_CONFIG.get('page_title', 'N/A')}")
        print(f"API地址: {API_BASE_URL}")
        print(f"导航页面数量: {len(NAVIGATION_CONFIG.get('pages', []))}")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🧪 开始前端功能测试...\n")
    
    all_passed = True
    
    # 测试导入
    print("=" * 50)
    print("📦 模块导入测试")
    print("=" * 50)
    if not test_imports():
        all_passed = False
    
    print("\n" + "=" * 50)
    print("⚙️ 配置测试")
    print("=" * 50)
    if not test_config():
        all_passed = False
    
    print("\n" + "=" * 50)
    print("📊 测试结果")
    print("=" * 50)
    
    if all_passed:
        print("✅ 所有测试通过！")
        print("\n🚀 前端应用应该能正常运行")
        print("📍 访问地址: http://localhost:8501")
        print("📊 统计页面: http://localhost:8501/statistics")
    else:
        print("❌ 部分测试失败")
        print("\n🔧 请检查:")
        print("1. 依赖包是否正确安装")
        print("2. 项目结构是否完整")
        print("3. Python路径是否正确")

if __name__ == "__main__":
    main() 