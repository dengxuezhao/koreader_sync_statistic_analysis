"""
性能监控和优化工具模块
"""
import time
import psutil
import asyncio
from typing import Dict, List, Optional, Callable, Any
from functools import wraps
import logging
from contextlib import asynccontextmanager

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest

logger = logging.getLogger(__name__)

# Prometheus指标
REGISTRY = CollectorRegistry()

REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=REGISTRY
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    registry=REGISTRY
)

ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections',
    registry=REGISTRY
)

DATABASE_CONNECTIONS = Gauge(
    'database_connections_total',
    'Total database connections',
    ['state'],
    registry=REGISTRY
)

CACHE_OPERATIONS = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'result'],
    registry=REGISTRY
)

BOOK_OPERATIONS = Counter(
    'book_operations_total',
    'Total book operations',
    ['operation'],
    registry=REGISTRY
)

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.slow_queries: List[Dict] = []
        self.max_slow_queries = 100
        
    def record_slow_query(self, query: str, duration: float, params: Dict = None):
        """记录慢查询"""
        if len(self.slow_queries) >= self.max_slow_queries:
            self.slow_queries.pop(0)
            
        self.slow_queries.append({
            'query': query,
            'duration': duration,
            'params': params,
            'timestamp': time.time()
        })
        
        logger.warning(f"慢查询检测: {duration:.2f}s - {query[:100]}...")
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict]:
        """获取慢查询记录"""
        return sorted(self.slow_queries, key=lambda x: x['duration'], reverse=True)[:limit]
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """获取系统性能指标"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'cpu': {
                'percent': cpu_percent,
                'count': psutil.cpu_count(),
                'load_avg': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            },
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent,
                'used': memory.used
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': disk.percent
            },
            'network': self._get_network_stats()
        }
    
    def _get_network_stats(self) -> Dict[str, int]:
        """获取网络统计"""
        try:
            stats = psutil.net_io_counters()
            return {
                'bytes_sent': stats.bytes_sent,
                'bytes_recv': stats.bytes_recv,
                'packets_sent': stats.packets_sent,
                'packets_recv': stats.packets_recv
            }
        except Exception:
            return {}

# 全局性能监控器实例
performance_monitor = PerformanceMonitor()

def monitor_performance(operation_type: str = "general"):
    """性能监控装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"操作失败 {operation_type}: {e}")
                raise
            finally:
                duration = time.time() - start_time
                if duration > 1.0:  # 超过1秒记录为慢操作
                    logger.warning(f"慢操作 {operation_type}: {func.__name__} - {duration:.2f}s")
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"操作失败 {operation_type}: {e}")
                raise
            finally:
                duration = time.time() - start_time
                if duration > 1.0:
                    logger.warning(f"慢操作 {operation_type}: {func.__name__} - {duration:.2f}s")
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

@asynccontextmanager
async def performance_context(operation_name: str):
    """性能监控上下文管理器"""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        if duration > 0.5:  # 超过0.5秒记录
            logger.info(f"操作耗时 {operation_name}: {duration:.2f}s")

class DatabasePerformanceTracker:
    """数据库性能跟踪器"""
    
    def __init__(self):
        self.query_stats: Dict[str, Dict] = {}
    
    def track_query(self, query_hash: str, duration: float, query: str = None):
        """跟踪查询性能"""
        if query_hash not in self.query_stats:
            self.query_stats[query_hash] = {
                'count': 0,
                'total_time': 0.0,
                'max_time': 0.0,
                'min_time': float('inf'),
                'avg_time': 0.0,
                'query': query[:200] if query else None  # 保存查询的前200字符
            }
        
        stats = self.query_stats[query_hash]
        stats['count'] += 1
        stats['total_time'] += duration
        stats['max_time'] = max(stats['max_time'], duration)
        stats['min_time'] = min(stats['min_time'], duration)
        stats['avg_time'] = stats['total_time'] / stats['count']
        
        # 记录慢查询
        if duration > 1.0:
            performance_monitor.record_slow_query(query or f"Query#{query_hash}", duration)
    
    def get_query_stats(self, limit: int = 20) -> List[Dict]:
        """获取查询统计，按平均执行时间排序"""
        return sorted(
            [
                {'hash': hash_val, **stats} 
                for hash_val, stats in self.query_stats.items()
            ],
            key=lambda x: x['avg_time'],
            reverse=True
        )[:limit]
    
    def reset_stats(self):
        """重置统计数据"""
        self.query_stats.clear()

# 全局数据库性能跟踪器
db_performance_tracker = DatabasePerformanceTracker()

def optimize_query_params(func: Callable):
    """查询优化装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # 添加查询优化逻辑
        # 例如：自动添加合适的索引提示、限制结果集大小等
        
        # 如果有limit参数且过大，则限制它
        if 'limit' in kwargs and kwargs['limit'] > 1000:
            logger.warning(f"限制查询结果集大小: {kwargs['limit']} -> 1000")
            kwargs['limit'] = 1000
        
        return await func(*args, **kwargs)
    
    return wrapper

async def get_performance_metrics() -> Dict[str, Any]:
    """获取完整的性能指标"""
    from app.core.cache import cache_manager
    from app.core.database import engine
    
    metrics = {
        'system': performance_monitor.get_system_metrics(),
        'slow_queries': performance_monitor.get_slow_queries(),
        'database': {
            'query_stats': db_performance_tracker.get_query_stats(),
            'pool_stats': {
                'size': engine.pool.size() if hasattr(engine, 'pool') else 0,
                'checked_in': engine.pool.checkedin() if hasattr(engine, 'pool') else 0,
                'checked_out': engine.pool.checkedout() if hasattr(engine, 'pool') else 0,
            }
        },
        'cache': await cache_manager.get_stats(),
        'prometheus_metrics': generate_latest(REGISTRY).decode('utf-8')
    }
    
    return metrics

def update_prometheus_metrics(method: str, endpoint: str, status_code: int, duration: float):
    """更新Prometheus指标"""
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=str(status_code)).inc()
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

def record_cache_operation(operation: str, result: str):
    """记录缓存操作"""
    CACHE_OPERATIONS.labels(operation=operation, result=result).inc()

def record_book_operation(operation: str):
    """记录书籍操作"""
    BOOK_OPERATIONS.labels(operation=operation).inc()

# 性能优化建议生成器
class PerformanceOptimizer:
    """性能优化建议生成器"""
    
    @staticmethod
    def analyze_performance(metrics: Dict[str, Any]) -> List[str]:
        """分析性能指标并提供优化建议"""
        suggestions = []
        
        # CPU使用率建议
        cpu_percent = metrics.get('system', {}).get('cpu', {}).get('percent', 0)
        if cpu_percent > 80:
            suggestions.append("CPU使用率过高，建议增加工作进程数或优化算法")
        
        # 内存使用建议
        memory_percent = metrics.get('system', {}).get('memory', {}).get('percent', 0)
        if memory_percent > 85:
            suggestions.append("内存使用率过高，建议检查内存泄漏或增加内存")
        
        # 慢查询建议
        slow_queries = metrics.get('slow_queries', [])
        if len(slow_queries) > 10:
            suggestions.append("检测到多个慢查询，建议优化数据库索引或查询逻辑")
        
        # 缓存命中率建议
        cache_stats = metrics.get('cache', {})
        if cache_stats.get('enabled') and cache_stats.get('keyspace_hits', 0) > 0:
            hit_rate = cache_stats['keyspace_hits'] / (
                cache_stats['keyspace_hits'] + cache_stats.get('keyspace_misses', 0)
            )
            if hit_rate < 0.7:  # 命中率低于70%
                suggestions.append("缓存命中率较低，建议调整缓存策略或增加缓存TTL")
        
        # 数据库连接池建议
        db_stats = metrics.get('database', {}).get('pool_stats', {})
        pool_usage = db_stats.get('checked_out', 0) / max(db_stats.get('size', 1), 1)
        if pool_usage > 0.8:
            suggestions.append("数据库连接池使用率过高，建议增加连接池大小")
        
        if not suggestions:
            suggestions.append("性能指标正常，无需特别优化")
        
        return suggestions

performance_optimizer = PerformanceOptimizer() 