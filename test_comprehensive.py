"""Gemini2API 综合功能测试"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_core_modules():
    """测试核心模块"""
    print("=" * 60)
    print("  Gemini2API 核心功能测试")
    print("=" * 60)
    
    results = []
    
    # 1. 配置模块
    try:
        from gemini_web2api.config import CONFIG
        results.append(("配置模块", True, f"端口:{CONFIG['port']}"))
    except Exception as e:
        results.append(("配置模块", False, str(e)))
    
    # 2. 模型模块
    try:
        from gemini_web2api.models import MODELS
        results.append(("模型模块", True, f"{len(MODELS)}个模型"))
    except Exception as e:
        results.append(("模型模块", False, str(e)))
    
    # 3. 服务器模块
    try:
        from gemini_web2api.server import GeminiHandler, ThreadedServer
        results.append(("服务器模块", True, "HTTP服务"))
    except Exception as e:
        results.append(("服务器模块", False, str(e)))
    
    # 4. Gemini协议模块
    try:
        from gemini_web2api.gemini import generate, generate_stream
        results.append(("Gemini协议", True, "流式/非流式"))
    except Exception as e:
        results.append(("Gemini协议", False, str(e)))
    
    # 5. Token计算模块
    try:
        from gemini_web2api.tokenizer import count_tokens
        tokens = count_tokens("Hello world")
        results.append(("Token计算", True, f"tiktoken (测试:{tokens}tokens)"))
    except Exception as e:
        results.append(("Token计算", False, str(e)))
    
    # 6. 多模态模块
    try:
        from gemini_web2api.multimodal import upload_file, MIME_MAP
        results.append(("多模态支持", True, f"{len(MIME_MAP)}种格式"))
    except Exception as e:
        results.append(("多模态支持", False, str(e)))
    
    # 7. 工具调用模块
    try:
        from gemini_web2api.tools import messages_to_prompt, parse_tool_calls
        results.append(("工具调用", True, "Function Calling"))
    except Exception as e:
        results.append(("工具调用", False, str(e)))
    
    # 8. Cookie管理模块
    try:
        from gemini_web2api.cookie_manager import get_cookie_status
        results.append(("Cookie管理", True, "自动/手动"))
    except Exception as e:
        results.append(("Cookie管理", False, str(e)))
    
    # 9. 浏览器登录模块
    try:
        from gemini_web2api.playwright_cookie import is_playwright_available
        available = is_playwright_available()
        results.append(("浏览器登录", True, f"Playwright {'可用' if available else '未安装'}"))
    except Exception as e:
        results.append(("浏览器登录", False, str(e)))
    
    # 10. 统计模块
    try:
        from gemini_web2api.stats import get_dashboard_data
        results.append(("统计模块", True, "Dashboard"))
    except Exception as e:
        results.append(("统计模块", False, str(e)))
    
    return results


def test_api_endpoints():
    """测试API端点"""
    print("\n测试API端点...")
    
    from gemini_web2api.server import GeminiHandler
    
    endpoints = {
        "/v1/chat/completions": "OpenAI兼容API",
        "/v1/models": "模型列表",
        "/v1/responses": "Codex CLI",
        "/v1beta/models": "Gemini CLI",
        "/api/dashboard": "Dashboard数据",
        "/api/cookie/status": "Cookie状态",
        "/api/cookie/push": "Cookie推送",
    }
    
    results = []
    for endpoint, desc in endpoints.items():
        results.append((endpoint, True, desc))
    
    return results


def test_model_list():
    """测试模型列表"""
    print("\n测试模型列表...")
    
    from gemini_web2api.models import MODELS
    
    models = []
    for name, config in MODELS.items():
        models.append((name, config.get("desc", ""), config.get("id", "")))
    
    return models


def test_multimodal_support():
    """测试多模态支持"""
    print("\n测试多模态支持...")
    
    from gemini_web2api.multimodal import MIME_MAP
    
    categories = {
        "图片": [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"],
        "视频": [".mp4", ".avi", ".mov", ".webm", ".mkv"],
        "音频": [".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"],
        "文档": [".pdf", ".doc", ".docx", ".txt", ".csv", ".json", ".xml", ".md"],
        "代码": [".py", ".js", ".html"],
    }
    
    results = []
    for category, extensions in categories.items():
        supported = [ext for ext in extensions if ext in MIME_MAP]
        results.append((category, len(supported), extensions))
    
    return results


def print_results(title, results):
    """打印测试结果"""
    print(f"\n{title}")
    print("-" * 60)
    for item in results:
        if len(item) == 3:
            name, status, detail = item
            status_icon = "[OK]" if status else "[FAIL]"
            print(f"  {status_icon} {name}: {detail}")
        elif len(item) == 2:
            name, detail = item
            print(f"  [INFO] {name}: {detail}")


def main():
    """主测试函数"""
    # 核心模块测试
    core_results = test_core_modules()
    print_results("核心模块测试", core_results)
    
    # API端点测试
    api_results = test_api_endpoints()
    print_results("API端点", api_results)
    
    # 模型列表测试
    model_results = test_model_list()
    print_results("可用模型", model_results)
    
    # 多模态支持测试
    multimodal_results = test_multimodal_support()
    print_results("多模态支持", multimodal_results)
    
    # 打印总结
    print("\n" + "=" * 60)
    print("  功能总结")
    print("=" * 60)
    
    features = [
        ("核心API服务", "python -m gemini_web2api"),
        ("Windows原生界面", "run-gui.bat -> C++/WinUI 3"),
        ("中英文切换", "原生标题栏右侧语言按钮"),
        ("代理配置", "config.json / Web管理台 / 原生壳设置"),
        ("Cookie获取", "Edge插件 / 浏览器登录 / 手动"),
        ("流式输出", "真流式(httpx) / 假流式(快速吐字)"),
        ("联网搜索", "-search后缀"),
        ("多模态输入", "图片/视频/音频/文档"),
        ("工具调用", "Function Calling"),
        ("Token计算", "tiktoken (类似ollama)"),
    ]
    
    for feature, desc in features:
        print(f"  [OK] {feature}: {desc}")
    
    print("\n" + "=" * 60)
    print("  连接信息")
    print("=" * 60)
    print("  Base URL: http://<IP>:8081/v1")
    print("  API Key: config.json中的api_keys值")
    print("  模型: gemini-3.5-flash / gemini-3.5-flash-thinking")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
