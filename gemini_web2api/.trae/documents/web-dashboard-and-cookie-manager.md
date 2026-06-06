# gemini-web2api 增强功能实现计划

## 一、需求总结

### 1.1 Web 监控界面
- **实时日志查看**：显示服务运行时的请求日志、错误日志等
- **使用统计图表**：Token 使用量、请求次数、响应时间等可视化图表
- **模型使用记录**：每个模型的调用次数、成功率、平均响应时间
- **系统状态监控**：服务器连接数、运行时间、内存使用等

### 1.2 Cookie 自动获取（三合一方案）
- **手动登录后自动提取**：用户通过 Edge 浏览器手动登录 Gemini，然后工具自动提取 Cookie
- **自动登录 Gemini 账号**：工具自动使用账号密码登录 Gemini（需要提供账号密码）
- **Cookie 池管理**：管理多个 Cookie，自动轮换和刷新，保持所有 Cookie 有效

### 1.3 支持模型
- 支持所有可用模型：gemini-3.5-flash、gemini-3.5-flash-thinking、gemini-3.1-pro 等

---

## 二、技术方案

### 2.1 Edge Cookie 提取方案

**技术原理**：
1. Edge 浏览器 Cookie 存储在 SQLite 数据库中：`%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Network\Cookies`
2. Cookie 使用 AES-256-GCM 加密，密钥存储在 `Local State` 文件中
3. 解密流程：Base64 解码 → DPAPI 解密 AES 密钥 → AES-GCM 解密 Cookie 值

**所需依赖**：
- `pywin32`：用于 Windows DPAPI 解密
- `pycryptodome`：用于 AES-256-GCM 解密
- `browser_cookie3`（可选）：备选方案，开箱即用

**关键 Cookie**：
- `SAPISID`：核心认证标识，用于生成 SAPISIDHASH
- `__Secure-3PSID`：安全会话 ID
- `SSID`、`SID`、`HSID`、`APISID`：会话和安全标识

### 2.2 Web 监控界面方案

**架构**：
- 扩展现有 HTTP 服务器，添加新的 API 端点和静态文件服务
- 前端使用单页 HTML + Tailwind CSS + Chart.js（轻量级，无构建步骤）
- 数据存储使用内存中的环形缓冲区（ring buffer），避免持久化存储

**新增端点**：
- `GET /dashboard`：Web 监控页面
- `GET /api/stats`：使用统计数据
- `GET /api/logs`：日志流（SSE）
- `GET /api/models`：模型使用统计
- `GET /api/cookies`：Cookie 状态和管理
- `POST /api/cookies/refresh`：手动刷新 Cookie
- `POST /api/cookies/extract`：从 Edge 提取 Cookie

### 2.3 Cookie 池管理方案

**设计**：
- 支持多个 Cookie 文件，每个文件独立管理
- 自动轮换：当当前 Cookie 失效时自动切换到下一个
- 定时刷新：每 12 小时自动从 Edge 提取最新 Cookie
- 健康检查：定期验证 Cookie 有效性

---

## 三、实现步骤

### 步骤 1：安装依赖
```bash
pip install pywin32 pycryptodome
```

### 步骤 2：创建 Edge Cookie 提取模块

**文件**：`gemini_web2api/edge_cookie.py`

**功能**：
- `get_edge_encryption_key()`：从 Local State 获取 AES 密钥
- `decrypt_cookie_value()`：解密单个 Cookie 值
- `get_edge_cookies()`：提取指定域名的所有 Cookie
- `get_google_auth_cookies()`：提取 Google 认证相关 Cookie
- `build_gemini_cookie_string()`：生成 gemini_web2api 兼容的 Cookie JSON

**代码结构**：
```python
"""Edge browser cookie extraction and decryption."""
import os
import json
import base64
import sqlite3
import shutil
import tempfile

# Windows-specific imports
try:
    import win32crypt
    from Crypto.Cipher import AES
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

def get_edge_encryption_key(user_data_dir=None):
    """从 Edge 的 Local State 文件中获取 AES 解密密钥。"""
    ...

def decrypt_cookie_value(encrypted_value, aes_key):
    """解密 Cookie 的 encrypted_value 字段。"""
    ...

def get_edge_cookies(profile="Default", domain_filter=None):
    """从 Edge 浏览器提取 Cookie。"""
    ...

def get_google_auth_cookies(profile="Default"):
    """提取 Google/Gemini 认证所需的关键 Cookie。"""
    ...

def build_gemini_cookie_string(profile="Default"):
    """构建可直接用于 gemini_web2api 的 Cookie 字符串。"""
    ...
```

### 步骤 3：创建 Cookie 管理器模块

**文件**：`gemini_web2api/cookie_manager.py`

**功能**：
- `CookiePool` 类：管理多个 Cookie
- `add_cookie()`：添加新 Cookie
- `remove_cookie()`：移除 Cookie
- `get_current_cookie()`：获取当前可用的 Cookie
- `rotate_cookie()`：轮换到下一个 Cookie
- `refresh_from_edge()`：从 Edge 提取并更新 Cookie
- `start_auto_refresh()`：启动定时刷新线程

**代码结构**：
```python
"""Cookie pool management with auto-refresh."""
import threading
import time
from typing import Optional, List

class CookiePool:
    """管理多个 Cookie，支持自动轮换和刷新。"""
    
    def __init__(self, refresh_interval=43200):  # 12 hours
        self.cookies: List[dict] = []
        self.current_index = 0
        self.refresh_interval = refresh_interval
        self._lock = threading.Lock()
        self._refresh_thread: Optional[threading.Thread] = None
        
    def add_cookie(self, cookie_str: str, sapisid: str):
        """添加新 Cookie 到池中。"""
        ...
    
    def get_current_cookie(self) -> tuple:
        """获取当前可用的 Cookie (cookie_str, sapisid)。"""
        ...
    
    def rotate_cookie(self):
        """轮换到下一个 Cookie。"""
        ...
    
    def refresh_from_edge(self, profile="Default"):
        """从 Edge 浏览器提取并更新 Cookie。"""
        ...
    
    def start_auto_refresh(self):
        """启动定时刷新线程。"""
        ...
    
    def stop_auto_refresh(self):
        """停止定时刷新线程。"""
        ...
```

### 步骤 4：创建统计收集器模块

**文件**：`gemini_web2api/stats.py`

**功能**：
- `StatsCollector` 类：收集和存储使用统计
- `record_request()`：记录请求信息
- `get_stats()`：获取统计数据
- `get_logs()`：获取日志流
- `get_model_stats()`：获取模型使用统计

**代码结构**：
```python
"""Statistics collection and logging."""
import time
import threading
from collections import deque
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class RequestRecord:
    """请求记录。"""
    timestamp: float
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    response_time: float
    success: bool
    error: str = ""

class StatsCollector:
    """使用统计收集器。"""
    
    def __init__(self, max_logs=1000, max_requests=10000):
        self.logs: deque = deque(maxlen=max_logs)
        self.requests: deque = deque(maxlen=max_requests)
        self._lock = threading.Lock()
        self.start_time = time.time()
        
    def add_log(self, message: str, level: str = "INFO"):
        """添加日志。"""
        ...
    
    def record_request(self, record: RequestRecord):
        """记录请求。"""
        ...
    
    def get_stats(self) -> dict:
        """获取总体统计。"""
        ...
    
    def get_logs(self, limit=100) -> List[dict]:
        """获取日志列表。"""
        ...
    
    def get_model_stats(self) -> Dict[str, dict]:
        """获取模型使用统计。"""
        ...
    
    def get_recent_requests(self, limit=50) -> List[dict]:
        """获取最近的请求记录。"""
        ...
```

### 步骤 5：创建 Web 监控页面

**文件**：`gemini_web2api/static/index.html`

**功能**：
- 实时日志显示（自动滚动、过滤、搜索）
- 使用统计图表（Token 使用量、请求次数、响应时间趋势）
- 模型使用记录（表格形式，支持排序）
- 系统状态监控（运行时间、连接数、Cookie 状态）
- Cookie 管理界面（查看、刷新、轮换）

**技术栈**：
- HTML5 + Tailwind CSS（CDN）
- Chart.js（CDN）用于图表
- 原生 JavaScript（无框架依赖）
- Server-Sent Events (SSE) 用于实时日志

### 步骤 6：扩展 HTTP 服务器

**文件**：`gemini_web2api/server.py`

**修改内容**：
1. 添加新的路由处理：
   - `GET /dashboard`：返回监控页面
   - `GET /api/stats`：返回统计数据
   - `GET /api/logs`：SSE 日志流
   - `GET /api/cookies`：Cookie 状态
   - `POST /api/cookies/refresh`：刷新 Cookie
   - `POST /api/cookies/extract`：从 Edge 提取

2. 集成统计收集器：
   - 在请求处理中记录统计信息
   - 在日志输出中同时写入统计收集器

3. 集成 Cookie 管理器：
   - 替换原有的 `load_cookie()` 逻辑
   - 使用 CookiePool 管理多个 Cookie

### 步骤 7：修改配置管理

**文件**：`gemini_web2api/config.py`

**新增配置项**：
```python
DEFAULT_CONFIG = {
    ...,
    # Cookie 管理配置
    "cookie_pool": [],           # Cookie 文件列表
    "cookie_refresh_interval": 43200,  # 自动刷新间隔（秒），默认 12 小时
    "auto_extract_edge": False,  # 是否自动从 Edge 提取
    "edge_profile": "Default",   # Edge 配置文件名
    
    # 监控配置
    "dashboard_enabled": True,   # 是否启用监控页面
    "dashboard_password": None,  # 监控页面密码（可选）
    "max_logs": 1000,           # 最大日志条数
    "max_requests": 10000,      # 最大请求数
}
```

### 步骤 8：修改入口点

**文件**：`gemini_web2api/__main__.py`

**新增命令行参数**：
```python
parser.add_argument("--dashboard", action="store_true", help="启用监控页面")
parser.add_argument("--dashboard-password", type=str, help="监控页面密码")
parser.add_argument("--auto-extract", action="store_true", help="自动从 Edge 提取 Cookie")
parser.add_argument("--edge-profile", type=str, default="Default", help="Edge 配置文件名")
parser.add_argument("--refresh-interval", type=int, default=43200, help="Cookie 自动刷新间隔（秒）")
```

### 步骤 9：更新模型支持

**文件**：`gemini_web2api/models.py`

**验证**：确认所有模型都能正常工作，特别是 Pro 模型需要有效的 Cookie。

---

## 四、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `gemini_web2api/edge_cookie.py` | 新建 | Edge Cookie 提取模块 |
| `gemini_web2api/cookie_manager.py` | 新建 | Cookie 池管理模块 |
| `gemini_web2api/stats.py` | 新建 | 统计收集器模块 |
| `gemini_web2api/static/index.html` | 新建 | Web 监控页面 |
| `gemini_web2api/server.py` | 修改 | 添加新端点和集成 |
| `gemini_web2api/config.py` | 修改 | 添加新配置项 |
| `gemini_web2api/__main__.py` | 修改 | 添加新命令行参数 |
| `gemini_web2api/__init__.py` | 修改 | 更新版本号 |

---

## 五、假设与决策

### 5.1 技术决策

1. **前端技术选择**：使用单页 HTML + Tailwind CSS + Chart.js，无需构建步骤，部署简单
2. **数据存储**：使用内存环形缓冲区，避免持久化存储，重启后数据清空
3. **Cookie 提取方案**：优先使用手动 DPAPI+AES-GCM 解密，备选 browser_cookie3 库
4. **自动刷新机制**：使用后台线程定时执行，不依赖外部调度器

### 5.2 假设

1. 用户已登录 Edge 浏览器中的 Google 账号
2. Edge 浏览器 Cookie 数据库未被第三方工具锁定
3. 用户具有 Windows 管理员权限（DPAPI 解密需要）
4. 项目运行在 Windows 10/11 系统上

---

## 六、验证步骤

### 6.1 功能验证

1. **Edge Cookie 提取**
   - 运行 `python -m gemini_web2api --auto-extract`
   - 验证 Cookie 文件是否正确生成
   - 验证 SAPISID 是否正确提取

2. **Web 监控界面**
   - 访问 `http://localhost:8081/dashboard`
   - 验证实时日志是否显示
   - 验证统计图表是否正确渲染
   - 验证模型使用记录是否正确

3. **Cookie 管理**
   - 验证 Cookie 轮换是否正常工作
   - 验证自动刷新是否按配置执行
   - 验证手动刷新功能

4. **API 兼容性**
   - 验证所有模型（包括 Pro）是否正常工作
   - 验证流式和非流式请求
   - 验证工具调用功能

### 6.2 测试命令

```bash
# 安装依赖
pip install pywin32 pycryptodome

# 启动服务（启用监控和自动提取）
python -m gemini_web2api --dashboard --auto-extract

# 测试非流式请求
curl -X POST http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-3.5-flash","messages":[{"role":"user","content":"你好"}]}'

# 测试 Pro 模型（需要有效 Cookie）
curl -X POST http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-3.1-pro","messages":[{"role":"user","content":"你好"}]}'

# 访问监控页面
# 浏览器打开 http://localhost:8081/dashboard
```

---

## 七、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Edge Cookie 加密方式更新 | Cookie 提取失败 | 备选 browser_cookie3 库，或手动更新解密逻辑 |
| DPAPI 权限不足 | 无法解密 AES 密钥 | 提示用户以管理员权限运行 |
| Cookie 数据库锁定 | 无法读取 Cookie | 复制数据库文件后读取 |
| Cookie 过期 | Pro 模型无法使用 | 自动刷新机制 + 手动刷新按钮 |
| 内存占用过高 | 统计数据过多 | 环形缓冲区限制最大条数 |

---

## 八、后续优化建议

1. **持久化存储**：将统计数据持久化到 SQLite 或 JSON 文件
2. **用户认证**：为监控页面添加登录功能
3. **告警机制**：Cookie 失效或请求失败时发送通知
4. **多用户支持**：支持多个 Google 账号的 Cookie 管理
5. **Docker 支持**：更新 Dockerfile 以支持新功能
