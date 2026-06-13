# gemini-web2api

<p align="center">
  <img src="logo.png" width="200" alt="gemini-web2api logo">
</p>

[English](README.md)

快速索引请先看: `START_HERE_CN.md`

将 Google Gemini 网页端转换为 OpenAI 兼容 API. 零成本, 跨平台, 单文件. 桌面壳与界面重设计作者: xiaoliACG.

## 特性

- **可选密钥**: `api_keys` 为空时免密, 填入密钥后按 OpenAI Bearer Key 校验
- **OpenAI 兼容**: 直接替换 `/v1/chat/completions` 和 `/v1/models`
- **工具调用**: 完整的 Function Calling 支持 (OpenAI 格式)
- **多模型**: Flash, Flash Thinking (2万字+输出), Pro, Auto, Lite
- **思考深度**: 通过 `-think=N` 后缀调节 (0=最深, 4=最浅)
- **联网搜索**: 内置互联网访问 (Gemini 原生搜索能力)
- **跨平台**: 纯 Python, 仅一个可选依赖 (`httpx` 用于流式输出)
- **流式输出**: 基于 `httpx` 的 SSE Streaming 支持
- **Codex CLI**: Responses API (`/v1/responses`) 兼容 OpenAI Codex
- **Gemini CLI**: Google 原生 API (`/v1beta/models`) 兼容 Gemini CLI

## 快速开始

```bash
pip install -r requirements.txt
python -m gemini_web2api
```

Windows 桌面壳启动（C++/WinUI 3 原生界面）:

```bash
run-gui.bat
```

该脚本会在缺少 `build/native/x64/Release/Gemini2API.WinUI.exe` 时自动构建，然后启动原生壳。Python UI 文件仅保留为 legacy fallback，正常应用端不再走 Python 壳。

桌面壳 CLI 模式:

```bash
python app.py --cli
```

Legacy PyQt 文件只保留为紧急兼容回退。Windows 桌面应用请使用 `run-gui.bat`。

服务启动在 `http://localhost:8081/v1`.
管理面板: `http://localhost:8081/dashboard`

根目录快捷脚本:

- `run-api.bat`
- `run-gui.bat` - C++/WinUI 原生桌面壳
- `run-gui-pyqt.bat` - 仅作紧急 legacy fallback
- `run-docker.bat`
- `open-dashboard.bat`
- `build.bat`

## 真实环境验证

使用固定验证提示词 `Who are you` 对 Gemini Web 跑真实网络 smoke test:

```bash
python -m gemini_web2api.live_verify --start-server --port 8099 --cookie-file cookie.txt --source-probe
```

如果真实 Gemini Web URL 带账号前缀，例如 `https://gemini.google.com/u/1/app`，请传入同一个账号序号:

```bash
python -m gemini_web2api.live_verify --start-server --port 8099 --cookie-file cookie.txt --auth-user 1 --source-probe
```

如果要把图片、视频、音乐/TTS、照片、Notebook、Deep research 等实验性 Gemini Web 工具 alias 也纳入真实检查:

```bash
python -m gemini_web2api.live_verify --start-server --port 8099 --cookie-file cookie.txt --auth-user 1 --skip-multimodal --include-web-tools
```

如果要用同一份 cookie 文件进行真实浏览器 UI 状态探针:

```bash
python -m gemini_web2api.browser_probe --cookie-file cookie.txt --auth-user 1 --out output/browser_probe/report.json
```

报告会写入 `output/`，并把结果拆成 `pass`、`fail`、`limited`。`--strict` 会在硬失败时返回非零退出码；如果实验性/受限能力（例如多模态交接）也必须算失败，使用 `--strict-limited`。能力矩阵也可通过 API 查看:

```bash
curl http://localhost:8081/api/capabilities
```

如果要把浏览器 HAR 当辅助证据分析，可使用脱敏工具，不会输出 cookie 或 prompt 原文:

```bash
python -m gemini_web2api.har_analyze browser.har --out output/har_analysis.json
```

如果要专门真实探测 Gemini Web 文件引用 payload 的多种形状:

```bash
python -m gemini_web2api.multimodal_probe --cookie-file cookie.txt --auth-user 1 --out output/multimodal_probe.json
```

如果要只用 GET 请求抓取当前登录态 Gemini Web 页面和 JavaScript 资源，并记录网页暴露的功能关键词:

```bash
python -m gemini_web2api.web_probe --cookie-file cookie.txt --auth-user 1 --out output/web_probe.json
```

## 客户端配置

### Cherry Studio / ChatBox / 任何 OpenAI 兼容客户端

| 字段 | 值 |
|------|-----|
| Base URL | `http://localhost:8081/v1` |
| API Key | `config.json` 中的任意 `api_keys`；未配置时随便填 |
| Model | `gemini-3.5-flash-thinking` |

### curl

```bash
curl http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-key" \
  -d '{"model":"gemini-3.5-flash","messages":[{"role":"user","content":"你好!"}]}'
```

### OpenAI Python SDK

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8081/v1", api_key="sk-your-key")
resp = client.chat.completions.create(
    model="gemini-3.5-flash-thinking",
    messages=[{"role": "user", "content": "解释量子计算"}]
)
print(resp.choices[0].message.content)
```

### Gemini CLI

```bash
export GEMINI_API_KEY=none
export GOOGLE_GEMINI_BASE_URL=http://localhost:8081
gemini
```

支持 Google 原生 API 端点:
- `GET /v1beta/models` — 模型列表
- `POST /v1beta/models/{model}:generateContent` — 非流式生成
- `POST /v1beta/models/{model}:streamGenerateContent` — 流式生成 (SSE)

## 可用模型

| 模型 | 说明 | 输出量 |
|------|------|--------|
| `gemini-3.5-flash` | 快速通用 | ~1.2万字 |
| `gemini-3.5-flash-thinking` | 深度思考, 最长输出 | **~2万字** |
| `gemini-3.5-flash-thinking-lite` | 自适应思考深度 | ~1.5万字 |
| `gemini-3.1-pro` | Pro (需 cookie 才能真正路由) | ~1.2万字 |
| `gemini-auto` | 自动选择模型 | 不定 |
| `gemini-flash-lite` | 轻量快速 | ~1万字 |
| `gemini-3.5-flash-search` | Flash + 联网搜索 | ~1.2万字 |
| `gemini-3.5-flash-thinking-search` | Thinking + 联网搜索 | **~2万字** |
| `gemini-3.1-pro-search` | Pro + 联网搜索 | ~1.2万字 |
| `gemini-3.1-flash-lite` / `3.1-flash-lite` | Gemini Web UI Flash-Lite alias | ~1万字 |

### Gemini Web 工具 Alias

这些 alias 来自 Gemini Web 源码/HAR 中观察到的名称。它们可以作为模型名或后缀被客户端调用，但只有真实验证返回了图片、视频或其他工件时，才算完全支持。

| 功能 | 模型名 / 后缀 | 状态 |
|------|---------------|------|
| 创建图片 | `nano-banana-2`, `nano-banana-pro`, `gemini-2.5-flash-image`, `gemini-2.5-flash-image-preview`, `gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview-11-2025`, `imagen-3.0-generate-001`, `imagen-3.0-generate-002`, `imagen-4.0-generate-001`, 或后缀 `-image` / `-images` / `-create-image` | experimental |
| 创建视频 | `omni`, `veo-2.0-generate-001`, 或后缀 `-video` / `-videos` / `-create-video` | experimental |
| Deep research | `gemini-deep-research`, 或后缀 `-deep-research` / `-research` | experimental |
| Canvas 工件 | `gemini-canvas`, 或后缀 `-canvas` | 通过代码/HTML artifact 提取支持 |
| Music / TTS | `lyria-3`, `gemini-2.5-flash-preview-tts`, 或后缀 `-music`, `-tts`, `-speech`, `-audio` | limited |
| Photos / Library / Notebooks | `gemini-photos`, `google-photos`, `gemini-library`, `gemini-notebook`, `notebooklm`, 或后缀 `-photo`, `-photos`, `-library`, `-notebook` | limited |

源码中还发现并注册了这些文本/Pro 风格别名: `gemini-2.5-flash-preview-04-17`, `gemini-2.5-flash-preview-05-20`, `gemini-2.5-flash-preview-09-2025`, `gemini-3-flash-preview`, `gemini-advanced`。

同时支持 OpenAI 风格媒体端点:

- `POST /v1/images/generations`，请求体 `{ "model": "nano-banana-2", "prompt": "..." }`
- `POST /v1/videos/generations`，请求体 `{ "model": "omni", "prompt": "..." }`
- `POST /v1/audio/speech`，请求体 `{ "model": "gemini-2.5-flash-preview-tts", "input": "..." }`

这些端点只有在 Gemini Web 真正返回媒体 artifact 时才会填充 `data`；否则会返回上游真实文本和 `web_feature.runtime_status = "limited"`。

### 思考深度

在思考/搜索模型名后追加 `-think=N`:

```
gemini-3.5-flash-thinking-think=0   # 最深 (默认)
gemini-3.5-flash-thinking-think=2   # 中等
gemini-3.5-flash-thinking-think=4   # 最浅
gemini-3.5-flash-thinking-standard  # Gemini Web UI Standard
gemini-3.5-flash-thinking-extended  # Gemini Web UI Extended
```

### 联网搜索

在模型名后追加 `-search`:

```
gemini-3.5-flash-search              # Flash + 搜索
gemini-3.5-flash-thinking-search     # Thinking + 搜索
gemini-3.1-pro-search                # Pro + 搜索
gemini-3.5-flash-search              # 同上
```

## 可选: Cookie 配置 (Pro 模型)

匿名访问对所有模型有效, 但 `gemini-3.1-pro` 在无认证时会路由到 Flash. 要获得真正的 Pro 路由, 需要 **Gemini Advanced (付费订阅)** 账号的 cookie:

```bash
python -m gemini_web2api --cookie-file cookie.txt
```

### 如何获取 Cookie

1. 打开 Chrome, 访问 [gemini.google.com](https://gemini.google.com) 并登录 **Gemini Advanced** 付费账号
2. 打开开发者工具 (F12) → Application → Cookies → `https://gemini.google.com`
3. 复制以下 cookie 值: `SID`, `HSID`, `SSID`, `APISID`, `SAPISID`, `__Secure-1PSID`
4. 创建 `cookie.txt`, 格式如下:

```
SID=你的SID值; HSID=你的HSID值; SSID=你的SSID值; APISID=你的APISID值; SAPISID=你的SAPISID值; __Secure-1PSID=你的1PSID值
```

或使用 JSON 格式:
```json
{"cookie": "SID=xxx; HSID=xxx; SSID=xxx; APISID=xxx; SAPISID=xxx; __Secure-1PSID=xxx", "sapisid": "你的SAPISID值"}
```

**替代方案 (浏览器扩展)**: 可以使用单行 `Cookie` header、上面的 JSON 格式，或浏览器扩展导出的表格 cookie 文件。加载器会保留 Gemini 相关的 `google.com` / `gemini.google.com` cookie，并自动提取 `SAPISID`。

如果目标是完整 Gemini Web UI/工具能力，而不只是后端文本调用，导出的同一登录浏览器会话通常还需要包含 `__Secure-1PSID` 或 `__Secure-3PSID`。可以用下面命令脱敏检查，不会打印 cookie 值:

```bash
python -m gemini_web2api.cookie_diag cookie.txt
```

### 登录账号路径与 XSRF Token

如果已登录的 Gemini 页面 URL 带账号序号, 例如:

```
https://gemini.google.com/u/1/app/...
```

请把 `auth_user` 设置为该序号。登录态的 Gemini Web 请求还可能需要页面里的 XSRF token。该 token 在渲染后的 Gemini 页面源码中名为 `SNlM0e`; 在 `config.json` 中填入 `xsrf_token` 后, 服务会把它作为 `at` 表单字段提交。

示例:

```json
{
  "cookie_file": "/app/cookie.txt",
  "auth_user": "1",
  "xsrf_token": "AOOh0P...",
  "gemini_bl": "boq_assistant-bard-web-server_YYYYMMDD.xx_p0"
}
```

如果登录态请求返回 HTTP 400 且错误中包含 `xsrf`, 请刷新 Gemini Web 后更新 `xsrf_token`, 并确认 `auth_user` 与浏览器 URL 中的 `/u/<序号>/` 一致.

Pro 路由需要 **Gemini Advanced** (付费订阅). 免费 Google 账号的 cookie 可以登录认证, 但会静默回退到 Flash.

如需对比 Gemini Web 匿名态与登录态源码:

```bash
python -m gemini_web2api.source_probe --cookie-file cookie.txt --out gemini_source_probe
```

如果本机浏览器已经登录 Gemini, 也可以尝试读取本机浏览器 cookie:

```bash
python -m gemini_web2api.source_probe --browser-cookie --out gemini_source_probe
```

## 配置文件

在同目录创建 `config.json`:

```json
{
  "port": 8081,
  "host": "0.0.0.0",
  "retry_attempts": 3,
  "retry_delay_sec": 2,
  "request_timeout_sec": 180,
  "gemini_bl": "boq_assistant-bard-web-server_20260525.09_p0",
  "auth_user": null,
  "xsrf_token": null,
  "api_keys": ["sk-your-key"],
  "cookie_file": "cookie.txt",
  "proxy": null,
  "log_requests": true,
  "cookie_files": ["cookie1.txt", "cookie2.txt"],
  "cookie_rotation": true,
  "cookie_rotation_interval": 10,
  "proxies": ["http://proxy1:8080", "http://proxy2:8080"],
  "proxy_rotation": true,
  "proxy_rotation_interval": 10,
  "rate_limit_per_minute": 30,
  "rate_limit_delay": 2
}
```

`api_keys` 为空数组 `[]` 时不校验密钥；填入一个或多个密钥后, `/v1/*` 接口需要 `Authorization: Bearer <key>` 或 `x-api-key: <key>`.

### Cookie 轮询

配置多个 cookie 文件，自动轮询使用，避免被封：

```json
{
  "cookie_files": ["cookie1.txt", "cookie2.txt", "cookie3.txt"],
  "cookie_rotation": true,
  "cookie_rotation_interval": 10
}
```

### 代理轮询

配置多个代理，自动轮询使用：

```json
{
  "proxies": ["http://proxy1:8080", "http://proxy2:8080", "socks5://proxy3:1080"],
  "proxy_rotation": true,
  "proxy_rotation_interval": 10
}
```

## Docker 部署

```bash
cp config.example.json config.json
docker build -t gemini-web2api .
docker run -d --name gemini-web2api -p 8081:8081 -v ./config.json:/app/config.json gemini-web2api
```

或使用 Docker Compose:

```bash
cp config.example.json config.json
docker compose up -d
```

仓库内本地 compose 文件:

```bash
docker compose -f docker-compose.local.yml up -d
```

如需挂载 Cookie 文件:

```bash
docker run -d --name gemini-web2api -p 8081:8081 -v ./config.json:/app/config.json -v ./cookie.txt:/app/cookie.txt gemini-web2api
```

此时 `config.json` 中设置 `"cookie_file": "/app/cookie.txt"`.

> **注意**: 如果 Docker 默认 bridge 网络下出现空回复 (`content: null`), 请切换到 host 网络: `docker run --network host ...` 或在 compose 文件中添加 `network_mode: host`. 这是 Gemini 上游拒绝来自 Docker NAT IP 段的请求导致的.

## 代理配置

如果无法直接访问 `gemini.google.com` (连接超时), 需要配置代理:

**方式 1: 命令行参数**
```bash
python -m gemini_web2api --proxy http://127.0.0.1:7890
```

**方式 2: config.json**
```json
{"proxy": "http://127.0.0.1:7890"}
```

**方式 3: 环境变量** (自动检测)
```bash
set HTTPS_PROXY=http://127.0.0.1:7890
python -m gemini_web2api
```

支持 Clash, V2Ray, Shadowsocks 等任何 HTTP 代理.

## 已知限制

- **图片/多模态输入仍是实验性**: 服务端可以把小文件上传到 Gemini Web 的 content-push 服务，但最终私有 Web `StreamGenerate` 交接仍可能被 Google 拒绝并返回 `BardErrorInfo [1003]`，即使提供 cookie 也可能发生。稳定的文件提示词建议使用 Google 官方 Gemini API Files API 和 API key。
- **Gemini Web 工具依赖账号/UI 状态**: 图片、视频、音乐、Photos、Notebook 等 alias 已能被模型名调用，但如果同一浏览器会话缺少 `__Secure-1PSID` 或 `__Secure-3PSID` 等完整 Web UI cookie，或上游工具流没有返回真实工件，结果会标记为 `limited`。
- **Pro/Ultra 非真实路由**: 无付费订阅 cookie 时, `gemini-3.1-pro` 实际路由到 Flash 模型. "Pro" 只是 UI 偏好标签.
- **单轮对话**: 每次请求是独立对话, 多轮上下文通过在 prompt 中包含历史消息模拟.
- **频率限制**: Google 可能限制高频请求, server 会自动重试但持续高负载可能被封.

## 系统要求

- Python 3.8+
- `httpx` (`pip install httpx`) — 用于流式请求
- 需要能访问 `gemini.google.com` (部分地区需代理)

## 工作原理

逆向 Google Gemini 网页端的 StreamGenerate 协议, 将 OpenAI API 格式与 Gemini 内部 protobuf-like 格式互转. 模型选择通过请求 payload 的 `[79]` 字段控制, 映射自 Gemini 前端 JS 源码中的 `MODE_CATEGORY` 枚举.

## 致谢

- [linux.do](https://linux.do) 社区
- 开源 API 代理生态

## License

MIT
