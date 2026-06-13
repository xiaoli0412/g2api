# Gemini2API - 功能清单

## 核心功能

| 功能 | 状态 | 说明 |
|------|------|------|
| OpenAI兼容API | ✅ | /v1/chat/completions |
| 流式输出 | ✅ | 真流式(httpx) + 假流式 |
| 联网搜索 | ✅ | -search后缀 |
| 多模态输入 | ✅ | 图片/视频/音频/文档 |
| 工具调用 | ✅ | Function Calling |
| Token计算 | ✅ | 估算token数 |
| 深度思考 | ✅ | -think=N后缀 |
| Cookie管理 | ✅ | Edge插件 + 手动 |
| 代理支持 | ✅ | HTTP/SOCKS5 |
| Dashboard | ✅ | /dashboard |
| Web 配置管理 | ✅ | /api/config + Dashboard 设置页 |
| 图片提取 | ✅ | 自动从响应中提取图片URL |
| 代码提取 | ✅ | 自动提取代码/HTML artifacts |

## 新增功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 搜索模型 | ✅ | -search后缀启用联网搜索 |
| Cookie轮询 | ✅ | 多cookie文件自动轮询 |
| 代理轮询 | ✅ | 多代理自动轮询 |
| 代理池 | ✅ | 订阅、策略、健康检查、进程隔离 |
| 速率限制 | ✅ | 可配置请求间隔 |
| Edge扩展 | ✅ | 自动获取和推送Cookie |
| 匿名模型 | ✅ | 未登录只显示可用模型 |
| 多文件上传 | ✅ | 图片/视频/音频/文档 |
| 图片响应解析 | ✅ | 自动提取markdown/URL/base64图片 |
| 媒体响应解析 | ✅ | 自动提取图片/视频/音频 URL 与 data URL |
| Canvas artifacts | ✅ | 提取代码块和HTML artifacts |

## 启动方式

| 方式 | 命令 | 说明 |
|------|------|------|
| 命令行 | `python -m gemini_web2api` | 最稳定 |
| Windows GUI | `run-gui.bat` | C++/WinUI 3 原生桌面壳 |
| Legacy GUI | `run-gui-pyqt.bat` | emergency fallback only |
| Docker | `docker run -p 8081:8081 gemini-web2api` | 容器化 |
| EXE | `build/native/x64/Release/Gemini2API.WinUI.exe` | 原生 WinUI 独立运行 |

## 模型列表

### MODE_CATEGORY 映射

Gemini 后端使用 MODE_CATEGORY 整数路由模型，`inner[79]` 字段控制：

| MODE_CATEGORY | 模型类型 | 说明 |
|---------------|----------|------|
| 1 | FAST | 快速通用模型 |
| 2 | THINKING | 深度思考模式 |
| 3 | PRO | 专业模型(数学/代码) |
| 4 | AUTO | 自动选择 |
| 5 | FAST_DYNAMIC_THINKING | 动态思考 |
| 6 | FLASH_LITE | 轻量模型 |

### 匿名可用（无需登录）

| 模型 | MODE_CATEGORY | 说明 |
|------|---------------|------|
| gemini-3.5-flash | 1 | 快速通用 (全方位帮助) |
| gemini-3.5-flash-thinking | 2 | 深度思考 (解决复杂问题) |
| gemini-3.5-flash-thinking-lite | 5 | 自适应思考 |
| gemini-auto | 4 | 自动选择 |
| gemini-flash-lite | 6 | 轻量快速 |
| gemini-2.5-flash | 1 | 2.5 Flash |
| gemini-2.5-flash-lite | 6 | 2.5 Flash Lite |
| gemini-3.0-flash | 1 | 3.0 Flash |
| gemini-2.0-flash | 1 | 2.0 Flash |
| gemini-2.5-flash-preview-04-17 | 1 | 源码发现的 2.5 Flash preview |
| gemini-2.5-flash-preview-05-20 | 1 | 源码发现的 2.5 Flash preview |
| gemini-2.5-flash-preview-09-2025 | 1 | 源码发现的 2.5 Flash preview |
| gemini-3-flash-preview | 1 | 源码发现的 3 Flash preview |

### 需要登录

| 模型 | MODE_CATEGORY | 说明 |
|------|---------------|------|
| gemini-3.1-pro | 3 | Pro模型 (高等数学与代码) |
| gemini-3.1-pro-enhanced | 3 | Pro增强 |
| gemini-2.5-pro | 3 | 2.5 Pro |
| gemini-3.0-pro | 3 | 3.0 Pro |
| gemini-advanced | 3 | Gemini Web Advanced 别名，真实路由取决于账号权益 |

### 搜索模型

| 模型 | 说明 |
|------|------|
| gemini-3.5-flash-search | Flash+搜索 |
| gemini-3.5-flash-thinking-search | Thinking+搜索 |
| gemini-3.1-pro-search | Pro+搜索 |
| gemini-2.5-pro-search | 2.5 Pro+搜索 |
| gemini-2.5-flash-search | 2.5 Flash+搜索 |

### 模型参数

| 后缀 | 说明 | 示例 |
|------|------|------|
| -think=N | 设置思考深度 (0=最深, 4=无) | gemini-3.5-flash-think=0 |
| -search | 启用联网搜索 | gemini-3.5-flash-search |
| -image/-video/-music/-tts | Gemini Web 工具别名 | gemini-3.5-flash-image |
| -photos/-library/-notebook | Gemini Web 管理/集成入口别名 | gemini-3.5-flash-photos |
| @think=N | 旧版思考深度语法(兼容) | gemini-3.5-flash@think=2 |
| @search | 旧版搜索语法(兼容) | gemini-3.5-flash@search |

### Gemini Web 工具 Alias

| 功能 | 模型名 / 后缀 | 状态 |
|------|---------------|------|
| 创建图片 | nano-banana-2, nano-banana-pro, imagen-*, gemini-*-image* 或 -image/-images/-create-image | experimental |
| 创建视频 | omni, veo-2.0-generate-001 或 -video/-videos/-create-video | experimental |
| 音乐/TTS | lyria-3, gemini-2.5-flash-preview-tts 或 -music/-tts/-speech/-audio | limited |
| Deep research | gemini-deep-research 或 -deep-research/-research | experimental |
| Canvas | gemini-canvas 或 -canvas | ✅ artifact 提取 |
| Photos/Library/Notebook | gemini-photos, google-photos, gemini-library, gemini-notebook, notebooklm 或对应后缀 | limited |

### 媒体端点

| 端点 | 默认模型 | 返回 |
|------|----------|------|
| POST /v1/images/generations | nano-banana-2 | OpenAI image data；无真实图片时返回 limited |
| POST /v1/videos/generations | omni | video_url data；无真实视频时返回 limited |
| POST /v1/audio/speech | gemini-2.5-flash-preview-tts | 音频二进制或 JSON fallback；无真实音频时返回 limited |

## 响应格式

### 图片提取

API 自动从响应中提取图片，返回 `images` 字段：

```json
{
  "images": [
    {"url": "https://...", "alt": "描述", "type": "markdown"},
    {"url": "data:image/png;base64,...", "alt": "生成图片", "type": "base64"}
  ]
}
```

### 媒体提取

API 自动从响应中提取媒体，返回 `media` 字段：

```json
{
  "media": [
    {"kind": "image", "url": "https://...", "type": "url"},
    {"kind": "video", "url": "https://.../clip.mp4", "type": "url"},
    {"kind": "audio", "url": "data:audio/mp3;base64,...", "type": "base64"}
  ]
}
```

### Canvas Artifacts

API 自动提取代码块，返回 `artifacts` 字段：

```json
{
  "artifacts": [
    {"type": "code", "language": "python", "content": "print('hello')"},
    {"type": "html", "language": "html", "content": "<div>Hello</div>"}
  ]
}
```

## 多模态支持

| 类型 | 格式 |
|------|------|
| 图片 | png, jpg, jpeg, gif, webp, bmp |
| 视频 | mp4, avi, mov, webm, mkv |
| 音频 | mp3, wav, ogg, flac, m4a, aac |
| 文档 | pdf, doc, docx, txt, csv, json, xml, md |
| 代码 | py, js, html |

## 配置选项

```json
{
  "port": 8081,
  "host": "0.0.0.0",
  "api_keys": ["sk-gemini"],
  "cookie_file": "cookie.txt",
  "proxy": null,
  "cookie_files": [],
  "cookie_rotation": false,
  "cookie_rotation_interval": 10,
  "proxies": [],
  "proxy_rotation": false,
  "proxy_rotation_interval": 10,
  "rate_limit_per_minute": 30,
  "rate_limit_delay": 2,
  "proxy_pool_enabled": false,
  "proxy_subscriptions": [],
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

## Edge扩展

1. 打开 `edge://extensions/`
2. 开启"开发人员模式"
3. 点击"加载解压缩的扩展"
4. 选择 `extension` 文件夹
5. 登录 gemini.google.com
6. 扩展自动推送Cookie

## 文件结构

```
gemini2api/
├── gemini_web2api/        # 核心代码
├── extension/             # Edge扩展
├── native/Gemini2API.WinUI/ # C++/WinUI 3 原生桌面壳
├── app.py                 # legacy customtkinter GUI
├── gui_app.py             # legacy PyQt fallback source
├── gemini_web2api_standalone.py  # 单文件版本
├── config.json            # 配置文件
├── requirements.txt       # 依赖列表
├── Dockerfile             # Docker配置
└── build/native/x64/Release/ # 原生 EXE 输出
```
