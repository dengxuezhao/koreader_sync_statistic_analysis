"""
Streamlit 前端配置
"""

import os
from typing import Dict, Any
from app.core.config import settings

# API 基础配置 - 修复地址问题
# 后端服务器绑定到 0.0.0.0，但客户端需要连接到 localhost
API_HOST = os.getenv("API_HOST", "localhost")  # 客户端连接地址
API_PORT = int(os.getenv("API_PORT", settings.PORT))
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
API_TIMEOUT = 30

# 页面配置
PAGE_CONFIG = {
    "page_title": "Kompanion 阅读统计分析",
    "page_icon": "📚",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
    "menu_items": {
        "Get Help": "https://github.com/kompanion/docs",
        "Report a bug": "https://github.com/kompanion/issues",
        "About": "# Kompanion 阅读统计分析系统\n现代化的 KOReader 数据分析平台"
    }
}

# 设计系统配置
DESIGN_SYSTEM = {
    "colors": {
        # 主色调
        "primary": "#0A2A4E",  # 深邃蓝
        "primary_light": "#1A3A5E",
        "primary_dark": "#05192E",
        
        # 辅助色/强调色
        "accent": "#38B2AC",  # 活力青
        "accent_light": "#4FD1C7",
        "accent_dark": "#2C7A7B",
        
        "secondary": "#F59E0B",  # 明亮橙
        "secondary_light": "#FBBF24",
        "secondary_dark": "#D97706",
        
        # 背景色
        "background": "#FFFFFF",
        "background_light": "#F7FAFC",
        "background_dark": "#EDF2F7",
        
        # 文字颜色
        "text_primary": "#2D3748",
        "text_secondary": "#718096",
        "text_light": "#A0AEC0",
        
        # 状态色
        "success": "#38A169",
        "warning": "#D69E2E",
        "error": "#E53E3E",
        "info": "#3182CE"
    },
    
    "fonts": {
        "primary": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
        "code": "JetBrains Mono, Consolas, monospace"
    },
    
    "spacing": {
        "xs": "0.25rem",
        "sm": "0.5rem", 
        "md": "1rem",
        "lg": "1.5rem",
        "xl": "2rem",
        "xxl": "3rem"
    },
    
    "border_radius": {
        "sm": "0.25rem",
        "md": "0.5rem",
        "lg": "0.75rem",
        "xl": "1rem"
    }
}

# 导航配置
NAVIGATION_CONFIG = {
    "pages": [
        {
            "name": "总览",
            "icon": "📊",
            "key": "overview",
            "description": "系统概览和关键指标"
        },
        {
            "name": "用户分析",
            "icon": "👥", 
            "key": "users",
            "description": "用户行为和活动分析"
        },
        {
            "name": "内容表现",
            "icon": "📚",
            "key": "content",
            "description": "书籍和阅读内容分析"
        },
        {
            "name": "设备管理",
            "icon": "📱",
            "key": "devices", 
            "description": "设备状态和同步分析"
        },
        {
            "name": "阅读统计",
            "icon": "📈",
            "key": "statistics",
            "description": "详细的阅读数据分析"
        },
        {
            "name": "系统设置",
            "icon": "⚙️",
            "key": "settings",
            "description": "系统配置和管理"
        }
    ]
}

# 图表配置
CHART_CONFIG = {
    "color_sequence": [
        "#38B2AC", "#F59E0B", "#8B5CF6", "#EF4444", 
        "#10B981", "#3B82F6", "#F97316", "#84CC16"
    ],
    "background_color": "rgba(0,0,0,0)",
    "grid_color": "#E2E8F0",
    "text_color": "#2D3748",
    "font_family": "Inter, sans-serif"
}

# 表格配置
TABLE_CONFIG = {
    "page_size": 20,
    "show_index": False,
    "use_container_width": True
} 