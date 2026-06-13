# Gemini2API - 项目总结

## 项目结构

优先入口:

- `START_HERE_CN.md`: 中文总索引
- `START_HERE.md`: English entry index

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
├── native/Gemini2API.WinUI/     # C++/WinUI 3 原生桌面壳
├── native/supervisor-rs/        # Rust 进程监督器
├── app.py                       # legacy GUI版本（customtkinter）
├── gui/                         # legacy GUI版本（PyQt5）
├── gemini_web2api_standalone.py # 单文件版本
├── gui_app.py                   # legacy PyQt5 fallback 源码
├── build.py                     # 构建脚本
├── config.json                  # 配置文件
├── config.example.json          # 配置示例
├── requirements.txt             # 依赖列表
├── Dockerfile                   # Docker构建文件
├── docker-compose.local.yml     # Docker Compose配置
└── build/native/x64/Release/    # 原生 EXE 输出目录
    └── Gemini2API.WinUI.exe
```

## 启动方式

### 1. 命令行模式（推荐）

```bash
pip install -r requirements.txt
python -m gemini_web2api
```

### 2. 原生桌面壳模式

```bash
run-gui.bat
```

### 3. Docker模式

```bash
docker compose -f docker-compose.local.yml up -d
```

### 4. 原生 EXE 模式

```
build/native/x64/Release/Gemini2API.WinUI.exe
```

## 连接信息

- **Base URL**: `http://<IP>:8081/v1`
- **Dashboard**: `http://localhost:8081/dashboard`
- **API Key**: config.json中的api_keys值
- **模型**: gemini-3.5-flash / gemini-3.5-flash-thinking

## 根目录快捷脚本

- `run-api.bat`
- `run-gui.bat` - 启动 C++/WinUI 3 原生桌面壳
- `run-gui-pyqt.bat` - 仅作紧急 legacy fallback
- `run-docker.bat`
- `open-dashboard.bat`
- `build.bat`

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
| 联网搜索 | ✅ | -search后缀 |
| 多模态输入 | ✅ | 图片/视频/音频/文档 |
| 工具调用 | ✅ | Function Calling |
| Token计算 | ✅ | tiktoken |
| Cookie管理 | ✅ | Edge插件 + 手动 |
| 代理支持 | ✅ | HTTP/SOCKS5 |
| Dashboard | ✅ | /dashboard |
| 代理池配置UI | ✅ | Web + 桌面壳已同步 |
| 服务设置UI | ✅ | Web 管理面板已同步 |
