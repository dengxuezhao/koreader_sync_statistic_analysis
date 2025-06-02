# API文档修复指南

## 问题症状
- 访问 `http://localhost:8080/docs` 显示空白页面
- Swagger UI 无法正常加载
- 设备管理和统计页面显示404错误

## 解决方案

### 1. 立即修复 - 重启服务器

**问题原因**: 新添加的API端点需要重启服务器才能生效

**解决步骤**:
```bash
# 1. 停止当前服务（按 Ctrl+C）
# 2. 重新启动服务
uv run python main.py both
# 3. 等待看到 "系统启动完成" 提示
# 4. 访问 http://localhost:8080/docs 验证修复
```

### 2. 验证修复效果

**测试API文档**:
- 访问: http://localhost:8080/docs
- 应该能看到完整的Swagger UI界面
- 可以展开各个API端点查看详情

**测试新的JSON端点**:
```bash
# 运行测试脚本
python test_api_endpoints.py

# 或者直接测试（需要认证）
curl "http://localhost:8080/api/v1/web/devices/json?page=1&size=5"
# 应该返回 401 Unauthorized（正常，因为需要认证）
```

**测试前端页面**:
- 访问: http://localhost:8501
- 登录后检查设备管理和统计页面是否正常工作

### 3. 如果问题仍然存在

**检查端口占用**:
```bash
# Windows
netstat -ano | findstr :8080
netstat -ano | findstr :8501

# 如果端口被占用，杀死进程
taskkill /F /PID <进程ID>
```

**清理并重启**:
```bash
# 1. 确保所有相关进程都已停止
taskkill /F /IM python.exe /FI "WINDOWTITLE eq Kompanion*"

# 2. 重新启动
uv run python main.py both
```

**检查日志**:
- 查看启动时的错误消息
- 确认数据库连接正常
- 确认所有路由都已注册

### 4. 已修复的功能

✅ **Swagger UI配置**: 添加了详细的参数配置
✅ **新JSON端点**: 
- `/api/v1/web/devices/json` - 设备管理数据
- `/api/v1/web/statistics/json` - 阅读统计数据
✅ **导航重复**: 移除了重复的快速导航按钮
✅ **API文档**: 创建了完整的文字版API文档

### 5. 相关文件

- **完整API文档**: `API_DOCUMENTATION.md`
- **快速启动指南**: `QUICK_START.md`  
- **API测试脚本**: `test_api_endpoints.py`

### 6. 常见问题

**Q: 重启后仍然显示404？**
A: 检查服务器是否完全启动，等待看到"系统启动完成"消息

**Q: Swagger UI仍然是空白？**
A: 清除浏览器缓存，或者尝试无痕浏览模式

**Q: 前端页面无法访问设备管理？**
A: 确保已经登录，并且后端API正常运行

---

**重要提醒**: 任何API端点的修改都需要重启服务器才能生效！ 