# Gemini2API 启动索引

这个文件是仓库总入口。打开项目后，优先看这里。

## 你现在最常用的入口

1. API 服务
   `python -m gemini_web2api`

2. Windows 桌面壳（C++/WinUI 3 原生界面）
   `run-gui.bat`

3. Windows 桌面壳 CLI 模式
   `python app.py --cli`

4. Web 管理面板
   `http://localhost:8081/dashboard`

5. Docker 本地启动
   `docker compose -f docker-compose.local.yml up -d`

6. 原生 EXE 构建
   `python build.py`
   或双击 `build.bat`

## 根目录脚本

- `run-api.bat`: 启动 API 服务
- `run-gui.bat`: 启动 C++/WinUI 原生桌面壳
- `run-gui-pyqt.bat`: 仅作故障回退，不作为正常桌面应用入口
- `run-docker.bat`: 启动本地 Docker 服务
- `open-dashboard.bat`: 打开 Web 管理面板
- `build.bat`: 构建新版 EXE

## 主要文件位置

- `gemini_web2api/`: 核心服务代码
- `gemini_web2api/dashboard.html`: 高级 Web 运维管理台
- `native/Gemini2API.WinUI/`: C++/WinUI 3 原生桌面壳
- `app.py`: legacy customtkinter 桌面壳
- `gui_app.py`: legacy PyQt fallback 源码，保留兼容
- `extension/`: Edge 扩展
- `config.example.json`: 配置模板
- `build/native/x64/Release/Gemini2API.WinUI.exe`: C++/WinUI 原生 EXE

## 管理界面说明

- Web 面板支持：运行概览、请求明细、模型统计、趋势分析、Cookie 管理、代理配置、服务设置
- 直接打开 `gemini_web2api/dashboard.html` 会进入离线预览模式
- 通过服务地址 `http://localhost:8081/dashboard` 打开会进入实时管理模式

## 推荐使用顺序

1. 复制配置模板
   `copy config.example.json config.json`

2. 启动服务
   `python -m gemini_web2api`

3. 打开面板
   `http://localhost:8081/dashboard`

4. 如果要桌面壳
   `run-gui.bat`

5. 如果要构建 EXE
   `build.bat`
