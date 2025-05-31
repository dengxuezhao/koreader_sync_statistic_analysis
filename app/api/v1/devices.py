"""
设备管理API端点

提供设备管理和监控功能。
"""

from fastapi import APIRouter

router = APIRouter()

# TODO: 实现设备管理端点
# - GET /devices/ - 获取当前用户的设备列表
# - GET /devices/{device_id} - 获取设备详情
# - PUT /devices/{device_id} - 更新设备信息
# - DELETE /devices/{device_id} - 删除设备
# - POST /devices/{device_id}/sync - 手动触发设备同步 