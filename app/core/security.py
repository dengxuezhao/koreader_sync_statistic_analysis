"""
安全配置和工具模块

提供完整的安全功能，包括密码处理、JWT令牌、API限流、安全头、输入验证等。
"""

import hashlib
import secrets
import time
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from functools import wraps
import logging
from ipaddress import ip_address, ip_network

from fastapi import HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
import bcrypt

from app.core.config import settings

logger = logging.getLogger(__name__)

# 密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer认证
security = HTTPBearer()

# 安全配置
SECURITY_CONFIG = {
    "MAX_LOGIN_ATTEMPTS": 5,
    "LOGIN_LOCKOUT_DURATION": 900,  # 15分钟
    "SESSION_TIMEOUT": 3600,  # 1小时
    "PASSWORD_MIN_LENGTH": 8,
    "PASSWORD_REQUIRE_SPECIAL": True,
    "PASSWORD_REQUIRE_NUMBERS": True,
    "PASSWORD_REQUIRE_UPPERCASE": True,
    "RATE_LIMIT_REQUESTS": 60,  # 每分钟请求数
    "RATE_LIMIT_WINDOW": 60,  # 时间窗口（秒）
    "MAX_FILE_SIZE": 500 * 1024 * 1024,  # 500MB
    "ALLOWED_MIME_TYPES": [
        "application/epub+zip",
        "application/pdf",
        "application/x-mobipocket-ebook",
        "application/vnd.amazon.ebook",
        "text/plain",
        "application/rtf"
    ]
}

class SecurityError(Exception):
    """安全相关异常"""
    pass

class RateLimiter:
    """API速率限制器"""
    
    def __init__(self):
        self.requests: Dict[str, List[float]] = {}
        self.blocked_ips: Dict[str, float] = {}
    
    def is_allowed(self, client_ip: str, limit: int = None, window: int = None) -> bool:
        """检查是否允许请求"""
        current_time = time.time()
        limit = limit or SECURITY_CONFIG["RATE_LIMIT_REQUESTS"]
        window = window or SECURITY_CONFIG["RATE_LIMIT_WINDOW"]
        
        # 检查IP是否被阻止
        if client_ip in self.blocked_ips:
            if current_time - self.blocked_ips[client_ip] < 3600:  # 阻止1小时
                return False
            else:
                del self.blocked_ips[client_ip]
        
        # 清理过期请求
        if client_ip in self.requests:
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if current_time - req_time < window
            ]
        else:
            self.requests[client_ip] = []
        
        # 检查请求频率
        if len(self.requests[client_ip]) >= limit:
            # 阻止该IP
            self.blocked_ips[client_ip] = current_time
            logger.warning(f"IP {client_ip} 被限流阻止")
            return False
        
        # 记录请求
        self.requests[client_ip].append(current_time)
        return True
    
    def reset_ip(self, client_ip: str):
        """重置IP的请求记录"""
        if client_ip in self.requests:
            del self.requests[client_ip]
        if client_ip in self.blocked_ips:
            del self.blocked_ips[client_ip]

class LoginAttemptTracker:
    """登录尝试跟踪器"""
    
    def __init__(self):
        self.attempts: Dict[str, Dict[str, Any]] = {}
    
    def record_attempt(self, identifier: str, success: bool):
        """记录登录尝试"""
        current_time = time.time()
        
        if identifier not in self.attempts:
            self.attempts[identifier] = {
                "count": 0,
                "last_attempt": current_time,
                "locked_until": 0
            }
        
        attempt_data = self.attempts[identifier]
        
        if success:
            # 登录成功，重置计数
            attempt_data["count"] = 0
            attempt_data["locked_until"] = 0
        else:
            # 登录失败，增加计数
            attempt_data["count"] += 1
            attempt_data["last_attempt"] = current_time
            
            # 检查是否需要锁定
            if attempt_data["count"] >= SECURITY_CONFIG["MAX_LOGIN_ATTEMPTS"]:
                attempt_data["locked_until"] = current_time + SECURITY_CONFIG["LOGIN_LOCKOUT_DURATION"]
                logger.warning(f"用户 {identifier} 因多次登录失败被锁定")
    
    def is_locked(self, identifier: str) -> bool:
        """检查是否被锁定"""
        if identifier not in self.attempts:
            return False
        
        attempt_data = self.attempts[identifier]
        current_time = time.time()
        
        if attempt_data["locked_until"] > current_time:
            return True
        
        # 锁定时间过期，重置
        if attempt_data["locked_until"] > 0:
            attempt_data["count"] = 0
            attempt_data["locked_until"] = 0
        
        return False
    
    def get_remaining_lockout_time(self, identifier: str) -> int:
        """获取剩余锁定时间"""
        if identifier not in self.attempts:
            return 0
        
        attempt_data = self.attempts[identifier]
        current_time = time.time()
        
        if attempt_data["locked_until"] > current_time:
            return int(attempt_data["locked_until"] - current_time)
        
        return 0

class InputValidator:
    """输入验证器"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """验证邮箱格式"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """验证用户名格式"""
        # 用户名：3-30字符，只允许字母、数字、下划线、连字符
        pattern = r'^[a-zA-Z0-9_-]{3,30}$'
        return re.match(pattern, username) is not None
    
    @staticmethod
    def validate_password(password: str) -> tuple[bool, str]:
        """验证密码强度"""
        if len(password) < SECURITY_CONFIG["PASSWORD_MIN_LENGTH"]:
            return False, f"密码长度至少{SECURITY_CONFIG['PASSWORD_MIN_LENGTH']}位"
        
        if SECURITY_CONFIG["PASSWORD_REQUIRE_UPPERCASE"] and not re.search(r'[A-Z]', password):
            return False, "密码必须包含大写字母"
        
        if SECURITY_CONFIG["PASSWORD_REQUIRE_NUMBERS"] and not re.search(r'\d', password):
            return False, "密码必须包含数字"
        
        if SECURITY_CONFIG["PASSWORD_REQUIRE_SPECIAL"] and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "密码必须包含特殊字符"
        
        return True, ""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """清理文件名，防止路径遍历攻击"""
        # 移除路径分隔符和特殊字符
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = filename.replace('..', '')
        
        # 限制长度
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:250] + ('.' + ext if ext else '')
        
        return filename
    
    @staticmethod
    def validate_file_type(filename: str, content_type: str) -> bool:
        """验证文件类型"""
        allowed_extensions = {'.epub', '.pdf', '.mobi', '.azw', '.azw3', '.fb2', '.txt', '.rtf'}
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        return (
            f'.{file_ext}' in allowed_extensions and
            content_type in SECURITY_CONFIG["ALLOWED_MIME_TYPES"]
        )

class SecurityHeaders:
    """安全头管理"""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """获取安全头"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            ),
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }

class IPWhitelist:
    """IP白名单管理"""
    
    def __init__(self):
        # 默认允许的IP范围
        self.allowed_networks = [
            ip_network("127.0.0.0/8"),     # 本地回环
            ip_network("10.0.0.0/8"),      # 私有网络
            ip_network("172.16.0.0/12"),   # 私有网络
            ip_network("192.168.0.0/16"),  # 私有网络
        ]
    
    def is_allowed(self, client_ip: str) -> bool:
        """检查IP是否在白名单中"""
        try:
            ip = ip_address(client_ip)
            return any(ip in network for network in self.allowed_networks)
        except ValueError:
            return False
    
    def add_network(self, network_str: str):
        """添加网络到白名单"""
        try:
            network = ip_network(network_str)
            self.allowed_networks.append(network)
        except ValueError as e:
            logger.error(f"无效的网络地址: {network_str} - {e}")

# 全局实例
rate_limiter = RateLimiter()
login_tracker = LoginAttemptTracker()
input_validator = InputValidator()
security_headers = SecurityHeaders()
ip_whitelist = IPWhitelist()

# KOReader兼容的MD5认证
def hash_password_md5(password: str) -> str:
    """KOReader兼容的MD5密码哈希
    
    注意：MD5被认为不安全，但为了与KOReader的kosync插件兼容，
    我们必须使用MD5哈希（无盐）。在未来KOReader更新认证方式后，
    可以考虑迁移到更安全的哈希算法。
    """
    return hashlib.md5(password.encode('utf-8')).hexdigest()

def verify_password_md5(password: str, hashed_password: str) -> bool:
    """验证MD5密码"""
    return hash_password_md5(password) == hashed_password

# 现代化密码哈希（用于管理员等）
def hash_password_bcrypt(password: str) -> str:
    """使用bcrypt哈希密码（安全）"""
    return pwd_context.hash(password)

def verify_password_bcrypt(plain_password: str, hashed_password: str) -> bool:
    """验证bcrypt密码"""
    return pwd_context.verify(plain_password, hashed_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """智能密码验证（自动检测哈希类型）"""
    if len(hashed_password) == 32:  # MD5哈希长度
        return verify_password_md5(plain_password, hashed_password)
    else:
        return verify_password_bcrypt(plain_password, hashed_password)

# JWT令牌管理
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建JWT访问令牌"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """验证JWT令牌"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

# 设备令牌管理（KOReader设备认证）
def create_device_token(user_id: int, device_name: str) -> str:
    """为KOReader设备创建专用令牌"""
    data = {
        "sub": str(user_id),
        "device": device_name,
        "type": "device",
    }
    # 设备令牌有效期更长（30天）
    expires_delta = timedelta(days=30)
    return create_access_token(data, expires_delta)

def verify_device_token(token: str) -> Optional[tuple[int, str]]:
    """验证设备令牌，返回(user_id, device_name)"""
    payload = verify_token(token)
    if payload is None:
        return None
    
    if payload.get("type") != "device":
        return None
    
    try:
        user_id = int(payload.get("sub"))
        device_name = payload.get("device")
        if user_id and device_name:
            return user_id, device_name
    except (ValueError, TypeError):
        pass
    
    return None

# API密钥管理
def generate_api_key() -> str:
    """生成安全的API密钥"""
    return secrets.token_urlsafe(32)

def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """验证API密钥"""
    # 使用bcrypt验证API密钥
    return verify_password_bcrypt(api_key, stored_hash)

def hash_api_key(api_key: str) -> str:
    """哈希API密钥"""
    return hash_password_bcrypt(api_key)

# 文件哈希计算
@staticmethod
def calculate_file_hash(file_content: bytes, algorithm: str = "sha256") -> str:
    """计算文件哈希值"""
    if algorithm == "md5":
        return hashlib.md5(file_content).hexdigest()
    elif algorithm == "sha1":
        return hashlib.sha1(file_content).hexdigest()
    elif algorithm == "sha256":
        return hashlib.sha256(file_content).hexdigest()
    else:
        raise ValueError(f"不支持的哈希算法: {algorithm}")

# 安全随机数生成
@staticmethod
def generate_random_string(length: int = 32) -> str:
    """生成安全的随机字符串"""
    return secrets.token_urlsafe(length)

@staticmethod
def generate_device_id() -> str:
    """生成设备ID"""
    return secrets.token_hex(16)  # 32字符的十六进制字符串

# 安全装饰器
def require_rate_limit(limit: int = None, window: int = None):
    """API速率限制装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从参数中提取Request对象
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if request:
                client_ip = request.client.host
                if not rate_limiter.is_allowed(client_ip, limit, window):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="请求过于频繁，请稍后再试"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_admin_ip():
    """管理员IP限制装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从参数中提取Request对象
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if request:
                client_ip = request.client.host
                if not ip_whitelist.is_allowed(client_ip):
                    logger.warning(f"未授权的管理访问尝试: {client_ip}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="访问被拒绝：IP地址未授权"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def validate_file_upload(filename: str, content_type: str, file_size: int):
    """文件上传验证"""
    # 验证文件名
    if not filename or len(filename.strip()) == 0:
        raise SecurityError("文件名不能为空")
    
    # 清理文件名
    safe_filename = input_validator.sanitize_filename(filename)
    if not safe_filename:
        raise SecurityError("文件名包含非法字符")
    
    # 验证文件类型
    if not input_validator.validate_file_type(filename, content_type):
        raise SecurityError("不支持的文件类型")
    
    # 验证文件大小
    if file_size > SECURITY_CONFIG["MAX_FILE_SIZE"]:
        raise SecurityError(f"文件大小超出限制 ({SECURITY_CONFIG['MAX_FILE_SIZE']} bytes)")
    
    return safe_filename

async def check_sql_injection(query_params: Dict[str, Any]) -> bool:
    """检查SQL注入"""
    sql_injection_patterns = [
        r"('|(\\')|(;)|(\\;))",  # 单引号和分号
        r"((\%27)|(\'))((\%6F)|o|(\%4F))((\%72)|r|(\%52))",  # 'or
        r"((\%27)|(\'))((\%75)|u|(\%55))((\%6E)|n|(\%4E))((\%69)|i|(\%49))((\%6F)|o|(\%4F))((\%6E)|n|(\%4E))",  # 'union
        r"(exec(\s|\+)+(s|x)p\w+)",  # exec stored procedures
        r"(union(.|\n)*?select)",  # union select
        r"(select(.|\n)*?from)",  # select from
        r"(insert(.|\n)*?into)",  # insert into
        r"(delete(.|\n)*?from)",  # delete from
        r"(update(.|\n)*?set)",  # update set
        r"(drop(.|\n)*?(table|database))",  # drop table/database
    ]
    
    for param_value in query_params.values():
        if isinstance(param_value, str):
            for pattern in sql_injection_patterns:
                if re.search(pattern, param_value.lower()):
                    logger.warning(f"检测到潜在SQL注入: {param_value}")
                    return True
    
    return False

def generate_csrf_token() -> str:
    """生成CSRF令牌"""
    return secrets.token_urlsafe(32)

def verify_csrf_token(token: str, expected_token: str) -> bool:
    """验证CSRF令牌"""
    return secrets.compare_digest(token, expected_token)

class SecurityAuditLogger:
    """安全审计日志器"""
    
    @staticmethod
    def log_security_event(event_type: str, user_id: Optional[int], ip_address: str, details: Dict[str, Any]):
        """记录安全事件"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
            "details": details
        }
        
        # 根据事件严重性选择日志级别
        if event_type in ["failed_login", "rate_limit_exceeded", "unauthorized_access"]:
            logger.warning(f"安全事件: {log_entry}")
        elif event_type in ["successful_login", "file_upload", "password_change"]:
            logger.info(f"安全事件: {log_entry}")
        else:
            logger.error(f"严重安全事件: {log_entry}")

# 全局安全审计日志器
security_audit = SecurityAuditLogger()

# 导出
__all__ = [
    "SecurityManager",
    "security", 
    "hash_password_md5",
    "verify_password_md5",
    "create_access_token",
    "verify_token",
] 