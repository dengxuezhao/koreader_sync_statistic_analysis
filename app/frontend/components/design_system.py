"""
设计系统组件 - 现代简约风格的 UI 组件
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, List, Optional, Union
import pandas as pd
from config import DESIGN_SYSTEM, CHART_CONFIG

def apply_custom_css():
    """应用自定义 CSS 样式"""
    colors = DESIGN_SYSTEM["colors"]
    fonts = DESIGN_SYSTEM["fonts"]
    
    css = f"""
    <style>
    /* 导入 Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* 全局样式 */
    .main .block-container {{
        padding-top: 2rem;
        padding-bottom: 2rem;
    }}
    
    /* 隐藏 Streamlit 默认元素 */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    .stDeployButton {{display:none;}}
    
    /* 主容器样式 */
    .stApp {{
        background-color: {colors["background_light"]};
        font-family: {fonts["primary"]};
    }}
    
    /* 侧边栏样式 */
    .css-1d391kg {{
        background-color: {colors["primary"]};
    }}
    
    /* 指标卡片样式 */
    .metric-card {{
        background: {colors["background"]};
        padding: 1.5rem;
        border-radius: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        border: 1px solid {colors["background_dark"]};
        margin-bottom: 1rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    
    .metric-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    }}
    
    .metric-value {{
        font-size: 2.5rem;
        font-weight: 700;
        color: {colors["text_primary"]};
        margin: 0;
        line-height: 1.2;
    }}
    
    .metric-label {{
        font-size: 1rem;
        font-weight: 500;
        color: {colors["text_secondary"]};
        margin: 0.5rem 0 0 0;
    }}
    
    .metric-trend {{
        font-size: 0.875rem;
        font-weight: 500;
        margin-top: 0.5rem;
    }}
    
    .trend-positive {{
        color: {colors["success"]};
    }}
    
    .trend-negative {{
        color: {colors["error"]};
    }}
    
    /* 页面标题样式 */
    .page-title {{
        font-size: 2rem;
        font-weight: 600;
        color: {colors["text_primary"]};
        margin-bottom: 0.5rem;
    }}
    
    .page-subtitle {{
        font-size: 1.125rem;
        color: {colors["text_secondary"]};
        margin-bottom: 2rem;
    }}
    
    /* 导航样式 */
    .nav-item {{
        display: flex;
        align-items: center;
        padding: 0.75rem 1rem;
        margin: 0.25rem 0;
        border-radius: 0.5rem;
        color: rgba(255, 255, 255, 0.8);
        text-decoration: none;
        transition: all 0.2s ease;
    }}
    
    .nav-item:hover {{
        background-color: rgba(255, 255, 255, 0.1);
        color: white;
    }}
    
    .nav-item.active {{
        background-color: {colors["accent"]};
        color: white;
    }}
    
    .nav-icon {{
        margin-right: 0.75rem;
        font-size: 1.25rem;
    }}
    
    /* 图表容器样式 */
    .chart-container {{
        background: {colors["background"]};
        border-radius: 1rem;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border: 1px solid {colors["background_dark"]};
        margin-bottom: 1.5rem;
    }}
    
    .chart-title {{
        font-size: 1.25rem;
        font-weight: 600;
        color: {colors["text_primary"]};
        margin-bottom: 1rem;
    }}
    
    /* 表格样式 */
    .dataframe {{
        border: none !important;
    }}
    
    .dataframe th {{
        background-color: {colors["background_dark"]} !important;
        color: {colors["text_primary"]} !important;
        font-weight: 600 !important;
        border: none !important;
        padding: 1rem !important;
    }}
    
    .dataframe td {{
        border: none !important;
        padding: 0.75rem 1rem !important;
        border-bottom: 1px solid {colors["background_dark"]} !important;
    }}
    
    /* 按钮样式 */
    .stButton > button {{
        background-color: {colors["accent"]};
        color: white;
        border: none;
        border-radius: 0.5rem;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
        transition: all 0.2s ease;
    }}
    
    .stButton > button:hover {{
        background-color: {colors["accent_dark"]};
        transform: translateY(-1px);
    }}
    
    /* 选择框样式 */
    .stSelectbox > div > div {{
        background-color: {colors["background"]};
        border: 1px solid {colors["background_dark"]};
        border-radius: 0.5rem;
    }}
    
    /* 文本输入框样式 */
    .stTextInput > div > div > input {{
        background-color: {colors["background"]};
        border: 1px solid {colors["background_dark"]};
        border-radius: 0.5rem;
        color: {colors["text_primary"]};
    }}
    
    /* 成功消息样式 */
    .stSuccess {{
        background-color: rgba(56, 161, 105, 0.1);
        border: 1px solid {colors["success"]};
        border-radius: 0.5rem;
        color: {colors["success"]};
    }}
    
    /* 错误消息样式 */
    .stError {{
        background-color: rgba(229, 62, 62, 0.1);
        border: 1px solid {colors["error"]};
        border-radius: 0.5rem;
        color: {colors["error"]};
    }}
    
    /* 警告消息样式 */
    .stWarning {{
        background-color: rgba(214, 158, 46, 0.1);
        border: 1px solid {colors["warning"]};
        border-radius: 0.5rem;
        color: {colors["warning"]};
    }}
    
    /* 信息消息样式 */
    .stInfo {{
        background-color: rgba(49, 130, 206, 0.1);
        border: 1px solid {colors["info"]};
        border-radius: 0.5rem;
        color: {colors["info"]};
    }}
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)

def metric_card(title: str, value: Union[str, int, float], 
               trend: Optional[float] = None, 
               prefix: str = "", suffix: str = "",
               trend_label: str = "较上期"):
    """创建指标卡片"""
    
    # 格式化数值
    if isinstance(value, (int, float)):
        if value >= 1000000:
            formatted_value = f"{value/1000000:.1f}M"
        elif value >= 1000:
            formatted_value = f"{value/1000:.1f}K"
        else:
            formatted_value = f"{value:,.0f}" if isinstance(value, int) else f"{value:.1f}"
    else:
        formatted_value = str(value)
    
    # 趋势显示
    trend_html = ""
    if trend is not None:
        trend_class = "trend-positive" if trend >= 0 else "trend-negative"
        trend_symbol = "↗" if trend >= 0 else "↘"
        trend_html = f"""
        <div class="metric-trend {trend_class}">
            {trend_symbol} {abs(trend):.1f}% {trend_label}
        </div>
        """
    
    card_html = f"""
    <div class="metric-card">
        <div class="metric-value">{prefix}{formatted_value}{suffix}</div>
        <div class="metric-label">{title}</div>
        {trend_html}
    </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)

def page_header(title: str, subtitle: str = ""):
    """创建页面标题"""
    st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="page-subtitle">{subtitle}</div>', unsafe_allow_html=True)

def chart_container(title: str, chart_content):
    """创建图表容器"""
    st.markdown(f"""
    <div class="chart-container">
        <div class="chart-title">{title}</div>
    </div>
    """, unsafe_allow_html=True)
    chart_content()

def create_trend_chart(data: List[Dict], x_field: str, y_field: str, 
                      title: str = "", color: str = None) -> go.Figure:
    """创建趋势图表"""
    if not color:
        color = CHART_CONFIG["color_sequence"][0]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=[item[x_field] for item in data],
        y=[item[y_field] for item in data],
        mode='lines+markers',
        line=dict(color=color, width=3),
        marker=dict(size=8, color=color),
        name=title,
        hovertemplate='<b>%{x}</b><br>%{y}<extra></extra>'
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="",
        yaxis_title="",
        font=dict(family=CHART_CONFIG["font_family"], size=12, color=CHART_CONFIG["text_color"]),
        plot_bgcolor=CHART_CONFIG["background_color"],
        paper_bgcolor=CHART_CONFIG["background_color"],
        showlegend=False,
        margin=dict(l=0, r=0, t=40, b=0),
        height=300
    )
    
    fig.update_xaxes(gridcolor=CHART_CONFIG["grid_color"], zeroline=False)
    fig.update_yaxes(gridcolor=CHART_CONFIG["grid_color"], zeroline=False)
    
    return fig

def create_donut_chart(data: List[Dict], values_field: str, names_field: str, 
                      title: str = "") -> go.Figure:
    """创建环形图"""
    colors = CHART_CONFIG["color_sequence"]
    
    fig = go.Figure(data=[go.Pie(
        labels=[item[names_field] for item in data],
        values=[item[values_field] for item in data],
        hole=0.4,
        marker_colors=colors[:len(data)],
        textinfo='label+percent',
        textposition='outside',
        hovertemplate='<b>%{label}</b><br>%{value}<br>%{percent}<extra></extra>'
    )])
    
    fig.update_layout(
        title=title,
        font=dict(family=CHART_CONFIG["font_family"], size=12, color=CHART_CONFIG["text_color"]),
        plot_bgcolor=CHART_CONFIG["background_color"],
        paper_bgcolor=CHART_CONFIG["background_color"],
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05),
        margin=dict(l=0, r=100, t=40, b=0),
        height=400
    )
    
    return fig

def create_bar_chart(data: List[Dict], x_field: str, y_field: str, 
                    title: str = "", color: str = None) -> go.Figure:
    """创建条形图"""
    if not color:
        color = CHART_CONFIG["color_sequence"][1]
    
    fig = go.Figure(data=[go.Bar(
        x=[item[x_field] for item in data],
        y=[item[y_field] for item in data],
        marker_color=color,
        hovertemplate='<b>%{x}</b><br>%{y}<extra></extra>'
    )])
    
    fig.update_layout(
        title=title,
        xaxis_title="",
        yaxis_title="",
        font=dict(family=CHART_CONFIG["font_family"], size=12, color=CHART_CONFIG["text_color"]),
        plot_bgcolor=CHART_CONFIG["background_color"],
        paper_bgcolor=CHART_CONFIG["background_color"],
        showlegend=False,
        margin=dict(l=0, r=0, t=40, b=0),
        height=400
    )
    
    fig.update_xaxes(gridcolor=CHART_CONFIG["grid_color"], zeroline=False)
    fig.update_yaxes(gridcolor=CHART_CONFIG["grid_color"], zeroline=False)
    
    return fig

def status_badge(status: str, type: str = "info") -> str:
    """创建状态徽章"""
    colors = DESIGN_SYSTEM["colors"]
    
    color_map = {
        "success": colors["success"],
        "warning": colors["warning"],
        "error": colors["error"],
        "info": colors["info"]
    }
    
    color = color_map.get(type, colors["info"])
    
    return f"""
    <span style="
        background-color: {color};
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.75rem;
        font-weight: 500;
    ">{status}</span>
    """

def progress_bar(value: float, max_value: float = 100, height: str = "8px") -> str:
    """创建进度条"""
    colors = DESIGN_SYSTEM["colors"]
    percentage = (value / max_value) * 100
    
    return f"""
    <div style="
        width: 100%;
        background-color: {colors["background_dark"]};
        border-radius: 1rem;
        height: {height};
        overflow: hidden;
    ">
        <div style="
            width: {percentage}%;
            background-color: {colors["accent"]};
            height: 100%;
            border-radius: 1rem;
            transition: width 0.3s ease;
        "></div>
    </div>
    """ 