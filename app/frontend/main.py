"""
Kompanion Streamlit 前端主应用

现代化的数据分析界面，集成到主项目中
"""

import streamlit as st
import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.frontend.config import PAGE_CONFIG
from app.frontend.components.design_system import apply_custom_css
from app.frontend.components.navigation import (
    check_authentication, 
    login_form, 
    sidebar_navigation, 
    get_current_page,
    require_admin
)

# 页面模块导入
from app.frontend.pages.overview import show_overview_page

# 导入页面模块，使用更健壮的导入逻辑
def import_page_modules():
    """导入页面模块，并处理导入错误"""
    modules = {}
    
    try:
        from app.frontend.pages.devices import show_devices_page
        modules['devices'] = show_devices_page
        logger.info("设备页面模块导入成功")
    except ImportError as e:
        logger.warning(f"设备页面模块导入失败: {e}")
        modules['devices'] = None
    
    try:
        from app.frontend.pages.statistics import show_statistics_page
        modules['statistics'] = show_statistics_page
        logger.info("统计页面模块导入成功")
    except ImportError as e:
        logger.warning(f"统计页面模块导入失败: {e}")
        modules['statistics'] = None
    
    return modules

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
        
        # 导入页面模块
        page_modules = import_page_modules()
        
        # 获取当前页面
        current_page = get_current_page()
        
        # 根据当前页面显示内容
        if current_page == "overview":
            show_overview_page()
        elif current_page == "devices":
            if page_modules['devices']:
                page_modules['devices']()
            else:
                show_placeholder_page("📱 设备管理", "设备管理页面暂时不可用，正在开发中...")
        elif current_page == "statistics":
            if page_modules['statistics']:
                page_modules['statistics']()
            else:
                show_placeholder_page("📊 阅读统计", "阅读统计页面暂时不可用，正在开发中...")
        elif current_page == "users":
            show_placeholder_page("👥 用户分析", "用户分析页面正在开发中...")
        elif current_page == "content":
            show_placeholder_page("📚 内容表现", "内容表现页面正在开发中...")
        elif current_page == "settings":
            require_admin()
            show_placeholder_page("⚙️ 系统设置", "系统设置页面正在开发中...")
        else:
            # 默认显示总览页面
            show_overview_page()
            
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        st.error(f"应用启动失败: {str(e)}")
        st.info("请检查后端服务是否正常运行")
        
        # 显示调试信息
        with st.expander("🔧 调试信息"):
            st.code(f"Error: {str(e)}")
            st.code(f"Python path: {sys.path}")

def show_placeholder_page(title: str, message: str):
    """显示占位符页面"""
    st.markdown(f"# {title}")
    st.info(message)
    
    # 添加一些有用的链接或信息
    if "统计" in title:
        st.markdown("""
        ### 📊 关于阅读统计功能
        
        增强版阅读统计页面包含以下功能：
        - **整体阅读总结**: 关键指标概览
        - **单书统计数据**: 详细的每本书分析
        - **阅读时间模式**: 时间分布和习惯分析
        - **元数据分析**: 作者、语言、设备使用分析
        
        如果页面显示此消息，可能的原因：
        1. 页面模块导入失败
        2. 后端API服务未启动
        3. 依赖包未正确安装
        """)

if __name__ == "__main__":
    main() 