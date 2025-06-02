"""
阅读统计页面 - 增强版本
包含四个主要分析维度：
A. 整体阅读总结
B. 单书统计数据  
C. 阅读时间模式分析
D. 类型、作者与语言分析
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

from app.frontend.api_client import StatisticsAPI, api_client
from app.frontend.components.navigation import page_header_with_actions
from app.frontend.config import DESIGN_SYSTEM, CHART_CONFIG

logger = logging.getLogger(__name__)

def show_statistics_page():
    """显示增强版阅读统计页面"""
    
    # 页面标题和操作
    page_header_with_actions(
        title="📊 深度阅读分析",
        subtitle="全方位洞察您的阅读习惯和成就",
        actions={
            "refresh": {
                "label": "🔄 刷新数据",
                "type": "primary",
                "callback": lambda: st.rerun()
            },
            "export": {
                "label": "📊 导出报告",
                "type": "secondary",  
                "callback": show_export_options
            }
        }
    )
    
    try:
        # 获取增强的阅读统计数据
        with st.spinner("正在加载深度分析数据..."):
            enhanced_stats = StatisticsAPI.get_enhanced_reading_statistics()
        
        if not enhanced_stats or enhanced_stats.get("message") == "暂无阅读数据":
            st.warning("📭 暂无阅读数据进行分析")
            show_empty_state()
            return
        
        # A. 整体阅读总结
        show_overall_summary_section(enhanced_stats.get("overall_summary", {}))
        
        # B. 单书统计数据
        show_per_book_stats_section(enhanced_stats.get("per_book_stats", []))
        
        # C. 阅读时间模式分析
        show_time_patterns_section(enhanced_stats.get("time_patterns", {}))
        
        # D. 类型、作者与语言分析
        show_metadata_analysis_section(enhanced_stats.get("metadata_analysis", {}))
        
        # 显示数据更新时间
        if enhanced_stats.get("generated_at"):
            st.caption(f"📅 数据更新时间: {enhanced_stats['generated_at']}")
        
    except Exception as e:
        logger.error(f"增强阅读统计页面加载失败: {e}")
        st.error(f"❌ 深度分析数据加载失败: {str(e)}")
        
        # 显示连接说明
        with st.expander("🔧 解决方案"):
            st.markdown("""
            **可能的原因：**
            1. 后端服务未启动
            2. 暂无足够的阅读数据进行分析
            3. API端点连接问题
            
            **解决方法：**
            1. 确保后端服务正在运行
            2. 通过KOReader上传更多统计数据
            3. 检查服务器日志排查问题
            """)


def show_overall_summary_section(summary: Dict[str, Any]):
    """A. 整体阅读总结"""
    
    st.header("📈 A. 整体阅读总结", divider="rainbow")
    st.markdown("关注用户阅读行为的宏观概览，提供一个关于阅读投入和广度的快照。")
    
    if not summary:
        st.info("📭 暂无整体统计数据")
        return
    
    # 核心指标展示卡片
    st.subheader("🔑 关键整体阅读指标")
    
    # 使用6列布局展示核心指标
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric(
            label="总互动书籍数量",
            value=f"{summary.get('total_interactive_books', 0)} 本",
            delta=f"今年: {summary.get('this_year_books', 0)}本"
        )
    
    with col2:
        st.metric(
            label="总阅读时长",
            value=f"{summary.get('total_reading_time_hours', 0):.1f} 小时",
            delta=f"约 {summary.get('total_reading_time_hours', 0)/24:.1f} 天"
        )
    
    with col3:
        st.metric(
            label="总阅读独立页数",
            value=f"{summary.get('total_unique_pages', 0):,} 页",
            delta="累计翻页数"
        )
    
    with col4:
        st.metric(
            label="平均单次阅读会话时长",
            value=f"{summary.get('avg_session_duration_minutes', 0):.0f} 分钟",
            delta=f"共 {summary.get('reading_sessions_count', 0)} 次会话"
        )
    
    with col5:
        st.metric(
            label="本年度已读/互动书籍数量",
            value=f"{summary.get('this_year_books', 0)} 本",
            delta=f"本月: {summary.get('this_month_books', 0)}本"
        )
    
    with col6:
        st.metric(
            label="阅读完成率",
            value=f"{summary.get('completion_rate', 0):.1f}%",
            delta=f"已完成: {summary.get('completed_books', 0)}本"
        )
    
    # 详细指标表格
    st.subheader("📊 详细指标概览")
    
    key_metrics = summary.get('key_metrics', {})
    if key_metrics:
        metrics_df = pd.DataFrame([
            {"指标名称": k, "数值": v, "单位": v.split()[-1] if ' ' in v else ''}
            for k, v in key_metrics.items()
        ])
        st.dataframe(metrics_df, use_container_width=True, hide_index=True)
    
    # 阅读时长趋势图
    st.subheader("📅 阅读时长分布")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("平均每日阅读", f"{summary.get('avg_daily_reading_minutes', 0):.1f} 分钟")
    with col2:
        st.metric("平均每周阅读", f"{summary.get('avg_weekly_reading_hours', 0):.1f} 小时")
    with col3:
        st.metric("平均每月阅读", f"{summary.get('avg_monthly_reading_hours', 0):.1f} 小时")
    
    # 完成度分布饼图
    if summary.get('completed_books', 0) > 0 or summary.get('in_progress_books', 0) > 0:
        st.subheader("📊 阅读完成度分布")
        
        completion_data = {
            "已完成": summary.get('completed_books', 0),
            "接近完成": summary.get('nearly_completed_books', 0),
            "进行中": summary.get('in_progress_books', 0)
        }
        
        fig = px.pie(
            values=list(completion_data.values()),
            names=list(completion_data.keys()),
            title="书籍阅读状态分布",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)


def show_per_book_stats_section(per_book_stats: List[Dict[str, Any]]):
    """B. 单书统计数据"""
    
    st.header("📚 B. 单书统计数据", divider="blue")
    st.markdown("针对每一本书籍进行细致的统计，了解在不同书籍上的投入和进度。")
    
    if not per_book_stats:
        st.info("📭 暂无单书统计数据")
        return
    
    # 创建DataFrame用于展示
    df = pd.DataFrame(per_book_stats)
    
    # 顶部汇总信息
    st.subheader("📊 单书统计概览")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总书籍数", len(df))
    with col2:
        avg_progress = df['reading_progress'].mean()
        st.metric("平均完成度", f"{avg_progress:.1f}%")
    with col3:
        avg_speed = df['reading_speed_pages_per_hour'].mean()
        st.metric("平均阅读速度", f"{avg_speed:.1f} 页/时")
    with col4:
        total_hours = df['total_reading_time_hours'].sum()
        st.metric("总投入时间", f"{total_hours:.1f} 小时")
    
    # 过滤和排序选项
    st.subheader("📖 每本书籍详细统计")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        sort_by = st.selectbox(
            "排序方式",
            ["总阅读时长", "阅读进度", "阅读速度", "书籍标题"],
            index=0
        )
    
    with col2:
        filter_status = st.selectbox(
            "筛选状态",
            ["全部", "已完成", "进行中", "未开始"],
            index=0
        )
    
    with col3:
        show_charts = st.checkbox("显示图表", value=True)
    
    # 应用筛选
    filtered_df = df.copy()
    if filter_status != "全部":
        if filter_status == "已完成":
            filtered_df = df[df['reading_progress'] >= 100]
        elif filter_status == "进行中":
            filtered_df = df[(df['reading_progress'] > 0) & (df['reading_progress'] < 100)]
        elif filter_status == "未开始":
            filtered_df = df[df['reading_progress'] == 0]
    
    # 应用排序
    sort_mapping = {
        "总阅读时长": "total_reading_time_hours",
        "阅读进度": "reading_progress", 
        "阅读速度": "reading_speed_pages_per_hour",
        "书籍标题": "book_title"
    }
    if sort_by in sort_mapping:
        sort_col = sort_mapping[sort_by]
        if sort_col in filtered_df.columns:
            filtered_df = filtered_df.sort_values(sort_col, ascending=False)
    
    # 显示图表
    if show_charts and len(filtered_df) > 0:
        col1, col2 = st.columns(2)
        
        with col1:
            # 阅读进度分布直方图
            fig = px.histogram(
                filtered_df,
                x='reading_progress',
                nbins=20,
                title="阅读进度分布",
                labels={'reading_progress': '阅读进度 (%)', 'count': '书籍数量'},
                color_discrete_sequence=['#2E86AB']
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 阅读时长 vs 阅读进度散点图
            fig = px.scatter(
                filtered_df,
                x='total_reading_time_hours',
                y='reading_progress',
                size='total_pages',
                hover_name='book_title',
                title="阅读时长 vs 阅读进度",
                labels={
                    'total_reading_time_hours': '阅读时长 (小时)',
                    'reading_progress': '阅读进度 (%)',
                    'total_pages': '总页数'
                },
                color='reading_speed_pages_per_hour',
                color_continuous_scale='Viridis'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # 详细数据表格
    st.subheader("📋 详细书籍统计表")
    
    # 准备显示的列
    display_columns = [
        'book_title', 'book_author', 'total_pages', 'read_pages', 
        'completion_percentage', 'total_reading_time_hours', 
        'reading_speed_pages_per_hour', 'reading_sessions',
        'highlights_count', 'notes_count', 'completion_status'
    ]
    
    # 重命名列以便显示
    column_names = {
        'book_title': '书籍标题',
        'book_author': '作者',
        'total_pages': '总页数',
        'read_pages': '已读页数',
        'completion_percentage': '完成度 (%)',
        'total_reading_time_hours': '总阅读时长 (小时)',
        'reading_speed_pages_per_hour': '平均阅读速度 (页/小时)',
        'reading_sessions': '阅读会话数',
        'highlights_count': '高亮数',
        'notes_count': '笔记数',
        'completion_status': '完成状态'
    }
    
    display_df = filtered_df[display_columns].rename(columns=column_names)
    
    # 格式化数值列
    if '完成度 (%)' in display_df.columns:
        display_df['完成度 (%)'] = display_df['完成度 (%)'].round(1)
    if '总阅读时长 (小时)' in display_df.columns:
        display_df['总阅读时长 (小时)'] = display_df['总阅读时长 (小时)'].round(2)
    if '平均阅读速度 (页/小时)' in display_df.columns:
        display_df['平均阅读速度 (页/小时)'] = display_df['平均阅读速度 (页/小时)'].round(1)
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "完成度 (%)": st.column_config.ProgressColumn(
                "完成度 (%)",
                help="阅读完成百分比",
                min_value=0,
                max_value=100,
            ),
        }
    )
    
    # 导出单书统计功能
    if st.button("📊 导出单书统计数据"):
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="下载 CSV 文件",
            data=csv,
            file_name=f"单书统计数据_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )


def show_time_patterns_section(time_patterns: Dict[str, Any]):
    """C. 阅读时间模式分析"""
    
    st.header("⏰ C. 阅读时间模式分析", divider="green")
    st.markdown("分析用户在不同时间维度上的阅读行为，发现阅读习惯的周期性特征。")
    
    if not time_patterns or time_patterns.get("message") == "暂无时间模式数据":
        st.info("📭 暂无时间模式数据")
        return
    
    # 阅读高峰时段
    peak_hours = time_patterns.get("peak_reading_hours", [])
    if peak_hours:
        st.subheader("🌟 阅读高峰时段")
        
        col1, col2, col3 = st.columns(3)
        for i, peak in enumerate(peak_hours[:3]):
            with [col1, col2, col3][i]:
                hour = peak.get("hour", 0)
                total_time = peak.get("total_time", 0) / 3600  # 转换为小时
                count = peak.get("count", 0)
                
                st.metric(
                    label=f"第{i+1}高峰",
                    value=f"{hour:02d}:00 时段",
                    delta=f"{total_time:.1f}h ({count}次)"
                )
    
    # 按小时分布的条形图
    hourly_dist = time_patterns.get("hourly_distribution", {})
    if hourly_dist:
        st.subheader("📊 24小时阅读分布")
        
        hours = list(range(24))
        reading_times = [hourly_dist.get(h, {}).get("total_time", 0) / 3600 for h in hours]  # 转换为小时
        counts = [hourly_dist.get(h, {}).get("count", 0) for h in hours]
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('阅读时长分布 (小时)', '阅读次数分布'),
            vertical_spacing=0.12
        )
        
        # 阅读时长条形图
        fig.add_trace(
            go.Bar(x=hours, y=reading_times, name="阅读时长", marker_color='skyblue'),
            row=1, col=1
        )
        
        # 阅读次数条形图
        fig.add_trace(
            go.Bar(x=hours, y=counts, name="阅读次数", marker_color='lightcoral'),
            row=2, col=1
        )
        
        fig.update_layout(
            height=500,
            showlegend=False,
            title_text="24小时阅读模式分析"
        )
        fig.update_xaxes(title_text="小时", row=2, col=1)
        fig.update_yaxes(title_text="时长 (小时)", row=1, col=1)
        fig.update_yaxes(title_text="次数", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
    
    # 星期分布饼图
    weekday_dist = time_patterns.get("weekday_distribution", {})
    if weekday_dist:
        st.subheader("📅 星期阅读分布")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 按阅读时长的饼图
            weekdays = list(weekday_dist.keys())
            reading_times = [weekday_dist[day]["total_time"] / 3600 for day in weekdays]
            
            fig = px.pie(
                values=reading_times,
                names=weekdays,
                title="按星期的阅读时长分布",
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 按阅读次数的饼图
            counts = [weekday_dist[day]["count"] for day in weekdays]
            
            fig = px.pie(
                values=counts,
                names=weekdays,
                title="按星期的阅读次数分布",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
    
    # 阅读热力图
    heatmap_data = time_patterns.get("reading_heatmap_data", [])
    if heatmap_data:
        st.subheader("🔥 阅读热力图 (时段 vs 星期)")
        
        # 准备热力图数据
        heatmap_df = pd.DataFrame(heatmap_data)
        if not heatmap_df.empty:
            # 创建透视表
            pivot_table = heatmap_df.pivot(index="hour", columns="weekday_name", values="intensity")
            
            fig = px.imshow(
                pivot_table,
                title="阅读时间热力图 - 黄金阅读时间发现",
                labels=dict(x="星期", y="小时", color="阅读强度 (小时)"),
                aspect="auto",
                color_continuous_scale="YlOrRd"
            )
            fig.update_layout(height=600)
            st.plotly_chart(fig, use_container_width=True)
            
            st.info("💡 **热力图解读**: 颜色越深表示该时段阅读时间越长，可以帮助您发现最佳的阅读时间窗口。")
    
    # 月份趋势
    monthly_dist = time_patterns.get("monthly_distribution", {})
    if monthly_dist:
        st.subheader("📈 月度阅读趋势")
        
        months = list(monthly_dist.keys())
        monthly_times = [monthly_dist[month]["total_time"] / 3600 for month in months]
        monthly_counts = [monthly_dist[month]["count"] for month in months]
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig.add_trace(
            go.Bar(x=months, y=monthly_times, name="阅读时长 (小时)", marker_color='lightblue'),
            secondary_y=False,
        )
        
        fig.add_trace(
            go.Scatter(x=months, y=monthly_counts, mode='lines+markers', name="阅读次数", line=dict(color='red')),
            secondary_y=True,
        )
        
        fig.update_yaxes(title_text="阅读时长 (小时)", secondary_y=False)
        fig.update_yaxes(title_text="阅读次数", secondary_y=True)
        fig.update_layout(title_text="月度阅读活动趋势")
        
        st.plotly_chart(fig, use_container_width=True)


def show_metadata_analysis_section(metadata_analysis: Dict[str, Any]):
    """D. 类型、作者与语言分析"""
    
    st.header("🏷️ D. 类型、作者与语言分析", divider="orange")
    st.markdown("基于书籍元数据分析阅读偏好和习惯，了解阅读兴趣的分布特征。")
    
    if not metadata_analysis:
        st.info("📭 暂无元数据分析")
        return
    
    # 作者分析
    author_analysis = metadata_analysis.get("author_analysis", {})
    if author_analysis:
        st.subheader("✍️ 最常阅读的作者")
        
        top_authors = author_analysis.get("top_authors", [])
        total_authors = author_analysis.get("total_authors", 0)
        
        if top_authors:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # 作者阅读量条形图
                authors = [author["author"] for author in top_authors[:10]]
                books_counts = [author["books_count"] for author in top_authors[:10]]
                reading_times = [author["total_reading_time"] / 3600 for author in top_authors[:10]]
                
                fig = make_subplots(
                    rows=1, cols=2,
                    subplot_titles=('按书籍数量', '按阅读时长'),
                    horizontal_spacing=0.1
                )
                
                fig.add_trace(
                    go.Bar(y=authors, x=books_counts, orientation='h', name="书籍数量", marker_color='lightgreen'),
                    row=1, col=1
                )
                
                fig.add_trace(
                    go.Bar(y=authors, x=reading_times, orientation='h', name="阅读时长", marker_color='lightcoral'),
                    row=1, col=2
                )
                
                fig.update_layout(height=400, showlegend=False, title_text="热门作者排行榜")
                fig.update_xaxes(title_text="书籍数量", row=1, col=1)
                fig.update_xaxes(title_text="阅读时长 (小时)", row=1, col=2)
                
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.metric("作者总数", total_authors)
                st.markdown("**🏆 TOP 5 作者:**")
                for i, author in enumerate(top_authors[:5]):
                    completed = author.get("completed_books", 0)
                    total_books = author.get("books_count", 0)
                    completion_rate = (completed / total_books * 100) if total_books > 0 else 0
                    
                    st.markdown(f"""
                    **{i+1}. {author['author']}**
                    - 📚 {total_books} 本书
                    - ⏱️ {author['total_reading_time']/3600:.1f} 小时
                    - ✅ 完成率: {completion_rate:.1f}%
                    """)
        
        # 作者详细统计表
        if len(top_authors) > 5:
            with st.expander("📊 查看完整作者统计"):
                authors_df = pd.DataFrame(top_authors)
                if not authors_df.empty:
                    authors_df['total_reading_hours'] = authors_df['total_reading_time'] / 3600
                    authors_df['completion_rate'] = (authors_df['completed_books'] / authors_df['books_count'] * 100).round(1)
                    
                    display_columns = ['author', 'books_count', 'total_reading_hours', 'completed_books', 'completion_rate', 'avg_progress']
                    column_names = {
                        'author': '作者',
                        'books_count': '书籍数量',
                        'total_reading_hours': '总阅读时长 (小时)',
                        'completed_books': '已完成书籍',
                        'completion_rate': '完成率 (%)',
                        'avg_progress': '平均进度 (%)'
                    }
                    
                    display_df = authors_df[display_columns].rename(columns=column_names)
                    display_df['总阅读时长 (小时)'] = display_df['总阅读时长 (小时)'].round(2)
                    display_df['平均进度 (%)'] = display_df['平均进度 (%)'].round(1)
                    
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # 语言分析
    language_analysis = metadata_analysis.get("language_analysis", {})
    if language_analysis:
        st.subheader("🌍 语言书籍阅读分布")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 语言分布饼图
            languages = list(language_analysis.keys())
            books_counts = [lang_data["books_count"] for lang_data in language_analysis.values()]
            
            fig = px.pie(
                values=books_counts,
                names=languages,
                title="按语言的书籍数量分布",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 语言阅读时长对比
            reading_times = [lang_data["total_reading_time"] / 3600 for lang_data in language_analysis.values()]
            
            fig = px.bar(
                x=languages,
                y=reading_times,
                title="按语言的阅读时长分布",
                labels={'x': '语言', 'y': '阅读时长 (小时)'},
                color=reading_times,
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # 设备分析
    device_analysis = metadata_analysis.get("device_analysis", {})
    if device_analysis:
        st.subheader("📱 设备使用分析")
        
        devices = list(device_analysis.keys())
        device_books = [dev_data["books_count"] for dev_data in device_analysis.values()]
        device_times = [dev_data["total_reading_time"] / 3600 for dev_data in device_analysis.values()]
        avg_sessions = [dev_data["avg_session_duration"] / 60 for dev_data in device_analysis.values()]
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 设备使用分布
            fig = px.bar(
                x=devices,
                y=device_books,
                title="各设备阅读书籍数量",
                labels={'x': '设备', 'y': '书籍数量'},
                color=device_books,
                color_continuous_scale='Greens'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 设备平均会话时长
            fig = px.bar(
                x=devices,
                y=avg_sessions,
                title="各设备平均阅读会话时长",
                labels={'x': '设备', 'y': '平均会话时长 (分钟)'},
                color=avg_sessions,
                color_continuous_scale='Oranges'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # 数据质量提示
    data_quality = metadata_analysis.get("data_quality", {})
    if data_quality:
        st.subheader("📊 数据质量报告")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "有作者信息", 
                data_quality.get("books_with_author", 0),
                delta=f"占比: {data_quality.get('books_with_author', 0)/data_quality.get('total_books', 1)*100:.1f}%"
            )
        
        with col2:
            st.metric(
                "缺失作者信息", 
                data_quality.get("books_without_author", 0),
                delta="建议补充元数据"
            )
        
        with col3:
            st.metric("书籍总数", data_quality.get("total_books", 0))
        
        # 数据质量建议
        if data_quality.get("books_without_author", 0) > 0:
            st.warning(f"""
            📝 **数据质量建议**: 
            检测到 {data_quality.get("books_without_author", 0)} 本书籍缺失作者信息。
            完善元数据可以获得更准确的分析结果。
            """)


def show_export_options():
    """显示导出选项"""
    
    st.subheader("📊 导出阅读分析报告")
    
    export_options = st.multiselect(
        "选择要导出的内容:",
        ["整体阅读总结", "单书统计数据", "时间模式分析", "元数据分析"],
        default=["整体阅读总结", "单书统计数据"]
    )
    
    file_format = st.selectbox("文件格式:", ["CSV", "Excel", "JSON"])
    
    if st.button("🚀 生成并下载报告"):
        st.success("📥 报告生成功能开发中...")
        st.info("💡 您可以使用浏览器的打印功能保存当前页面为PDF")


def show_empty_state():
    """显示空状态"""
    
    st.markdown("""
    <div style="text-align: center; padding: 3rem; color: #666;">
        <h2>📚 还没有阅读数据</h2>
        <p>开始使用KOReader阅读并同步数据，即可看到详细的阅读分析报告</p>
        
        <h3>🚀 快速开始:</h3>
        <ol style="text-align: left; display: inline-block;">
            <li>在KOReader中配置同步服务器</li>
            <li>开始阅读并产生统计数据</li>
            <li>上传KOReader统计文件</li>
            <li>返回此页面查看深度分析</li>
        </ol>
    </div>
    """, unsafe_allow_html=True) 