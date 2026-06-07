# Gemini2API - 项目总结

## 项目结构

```
gemini2api/
├── gemini_web2api/              # 多文件版本（主版本）
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── gemini.py
│   ├── models.py
│   ├── multimodal.py
│   ├── server.py
│   ├── tools.py
│   ├── tokenizer.py
│   ├── stats.py
│   ├── cookie_manager.py
│   ├── playwright_cookie.py
│   ├── dashboard.html
│   └── __pycache__/
├── extension/                   # Edge浏览器扩展
│   ├── manifest.json
│   ├── background.js
│   ├── popup.html
│   ├── popup.js
│   ├── README.md
│   └── icons/
├── app.py                       # GUI版本（customtkinter）
├── gui/                         # GUI版本（PyQt5）
├── gemini_web2api_standalone.py # 单文件版本
├── gui_app.py                   # PyQt5启动入口
├── build.py                     # 构建脚本
├── config.json                  # 配置文件
├── config.example.json          # 配置示例
├── requirements.txt             # 依赖列表
├── Dockerfile                   # Docker构建文件
├── docker-compose.local.yml     # Docker Compose配置
└── dist/Gemini2API/             # EXE输出目录
    └── Gemini2API.exe
```

## 启动方式

### 1. 命令行模式（推荐）

```bash
pip install httpx
python -m gemini_web2api
```

### 2. GUI模式

```bash
pip install httpx customtkinter pystray Pillow
python app.py
```

### 3. Docker模式

```bash
docker build -t gemini-web2api .
docker run -d -p 8081:8081 -v ./config.json:/app/config.json gemini-web2api
```

### 4. EXE模式

```
dist/Gemini2API/Gemini2API.exe
```

## 连接信息

- **Base URL**: `http://<IP>:8081/v1`
- **API Key**: config.json中的api_keys值
- **模型**: gemini-3.5-flash / gemini-3.5-flash-thinking

## Cookie获取方式

### 方式1: Edge浏览器扩展

1. 打开 `edge://extensions/`
2. 开启"开发人员模式"
3. 点击"加载解压缩的扩展"
4. 选择 `extension` 文件夹
5. 登录 gemini.google.com
6. 扩展自动推送Cookie

### 方式2: 手动获取

1. 打开 gemini.google.com
2. F12 → Application → Cookies
3. 复制以下Cookie值：
   - SID, HSID, SSID, APISID, SAPISID, __Secure-1PSID
4. 保存到 cookie.txt

## 核心功能

| 功能 | 状态 | 说明 |
|------|------|------|
| OpenAI兼容API | ✅ | /v1/chat/completions |
| 流式输出 | ✅ | 真流式(httpx) + 假流式 |
| 联网搜索 | ✅ | @search后缀 |
| 多模态输入 | ✅ | 图片/视频/音频/文档 |
| 工具调用 | ✅ | Function Calling |
| Token计算 | ✅ | tiktoken |
| Cookie管理 | ✅ | Edge插件 + 手动 |
| 代理支持 | ✅ | HTTP/SOCKS5 |
| Dashboard | ✅ | /dashboard |
