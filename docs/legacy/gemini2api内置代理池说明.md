# 内置代理池 - 零依赖，最小性能消耗

## 特性

- **纯 Python 实现** - 无需 V2Ray/sing-box 等外部二进制
- **零外部依赖** - 仅使用 Python 标准库
- **最小性能消耗** - 直接内存操作，无进程开销
- **多进程IP隔离** - 50进程=50不同IP

## 支持的代理格式

| 格式 | 示例 |
|------|------|
| HTTP | `http://user:pass@proxy.com:8080` |
| HTTPS | `https://proxy.com:443` |
| SOCKS5 | `socks5://127.0.0.1:1080` |
| VMess | `vmess://base64...` |
| VLESS | `vless://uuid@server:port` |
| SS | `ss://base64@server:port` |
| Trojan | `trojan://password@server:port` |
| Hysteria2 | `hy2://password@server:port` |

## 配置

```json
{
  "proxy_pool_enabled": true,
  "proxies": [
    "http://user:pass@proxy1.com:8080",
    "socks5://proxy2.com:1080"
  ],
  "proxy_subscriptions": [
    "https://your-provider.com/sub?token=xxx"
  ],
  "proxy_pool_strategy": "round_robin"
}
```

## 负载均衡策略

| 策略 | 说明 |
|------|------|
| `round_robin` | 轮询（默认） |
| `random` | 随机 |
| `fastest` | 最快节点 |
| `least_used` | 最少使用 |
| `ip_hash` | 进程级IP隔离 |

## 多进程IP隔离

```json
{
  "proxy_pool_enabled": true,
  "proxy_subscriptions": ["https://your-50-nodes-sub.com"],
  "proxy_pool_strategy": "ip_hash"
}
```

启动50个进程时，每个进程自动分配不同IP。

## 代码结构

```
gemini_web2api/
├── proxy_builtin.py  # 内置代理池（新增）
├── gemini.py         # 已集成代理池
├── config.py         # 已添加配置项
└── app.py            # 已添加初始化
```

## 与外部代理工具对比

| 特性 | 内置代理池 | V2Ray/sing-box |
|------|-----------|----------------|
| 外部依赖 | 无 | 需要安装 |
| 性能消耗 | 极低 | 较高（进程开销） |
| 协议支持 | HTTP/SOCKS5 + 订阅解析 | 全部协议 |
| 部署难度 | 简单 | 复杂 |

## 注意事项

1. **VMess/VLESS/Trojan 等加密协议**需要配合本地代理端口使用
2. **HTTP/SOCKS5 代理**可直接使用，无需额外配置
3. **订阅解析**支持 base64 编码和 Clash YAML 格式
