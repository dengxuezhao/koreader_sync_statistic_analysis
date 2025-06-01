"""
导航和认证组件
"""

import streamlit as st
from typing import Dict, Any, Optional, List
from app.frontend.config import NAVIGATION_CONFIG, DESIGN_SYSTEM, API_BASE_URL
from app.frontend.api_client import AuthAPI, check_api_health

def check_authentication() -> bool:
    """检查用户认证状态"""
    if 'auth_token' not in st.session_state:
        return False
    
    # 如果已经有用户信息，直接返回True
    if 'user_info' in st.session_state:
        return True
    
    # 验证 token 是否有效
    try:
        user_info = AuthAPI.get_current_user()
        st.session_state.user_info = user_info
        return True
    except:
        # /me端点失败时，尝试从token中解析基本信息
        # 这是临时解决方案，避免/me端点的500错误影响登录
        try:
            from jose import jwt
            token = st.session_state.auth_token
            # 不验证签名，只解析payload获取用户名
            payload = jwt.get_unverified_claims(token)
            username = payload.get("sub")
            if username:
                # 使用基本用户信息
                st.session_state.user_info = {
                    "username": username,
                    "is_admin": username.lower() == "admin",  # 简单假设admin是管理员
                    "is_active": True,
                    "email": None
                }
                return True
        except:
            pass
        
        # Token 无效，清除认证状态
        if 'auth_token' in st.session_state:
            del st.session_state.auth_token
        if 'user_info' in st.session_state:
            del st.session_state.user_info
        return False

def login_form():
    """显示登录表单"""
    st.markdown("""
    <div style="max-width: 400px; margin: 2rem auto; padding: 2rem; 
                background: white; border-radius: 1rem; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="color: #0A2A4E; margin-bottom: 0.5rem;">📚 Kompanion</h1>
            <p style="color: #718096; margin: 0;">阅读统计分析系统</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 检查 API 连接状态
    if not check_api_health():
        st.error("⚠️ 无法连接到后端服务")
        
        with st.expander("🔧 解决方案", expanded=True):
            st.markdown("""
            **后端服务未启动，请选择以下方式之一：**
            
            **方式 1：启动完整系统（推荐）**
            ```bash
            uv run python main.py both
            ```
            
            **方式 2：仅启动后端**
            ```bash
            uv run python main.py backend
            ```
            
            **方式 3：使用项目脚本**
            ```bash
            uv run koreader-server
            ```
            
            **启动成功后，刷新此页面即可使用。**
            """)
        
        st.info(f"💡 后端服务地址: {API_BASE_URL}")
        
        # 添加刷新按钮
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 检查连接", use_container_width=True, type="primary"):
                st.rerun()
        
        return
    
    # 连接正常，显示登录表单
    st.success("✅ 后端服务连接正常")
    
    with st.form("login_form"):
        st.subheader("用户登录")
        
        username = st.text_input("用户名", placeholder="请输入用户名")
        password = st.text_input("密码", type="password", placeholder="请输入密码")
        
        # 添加默认账户提示
        with st.expander("💡 默认账户信息"):
            st.info("""
            **默认管理员账户：**
            - 用户名: `admin`
            - 密码: `admin`
            
            如需修改，请在环境变量中设置 `AUTH_USERNAME` 和 `AUTH_PASSWORD`
            """)
        
        submitted = st.form_submit_button("登录", use_container_width=True)
        
        if submitted:
            if not username or not password:
                st.error("请输入用户名和密码")
                return
            
            try:
                with st.spinner("登录中..."):
                    response = AuthAPI.login(username, password)
                    
                if response.get("access_token"):
                    st.session_state.auth_token = response["access_token"]
                    # 使用基本用户信息，避免调用有问题的/me端点
                    st.session_state.user_info = {
                        "username": username,
                        "is_admin": username.lower() == "admin",  # 简单假设admin是管理员
                        "is_active": True,
                        "email": None
                    }
                    
                    st.success("登录成功！")
                    st.rerun()
                else:
                    st.error("登录失败：响应格式错误")
                    
            except Exception as e:
                st.error(f"登录失败：{str(e)}")

def sidebar_navigation():
    """创建侧边栏导航"""
    # 获取当前用户信息
    user_info = st.session_state.get('user_info', {})
    
    # Logo 和用户信息
    st.sidebar.markdown(f"""
    <div style="text-align: center; padding: 1rem 0; border-bottom: 1px solid rgba(255,255,255,0.2); margin-bottom: 1rem;">
        <h2 style="color: white; margin: 0; font-size: 1.5rem;">📚 Kompanion</h2>
        <p style="color: rgba(255,255,255,0.7); margin: 0.5rem 0 0 0; font-size: 0.8rem;">阅读数据分析</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 用户信息
    if user_info:
        st.sidebar.markdown(f"""
        <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 0.5rem; margin-bottom: 1.5rem;">
            <div style="color: white; font-weight: 500;">👤 {user_info.get('username', '用户')}</div>
            <div style="color: rgba(255,255,255,0.7); font-size: 0.8rem; margin-top: 0.25rem;">
                {'🔐 管理员' if user_info.get('is_admin') else '👤 普通用户'}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # 导航菜单
    st.sidebar.markdown("### 📊 数据分析")
    
    # 获取当前页面
    current_page = st.session_state.get('current_page', 'overview')
    
    # 创建导航按钮
    pages = NAVIGATION_CONFIG["pages"]
    
    for page in pages:
        # 权限检查
        if page["key"] == "settings" and not user_info.get('is_admin', False):
            continue
            
        # 创建按钮
        button_style = "primary" if page["key"] == current_page else "secondary"
        
        if st.sidebar.button(
            f"{page['icon']} {page['name']}",
            key=f"nav_{page['key']}",
            help=page["description"],
            use_container_width=True,
            type=button_style
        ):
            st.session_state.current_page = page["key"]
            st.rerun()
    
    # 添加分隔线
    st.sidebar.markdown("---")
    
    # 系统状态
    api_status = check_api_health()
    status_color = "#38A169" if api_status else "#E53E3E"
    status_text = "正常" if api_status else "异常"
    
    st.sidebar.markdown(f"""
    <div style="padding: 0.5rem; background: rgba(255,255,255,0.05); border-radius: 0.5rem; margin-bottom: 1rem;">
        <div style="color: rgba(255,255,255,0.7); font-size: 0.8rem;">系统状态</div>
        <div style="color: {status_color}; font-weight: 500; font-size: 0.9rem;">🔄 API服务: {status_text}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # 退出登录按钮
    if st.sidebar.button("🚪 退出登录", use_container_width=True, type="secondary"):
        # 清除会话状态
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

def get_current_page() -> str:
    """获取当前页面"""
    return st.session_state.get('current_page', 'overview')

def set_current_page(page: str):
    """设置当前页面"""
    st.session_state.current_page = page

def require_admin():
    """检查管理员权限"""
    user_info = st.session_state.get('user_info', {})
    if not user_info.get('is_admin', False):
        st.error("🔒 此功能需要管理员权限")
        st.stop()

def page_header_with_actions(title: str, subtitle: str = "", actions: Optional[Dict] = None):
    """创建带操作按钮的页面标题"""
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown(f"""
        <div style="margin-bottom: 1rem;">
            <h1 style="color: #2D3748; margin: 0; font-size: 2rem; font-weight: 600;">{title}</h1>
            {f'<p style="color: #718096; margin: 0.5rem 0 0 0; font-size: 1.1rem;">{subtitle}</p>' if subtitle else ''}
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if actions:
            for action_key, action_config in actions.items():
                if st.button(
                    action_config["label"],
                    key=f"action_{action_key}",
                    type=action_config.get("type", "secondary"),
                    use_container_width=True
                ):
                    if "callback" in action_config:
                        action_config["callback"]()

def breadcrumb(items: List[str]):
    """创建面包屑导航"""
    breadcrumb_html = ""
    for i, item in enumerate(items):
        if i > 0:
            breadcrumb_html += ' <span style="color: #A0AEC0;">></span> '
        
        if i == len(items) - 1:  # 最后一个项目
            breadcrumb_html += f'<span style="color: #2D3748; font-weight: 500;">{item}</span>'
        else:
            breadcrumb_html += f'<span style="color: #718096;">{item}</span>'
    
    st.markdown(f"""
    <div style="margin-bottom: 1rem; padding: 0.75rem 1rem; background: white; border-radius: 0.5rem; 
                border: 1px solid #E2E8F0;">
        {breadcrumb_html}
    </div>
    """, unsafe_allow_html=True) 