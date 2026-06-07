# Gemini2API - 功能清单

## 核心功能

| 功能 | 状态 | 说明 |
|------|------|------|
| OpenAI兼容API | ✅ | /v1/chat/completions |
| 流式输出 | ✅ | 真流式(httpx) + 假流式 |
| 联网搜索 | ✅ | -search后缀 |
| 多模态输入 | ✅ | 图片/视频/音频/文档 |
| 工具调用 | ✅ | Function Calling |
| Token计算 | ✅ | tiktoken |
| 深度思考 | ✅ | @think=N后缀 |
| Cookie管理 | ✅ | Edge插件 + 手动 |
| 代理支持 | ✅ | HTTP/SOCKS5 |
| Dashboard | ✅ | /dashboard |

## 新增功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 搜索模型 | ✅ | -search后缀启用联网搜索 |
| Cookie轮询 | ✅ | 多cookie文件自动轮询 |
| 代理轮询 | ✅ | 多代理自动轮询 |
| 速率限制 | ✅ | 可配置请求间隔 |
| Edge扩展 | ✅ | 自动获取和推送Cookie |
| 匿名模型 | ✅ | 未登录只显示可用模型 |
| 多文件上传 | ✅ | 图片/视频/音频/文档 |

## 启动方式

| 方式 | 命令 | 说明 |
|------|------|------|
| 命令行 | `python -m gemini_web2api` | 最稳定 |
| GUI | `python app.py` | 桌面界面 |
| Docker | `docker run -p 8081:8081 gemini-web2api` | 容器化 |
| EXE | `dist/Gemini2API/Gemini2API.exe` | 独立运行 |

## 模型列表

### 匿名可用（无需登录）

| 模型 | 说明 |
|------|------|
| gemini-3.5-flash | 快速通用 |
| gemini-3.5-flash-thinking | 深度思考 |
| gemini-3.5-flash-thinking-lite | 自适应思考 |
| gemini-auto | 自动选择 |
| gemini-flash-lite | 轻量快速 |
| gemini-3.5-flash-search | Flash+搜索 |
| gemini-3.5-flash-thinking-search | Thinking+搜索 |

### 需要登录

| 模型 | 说明 |
|------|------|
| gemini-3.1-pro | Pro模型 |
| gemini-3.1-pro-enhanced | Pro增强 |
| gemini-3.1-pro-search | Pro+搜索 |

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
  "rate_limit_delay": 2
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
├── app.py                 # GUI版本
├── gemini_web2api_standalone.py  # 单文件版本
├── config.json            # 配置文件
├── requirements.txt       # 依赖列表
├── Dockerfile             # Docker配置
└── dist/Gemini2API/       # EXE输出
```
