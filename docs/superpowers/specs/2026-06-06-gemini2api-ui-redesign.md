# Gemini2API UI重新设计规范

**日期**: 2026-06-06  
**版本**: 1.0  
**状态**: 已批准

## 1. 概述

### 1.1 项目背景
Gemini2API是一个将Google Gemini网页端转换为OpenAI兼容API的工具。当前版本基于customtkinter构建桌面应用，支持中英文切换、代理配置等功能。为了提升用户体验和视觉效果，决定迁移到PyQt5框架，实现Windows 11 Mica/Acrylic透明效果和Google Material Design混合风格。

### 1.2 设计目标
- **UI风格**: Windows 11透明效果 + Google卡片式布局混合风格
- **动效**: 基础平滑动效（页面切换、按钮悬停、状态变化）
- **优化**: 全面优化（性能、功能、稳定性、协议）
- **重构**: 重构代码，保持功能完整性

### 1.3 技术选型
- **UI框架**: PyQt5
- **透明效果**: Windows 11 Mica/Acrylic API
- **动效**: Qt Animation Framework
- **架构**: 分层架构（UI层、业务逻辑层、核心API层）

## 2. 架构设计

### 2.1 整体架构
```
┌─────────────────────────────────────────┐
│           PyQt5 Desktop App            │
├─────────────────────────────────────────┤
│  UI Layer (Qt Widgets + QML)           │
│  ├── Main Window (Mica/Acrylic)        │
│  ├── Sidebar Navigation               │
│  ├── Content Pages                    │
│  └── Status Bar                       │
├─────────────────────────────────────────┤
│  Business Logic Layer                 │
│  ├── Server Manager                   │
│  ├── Config Manager                   │
│  ├── Cookie Manager                   │
│  └── Stats Collector                  │
├─────────────────────────────────────────┤
│  Core API Server (gemini_web2api)     │
│  ├── HTTP Server                      │
│  ├── Gemini Protocol Handler          │
│  ├── OpenAI API Compatibility         │
│  └── Streaming Support                │
└─────────────────────────────────────────┘
```

### 2.2 模块职责
1. **UI模块**: 负责界面显示和用户交互
2. **业务逻辑模块**: 处理配置、服务器管理、Cookie等
3. **核心API模块**: 现有的gemini_web2api，负责协议转换

### 2.3 数据流
1. 用户操作 → UI模块 → 业务逻辑模块
2. 业务逻辑模块 → 核心API模块 → Gemini服务
3. 响应数据 → 核心API模块 → 业务逻辑模块 → UI模块

## 3. UI设计

### 3.1 Windows 11 Mica/Acrylic效果
```python
# 使用Qt的Win11 API实现透明效果
import ctypes
from ctypes import wintypes

def enable_mica(hwnd):
    """启用Windows 11 Mica效果"""
    # DWMWA_SYSTEMBACKDROP_TYPE = 38
    # DWMSBT_MAINWINDOW = 2 (Mica)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(
        hwnd, 38, ctypes.byref(ctypes.c_int(2)), 4
    )
```

### 3.2 配色方案（混合风格）
```python
COLORS = {
    # Windows 11 风格
    'mica_bg': '#2C2C2C',  # 半透明背景
    'acrylic_bg': '#333333',  # 亚克力效果
    
    # Google Material Design 风格
    'surface': '#1E1E1E',  # 卡片背景
    'surface_variant': '#2D2D2D',  # 次级表面
    'primary': '#8AB4F8',  # Google蓝
    'on_primary': '#003063',  # 主色上的文字
    
    # 状态颜色
    'success': '#81C995',  # 绿色
    'error': '#F28B82',  # 红色
    'warning': '#FDD663',  # 黄色
}
```

### 3.3 动效设计（基础平滑）
1. **页面切换**: 淡入淡出，持续时间200ms
2. **按钮悬停**: 颜色渐变，持续时间150ms
3. **状态变化**: 平滑过渡，持续时间300ms
4. **卡片展开**: 高度动画，持续时间250ms

### 3.4 布局设计
```
┌─────────────────────────────────────────┐
│  标题栏 (Mica效果)                      │
├──────┬──────────────────────────────────┤
│      │                                  │
│ 侧边栏│         内容区域                │
│      │    (Google卡片式布局)            │
│      │                                  │
│      │                                  │
├──────┴──────────────────────────────────┤
│  状态栏 (显示服务器状态、版本等)        │
└─────────────────────────────────────────┘
```

## 4. 功能设计

### 4.1 核心功能保留
1. **服务器管理**: 启动/停止API服务器
2. **配置管理**: 端口、代理、API密钥等
3. **Cookie管理**: 自动提取、手动刷新、浏览器登录
4. **流式输出配置**: 真流式/假流式/自动模式
5. **联网搜索**: @search后缀支持
6. **系统托盘**: 最小化到托盘，托盘菜单

### 4.2 新增功能
1. **多语言支持增强**:
   - 动态切换语言，无需重启
   - 支持更多语言（日语、韩语等）
   - 语言包外部化，方便扩展

2. **代理链接优化**:
   - 支持SOCKS5代理
   - 代理测试功能
   - 代理自动检测

3. **性能优化**:
   - 连接池管理
   - 请求缓存
   - 内存优化

4. **协议优化**:
   - 改进BL token发现机制
   - 优化请求payload
   - 减少被封风险

### 4.3 API端点扩展
```python
# 新增端点
/api/stats          # 实时统计
/api/health         # 健康检查
/api/config         # 配置管理
/api/logs           # 日志查看
/api/proxy/test     # 代理测试
```

## 5. 性能与协议优化

### 5.1 性能优化策略
1. **连接池管理**:
   ```python
   class ConnectionPool:
       def __init__(self, max_connections=10):
           self.pool = queue.Queue(maxsize=max_connections)
           self.initialize_pool()
   ```

2. **请求缓存**:
   - 模型列表缓存
   - 配置缓存
   - Cookie缓存优化

3. **内存优化**:
   - 及时释放大对象
   - 使用生成器处理流式数据
   - 优化日志存储

### 5.2 协议优化策略
1. **BL Token发现优化**:
   ```python
   def discover_bl_optimized():
       # 使用更高效的正则表达式
       # 添加缓存机制
       # 失败时使用配置值
   ```

2. **请求Payload优化**:
   - 分析Gemini前端JS源码
   - 优化字段顺序和内容
   - 减少不必要的字段

3. **反检测措施**:
   - 随机化请求间隔
   - 模拟真实浏览器行为
   - 动态User-Agent

### 5.3 错误处理改进
1. **重试机制**:
   - 指数退避算法
   - 智能错误分类
   - 自动切换代理

2. **异常监控**:
   - 错误统计
   - 异常报告
   - 自动恢复

## 6. 测试策略

### 6.1 单元测试
- 核心API模块测试
- 配置管理测试
- Cookie处理测试

### 6.2 集成测试
- 服务器启动/停止测试
- API端点测试
- 流式输出测试

### 6.3 UI测试
- 界面元素测试
- 用户交互测试
- 动效测试

### 6.4 性能测试
- 并发请求测试
- 内存使用测试
- 响应时间测试

## 7. 实现计划

### 7.1 阶段1：基础架构（1-2天）
- 搭建PyQt5项目结构
- 实现基础窗口和布局
- 集成现有核心API

### 7.2 阶段2：UI实现（2-3天）
- 实现Mica/Acrylic效果
- 创建所有页面布局
- 添加基础动效

### 7.3 阶段3：功能迁移（2-3天）
- 迁移所有现有功能
- 实现新功能
- 集成测试

### 7.4 阶段4：优化完善（1-2天）
- 性能优化
- 协议优化
- 错误处理改进

### 7.5 阶段5：测试发布（1天）
- 全面测试
- 打包发布
- 文档更新

## 8. 风险评估

### 8.1 技术风险
- PyQt5的Mica效果实现可能复杂
- 不同Windows版本的兼容性问题
- 新UI可能影响性能

### 8.2 缓解措施
- 提供fallback方案（无透明效果）
- 充分测试不同Windows版本
- 性能监控和优化

## 9. 附录

### 9.1 参考资料
- PyQt5文档
- Windows 11 Mica/Acrylic API文档
- Google Material Design指南

### 9.2 术语表
- **Mica**: Windows 11的透明效果
- **Acrylic**: Windows 10/11的模糊透明效果
- **Material Design**: Google的设计语言

---

**批准人**: 用户  
**批准日期**: 2026-06-06  
**下次审查**: 2026-06-13