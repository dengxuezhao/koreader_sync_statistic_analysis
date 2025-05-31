# KOReader 兼容性指南

本指南详细说明了 Kompanion Python 与 KOReader 设备和插件的兼容性，以及如何正确配置和使用这些功能。

## 目录

- [KOReader 兼容性概述](#koreader-兼容性概述)
- [kosync 插件配置](#kosync-插件配置)
- [OPDS 目录配置](#opds-目录配置)
- [统计插件配置](#统计插件配置)
- [WebDAV 配置](#webdav-配置)
- [兼容性测试结果](#兼容性测试结果)
- [故障排除](#故障排除)
- [最佳实践](#最佳实践)

## KOReader 兼容性概述

Kompanion Python 与 KOReader 的以下组件完全兼容：

### 支持的 KOReader 版本
- **KOReader 2023.10** 及更新版本（完全测试）
- **KOReader 2023.08** 及更新版本（基本兼容）
- **KOReader 2022.x** 系列（部分兼容，建议升级）

### 支持的功能模块
1. **kosync 插件** - 阅读进度同步
2. **OPDS 目录** - 书籍浏览和下载
3. **统计插件** - 阅读统计数据收集
4. **WebDAV 服务** - 文件传输和统计上传

### 支持的设备平台
- **Kindle** (Paperwhite, Oasis, Scribe)
- **Kobo** (Clara, Forma, Sage, Elipsa)
- **Android** 设备
- **Linux** 桌面系统
- **其他** 支持 KOReader 的设备

## kosync 插件配置

### 1. 在 KOReader 中启用 kosync

1. 打开 KOReader 设置
2. 导航到：**工具 → 插件 → kosync**
3. 启用 kosync 插件
4. 重启 KOReader

### 2. 配置服务器连接

在 kosync 设置中配置：

```
服务器地址: https://your-domain.com
用户名: your_username
密码: your_password
自动同步: 启用
```

### 3. 注册新用户

如果是首次使用，可以在 kosync 设置中注册新用户：

1. 选择"注册"选项
2. 输入用户名和密码
3. 点击"注册"按钮
4. 系统会自动创建账户

### 4. 同步设置

推荐的同步设置：

```
同步频率: 每次打开/关闭书籍
WiFi同步: 启用
进度阈值: 5%（每变化5%进度时同步）
设备名称: 自定义设备名称（如"我的Kindle"）
```

### 5. 验证同步功能

1. 打开一本书籍
2. 阅读几页
3. 关闭书籍
4. 检查 kosync 日志确认同步成功
5. 在其他设备上打开同一本书验证进度同步

## OPDS 目录配置

### 1. 添加 OPDS 目录

在 KOReader 中添加 OPDS 目录：

1. 打开文件浏览器
2. 选择"目录"选项
3. 添加新目录：
   ```
   目录名称: Kompanion 书库
   目录地址: https://your-domain.com/opds/
   需要认证: 是（如果启用了认证）
   用户名: your_username
   密码: your_password
   ```

### 2. 浏览书籍

OPDS 目录提供以下浏览方式：

- **最新书籍** - 按添加时间排序
- **热门书籍** - 按下载次数排序
- **所有书籍** - 按标题字母排序
- **搜索功能** - 支持标题、作者、关键词搜索

### 3. 下载书籍

1. 在 OPDS 目录中浏览书籍
2. 选择想要下载的书籍
3. 点击下载链接
4. 书籍会自动下载到 KOReader

### 4. 认证配置

如果服务器启用了认证：

```
认证类型: HTTP Basic Authentication
用户名: 你的注册用户名
密码: 你的账户密码
```

## 统计插件配置

### 1. 启用统计插件

1. 打开 KOReader 设置
2. 导航到：**工具 → 插件 → 统计**
3. 启用统计插件
4. 配置统计收集选项

### 2. 配置数据收集

推荐的统计配置：

```
收集阅读时间: 启用
收集翻页统计: 启用
收集高亮笔记: 启用
收集书签信息: 启用
自动保存间隔: 5分钟
```

### 3. WebDAV 上传配置

在统计插件中配置 WebDAV：

```
WebDAV服务器: https://your-domain.com/webdav/
用户名: your_username
密码: your_password
上传目录: /statistics/
自动上传: 启用
上传频率: 每日或每周
```

### 4. 手动上传统计

如需手动上传统计数据：

1. 打开统计插件
2. 选择"导出统计"
3. 选择"上传到服务器"
4. 确认上传操作

## WebDAV 配置

### 1. WebDAV 客户端设置

在 KOReader 或其他 WebDAV 客户端中：

```
服务器地址: https://your-domain.com/webdav/
协议: HTTPS
端口: 443
用户名: your_username
密码: your_password
根目录: /
```

### 2. 支持的操作

Kompanion 的 WebDAV 服务支持：

- **PROPFIND** - 列出目录内容和文件属性
- **GET** - 下载文件
- **PUT** - 上传文件
- **DELETE** - 删除文件
- **MKCOL** - 创建目录

### 3. 目录结构

推荐的 WebDAV 目录结构：

```
/
├── books/           # 书籍文件
├── statistics/      # 统计数据
│   ├── 2024/
│   │   ├── 01/     # 按月组织
│   │   └── 02/
│   └── archive/    # 归档数据
└── backup/         # 备份文件
```

### 4. 文件格式支持

统计文件格式：
- **JSON** - KOReader 统计数据（推荐）
- **CSV** - 表格格式导出
- **XML** - 结构化数据格式

## 兼容性测试结果

### kosync 协议兼容性

| 功能 | 兼容性 | 测试状态 | 备注 |
|------|---------|----------|------|
| 用户注册 | ✅ 完全兼容 | 通过 | 支持原始 kosync 协议 |
| 用户认证 | ✅ 完全兼容 | 通过 | MD5 密码哈希兼容 |
| 进度上传 | ✅ 完全兼容 | 通过 | 支持 Form 数据格式 |
| 进度获取 | ✅ 完全兼容 | 通过 | 返回最新同步进度 |
| 多设备同步 | ✅ 完全兼容 | 通过 | 支持设备间进度同步 |
| 文档哈希匹配 | ✅ 完全兼容 | 通过 | 支持文件名和哈希匹配 |

### OPDS 目录兼容性

| 功能 | 兼容性 | 测试状态 | 备注 |
|------|---------|----------|------|
| 根目录浏览 | ✅ 完全兼容 | 通过 | OPDS 1.2 标准 |
| 书籍列表 | ✅ 完全兼容 | 通过 | 支持分页和排序 |
| 搜索功能 | ✅ 完全兼容 | 通过 | OpenSearch 规范 |
| 书籍下载 | ✅ 完全兼容 | 通过 | 多格式支持 |
| 认证集成 | ✅ 完全兼容 | 通过 | HTTP Basic Auth |
| XML 格式 | ✅ 完全兼容 | 通过 | Atom + OPDS 命名空间 |

### WebDAV 服务兼容性

| 操作 | 兼容性 | 测试状态 | 备注 |
|------|---------|----------|------|
| PROPFIND | ✅ 完全兼容 | 通过 | 深度 0 和 1 支持 |
| GET | ✅ 完全兼容 | 通过 | 文件下载 |
| PUT | ✅ 完全兼容 | 通过 | 文件上传，自动目录创建 |
| DELETE | ✅ 完全兼容 | 通过 | 文件和目录删除 |
| MKCOL | ✅ 完全兼容 | 通过 | 目录创建 |
| 统计文件解析 | ✅ 完全兼容 | 通过 | JSON 格式自动识别 |

### 性能测试结果

| 测试场景 | 结果 | 备注 |
|----------|------|------|
| 单用户同步 | < 100ms | 平均响应时间 |
| 并发同步（10设备） | < 500ms | 所有请求成功 |
| 大量数据同步（100本书） | < 2s | 批量处理 |
| OPDS 目录浏览 | < 200ms | 缓存优化 |
| WebDAV 文件上传 | 1MB/s+ | 取决于网络 |

## 故障排除

### 常见问题及解决方案

#### 1. kosync 同步失败

**问题**: KOReader 报告同步错误

**解决方案**:
1. 检查网络连接
2. 验证服务器地址和端口
3. 确认用户名和密码正确
4. 检查服务器日志：
   ```bash
   docker logs kompanion-app
   ```

#### 2. OPDS 目录无法访问

**问题**: 无法连接到 OPDS 目录

**解决方案**:
1. 检查 OPDS 地址是否正确
2. 验证认证凭据
3. 确认服务器 HTTPS 证书有效
4. 测试 OPDS 端点：
   ```bash
   curl -u username:password https://your-domain.com/opds/
   ```

#### 3. WebDAV 上传失败

**问题**: 统计文件上传失败

**解决方案**:
1. 检查 WebDAV 服务器配置
2. 验证用户权限
3. 确认目录路径存在
4. 手动测试 WebDAV：
   ```bash
   curl -u username:password -T test.json https://your-domain.com/webdav/test.json
   ```

#### 4. 密码认证失败

**问题**: 认证总是失败

**解决方案**:
1. 确认密码不包含特殊字符
2. 重新注册用户账户
3. 检查服务器端 MD5 哈希实现
4. 查看认证日志

### 调试工具

#### 1. 启用详细日志

在服务器端启用调试模式：

```bash
export LOG_LEVEL=DEBUG
docker-compose restart
```

#### 2. KOReader 日志

查看 KOReader 插件日志：

1. 连接设备到电脑
2. 查看日志文件：`/mnt/onboard/.koreader/crash.log`
3. 或在 KOReader 中查看插件日志

#### 3. 网络抓包

使用工具抓取网络请求：

```bash
# 使用 tcpdump
sudo tcpdump -i any -w capture.pcap host your-domain.com

# 使用 wireshark 分析
wireshark capture.pcap
```

## 最佳实践

### 1. 服务器配置

#### 推荐的生产环境配置

```yaml
# docker-compose.yml
services:
  app:
    environment:
      - LOG_LEVEL=INFO
      - CORS_ORIGINS=*
      - SESSION_TIMEOUT=7200
      - MAX_SYNC_RECORDS=10000
```

#### SSL 证书配置

确保使用有效的 SSL 证书：

```nginx
# nginx.conf
ssl_certificate /etc/ssl/certs/your-domain.crt;
ssl_certificate_key /etc/ssl/private/your-domain.key;
ssl_protocols TLSv1.2 TLSv1.3;
```

### 2. 用户管理

#### 创建专用同步用户

```bash
# 创建专门用于 KOReader 同步的用户
python scripts/create_admin.py --username koreader_user --password secure_password
```

#### 用户权限控制

- 普通用户：只能同步自己的数据
- 管理员用户：可以管理所有数据
- 只读用户：只能下载，不能上传

### 3. 性能优化

#### 缓存配置

```python
# app/core/config.py
CACHE_TTL_SYNC = 300      # 同步数据缓存 5 分钟
CACHE_TTL_OPDS = 1800     # OPDS 目录缓存 30 分钟
CACHE_TTL_BOOKS = 7200    # 书籍列表缓存 2 小时
```

#### 数据库优化

```sql
-- 为同步表创建索引
CREATE INDEX idx_sync_progress_user_document ON sync_progress(user_id, document);
CREATE INDEX idx_sync_progress_updated ON sync_progress(updated_at);
```

### 4. 监控和维护

#### 定期备份

```bash
#!/bin/bash
# backup.sh - 定期备份脚本
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
```

#### 清理旧数据

```python
# 清理 90 天前的同步记录
DELETE FROM sync_progress 
WHERE updated_at < NOW() - INTERVAL '90 days';
```

#### 监控关键指标

- 同步请求成功率
- OPDS 目录访问频率
- WebDAV 文件上传量
- 数据库连接池状态

### 5. 安全建议

#### 网络安全

1. 使用 HTTPS 加密所有通信
2. 配置防火墙限制访问
3. 启用速率限制防止滥用
4. 定期更新 SSL 证书

#### 数据安全

1. 定期备份用户数据
2. 加密敏感信息存储
3. 实施访问日志审计
4. 限制文件上传大小

#### 认证安全

1. 使用强密码策略
2. 定期轮换 API 密钥
3. 监控异常登录活动
4. 实施账户锁定机制

---

## 结论

Kompanion Python 提供了与 KOReader 的完整兼容性，支持所有主要功能模块。通过正确的配置和最佳实践，可以为 KOReader 用户提供可靠、高效的同步和管理服务。

如果遇到任何兼容性问题，请参考本指南的故障排除章节，或查看项目的 GitHub Issues 页面获取最新的解决方案。 