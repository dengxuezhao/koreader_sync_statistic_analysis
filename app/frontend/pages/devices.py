"""
设备管理页面
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

from app.frontend.api_client import DevicesAPI, api_client
from app.frontend.components.navigation import require_admin, page_header_with_actions
from app.frontend.config import DESIGN_SYSTEM, CHART_CONFIG

logger = logging.getLogger(__name__)

def show_devices_page():
    """显示设备管理页面"""
    
    # 页面标题和操作
    page_header_with_actions(
        title="📱 设备管理",
        subtitle="管理和监控 KOReader 设备状态",
        actions={
            "refresh": {
                "label": "🔄 刷新数据",
                "type": "primary",
                "callback": lambda: st.rerun()
            }
        }
    )
    
    try:
        # 获取设备数据
        with st.spinner("正在加载设备数据..."):
            devices_data = DevicesAPI.get_devices(page=1, size=100)
        
        if not devices_data or "devices" not in devices_data:
            st.warning("📭 暂无设备数据")
            return
        
        devices = devices_data["devices"]
        
        # 设备概览统计
        show_device_overview(devices)
        
        # 设备列表
        show_device_list(devices)
        
        # 设备分析图表
        show_device_analytics(devices)
        
    except Exception as e:
        logger.error(f"设备页面加载失败: {e}")
        st.error(f"❌ 设备数据加载失败: {str(e)}")
        
        # 显示连接说明
        with st.expander("🔧 解决方案"):
            st.markdown("""
            **可能的原因：**
            1. 后端服务未启动
            2. 网络连接问题
            3. 用户权限不足
            
            **解决方法：**
            1. 确保后端服务正在运行
            2. 检查API连接状态
            3. 尝试重新登录
            """)

def show_device_overview(devices: List[Dict[str, Any]]):
    """显示设备概览统计"""
    
    # 计算统计数据
    total_devices = len(devices)
    active_devices = len([d for d in devices if d.get("is_active", False)])
    recent_sync_devices = len([d for d in devices if d.get("last_sync_at")])
    sync_enabled_devices = len([d for d in devices if d.get("sync_enabled", False)])
    
    # 显示统计卡片
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📱 设备总数",
            value=total_devices,
            delta=None
        )
    
    with col2:
        st.metric(
            label="✅ 活跃设备", 
            value=active_devices,
            delta=f"{(active_devices/total_devices*100):.1f}%" if total_devices > 0 else "0%"
        )
    
    with col3:
        st.metric(
            label="🔄 已同步设备",
            value=recent_sync_devices,
            delta=f"{(recent_sync_devices/total_devices*100):.1f}%" if total_devices > 0 else "0%"
        )
    
    with col4:
        st.metric(
            label="⚙️ 启用同步",
            value=sync_enabled_devices, 
            delta=f"{(sync_enabled_devices/total_devices*100):.1f}%" if total_devices > 0 else "0%"
        )

def show_device_list(devices: List[Dict[str, Any]]):
    """显示设备列表"""
    
    st.subheader("📋 设备列表")
    
    if not devices:
        st.info("📭 暂无设备数据")
        return
    
    # 准备表格数据
    table_data = []
    for device in devices:
        # 处理同步时间
        last_sync = device.get("last_sync_at")
        if last_sync:
            try:
                sync_time = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
                sync_display = sync_time.strftime("%Y-%m-%d %H:%M")
                sync_ago = datetime.now() - sync_time.replace(tzinfo=None)
                if sync_ago.days > 0:
                    sync_status = f"📅 {sync_ago.days}天前"
                elif sync_ago.seconds > 3600:
                    sync_status = f"🕐 {sync_ago.seconds//3600}小时前"
                else:
                    sync_status = f"🕐 {sync_ago.seconds//60}分钟前"
            except:
                sync_display = "未知"
                sync_status = "❓ 异常"
        else:
            sync_display = "从未同步"
            sync_status = "⚪ 从未"
        
        # 状态标识
        status_icon = "🟢" if device.get("is_active") else "🔴"
        sync_icon = "✅" if device.get("sync_enabled") else "❌"
        
        table_data.append({
            "设备名称": device.get("device_name", "未知设备"),
            "型号": device.get("model", "-"),
            "状态": f"{status_icon} {'活跃' if device.get('is_active') else '非活跃'}",
            "同步": f"{sync_icon} {'启用' if device.get('sync_enabled') else '禁用'}",
            "最后同步": sync_display,
            "同步状态": sync_status,
            "同步次数": device.get("sync_count", 0),
            "固件版本": device.get("firmware_version", "-"),
            "KOReader版本": device.get("app_version", "-")
        })
    
    # 创建DataFrame并显示
    df = pd.DataFrame(table_data)
    
    # 添加过滤选项
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        status_filter = st.selectbox(
            "筛选状态",
            ["全部", "活跃", "非活跃"],
            key="device_status_filter"
        )
    
    with col2:
        sync_filter = st.selectbox(
            "筛选同步状态", 
            ["全部", "启用同步", "禁用同步"],
            key="device_sync_filter"
        )
    
    with col3:
        search_term = st.text_input(
            "搜索设备名称",
            placeholder="输入设备名称...",
            key="device_search"
        )
    
    # 应用过滤
    filtered_df = df.copy()
    
    if status_filter != "全部":
        filtered_df = filtered_df[filtered_df["状态"].str.contains(status_filter)]
    
    if sync_filter != "全部":
        if sync_filter == "启用同步":
            filtered_df = filtered_df[filtered_df["同步"].str.contains("启用")]
        else:
            filtered_df = filtered_df[filtered_df["同步"].str.contains("禁用")]
    
    if search_term:
        filtered_df = filtered_df[filtered_df["设备名称"].str.contains(search_term, case=False)]
    
    # 显示过滤后的表格
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "设备名称": st.column_config.TextColumn("🏷️ 设备名称", width="medium"),
            "型号": st.column_config.TextColumn("📱 型号", width="small"), 
            "状态": st.column_config.TextColumn("🟢 状态", width="small"),
            "同步": st.column_config.TextColumn("🔄 同步", width="small"),
            "最后同步": st.column_config.TextColumn("📅 最后同步", width="medium"),
            "同步状态": st.column_config.TextColumn("⏰ 状态", width="small"),
            "同步次数": st.column_config.NumberColumn("🔢 次数", width="small"),
            "固件版本": st.column_config.TextColumn("⚙️ 固件", width="small"),
            "KOReader版本": st.column_config.TextColumn("📖 KOReader", width="small")
        }
    )
    
    # 显示筛选结果统计
    if len(filtered_df) != len(df):
        st.caption(f"筛选结果：{len(filtered_df)} / {len(df)} 台设备")

def show_device_analytics(devices: List[Dict[str, Any]]):
    """显示设备分析图表"""
    
    st.subheader("📊 设备分析")
    
    if not devices:
        st.info("📭 暂无数据可供分析")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 设备状态分布饼图
        active_count = len([d for d in devices if d.get("is_active", False)])
        inactive_count = len(devices) - active_count
        
        fig_status = go.Figure(data=[go.Pie(
            labels=["活跃设备", "非活跃设备"],
            values=[active_count, inactive_count],
            marker_colors=[CHART_CONFIG["color_sequence"][0], CHART_CONFIG["color_sequence"][3]],
            hole=0.4
        )])
        
        fig_status.update_layout(
            title="设备状态分布",
            font=dict(family=CHART_CONFIG["font_family"]),
            showlegend=True,
            height=300
        )
        
        st.plotly_chart(fig_status, use_container_width=True)
    
    with col2:
        # 同步状态分布饼图
        sync_enabled = len([d for d in devices if d.get("sync_enabled", False)])
        sync_disabled = len(devices) - sync_enabled
        
        fig_sync = go.Figure(data=[go.Pie(
            labels=["启用同步", "禁用同步"],
            values=[sync_enabled, sync_disabled],
            marker_colors=[CHART_CONFIG["color_sequence"][1], CHART_CONFIG["color_sequence"][4]],
            hole=0.4
        )])
        
        fig_sync.update_layout(
            title="同步设置分布",
            font=dict(family=CHART_CONFIG["font_family"]),
            showlegend=True,
            height=300
        )
        
        st.plotly_chart(fig_sync, use_container_width=True)
    
    # 设备型号统计
    model_counts = {}
    for device in devices:
        model = device.get("model", "未知型号")
        model_counts[model] = model_counts.get(model, 0) + 1
    
    if len(model_counts) > 1:
        st.subheader("📱 设备型号分布")
        
        models = list(model_counts.keys())
        counts = list(model_counts.values())
        
        fig_models = px.bar(
            x=models,
            y=counts,
            title="设备型号统计",
            labels={"x": "设备型号", "y": "数量"},
            color_discrete_sequence=CHART_CONFIG["color_sequence"]
        )
        
        fig_models.update_layout(
            font=dict(family=CHART_CONFIG["font_family"]),
            xaxis_tickangle=-45,
            height=400
        )
        
        st.plotly_chart(fig_models, use_container_width=True)
    
    # 同步活动时间线（如果有同步数据）
    sync_devices = [d for d in devices if d.get("last_sync_at")]
    if sync_devices:
        st.subheader("📅 同步活动时间线")
        
        # 准备时间线数据
        timeline_data = []
        for device in sync_devices:
            try:
                sync_time = datetime.fromisoformat(device["last_sync_at"].replace("Z", "+00:00"))
                timeline_data.append({
                    "设备": device.get("device_name", "未知"),
                    "同步时间": sync_time,
                    "同步次数": device.get("sync_count", 0)
                })
            except:
                continue
        
        if timeline_data:
            df_timeline = pd.DataFrame(timeline_data)
            df_timeline = df_timeline.sort_values("同步时间")
            
            fig_timeline = px.scatter(
                df_timeline,
                x="同步时间",
                y="设备",
                size="同步次数",
                title="设备同步活动时间线",
                color="设备",
                color_discrete_sequence=CHART_CONFIG["color_sequence"]
            )
            
            fig_timeline.update_layout(
                font=dict(family=CHART_CONFIG["font_family"]),
                height=400,
                showlegend=False
            )
            
            st.plotly_chart(fig_timeline, use_container_width=True)

if __name__ == "__main__":
    show_devices_page() 