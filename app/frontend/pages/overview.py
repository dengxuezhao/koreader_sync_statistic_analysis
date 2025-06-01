"""
总览页面
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging

from app.frontend.api_client import BooksAPI, api_client
from app.frontend.components.navigation import page_header_with_actions
from app.frontend.config import DESIGN_SYSTEM, CHART_CONFIG

logger = logging.getLogger(__name__)

def show_overview_page():
    """显示总览页面"""
    
    # 页面标题
    page_header_with_actions(
        title="📊 系统总览",
        subtitle="KOReader 阅读数据分析概览",
        actions={
            "refresh": {
                "label": "🔄 刷新数据",
                "type": "primary", 
                "callback": lambda: st.rerun()
            }
        }
    )
    
    try:
        # 获取阅读统计概览
        with st.spinner("正在加载数据..."):
            stats_overview = BooksAPI.get_reading_stats_overview()
        
        # 显示核心指标
        show_key_metrics(stats_overview)
        
        # 显示图表分析
        show_overview_charts(stats_overview)
        
        # 显示使用提示而不是快速链接，避免导航重复
        show_usage_tips()
        
    except Exception as e:
        logger.error(f"总览页面加载失败: {e}")
        st.error("❌ 数据加载失败，请检查后端服务状态")
        
        with st.expander("🔧 故障排除"):
            st.markdown("""
            **可能的原因：**
            1. 后端API服务未启动
            2. 网络连接问题
            3. 认证令牌过期
            
            **解决方法：**
            1. 确认后端服务正在运行
            2. 尝试重新登录
            3. 检查API连接状态
            """)

def show_key_metrics(stats: dict):
    """显示关键指标"""
    
    # 核心指标卡片
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📚 总书籍数",
            value=stats.get("total_books", 0),
            delta=None
        )
    
    with col2:
        completion_rate = stats.get("completion_rate", 0)
        st.metric(
            label="✅ 完成率",
            value=f"{completion_rate}%",
            delta=f"{stats.get('completed_books', 0)} 本已完成"
        )
    
    with col3:
        reading_hours = stats.get("total_reading_hours", 0)
        st.metric(
            label="⏰ 总阅读时长",
            value=f"{reading_hours}h",
            delta=f"平均 {stats.get('avg_reading_time', 0)//60} 分钟/书"
        )
    
    with col4:
        st.metric(
            label="📱 设备数量",
            value=stats.get("devices_count", 0),
            delta=f"{stats.get('recent_activity_count', 0)} 最近活跃"
        )

def show_overview_charts(stats: dict):
    """显示概览图表"""
    
    st.subheader("📈 阅读分析")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 阅读状态分布饼图
        completed = stats.get("completed_books", 0)
        reading = stats.get("reading_books", 0)
        total = stats.get("total_books", 0)
        not_started = max(0, total - completed - reading)
        
        fig_status = go.Figure(data=[go.Pie(
            labels=["已完成", "正在阅读", "未开始"],
            values=[completed, reading, not_started],
            marker_colors=[
                CHART_CONFIG["color_sequence"][0],
                CHART_CONFIG["color_sequence"][1], 
                CHART_CONFIG["color_sequence"][2]
            ],
            hole=0.4
        )])
        
        fig_status.update_layout(
            title="📊 阅读状态分布",
            font=dict(family=CHART_CONFIG["font_family"]),
            showlegend=True,
            height=300
        )
        
        st.plotly_chart(fig_status, use_container_width=True)
    
    with col2:
        # 阅读进度条
        progress_data = {
            "类型": ["已完成", "进行中", "未开始"],
            "数量": [completed, reading, not_started],
            "百分比": [
                completed/total*100 if total > 0 else 0,
                reading/total*100 if total > 0 else 0,
                not_started/total*100 if total > 0 else 0
            ]
        }
        
        fig_progress = px.bar(
            x=progress_data["类型"],
            y=progress_data["数量"],
            title="📈 阅读进度统计",
            color=progress_data["类型"],
            color_discrete_sequence=CHART_CONFIG["color_sequence"],
            text=progress_data["数量"]
        )
        
        fig_progress.update_layout(
            font=dict(family=CHART_CONFIG["font_family"]),
            showlegend=False,
            height=300,
            yaxis_title="书籍数量"
        )
        
        fig_progress.update_traces(textposition='outside')
        
        st.plotly_chart(fig_progress, use_container_width=True)

def show_usage_tips():
    """显示使用提示"""
    
    st.subheader("💡 使用指南")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("""
        **📱 设备管理**
        
        使用左侧导航访问设备管理页面，查看：
        - 设备状态监控
        - 同步活动分析
        - 设备使用统计
        """)
    
    with col2:
        st.info("""
        **📈 阅读统计**
        
        使用左侧导航访问统计页面，查看：
        - 详细阅读数据
        - 阅读习惯分析
        - 进度跟踪图表
        """)
    
    with col3:
        st.info("""
        **🔗 公开统计**
        
        系统提供公开API端点：
        - 无需认证即可访问
        - 适合博客嵌入展示
        - 查看API文档了解详情
        """)

def show_public_stats_info():
    """显示公开统计信息"""
    
    st.info("🔗 公开阅读统计功能")
    
    with st.expander("💡 如何使用公开统计", expanded=True):
        user_info = st.session_state.get('user_info', {})
        username = user_info.get('username', 'admin')
        
        st.markdown(f"""
        **公开API端点：**
        ```
        GET /api/v1/books/stats/public?username={username}
        ```
        
        **特性：**
        - 🔓 无需认证即可访问
        - 📊 适合嵌入博客或个人网站
        - 🎨 提供结构化的阅读数据
        - 📱 响应式设计，支持各种设备
        
        **返回数据包括：**
        - 阅读概览统计
        - 最近阅读的书籍
        - 已完成的书籍列表
        - 正在阅读的书籍
        
        **使用示例：**
        在您的博客中添加JavaScript代码即可展示您的阅读统计！
        """)

if __name__ == "__main__":
    show_overview_page() 