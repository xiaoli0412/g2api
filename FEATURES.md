# Gemini2API 功能清单与使用指南

## 核心功能状态

| 功能 | 状态 | 说明 |
|------|------|------|
| OpenAI兼容API | ✅ | /v1/chat/completions |
| 模型列表 | ✅ | /v1/models |
| 流式输出 | ✅ | 真流式(httpx) + 假流式(快速吐字) |
| 联网搜索 | ✅ | @search后缀 |
| 多模态输入 | ✅ | 图片/视频/音频/文档 |
| 工具调用 | ✅ | Function Calling |
| Token计算 | ✅ | tiktoken (类似ollama) |
| Cookie管理 | ✅ | Edge插件 + 浏览器登录 + 手动 |
| 代理支持 | ✅ | HTTP/SOCKS5 |
| 中英文切换 | ✅ | GUI支持 |
| 系统托盘 | ✅ | 最小化到托盘 |
| Dashboard | ✅ | /dashboard |

## 启动方式

### 命令行模式
```bash
python -m gemini_web2api
```

### GUI模式
```bash
python gui_app.py
```

## 连接信息

- **Base URL**: `http://<IP>:8081/v1`
- **API Key**: config.json中的api_keys值
- **模型**: gemini-3.5-flash / gemini-3.5-flash-thinking

## Cookie获取方式

### 方式1: Edge浏览器插件
1. 安装extension目录下的Edge扩展
2. 登录gemini.google.com
3. 插件自动推送cookie

### 方式2: 浏览器登录
1. GUI中点击"浏览器登录"
2. 自动打开Edge浏览器
3. 登录Google账号
4. 自动获取cookie

### 方式3: 手动获取
1. 打开gemini.google.com
2. F12 → Application → Cookies
3. 复制SID, HSID, SSID, APISID, SAPISID, __Secure-1PSID
4. 保存到cookie.txt

## 流式输出模式

- **auto**: 自动选择（有httpx用真流式，否则假流式）
- **true**: 真流式（需要httpx）
- **fake**: 假流式（全部生成完再快速吐字）

## 多模态支持

- **图片**: png, jpg, jpeg, gif, webp, bmp
- **视频**: mp4, avi, mov, webm, mkv
- **音频**: mp3, wav, ogg, flac, m4a, aac
- **文档**: pdf, doc, docx, txt, csv, json, xml, md
- **代码**: py, js, html

## 联网搜索

使用@search后缀：
```
gemini-3.5-flash@search
gemini-3.5-flash-thinking@search
```

## 测试命令

```bash
# 测试核心功能
python test_comprehensive.py

# 测试API
curl http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-key" \
  -d '{"model":"gemini-3.5-flash","messages":[{"role":"user","content":"Hello!"}]}'
```
