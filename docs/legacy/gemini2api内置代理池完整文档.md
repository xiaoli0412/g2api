# 内置代理池 - 完整功能说明

## 特性总览

| 特性 | 状态 | 说明 |
|------|------|------|
| HTTP/HTTPS/SOCKS5 代理 | ✅ | 直接支持 |
| VMess/VLESS/SS/Trojan/Hy2/Tuic | ✅ | 订阅解析 |
| Clash YAML 格式 | ✅ | 纯 Python 解析 |
| Base64 订阅 | ✅ | 自动解码 |
| 健康检查 | ✅ | 后台自动检查 |
| 代理测速 | ✅ | 延迟测试 |
| 故障转移 | ✅ | 自动标记不健康节点 |
| 持久化缓存 | ✅ | 本地文件缓存 |
| 多进程IP隔离 | ✅ | 每进程独立IP |
| 后台自动更新 | ✅ | 定时更新订阅 |
| API 状态查看 | ✅ | /api/proxy/status |

## 支持的格式

### 1. 标准代理格式

```
http://user:pass@proxy.com:8080
https://proxy.com:443
socks5://proxy.com:1080
socks5://user:pass@proxy.com:1080
```

### 2. V2Ray/SingBox 格式

```
vmess://base64...
vless://uuid@server:port?params#name
ss://base64@server:port#name
trojan://password@server:port#name
hy2://password@server:port#name
tuic://uuid:password@server:port#name
```

### 3. Clash YAML 格式

```yaml
proxies:
  - name: "Node1"
    type: http
    server: proxy.com
    port: 8080
    username: user
    password: pass
  - name: "Node2"
    type: socks5
    server: proxy2.com
    port: 1080
```

### 4. Base64 编码订阅

```
aHR0cDovL3Byb3h5LmNvbTo4MDgwCnNvY2tzNTovL3Byb3h5Mi5jb206MTA4MA==
```

## 配置示例

### 基本配置

```json
{
  "proxy_pool_enabled": true,
  "proxies": [
    "http://user:pass@proxy1.com:8080",
    "socks5://proxy2.com:1080"
  ]
}
```

### 订阅配置

```json
{
  "proxy_pool_enabled": true,
  "proxy_subscriptions": [
    "https://your-provider.com/sub?token=xxx",
    "https://another-provider.com/clash"
  ],
  "proxy_pool_strategy": "round_robin",
  "proxy_pool_health_check": true,
  "proxy_pool_health_check_interval": 300
}
```

### 50进程50IP配置

```json
{
  "proxy_pool_enabled": true,
  "proxy_subscriptions": ["https://your-50-nodes-sub.com"],
  "proxy_pool_strategy": "ip_hash",
  "proxy_pool_isolate_by_process": true
}
```

## API 端点

### 查看代理池状态

```
GET /api/proxy/status
```

响应示例：

```json
{
  "total_nodes": 50,
  "healthy_nodes": 48,
  "strategy": "round_robin",
  "nodes": [
    {
      "name": "US-Node1",
      "type": "http",
      "host": "proxy1.com",
      "port": 8080,
      "latency_ms": 123.4,
      "is_healthy": true,
      "failure_count": 0,
      "success_count": 156
    }
  ]
}
```

## 负载均衡策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `round_robin` | 轮询 | 通用场景 |
| `random` | 随机 | 分散请求 |
| `fastest` | 最快节点 | 延迟敏感 |
| `least_used` | 最少使用 | 负载均衡 |
| `ip_hash` | 进程级IP隔离 | 多进程场景 |

## 健康检查

- 每 300 秒自动检查一次（可配置）
- 连续 3 次失败标记为不健康
- 成功后自动恢复

## 持久化缓存

- 代理列表保存到 `proxy_cache.json`
- 启动时自动加载
- 更新后自动保存

## 性能消耗

| 操作 | 耗时 | 说明 |
|------|------|------|
| 代理解析 | <1ms | 内存操作 |
| 获取代理 | <0.1ms | 数组索引 |
| 健康检查 | ~100ms | 后台线程 |
| 订阅更新 | ~1s | 网络请求 |

## 代码结构

```
gemini_web2api/
├── proxy_builtin.py   # 内置代理池
│   ├── ProxyNode      # 代理节点
│   ├── ProxyPool      # 代理池
│   ├── parse_*        # 解析函数
│   ├── socks5_*       # SOCKS5 实现
│   └── _parse_clash_* # Clash YAML 解析
├── gemini.py          # 已集成代理池
├── server.py          # 已添加 API 端点
└── config.py          # 已添加配置项
```

## 注意事项

1. **VMess/VLESS/Trojan 等加密协议**：解析后存储为原始链接，需要配合本地代理端口使用
2. **HTTP/SOCKS5 代理**：可直接使用，无需额外配置
3. **SOCKS5 原生实现**：纯 Python 实现，零依赖
4. **Clash YAML 解析**：不依赖 pyyaml，纯 Python 实现

## 故障排除

### Q1: 代理加载失败
- 检查订阅链接是否有效
- 检查网络连接
- 查看日志中的错误信息

### Q2: 所有节点都不健康
- 检查代理是否可用
- 尝试手动测试代理
- 查看 `/api/proxy/status` 获取详情

### Q3: 多进程IP相同
- 确保订阅中有足够的节点
- 检查 `proxy_pool_strategy` 是否为 `ip_hash`
- 检查节点健康状态
