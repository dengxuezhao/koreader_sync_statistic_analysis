"""
公开阅读统计页面
可嵌入博客或个人网站的阅读数据展示页面
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from typing import Dict, Any, List
import logging

from app.frontend.api_client import BooksAPI
from app.frontend.config import CHART_CONFIG

logger = logging.getLogger(__name__)

def show_public_reading_page(username: str = None):
    """显示公开阅读统计页面"""
    
    # 页面配置 - 紧凑布局适合嵌入
    st.set_page_config(
        page_title="📚 阅读统计",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    try:
        # 获取公开阅读统计数据
        with st.spinner("正在加载阅读数据..."):
            stats_data = BooksAPI.get_public_reading_stats(username=username)
        
        user_info = stats_data.get("user", {})
        summary = stats_data.get("summary", {})
        recent_books = stats_data.get("recent_books", [])
        reading_books = stats_data.get("reading_books", [])
        completed_books = stats_data.get("completed_books", [])
        
        # 标题区域
        show_header(user_info, summary)
        
        # 统计概览
        show_stats_overview(summary)
        
        # 阅读图表
        show_reading_charts(summary, recent_books)
        
        # 书籍列表
        show_books_section(recent_books, reading_books, completed_books)
        
        # 页脚
        show_footer(stats_data.get("updated_at"))
        
    except Exception as e:
        logger.error(f"公开阅读统计页面加载失败: {e}")
        st.error("❌ 无法加载阅读数据")
        
        st.markdown("""
        <div style="text-align: center; padding: 2rem; color: #666;">
            <h3>📚 暂无阅读数据</h3>
            <p>请稍后再试或联系管理员</p>
        </div>
        """, unsafe_allow_html=True)

def show_header(user_info: Dict[str, Any], summary: Dict[str, Any]):
    """显示页面标题"""
    
    username = user_info.get("username", "书友")
    total_hours = user_info.get("total_reading_hours", 0)
    
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 2rem; padding: 1rem; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                border-radius: 1rem; color: white;">
        <h1 style="margin: 0; font-size: 2rem;">📚 {username} 的阅读统计</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.1rem; opacity: 0.9;">
            累计阅读 {total_hours} 小时 | 完成率 {summary.get('completion_rate', 0)}%
        </p>
    </div>
    """, unsafe_allow_html=True)

def show_stats_overview(summary: Dict[str, Any]):
    """显示统计概览"""
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📚 总书籍",
            value=summary.get("total_books", 0),
            delta=None
        )
    
    with col2:
        st.metric(
            label="✅ 已完成",
            value=summary.get("completed_count", 0),
            delta=f"{summary.get('completion_rate', 0)}%"
        )
    
    with col3:
        st.metric(
            label="📖 进行中",
            value=summary.get("reading_count", 0),
            delta=None
        )
    
    with col4:
        reading_hours = summary.get("total_reading_time", 0) // 3600
        st.metric(
            label="⏰ 阅读时长",
            value=f"{reading_hours}h",
            delta=None
        )

def show_reading_charts(summary: Dict[str, Any], recent_books: List[Dict[str, Any]]):
    """显示阅读图表"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 阅读状态分布
        completed = summary.get("completed_count", 0)
        reading = summary.get("reading_count", 0)
        total = summary.get("total_books", 0)
        not_started = max(0, total - completed - reading)
        
        if total > 0:
            fig_status = go.Figure(data=[go.Pie(
                labels=["已完成", "进行中", "未开始"],
                values=[completed, reading, not_started],
                marker_colors=["#38B2AC", "#F59E0B", "#E2E8F0"],
                hole=0.4
            )])
            
            fig_status.update_layout(
                title="📊 阅读状态分布",
                font=dict(family="Arial, sans-serif"),
                showlegend=True,
                height=300,
                margin=dict(t=50, b=0, l=0, r=0)
            )
            
            st.plotly_chart(fig_status, use_container_width=True)
    
    with col2:
        # 最近阅读活动
        if recent_books:
            activity_data = []
            for book in recent_books[:10]:
                if book.get("last_read_time"):
                    try:
                        read_date = datetime.fromisoformat(book["last_read_time"].replace("Z", "+00:00"))
                        activity_data.append({
                            "日期": read_date.strftime("%m-%d"),
                            "进度": book.get("reading_progress", 0),
                            "书籍": book.get("book_title", "")[:15] + "..."
                        })
                    except:
                        continue
            
            if activity_data:
                df_activity = pd.DataFrame(activity_data)
                
                fig_activity = px.bar(
                    df_activity,
                    x="日期",
                    y="进度",
                    title="📈 最近阅读活动",
                    hover_data=["书籍"],
                    color_discrete_sequence=["#667eea"]
                )
                
                fig_activity.update_layout(
                    font=dict(family="Arial, sans-serif"),
                    height=300,
                    yaxis_title="阅读进度 (%)",
                    margin=dict(t=50, b=0, l=0, r=0)
                )
                
                st.plotly_chart(fig_activity, use_container_width=True)

def show_books_section(recent_books: List[Dict[str, Any]], 
                      reading_books: List[Dict[str, Any]], 
                      completed_books: List[Dict[str, Any]]):
    """显示书籍列表"""
    
    tab1, tab2, tab3 = st.tabs(["📖 最近阅读", "🔄 进行中", "✅ 已完成"])
    
    with tab1:
        if recent_books:
            for book in recent_books[:5]:
                show_book_card(book)
        else:
            st.info("📭 暂无最近阅读记录")
    
    with tab2:
        if reading_books:
            for book in reading_books[:10]:
                show_book_card(book, show_progress=True)
        else:
            st.info("📭 暂无正在阅读的书籍")
    
    with tab3:
        if completed_books:
            for book in completed_books[:10]:
                show_book_card(book, completed=True)
        else:
            st.info("📭 暂无已完成的书籍")

def show_book_card(book: Dict[str, Any], show_progress: bool = False, completed: bool = False):
    """显示书籍卡片"""
    
    title = book.get("book_title", "未知书籍")
    author = book.get("book_author", "未知作者")
    progress = book.get("reading_progress", 0)
    reading_time = book.get("reading_time_formatted", "0分钟")
    
    # 状态图标
    if completed:
        status_icon = "✅"
        status_color = "#38A169"
    elif progress > 0:
        status_icon = "📖"
        status_color = "#3182CE"
    else:
        status_icon = "⭕"
        status_color = "#A0AEC0"
    
    # 卡片布局
    with st.container():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"""
            <div style="padding: 0.5rem 0; border-bottom: 1px solid #E2E8F0;">
                <div style="font-weight: 600; color: #2D3748; margin-bottom: 0.25rem;">
                    {status_icon} {title}
                </div>
                <div style="color: #718096; font-size: 0.9rem;">
                    👤 {author} | ⏰ {reading_time}
                </div>
                {f'<div style="margin-top: 0.5rem;"><div style="background: #E2E8F0; border-radius: 10px; height: 8px;"><div style="background: {status_color}; width: {progress}%; height: 8px; border-radius: 10px;"></div></div></div>' if show_progress else ''}
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            if show_progress:
                st.metric("", f"{progress:.1f}%", delta=None)

def show_footer(updated_at: str):
    """显示页脚"""
    
    if updated_at:
        try:
            update_time = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            time_str = update_time.strftime("%Y-%m-%d %H:%M")
        except:
            time_str = "未知"
    else:
        time_str = "未知"
    
    st.markdown("---")
    st.markdown(f"""
    <div style="text-align: center; color: #718096; font-size: 0.8rem; padding: 1rem;">
        <p>📚 Powered by Kompanion | 📊 数据更新时间: {time_str}</p>
        <p>🔗 <a href="https://github.com/kompanion" target="_blank" style="color: #667eea;">GitHub</a> | 
           📖 <a href="/docs" target="_blank" style="color: #667eea;">API文档</a></p>
    </div>
    """, unsafe_allow_html=True)

# 独立启动函数（用于嵌入）
def run_public_page():
    """运行公开阅读统计页面"""
    
    # 从URL参数获取用户名
    query_params = st.query_params
    username = query_params.get("username", None)
    
    if not username:
        st.error("❌ 请在URL中指定用户名参数：?username=your_username")
        return
    
    show_public_reading_page(username)

if __name__ == "__main__":
    run_public_page() 