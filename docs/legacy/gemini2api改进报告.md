# HelloKimi 学习应用报告 - gemini2api 改进

> 日期：2026-06-08
> 状态：已完成并测试通过

---

## 一、改进内容

### 1. 工具调用解析增强（三层兜底）✅

**文件**：`gemini_web2api/tools.py`

**改进前**：
- 只支持单一正则匹配 ` ```tool_call ``` ` 格式
- 解析失败时直接丢失

**改进后**：
- **Layer 1**：` ```tool_call\n{...}\n``` ` 标准格式
- **Layer 2**：` ```json\n{...}\n``` ` 或 ` ```function_call ``` ` 代码块
- **Layer 3**：平衡括号扫描裸 JSON（必须含 name + arguments）

**新增函数**：
```python
def _scan_balanced_json(text: str) -> list:
    """扫描文本中的平衡 JSON 对象"""

def _coerce_tool_call(obj: dict) -> dict | None:
    """标准化各种工具调用格式"""
```

**测试结果**：
```
Test 1 (standard): 1 calls - [OK]
Test 2 (json block): 1 calls - [OK]  
Test 3 (raw JSON): 1 calls - [OK]
Test 4 (google): 1 calls - [OK]
Test 5 (no tools): 0 calls - [OK]
Test 6 (multiple): 2 calls - [OK]
Test 7 (args format): 1 calls - [OK]
```

---

### 2. Token 估算算法改进 ✅

**文件**：`gemini_web2api/server.py`

**改进前**：
```python
def _usage(prompt, text):
    p = len(prompt) // 4
    c = len(text) // 4
```

**改进后**：
```python
def _approx_tokens(s: str) -> int:
    """CJK: ~1.5 chars/token, ASCII: ~4 chars/token"""
    cjk_count = sum(1 for c in s if '\u4e00' <= c <= '\u9fff')
    ascii_count = len(s) - cjk_count
    return max(1, int(cjk_count / 1.5 + ascii_count / 4))
```

**测试结果**：
```
ASCII 'Hello World': 2 tokens
Chinese '你好世界': 2 tokens  
Mixed 'Hello 你好 World 世界': 5 tokens
```

---

## 二、未采用的设计（原因说明）

### 1. CF Workers 部署方式
- 用户采用订阅/梯子方式
- 不需要 CF 边缘计算

### 2. KV 存储
- gemini2api 使用文件系统存储 cookie
- 当前方案更适合本地部署场景

### 3. Nonce 管理
- Gemini 使用 cookie 认证，不同于 Kimi 的 nonce 机制
- 已有 cookie_manager.py 处理

---

## 三、代码变更摘要

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `tools.py` | 增强 | 三层兜底解析、平衡括号扫描 |
| `server.py` | 优化 | Token 估算算法改进 |

---

## 四、兼容性

- ✅ 向后兼容原有 `tool_call` 格式
- ✅ 新增支持 `json`、`function_call` 代码块
- ✅ 新增支持裸 JSON 解析
- ✅ Google API 格式同步增强

---

## 五、后续建议

1. **监控工具调用成功率** - 观察新解析器在生产环境的表现
2. **扩展工具格式支持** - 如有新的模型输出格式可快速适配
3. **性能优化** - 平衡括号扫描在超长文本时可能需要优化

---

*改进已完成，测试通过，可投入使用。*
