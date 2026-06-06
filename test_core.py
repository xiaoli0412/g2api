"""API功能测试脚本"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_modules():
    """测试核心模块"""
    print("测试核心模块...")
    
    try:
        from gemini_web2api.config import CONFIG
        print(f"[OK] 配置模块加载成功")
    except Exception as e:
        print(f"[FAIL] 配置模块: {e}")
        return False
    
    try:
        from gemini_web2api.models import MODELS
        print(f"[OK] 模型模块加载成功, 可用模型: {len(MODELS)}个")
    except Exception as e:
        print(f"[FAIL] 模型模块: {e}")
        return False
    
    try:
        from gemini_web2api.server import GeminiHandler, ThreadedServer
        print(f"[OK] 服务器模块加载成功")
    except Exception as e:
        print(f"[FAIL] 服务器模块: {e}")
        return False
    
    try:
        from gemini_web2api.gemini import generate, generate_stream
        print(f"[OK] Gemini协议模块加载成功")
    except Exception as e:
        print(f"[FAIL] Gemini协议模块: {e}")
        return False
    
    return True


def test_api_endpoints():
    """测试API端点定义"""
    print("\n测试API端点...")
    
    from gemini_web2api.server import GeminiHandler
    
    # 检查关键方法
    methods = ['do_GET', 'do_POST', 'do_OPTIONS', '_handle_chat']
    for method in methods:
        if hasattr(GeminiHandler, method):
            print(f"[OK] {method} 方法存在")
        else:
            print(f"[FAIL] {method} 方法缺失")
            return False
    
    return True


def test_config():
    """测试配置"""
    print("\n测试配置...")
    
    from gemini_web2api.config import CONFIG
    
    required_keys = ['port', 'host', 'api_keys', 'proxy', 'cookie_file']
    for key in required_keys:
        if key in CONFIG:
            print(f"[OK] {key}: {CONFIG[key]}")
        else:
            print(f"[WARN] {key} 未配置")
    
    return True


def main():
    print("=" * 50)
    print("  Gemini2API 核心功能测试")
    print("=" * 50)
    
    if not test_modules():
        print("\n模块测试失败!")
        return 1
    
    if not test_api_endpoints():
        print("\nAPI端点测试失败!")
        return 1
    
    if not test_config():
        print("\n配置测试失败!")
        return 1
    
    print("\n" + "=" * 50)
    print("  所有测试通过!")
    print("=" * 50)
    print("\n核心功能:")
    print("  - API端点: /v1/chat/completions")
    print("  - 模型列表: /v1/models")
    print("  - Google兼容: /v1beta/models")
    print("  - 响应API: /v1/responses")
    print("\n启动命令:")
    print("  python -m gemini_web2api")
    print("\n连接信息:")
    print("  Base URL: http://<IP>:8081/v1")
    print("  API Key: config.json中的api_keys值")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
