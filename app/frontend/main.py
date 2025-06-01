"""
Kompanion Streamlit 前端主应用

现代化的数据分析界面，集成到主项目中
"""

import streamlit as st
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.frontend.config import PAGE_CONFIG
from app.frontend.components.design_system import apply_custom_css
from app.frontend.components.navigation import (
    check_authentication, 
    login_form, 
    sidebar_navigation, 
    get_current_page
)

# 页面模块导入
from app.frontend.pages.overview import show_overview_page

# 导入页面模块
try:
    from app.frontend.pages.devices import show_devices_page
    from app.frontend.pages.statistics import show_statistics_page
    PAGES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"部分页面模块导入失败: {e}")
    PAGES_AVAILABLE = False

def main():
    """Streamlit 应用主函数"""
    try:
        # 配置页面
        st.set_page_config(**PAGE_CONFIG)
        
        # 应用自定义样式
        apply_custom_css()
        
        # 检查认证状态
        if not check_authentication():
            # 显示登录页面
            login_form()
            return
        
        # 显示导航栏
        sidebar_navigation()
        
        # 获取当前页面
        current_page = get_current_page()
        
        # 根据当前页面显示内容
        if current_page == "overview":
            show_overview_page()
        elif current_page == "devices":
            if PAGES_AVAILABLE:
                show_devices_page()
            else:
                st.error("设备管理页面暂时不可用")
        elif current_page == "statistics":
            if PAGES_AVAILABLE:
                show_statistics_page()
            else:
                st.error("阅读统计页面暂时不可用")
        elif current_page == "users":
            st.info("👥 用户分析页面正在开发中...")
        elif current_page == "content":
            st.info("📚 内容表现页面正在开发中...")
        elif current_page == "settings":
            require_admin()
            st.info("⚙️ 系统设置页面正在开发中...")
        else:
            # 默认显示总览页面
            show_overview_page()
            
    except Exception as e:
        st.error(f"应用启动失败: {str(e)}")
        st.info("请检查后端服务是否正常运行")

def show_users_page():
    """用户分析页面（占位符）"""
    st.markdown("# 👥 用户分析")
    st.info("用户分析页面正在开发中...")

def show_content_page():
    """内容表现页面（占位符）"""
    st.markdown("# 📚 内容表现")
    st.info("内容表现页面正在开发中...")

def show_devices_page():
    """设备管理页面（占位符）"""
    st.markdown("# 📱 设备管理")
    st.info("设备管理页面正在开发中...")

def show_statistics_page():
    """阅读统计页面（占位符）"""
    st.markdown("# 📈 阅读统计")
    st.info("阅读统计页面正在开发中...")

def show_settings_page():
    """系统设置页面（占位符）"""
    st.markdown("# ⚙️ 系统设置")
    st.info("系统设置页面正在开发中...")

if __name__ == "__main__":
    main() 