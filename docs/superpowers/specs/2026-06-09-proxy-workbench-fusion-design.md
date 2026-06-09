# Gemini2API 代理工作台融合设计

**日期**: 2026-06-09
**状态**: 待用户复核
**方向**: 融合 FlClash 的代理信息架构，保留 Gemini2API 现有 UI 与后端边界

## 目标

把当前项目里分散在服务器设置、dashboard 和代理池配置中的代理能力，重构成一个“代理工作台”。工作台参考 FlClash 的代理页结构，但不做大迁移、不照搬 Flutter UI，也不推翻现有 WinUI、PyQt、HTML dashboard 的入口。

本设计支持两类合法使用场景：

1. 匿名模式下使用出口池、队列、并发上限、限速、退避和健康检查，减少单一出口过载。
2. 多账号模式下为每个账号配置文件绑定固定或首选代理出口，并分别设置限额、健康状态和失败处理。

本设计不实现绕过封锁、规避风控、规避服务限制或模拟无限流量的行为。所有“多线程”和“多出口”能力都必须经过显式并发上限、请求队列、速率限制和失败退避。

## 参考来源

FlClash 参考文件：

- `lib/views/proxies/proxies.dart`: 顶部搜索、动作菜单、设置页、provider 入口、测速按钮。
- `lib/views/proxies/tab.dart`: 代理组标签页、当前组、滚动到选中节点、批量延迟测试。
- `lib/views/proxies/list.dart`: 分组列表、可展开组、粘性组头、按组定位。
- `lib/views/proxies/card.dart`: 代理卡片、延迟状态、选中态、代理类型与描述。
- `lib/views/proxies/providers.dart`: Provider 更新、订阅信息、上传/同步动作。
- `lib/views/proxies/setting.dart`: 视图类型、排序、卡片大小、布局密度设置。

Gemini2API 当前相关文件：

- `gemini_web2api/proxy_builtin.py`: 内置代理池、订阅解析、健康检查、测速、策略选择。
- `gemini_web2api/admin.py`: `/admin/proxy` 与代理状态摘要。
- `gemini_web2api/server.py`: `/api/proxy/status`、`/api/config` 与请求日志代理字段。
- `gemini_web2api/gemini.py`: 请求时选择代理、记录当前线程最后使用代理。
- `gemini_web2api/config.py`: 代理池、代理轮换、限速配置。
- `gui/pages/server_page.py`: PyQt 服务器页内的代理配置。
- `native/Gemini2API.WinUI/src/Views/ServerPage.xaml`: WinUI 服务器页代理表单。
- `gemini_web2api/dashboard.html`: Web dashboard 的代理配置和状态入口。

## 设计原则

1. **融合而非迁移**: 保留现有 UI 栈，只把代理体验从“表单配置”升级成“可观察、可操作的工作台”。
2. **WinUI 优先，PyQt 与 dashboard 兼容**: 原生 WinUI 是主要体验；PyQt 和 dashboard 提供同等配置入口和基础状态视图。
3. **FlClash 信息架构，本项目视觉语言**: 借用搜索、分组、卡片、provider、测速、排序等结构；视觉上继续使用 Windows 11 / Fluent / 当前 PyQt 卡片风格。
4. **安全出口治理**: 多出口用于负载治理、隔离故障、账号配置绑定和可观测性，不用于绕过封禁或规避限制。
5. **最小后端重构**: 继续使用 `proxy_builtin.py` 作为代理池核心，只增加账号绑定、并发治理、路由决策和管理 API。

## 推荐方案

采用“代理工作台 + 后端路由策略层”的融合方案。

现有 Server/Settings 页面继续保留基础代理字段：单代理 URL、是否启用代理池、默认策略。新增或强化独立代理工作台页面，承载高级代理池、订阅、测速、节点健康、账号绑定和并发治理。

### 为什么不大迁移

直接迁到 FlClash 式 Flutter UI 会与当前 WinUI/PyQt 结构割裂，也会让已有 native shell 迁移工作失去连续性。直接只改 Server 表单又无法承载几十个节点、账号绑定和健康状态。因此融合方案最稳：把 FlClash 的代理页变成 Gemini2API 自己的 Fluent 工作台。

## UI 设计

### 导航

新增“代理”页面，放在 Server 与 Cookies 附近。

WinUI 导航建议：

- Home
- Server
- Proxies
- Cookies
- Streaming
- Models
- Logs
- Settings

PyQt 导航同步新增 `proxy` 页；dashboard 新增或强化 Proxy tab。

### 代理工作台页面

顶部区域：

- 页面标题: `Proxies` / `代理`
- 副标题: 出口池、账号绑定、并发治理和健康状态。
- 搜索框: 按节点名、协议、host、标签、账号绑定过滤。
- 命令按钮:
  - Refresh status
  - Test selected
  - Test all healthy
  - Update providers
  - Add proxy
  - Settings

摘要条：

- 总节点数
- 健康节点数
- 当前策略
- 队列长度
- 活跃请求数
- 匿名模式并发上限
- 账号绑定数量

主体视图支持两种模式：

1. **分组视图**: 参考 FlClash tab 视图。组包括 `All`、`Healthy`、`Unhealthy`、`Anonymous pool`、`Account-bound`、订阅 provider 名称、手动节点。
2. **列表视图**: 参考 FlClash list 视图。分组头可展开，支持滚动到选中节点。

代理卡片：

- 节点名
- 协议类型
- masked URL 或 host
- 延迟: 未测试、测试中、毫秒、timeout
- 状态: healthy、cooldown、unhealthy、disabled
- 最近使用时间
- 成功/失败计数
- 当前绑定账号数量
- 最近失败原因
- 操作: test、disable/enable、copy masked、bind account、remove

Provider 面板：

- 订阅名称或 URL 预览
- 节点数
- 最近更新时间
- 更新状态
- 操作: sync、disable、remove、upload local provider

设置面板：

- 视图模式: group / list
- 排序: default / delay / name / health / last used
- 卡片密度: compact / standard / expanded
- 策略: round_robin / random / fastest / least_used / sticky_account
- 健康检查开关与间隔
- 自动更新订阅开关与间隔
- 匿名模式并发上限
- 每出口并发上限
- 每账号并发上限
- 失败退避策略

### 与现有页面融合

Server 页面只保留基础代理摘要和入口按钮，不再塞入大段代理列表：

- Proxy URL
- Proxy pool enabled
- Strategy
- Open proxy workbench

Cookies 页面增加账号绑定提示，不直接承担代理管理：

- 每个 cookie/account 显示绑定代理摘要。
- `Bind in Proxies` 按钮跳转代理工作台。

Logs 页面显示路由决策：

- request id
- account profile
- proxy node
- queue wait
- status
- retry count
- failure reason

## 后端设计

### 配置结构

新增或扩展配置字段：

```json
{
  "proxy_workbench_enabled": true,
  "proxy_groups": [],
  "proxy_providers": [],
  "proxy_account_bindings": [],
  "anonymous_route_policy": {
    "enabled": true,
    "strategy": "round_robin",
    "max_concurrent_requests": 20,
    "max_concurrent_per_proxy": 2,
    "requests_per_minute_per_proxy": 30,
    "queue_max_size": 200,
    "cooldown_seconds": 120
  },
  "account_route_policy": {
    "strategy": "sticky_account",
    "max_concurrent_per_account": 1,
    "fallback": "queue_then_fail"
  }
}
```

`max_concurrent_requests` 可以由用户调高，但 UI 必须提示风险，并且所有请求仍经过队列、限速和失败退避。默认值不应设置为 100。

账号绑定结构：

```json
{
  "account_id": "u/1",
  "label": "work account",
  "cookie_file": "cookies/work.txt",
  "primary_proxy": "node-id-1",
  "fallback_group": "Healthy",
  "enabled": true
}
```

### 路由策略层

新增 `gemini_web2api/proxy_routing.py`，作为 `gemini.py` 与 `proxy_builtin.py` 之间的策略层。

职责：

- 根据请求上下文判断匿名模式或账号模式。
- 为匿名请求选择出口池节点。
- 为账号请求选择绑定节点。
- 应用队列、并发信号量和速率限制。
- 标记成功、失败、冷却和熔断。
- 返回路由决策对象，供日志、dashboard 和 UI 显示。

路由决策对象包含：

- route_id
- mode: anonymous / account
- account_id
- proxy_node_id
- proxy_url
- strategy
- queue_wait_ms
- retry_count
- decision_reason

### 账号模型

现有 `auth_user` 和 cookie pool 只能表达当前账号索引或轮换 cookie，无法可靠表达“十几个账号分别绑定不同 IP”。需要新增账号配置文件概念，但不迁移旧 cookie 行为：

- 旧 `cookie_file` 继续可用。
- 旧 `cookie_files` 继续作为兼容轮换。
- 新 `accounts` 或 `proxy_account_bindings` 用于绑定账号与代理。
- 如果请求未指定账号，走默认 cookie 或匿名模式。
- 如果请求指定账号，使用账号配置文件里的 cookie、auth_user、proxy binding。

请求如何指定账号：

- 管理 API 可维护账号 profile。
- OpenAI-compatible 请求可通过可选 header 指定账号 profile，例如 `X-Gemini-Account`.
- 若未指定账号，使用默认策略。

### 管理 API

保留现有端点：

- `GET /api/proxy/status`
- `GET /admin/proxy`
- `POST /api/config`

新增端点：

- `GET /admin/proxy/nodes`
- `POST /admin/proxy/nodes`
- `PATCH /admin/proxy/nodes/{id}`
- `DELETE /admin/proxy/nodes/{id}`
- `POST /admin/proxy/test`
- `POST /admin/proxy/test-all`
- `GET /admin/proxy/providers`
- `POST /admin/proxy/providers/sync`
- `GET /admin/proxy/routes`
- `GET /admin/accounts`
- `POST /admin/accounts`
- `PATCH /admin/accounts/{id}`
- `DELETE /admin/accounts/{id}`
- `POST /admin/accounts/{id}/bind-proxy`

所有返回值必须 mask 代理账号密码、订阅 token、cookie 和 API key。

## 数据流

匿名请求：

1. HTTP 请求进入 `server.py`。
2. `gemini.py` 构建 Gemini 请求。
3. `proxy_routing.py` 判断没有账号上下文，进入 anonymous policy。
4. 队列和并发限制允许后，从 `proxy_builtin.py` 获取健康节点。
5. 请求发出。
6. 成功则标记节点成功；失败则按错误类型标记失败、冷却或重试。
7. `stats.py` 记录 route decision。

账号请求：

1. 请求带 `X-Gemini-Account` 或默认账号上下文。
2. 路由策略加载账号配置文件。
3. 使用该账号 cookie/auth_user 和绑定代理。
4. 若绑定代理不可用，按 `fallback` 策略排队、切换到 fallback group 或直接失败。
5. 日志记录账号 profile 和代理节点，但不记录敏感值。

UI 状态刷新：

1. WinUI/PyQt/dashboard 调用 `/api/proxy/status` 和 `/admin/proxy/*`。
2. 后端返回 masked 节点、provider、健康、队列、绑定和最近路由。
3. UI 渲染摘要、卡片、分组和日志。

## 错误处理

代理错误分类：

- 连接失败
- DNS 失败
- TLS 失败
- 超时
- upstream HTTP 错误
- 账号/cookie 错误
- 速率限制/过载
- 配置错误

处理策略：

- 单次代理错误增加 failure count。
- 连续失败达到阈值后进入 cooldown。
- cooldown 到期后允许健康检查恢复。
- 账号绑定代理失败时，不静默切换到任意代理；按用户配置 fallback。
- 队列满时返回明确错误，而不是无限开线程。
- 所有错误写入 request detail，但 mask 敏感字段。

## 安全与合规边界

本项目可以提供：

- 合法代理配置管理。
- 节点健康检测。
- 出口负载治理。
- 账号和出口的显式绑定。
- 请求队列、限速和退避。
- 管理端可观察性。

本项目不提供：

- 绕过封锁或封禁的保证。
- 绕过服务配额、风控、账号限制或 IP 限制的逻辑。
- 自动生成大量身份、账号或代理来规避限制。
- 隐藏真实意图或规避检测的请求伪装。

UI 文案应使用“出口治理”“健康检查”“绑定”“限额”“队列”“退避”等词，不使用“防封”“绕过”“规避风控”等承诺性表述。

## 测试策略

单元测试：

- `proxy_routing.py` 策略选择。
- 匿名策略并发上限。
- 每代理并发上限。
- 账号绑定优先级。
- fallback 行为。
- 敏感字段 mask。
- 失败计数和 cooldown。

集成测试：

- `/api/config` 更新后代理池重新初始化。
- `/api/proxy/status` 返回工作台摘要。
- `/admin/proxy/test` 能更新节点延迟。
- `/admin/accounts` 增删改查。
- 带 `X-Gemini-Account` 的请求走绑定代理。
- 未带账号的请求走匿名策略。

UI 验证：

- WinUI 代理页可显示摘要、分组、节点卡片、provider 和设置。
- PyQt 代理页可编辑核心配置并展示节点状态。
- dashboard Proxy tab 可展示同样的摘要和基础操作。
- 小窗口下文本不重叠，长代理名和长 provider URL 截断显示。

回归测试：

- 现有 Python API 测试继续通过。
- 旧 `proxy` 单代理配置仍可用。
- 旧 `proxies` 和 `proxy_subscriptions` 配置仍可被读取。
- 未启用代理池时，行为与当前版本一致。

## 分阶段实施

### 阶段 1: 后端模型与兼容 API

- 新增 `proxy_routing.py`。
- 扩展配置默认值。
- 增加账号绑定数据结构。
- 增加代理状态、节点、provider 和账号 API。
- 保持旧配置兼容。

### 阶段 2: WinUI 融合代理页

- 新增 Proxies 页面。
- Server 页面只保留代理摘要与入口。
- Logs 页面显示路由决策字段。
- 使用当前 Fluent/Settings 卡片风格，不照搬 Flutter 控件。

### 阶段 3: PyQt 与 dashboard 兼容入口

- PyQt 新增或强化代理页。
- dashboard Proxy tab 显示工作台摘要、节点表和 provider 操作。
- Server 基础代理设置继续可用。

### 阶段 4: 验证与调优

- 增加策略和 API 测试。
- 跑现有 pytest。
- 做 UI 静态检查和必要截图验证。
- 检查日志与状态返回不会泄露敏感字段。

## 验收标准

- 用户能在代理工作台中查看、搜索、测速、禁用和同步代理节点。
- 用户能看到匿名出口池的并发上限、队列长度、每出口限额和健康状态。
- 用户能创建多个账号 profile，并把不同账号绑定到不同代理节点或 fallback 组。
- 请求日志能显示每次请求的账号 profile、代理节点、排队时间、失败原因和重试次数。
- 未登录匿名请求和已登录账号请求都经过同一个路由策略层。
- 所有敏感值在 API、UI 和日志中被 mask。
- 旧配置和旧启动方式不被破坏。
- UI 与当前项目风格融合，不出现一部分像 FlClash、一部分像旧表单的割裂感。
