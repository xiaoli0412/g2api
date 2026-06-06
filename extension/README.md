# Gemini Cookie Pusher - Edge Extension

## 功能说明

自动从 gemini.google.com 获取 Cookie 并推送到 gemini-web2api 服务器。

## 安装步骤

### 方法1：开发者模式安装（推荐）

1. 打开 Edge 浏览器
2. 地址栏输入 `edge://extensions/` 并回车
3. 打开右上角的 **"开发人员模式"** 开关
4. 点击 **"加载解压缩的扩展"** 按钮
5. 选择 `extension` 文件夹
6. 扩展安装完成，会出现在扩展列表中

### 方法2：打包后安装

1. 打开 Edge 浏览器
2. 地址栏输入 `edge://extensions/` 并回车
3. 打开右上角的 **"开发人员模式"** 开关
4. 点击 **"打包扩展"** 按钮
5. 选择 `extension` 文件夹
6. 会生成 `.crx` 文件和 `.pem` 密钥文件
7. 将 `.crx` 文件拖入 Edge 窗口安装

## 使用说明

### 前置条件

1. 确保 gemini-web2api 服务已启动
2. 确保已登录 gemini.google.com

### 操作步骤

1. 点击工具栏中的扩展图标
2. 查看 Cookie 状态（绿色表示已找到，红色表示缺失）
3. 点击 **"Push Cookies Now"** 按钮手动推送
4. 扩展会每 10 分钟自动检查并推送

### 配置说明

- **Server URL**: API 服务器地址，默认 `http://127.0.0.1:8081`
- **Connection Status**: 连接状态
- **Last Push**: 上次推送时间
- **Cookies**: 已找到的 Cookie 数量

## Cookie 说明

需要以下 Cookie：

| Cookie 名称 | 说明 |
|-------------|------|
| SID | 会话 ID |
| HSID | 会话 ID |
| SSID | 会话 ID |
| APISID | API 会话 ID |
| SAPISID | 安全 API 会话 ID |
| __Secure-1PSID | 安全会话 ID |

## 故障排除

### 问题：显示 "No Cookies"

**解决方案**：
1. 确保已登录 gemini.google.com
2. 刷新 gemini.google.com 页面
3. 重新点击扩展图标

### 问题：显示 "Disconnected"

**解决方案**：
1. 确保 gemini-web2api 服务已启动
2. 检查 Server URL 是否正确
3. 检查防火墙设置

### 问题：显示 "Server Error"

**解决方案**：
1. 检查 gemini-web2api 服务日志
2. 确保 API 端点正常工作

## 开发说明

### 文件结构

```
extension/
├── manifest.json      # 扩展配置
├── background.js      # 后台脚本
├── popup.html         # 弹出页面
├── popup.js           # 弹出页面脚本
└── icons/             # 图标
    ├── icon16.png
    ├── icon32.png
    ├── icon48.png
    └── icon128.png
```

### 权限说明

- `cookies`: 读取 gemini.google.com 的 Cookie
- `alarms`: 定时任务
- `storage`: 存储配置
- `activeTab`: 访问当前标签页

### API 接口

扩展通过以下 API 与服务器通信：

- `POST /api/cookie/push`: 推送 Cookie
  ```json
  {
    "cookies": "SID=xxx; HSID=xxx; ...",
    "sapisid": "xxx"
  }
  ```

## 版本历史

### v1.0.0 (2026-06-06)

- 初始版本
- 支持自动获取 Cookie
- 支持手动推送
- 支持定时推送
- 支持配置服务器地址
