"""
缓存模块 - Redis缓存和性能优化
"""
import json
import pickle
import hashlib
from typing import Any, Optional, Union, Callable
from functools import wraps
import asyncio
import logging

from .config import settings

logger = logging.getLogger(__name__)

class CacheManager:
    """缓存管理器"""
    
    def __init__(self):
        self.redis_client: Optional[Any] = None
        self.enabled = settings.ENABLE_REDIS_CACHE
        self._connection_failed = False
        
    async def init(self):
        """初始化Redis连接"""
        if not self.enabled:
            logger.info("Redis缓存已禁用")
            return
            
        try:
            # 延迟导入redis，避免未安装时出错
            import redis.asyncio as redis
            
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=3,
                socket_connect_timeout=3,
                retry_on_timeout=False,
                max_connections=20
            )
            
            # 测试连接
            await self.redis_client.ping()
            logger.info("Redis缓存连接成功")
            self._connection_failed = False
            
        except ImportError:
            logger.warning("Redis未安装，禁用缓存功能")
            self.enabled = False
            self.redis_client = None
        except Exception as e:
            logger.warning(f"Redis连接失败，继续运行但禁用缓存: {e}")
            self.enabled = False
            self.redis_client = None
            self._connection_failed = True
    
    async def close(self):
        """关闭Redis连接"""
        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception as e:
                logger.warning(f"关闭Redis连接时出错: {e}")
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """生成缓存键"""
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return f"kompanion:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if not self.enabled or not self.redis_client:
            return None
            
        try:
            data = await self.redis_client.get(key)
            if data:
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    # 尝试pickle反序列化
                    return pickle.loads(data.encode('latin1'))
        except Exception as e:
            logger.debug(f"缓存获取失败 {key}: {e}")
        return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """设置缓存"""
        if not self.enabled or not self.redis_client:
            return False
            
        try:
            ttl = ttl or settings.CACHE_TTL_DEFAULT
            
            # 尝试JSON序列化
            try:
                data = json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                # 使用pickle序列化
                data = pickle.dumps(value).decode('latin1')
            
            await self.redis_client.setex(key, ttl, data)
            return True
            
        except Exception as e:
            logger.debug(f"缓存设置失败 {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self.enabled or not self.redis_client:
            return False
            
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.debug(f"缓存删除失败 {key}: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """清除匹配模式的缓存"""
        if not self.enabled or not self.redis_client:
            return 0
            
        try:
            keys = await self.redis_client.keys(f"kompanion:{pattern}")
            if keys:
                deleted = await self.redis_client.delete(*keys)
                return deleted
        except Exception as e:
            logger.debug(f"批量删除缓存失败 {pattern}: {e}")
        return 0
    
    async def get_stats(self) -> dict:
        """获取缓存统计信息"""
        if not self.enabled:
            return {"enabled": False, "reason": "disabled"}
        
        if self._connection_failed:
            return {"enabled": False, "reason": "connection_failed"}
            
        if not self.redis_client:
            return {"enabled": False, "reason": "not_connected"}
            
        try:
            info = await self.redis_client.info()
            return {
                "enabled": True,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "keys_count": await self.redis_client.dbsize(),
            }
        except Exception as e:
            logger.debug(f"获取缓存统计失败: {e}")
            return {"enabled": True, "error": str(e)}

# 全局缓存管理器实例
cache_manager = CacheManager()

def cache_result(ttl: int = None, key_prefix: str = "default"):
    """缓存装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not cache_manager.enabled:
                return await func(*args, **kwargs)
            
            cache_key = cache_manager._generate_key(
                f"{key_prefix}:{func.__name__}", *args, **kwargs
            )
            
            # 尝试从缓存获取
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数并缓存结果
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 同步函数版本
            return asyncio.get_event_loop().run_until_complete(
                async_wrapper(*args, **kwargs)
            )
        
        # 根据函数类型返回不同的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# 特定类型的缓存装饰器
def cache_opds(ttl: int = None):
    """OPDS缓存装饰器"""
    return cache_result(ttl or settings.CACHE_TTL_OPDS, "opds")

def cache_books(ttl: int = None):
    """书籍数据缓存装饰器"""
    return cache_result(ttl or settings.CACHE_TTL_BOOKS, "books")

def cache_stats(ttl: int = None):
    """统计数据缓存装饰器"""
    return cache_result(ttl or settings.CACHE_TTL_STATS, "stats")

async def invalidate_cache_pattern(pattern: str):
    """使指定模式的缓存失效"""
    return await cache_manager.clear_pattern(pattern)

async def warm_cache():
    """缓存预热"""
    if not settings.ENABLE_CACHE_WARMUP or not cache_manager.enabled:
        return
    
    logger.info("开始缓存预热...")
    
    try:
        # 这里可以添加预热逻辑
        # 例如：预加载热门书籍、常用OPDS目录等
        logger.info("缓存预热完成")
    except Exception as e:
        logger.error(f"缓存预热失败: {e}") 