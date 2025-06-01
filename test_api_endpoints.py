#!/usr/bin/env python3
"""
API端点测试脚本

用于验证新的JSON API端点是否正常工作
"""

import requests
import json

def test_api_endpoints():
    """测试API端点"""
    base_url = "http://localhost:8080"
    
    # 测试端点列表
    endpoints = [
        "/health",
        "/api/v1/web/devices/json?page=1&size=5",
        "/api/v1/web/statistics/json?page=1&size=5",
        "/api/v1/books/stats/overview",
        "/api/v1/books/stats/public?username=admin"
    ]
    
    print("🔍 测试API端点连通性...\n")
    
    # 首先测试健康检查
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ 服务器连接正常")
        else:
            print("❌ 服务器连接异常")
            return
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        print("\n💡 请确保服务器正在运行:")
        print("   uv run python main.py both")
        return
    
    # 测试需要认证的端点（模拟）
    auth_endpoints = [
        "/api/v1/web/devices/json?page=1&size=5",
        "/api/v1/web/statistics/json?page=1&size=5",
        "/api/v1/books/stats/overview"
    ]
    
    print("\n📊 测试API端点...")
    for endpoint in auth_endpoints:
        try:
            url = f"{base_url}{endpoint}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                print(f"✅ {endpoint} - 正常")
            elif response.status_code == 404:
                print(f"❌ {endpoint} - 404 Not Found (端点不存在)")
            elif response.status_code == 401:
                print(f"🔐 {endpoint} - 需要认证 (正常)")
            else:
                print(f"⚠️ {endpoint} - {response.status_code}")
                
        except Exception as e:
            print(f"❌ {endpoint} - 连接错误: {e}")
    
    # 测试公开端点
    public_endpoint = "/api/v1/books/stats/public?username=admin"
    try:
        url = f"{base_url}{public_endpoint}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            print(f"✅ {public_endpoint} - 正常")
        else:
            print(f"❌ {public_endpoint} - {response.status_code}")
            
    except Exception as e:
        print(f"❌ {public_endpoint} - 连接错误: {e}")
    
    print("\n💡 说明：")
    print("- ✅ 表示端点正常工作")
    print("- 🔐 表示需要认证（这是正常的）") 
    print("- ❌ 表示端点有问题，可能需要重启服务器")
    print("- ⚠️ 表示其他HTTP状态码")

if __name__ == "__main__":
    test_api_endpoints() 