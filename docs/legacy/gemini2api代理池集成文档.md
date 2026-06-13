# gemini2api 代理池集成与优化报告

> 日期：2026-06-08
> 版本：v2.0

---

## 一、新增功能概览

### 1. 代理池管理 (proxy_pool.py) ⭐⭐⭐

**核心功能**：
- 支持所有主流代理协议的订阅导入
- 多节点负载均衡和故障转移
- 多进程IP隔离

**支持的协议**：
| 协议 | 链接格式 | 状态 |
|------|----------|------|
| VMess | `vmess://` | ✅ |
| VLESS | `vless://` | ✅ |
| Shadowsocks | `ss://` | ✅ |
| ShadowsocksR | `ssr://` | ✅ |
| Trojan | `trojan://` | ✅ |
| Hysteria2 | `hy2://`, `hysteria2://` | ✅ |
| TUIC | `tuic://` | ✅ |
| HTTP/HTTPS | `http://`, `https://` | ✅ |
| SOCKS5 | `socks5://` | ✅ |

**负载均衡策略**：
- `round_robin` - 轮询
- `random` - 随机
- `fastest` - 最快节点
- `least_connections` - 最少连接
- `ip_hash` - IP哈希（确保同一进程使用同一节点）

---

### 2. 代理启动器 (proxy_launcher.py) ⭐⭐⭐

**核心功能**：
- 自动将代理链接转换为本地 HTTP/SOCKS5 代理
- 支持 V2Ray 和 sing-box 双核心
- 多进程代理隔离

**工作原理**：
```
订阅链接 → 解析节点 → 启动本地代理 → 分配给进程
   ↓           ↓           ↓            ↓
 vmess://   ProxyNode   V2Ray/sing-box  HTTP端口
```

---

### 3. 自愈机制 (gemini.py 改进) ⭐⭐

**借鉴 HelloKimi 的设计**：
- Cookie 失效自动刷新
- BL Token 自动更新
- 指数退避重试

**错误处理层次**：
```python
UpstreamError          # 基础错误类
├── CookieExpiredError # Cookie过期（自动刷新）
└── RateLimitError     # 频率限制（智能等待）
```

---

### 4. 工具调用解析增强 (tools.py) ⭐⭐⭐

**三层兜底解析**：
1. ` ```tool_call\n{...}\n``` ` - 标准格式
2. ` ```json\n{...}\n``` ` - JSON代码块
3. 平衡括号扫描裸 JSON

---

### 5. Token 估算改进 (server.py) ⭐

**改进算法**：
- CJK 字符：~1.5 字符/token
- ASCII 字符：~4 字符/token
- 比原来的 `len//4` 更精确

---

## 二、配置说明

### config.json 新增配置项

```json
{
  "proxy_pool_enabled": true,
  "proxy_subscriptions": [
    "https://your-subscription-url.com/sub",
    "vmess://...",
    "vless://..."
  ],
  "proxy_pool_strategy": "round_robin",
  "proxy_pool_health_check": true,
  "proxy_pool_health_check_interval": 300,
  "proxy_pool_max_failures": 3,
  "proxy_pool_port_range_start": 10000,
  "proxy_pool_port_range_end": 20000,
  "proxy_pool_auto_update": true,
  "proxy_pool_update_interval": 3600,
  "proxy_pool_isolate_by_process": true
}
```

### 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `proxy_pool_enabled` | false | 启用代理池 |
| `proxy_subscriptions` | [] | 订阅链接列表 |
| `proxy_pool_strategy` | round_robin | 负载均衡策略 |
| `proxy_pool_health_check` | true | 启用健康检查 |
| `proxy_pool_isolate_by_process` | true | 多进程IP隔离 |

---

## 三、使用示例

### 1. 基本配置

```json
{
  "proxy_pool_enabled": true,
  "proxy_subscriptions": [
    "https://your-vpn-provider.com/sub?token=xxx"
  ]
}
```

### 2. 多订阅源

```json
{
  "proxy_subscriptions": [
    "https://provider1.com/clash",
    "https://provider2.com/v2ray",
    "vmess://eyJ2IjoiMi...",
    "trojan://password@server:443"
  ]
}
```

### 3. 50进程50IP场景

```json
{
  "proxy_pool_enabled": true,
  "proxy_subscriptions": ["https://your-50-nodes-sub.com/sub"],
  "proxy_pool_strategy": "ip_hash",
  "proxy_pool_isolate_by_process": true
}
```

启动50个进程时，每个进程会自动分配不同的代理节点。

---

## 四、代码结构

```
gemini_web2api/
├── config.py           # 配置管理（已更新）
├── proxy_pool.py       # 代理池管理（新增）
├── proxy_launcher.py   # 代理启动器（新增）
├── tools.py            # 工具调用（已增强）
├── gemini.py           # 核心逻辑（已增强自愈）
├── server.py           # HTTP服务（已优化）
└── ...
```

---

## 五、依赖要求

### 必需
- Python 3.8+
- V2Ray 或 sing-box 二进制文件（用于启动本地代理）

### 可选
- httpx（用于流式生成）
- pyyaml（用于解析Clash订阅）

### 安装 V2Ray
```bash
# Windows
winget install V2Ray.V2Ray

# Linux
bash <(curl -L https://raw.githubusercontent.com/v2fly/fhs-install-v2ray/master/install-release.sh)

# macOS
brew install v2ray
```

### 安装 sing-box（支持更多协议）
```bash
# Windows
winget install SagerNet.sing-box

# Linux
bash <(curl -fsSL https://sing-box.app/deb-install.sh)
```

---

## 六、与 HelloKimi 的对比

| 特性 | HelloKimi | gemini2api (改进后) |
|------|-----------|---------------------|
| 工具调用解析 | 三层兜底 ✅ | 三层兜底 ✅ |
| Token估算 | CJK优化 ✅ | CJK优化 ✅ |
| 自愈机制 | Nonce刷新 ✅ | Cookie/BL刷新 ✅ |
| 代理支持 | CF内网 | 代理池+多协议 ✅ |
| 多进程IP | N/A | 进程级隔离 ✅ |
| 订阅导入 | N/A | 全格式支持 ✅ |

---

## 七、注意事项

1. **V2Ray/sing-box 必须安装**：代理池功能需要本地有 V2Ray 或 sing-box 二进制文件
2. **端口范围**：默认使用 10000-20000 端口，确保防火墙允许
3. **订阅更新**：默认每小时自动更新订阅
4. **健康检查**：默认每5分钟检查节点健康状态

---

## 八、故障排除

### Q1: 代理启动失败
- 检查 V2Ray/sing-box 是否安装
- 检查端口是否被占用
- 查看日志中的错误信息

### Q2: 订阅加载失败
- 检查订阅链接是否有效
- 检查网络连接
- 尝试手动访问订阅链接

### Q3: 多进程IP相同
- 确保订阅中有足够的节点
- 检查 `proxy_pool_isolate_by_process` 是否为 true
- 尝试使用 `ip_hash` 策略

---

*文档完成，功能已测试通过。*
