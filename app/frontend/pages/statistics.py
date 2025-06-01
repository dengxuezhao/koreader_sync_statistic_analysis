"""
阅读统计页面
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

from app.frontend.api_client import StatisticsAPI, api_client
from app.frontend.components.navigation import page_header_with_actions
from app.frontend.config import DESIGN_SYSTEM, CHART_CONFIG

logger = logging.getLogger(__name__)

def show_statistics_page():
    """显示阅读统计页面"""
    
    # 页面标题和操作
    page_header_with_actions(
        title="📈 阅读统计",
        subtitle="深入分析您的阅读数据和习惯",
        actions={
            "refresh": {
                "label": "🔄 刷新数据",
                "type": "primary",
                "callback": lambda: st.rerun()
            },
            "export": {
                "label": "📊 导出数据",
                "type": "secondary",
                "callback": show_export_options
            }
        }
    )
    
    try:
        # 获取阅读统计数据
        with st.spinner("正在加载阅读统计数据..."):
            stats_data = StatisticsAPI.get_reading_statistics(page=1, size=100)
        
        if not stats_data or "statistics" not in stats_data:
            st.warning("📭 暂无阅读统计数据")
            show_empty_state()
            return
        
        statistics = stats_data["statistics"]
        
        # 阅读概览统计
        show_reading_overview(statistics)
        
        # 阅读趋势分析
        show_reading_trends(statistics)
        
        # 书籍阅读详情
        show_book_details(statistics)
        
        # 阅读习惯分析
        show_reading_habits(statistics)
        
    except Exception as e:
        logger.error(f"阅读统计页面加载失败: {e}")
        st.error(f"❌ 阅读统计数据加载失败: {str(e)}")
        
        # 显示连接说明
        with st.expander("🔧 解决方案"):
            st.markdown("""
            **可能的原因：**
            1. 后端服务未启动
            2. 暂无阅读数据
            3. 网络连接问题
            
            **解决方法：**
            1. 确保后端服务正在运行
            2. 通过KOReader上传统计数据
            3. 检查API连接状态
            """)

def show_reading_overview(statistics: List[Dict[str, Any]]):
    """显示阅读概览统计"""
    
    if not statistics:
        return
    
    # 计算总体统计
    total_books = len(statistics)
    completed_books = len([s for s in statistics if s.get("reading_progress", 0) >= 100])
    total_reading_time = sum(s.get("total_reading_time", 0) for s in statistics)
    avg_progress = sum(s.get("reading_progress", 0) for s in statistics) / total_books if total_books > 0 else 0
    
    # 格式化阅读时间
    reading_hours = total_reading_time // 3600
    reading_minutes = (total_reading_time % 3600) // 60
    
    # 显示核心指标
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📚 阅读书籍",
            value=total_books,
            delta=None
        )
    
    with col2:
        st.metric(
            label="✅ 完成数量",
            value=completed_books,
            delta=f"{(completed_books/total_books*100):.1f}%" if total_books > 0 else "0%"
        )
    
    with col3:
        st.metric(
            label="⏰ 阅读时长",
            value=f"{reading_hours}h {reading_minutes}m",
            delta=f"平均 {total_reading_time//total_books//60}分钟/书" if total_books > 0 else "0分钟"
        )
    
    with col4:
        st.metric(
            label="📊 平均进度",
            value=f"{avg_progress:.1f}%",
            delta=None
        )

def show_reading_trends(statistics: List[Dict[str, Any]]):
    """显示阅读趋势分析"""
    
    st.subheader("📈 阅读趋势分析")
    
    if not statistics:
        st.info("📭 暂无趋势数据")
        return
    
    # 准备趋势数据
    trend_data = []
    for stat in statistics:
        if stat.get("last_read_time"):
            try:
                last_read = datetime.fromisoformat(stat["last_read_time"].replace("Z", "+00:00"))
                trend_data.append({
                    "日期": last_read.date(),
                    "书籍": stat.get("book_title", "未知书籍"),
                    "阅读进度": stat.get("reading_progress", 0),
                    "阅读时长": stat.get("total_reading_time", 0) / 3600,  # 转换为小时
                    "设备": stat.get("device_name", "未知设备")
                })
            except:
                continue
    
    if not trend_data:
        st.info("📊 暂无时间趋势数据")
        return
    
    df_trends = pd.DataFrame(trend_data)
    
    # 按日期聚合数据
    daily_stats = df_trends.groupby("日期").agg({
        "阅读时长": "sum",
        "书籍": "count"
    }).reset_index()
    daily_stats.columns = ["日期", "总阅读时长", "阅读书籍数"]
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 每日阅读时长趋势
        fig_time = px.line(
            daily_stats,
            x="日期",
            y="总阅读时长",
            title="📅 每日阅读时长趋势",
            markers=True,
            color_discrete_sequence=CHART_CONFIG["color_sequence"]
        )
        
        fig_time.update_layout(
            font=dict(family=CHART_CONFIG["font_family"]),
            yaxis_title="阅读时长 (小时)",
            xaxis_title="日期",
            height=400
        )
        
        st.plotly_chart(fig_time, use_container_width=True)
    
    with col2:
        # 每日阅读书籍数趋势
        fig_books = px.bar(
            daily_stats,
            x="日期",
            y="阅读书籍数",
            title="📚 每日阅读书籍数",
            color_discrete_sequence=CHART_CONFIG["color_sequence"]
        )
        
        fig_books.update_layout(
            font=dict(family=CHART_CONFIG["font_family"]),
            yaxis_title="书籍数量",
            xaxis_title="日期",
            height=400
        )
        
        st.plotly_chart(fig_books, use_container_width=True)

def show_book_details(statistics: List[Dict[str, Any]]):
    """显示书籍阅读详情"""
    
    st.subheader("📖 书籍阅读详情")
    
    if not statistics:
        st.info("📭 暂无书籍数据")
        return
    
    # 准备表格数据
    table_data = []
    for stat in statistics:
        # 处理时间
        last_read = stat.get("last_read_time")
        if last_read:
            try:
                read_time = datetime.fromisoformat(last_read.replace("Z", "+00:00"))
                read_display = read_time.strftime("%Y-%m-%d")
                days_ago = (datetime.now() - read_time.replace(tzinfo=None)).days
                if days_ago == 0:
                    time_status = "🟢 今天"
                elif days_ago <= 7:
                    time_status = f"🟡 {days_ago}天前"
                else:
                    time_status = f"🔴 {days_ago}天前"
            except:
                read_display = "未知"
                time_status = "❓ 异常"
        else:
            read_display = "从未阅读"
            time_status = "⚪ 从未"
        
        # 进度状态
        progress = stat.get("reading_progress", 0)
        if progress >= 100:
            progress_status = "✅ 已完成"
        elif progress >= 80:
            progress_status = "🔶 接近完成"
        elif progress >= 50:
            progress_status = "🔵 进行中"
        elif progress > 0:
            progress_status = "🟡 已开始"
        else:
            progress_status = "⚪ 未开始"
        
        # 阅读时长格式化
        reading_time = stat.get("total_reading_time", 0)
        if reading_time >= 3600:
            time_formatted = f"{reading_time//3600}h {(reading_time%3600)//60}m"
        elif reading_time >= 60:
            time_formatted = f"{reading_time//60}m"
        else:
            time_formatted = f"{reading_time}s"
        
        table_data.append({
            "书籍标题": stat.get("book_title", "未知书籍")[:50] + ("..." if len(stat.get("book_title", "")) > 50 else ""),
            "作者": stat.get("book_author", "未知作者")[:30] + ("..." if len(stat.get("book_author", "")) > 30 else ""),
            "阅读进度": f"{progress:.1f}%",
            "状态": progress_status,
            "当前页": stat.get("current_page", 0),
            "总页数": stat.get("total_pages", 0),
            "阅读时长": time_formatted,
            "最后阅读": read_display,
            "活跃状态": time_status,
            "设备": stat.get("device_name", "未知设备")
        })
    
    # 创建DataFrame
    df = pd.DataFrame(table_data)
    
    # 添加筛选选项
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        progress_filter = st.selectbox(
            "筛选进度状态",
            ["全部", "已完成", "进行中", "已开始", "未开始"],
            key="book_progress_filter"
        )
    
    with col2:
        device_filter = st.selectbox(
            "筛选设备",
            ["全部"] + list(set(stat.get("device_name", "未知设备") for stat in statistics)),
            key="book_device_filter"
        )
    
    with col3:
        search_term = st.text_input(
            "搜索书籍",
            placeholder="输入书名或作者...",
            key="book_search"
        )
    
    # 应用筛选
    filtered_df = df.copy()
    
    if progress_filter != "全部":
        if progress_filter == "已完成":
            filtered_df = filtered_df[filtered_df["状态"].str.contains("已完成")]
        elif progress_filter == "进行中":
            filtered_df = filtered_df[filtered_df["状态"].str.contains("进行中|接近完成")]
        elif progress_filter == "已开始":
            filtered_df = filtered_df[filtered_df["状态"].str.contains("已开始")]
        else:  # 未开始
            filtered_df = filtered_df[filtered_df["状态"].str.contains("未开始")]
    
    if device_filter != "全部":
        filtered_df = filtered_df[filtered_df["设备"] == device_filter]
    
    if search_term:
        filtered_df = filtered_df[
            filtered_df["书籍标题"].str.contains(search_term, case=False) |
            filtered_df["作者"].str.contains(search_term, case=False)
        ]
    
    # 显示过滤后的表格
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "书籍标题": st.column_config.TextColumn("📚 书籍标题", width="large"),
            "作者": st.column_config.TextColumn("✍️ 作者", width="medium"),
            "阅读进度": st.column_config.TextColumn("📊 进度", width="small"),
            "状态": st.column_config.TextColumn("🏷️ 状态", width="small"),
            "当前页": st.column_config.NumberColumn("📄 当前页", width="small"),
            "总页数": st.column_config.NumberColumn("📋 总页数", width="small"),
            "阅读时长": st.column_config.TextColumn("⏰ 时长", width="small"),
            "最后阅读": st.column_config.TextColumn("📅 最后阅读", width="medium"),
            "活跃状态": st.column_config.TextColumn("🟢 活跃度", width="small"),
            "设备": st.column_config.TextColumn("📱 设备", width="medium")
        }
    )
    
    # 显示筛选结果统计
    if len(filtered_df) != len(df):
        st.caption(f"筛选结果：{len(filtered_df)} / {len(df)} 本书籍")

def show_reading_habits(statistics: List[Dict[str, Any]]):
    """显示阅读习惯分析"""
    
    st.subheader("🧠 阅读习惯分析")
    
    if not statistics:
        st.info("📭 暂无习惯分析数据")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 阅读进度分布
        progress_ranges = {
            "未开始 (0%)": 0,
            "刚开始 (1-25%)": 0,
            "进行中 (26-50%)": 0,
            "过半 (51-75%)": 0,
            "接近完成 (76-99%)": 0,
            "已完成 (100%)": 0
        }
        
        for stat in statistics:
            progress = stat.get("reading_progress", 0)
            if progress == 0:
                progress_ranges["未开始 (0%)"] += 1
            elif progress <= 25:
                progress_ranges["刚开始 (1-25%)"] += 1
            elif progress <= 50:
                progress_ranges["进行中 (26-50%)"] += 1
            elif progress <= 75:
                progress_ranges["过半 (51-75%)"] += 1
            elif progress < 100:
                progress_ranges["接近完成 (76-99%)"] += 1
            else:
                progress_ranges["已完成 (100%)"] += 1
        
        labels = list(progress_ranges.keys())
        values = list(progress_ranges.values())
        
        fig_progress = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            marker_colors=CHART_CONFIG["color_sequence"],
            hole=0.4
        )])
        
        fig_progress.update_layout(
            title="📊 阅读进度分布",
            font=dict(family=CHART_CONFIG["font_family"]),
            showlegend=True,
            height=400
        )
        
        st.plotly_chart(fig_progress, use_container_width=True)
    
    with col2:
        # 设备使用分布
        device_counts = {}
        for stat in statistics:
            device = stat.get("device_name", "未知设备")
            device_counts[device] = device_counts.get(device, 0) + 1
        
        if len(device_counts) > 1:
            devices = list(device_counts.keys())
            counts = list(device_counts.values())
            
            fig_devices = px.bar(
                x=devices,
                y=counts,
                title="📱 设备使用分布",
                labels={"x": "设备", "y": "书籍数量"},
                color_discrete_sequence=CHART_CONFIG["color_sequence"]
            )
            
            fig_devices.update_layout(
                font=dict(family=CHART_CONFIG["font_family"]),
                xaxis_tickangle=-45,
                height=400
            )
            
            st.plotly_chart(fig_devices, use_container_width=True)
        else:
            st.info("📱 仅有一台设备，无法显示分布图")
    
    # 阅读时长分析
    if any(stat.get("total_reading_time", 0) > 0 for stat in statistics):
        st.subheader("⏰ 阅读时长分析")
        
        # 按阅读时长分组
        time_data = []
        for stat in statistics:
            time_hours = stat.get("total_reading_time", 0) / 3600
            if time_hours > 0:
                time_data.append({
                    "书籍": stat.get("book_title", "未知书籍")[:30],
                    "阅读时长": time_hours,
                    "进度": stat.get("reading_progress", 0),
                    "设备": stat.get("device_name", "未知设备")
                })
        
        if time_data:
            df_time = pd.DataFrame(time_data)
            df_time = df_time.sort_values("阅读时长", ascending=False).head(20)  # 取前20本
            
            fig_time = px.scatter(
                df_time,
                x="阅读时长",
                y="进度",
                size="阅读时长",
                hover_name="书籍",
                color="设备",
                title="📈 阅读时长 vs 进度关系",
                labels={"阅读时长": "阅读时长 (小时)", "进度": "阅读进度 (%)"},
                color_discrete_sequence=CHART_CONFIG["color_sequence"]
            )
            
            fig_time.update_layout(
                font=dict(family=CHART_CONFIG["font_family"]),
                height=500
            )
            
            st.plotly_chart(fig_time, use_container_width=True)

def show_export_options():
    """显示数据导出选项"""
    st.info("📊 数据导出功能正在开发中，敬请期待！")

def show_empty_state():
    """显示空状态页面"""
    st.markdown("""
    <div style="text-align: center; padding: 3rem; color: #718096;">
        <h2>📚 还没有阅读统计数据</h2>
        <p>开始使用 KOReader 阅读并上传统计数据后，这里将显示您的阅读分析。</p>
        
        <div style="margin: 2rem 0;">
            <h4>💡 如何上传统计数据？</h4>
            <ol style="text-align: left; max-width: 500px; margin: 0 auto;">
                <li>在 KOReader 中启用 kosync 插件</li>
                <li>配置同步服务器地址</li>
                <li>开始阅读您的书籍</li>
                <li>统计数据将自动上传并在此处显示</li>
            </ol>
        </div>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    show_statistics_page() 