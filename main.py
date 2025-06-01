#!/usr/bin/env python3
"""
Kompanion 阅读统计分析系统

KOReader 同步和数据分析平台
支持多种运行模式：
- FastAPI 后端服务
- Streamlit 前端应用
"""

import argparse
import uvicorn
import sys
import os
import signal
import subprocess
import time
import platform
from pathlib import Path
import socket

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_fastapi():
    """启动 FastAPI 后端服务"""
    print("🚀 启动 Kompanion FastAPI 服务...")
    print("📍 API 地址: http://localhost:8080")
    print("📋 API 文档: http://localhost:8080/docs")
    print("-" * 50)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )

def run_streamlit():
    """启动 Streamlit 前端应用"""
    print("🚀 启动 Kompanion Streamlit 应用...")
    print("📍 访问地址: http://localhost:8501")
    print("⚙️  后端服务地址: http://localhost:8080")
    print("-" * 50)
    
    try:
        # 确保在正确的目录中运行
        os.chdir(project_root)
        
        # 构建 streamlit 命令
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            "app/frontend/main.py",
            "--server.port", "8501",
            "--server.address", "0.0.0.0",
            "--server.headless", "true",
            "--server.enableCORS", "false",
            "--server.enableXsrfProtection", "false"
        ]
        
        # 启动 Streamlit
        subprocess.run(cmd, check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Streamlit 启动失败: {e}")
    except KeyboardInterrupt:
        print("\n👋 Streamlit 应用已停止")
    except Exception as e:
        print(f"❌ 启动过程中出错: {e}")

def _run_backend_process():
    """后端进程函数（模块级别，可序列化）"""
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=False,  # 禁用热重载
        log_level="info"
    )

def _run_frontend_process():
    """前端进程函数（模块级别，可序列化）"""
    try:
        os.chdir(project_root)
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            "app/frontend/main.py",
            "--server.port", "8501",
            "--server.address", "0.0.0.0",
            "--server.headless", "true",
            "--server.enableCORS", "false",
            "--server.enableXsrfProtection", "false"
        ]
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"前端启动失败: {e}")

def run_both():
    """同时启动后端和前端服务"""
    print("🚀 启动 Kompanion 完整系统...")
    print("📍 后端 API: http://localhost:8080")
    print("📍 前端界面: http://localhost:8501")
    print("-" * 50)
    
    # 检测操作系统
    is_windows = platform.system() == "Windows"
    
    if is_windows:
        # Windows 系统提供简化指引
        print("🖥️  检测到 Windows 系统")
        print("💡 为避免复杂的多进程问题，建议使用以下方式：")
        print()
        print("🔸 方案 1: 分步启动（推荐）")
        print("   1. 打开第一个终端，运行: uv run python main.py backend")
        print("   2. 打开第二个终端，运行: uv run python main.py frontend")
        print()
        print("🔸 方案 2: 使用批处理文件")
        create_batch_files()
        print("   已创建 start_backend.bat 和 start_frontend.bat")
        print("   请先运行 start_backend.bat，再运行 start_frontend.bat")
        print()
        print("🔸 方案 3: 自动尝试启动")
        auto_start = input("是否自动尝试启动？(y/N): ").lower().strip()
        if auto_start == 'y':
            run_both_windows()
    else:
        # Unix 系统使用多进程方式
        run_both_unix()

def create_batch_files():
    """创建 Windows 批处理文件"""
    backend_bat = """@echo off
title Kompanion Backend
echo 🚀 启动 Kompanion 后端服务...
uv run python main.py backend
pause
"""
    
    frontend_bat = """@echo off
title Kompanion Frontend  
echo 🚀 启动 Kompanion 前端服务...
echo 💡 请确保后端服务已启动
uv run python main.py frontend
pause
"""
    
    try:
        with open("start_backend.bat", "w", encoding="utf-8") as f:
            f.write(backend_bat)
        with open("start_frontend.bat", "w", encoding="utf-8") as f:
            f.write(frontend_bat)
        print("✅ 批处理文件已创建")
    except Exception as e:
        print(f"❌ 创建批处理文件失败: {e}")

def run_both_windows():
    """Windows 兼容的启动方式"""
    import socket
    
    print("📍 尝试自动启动...")
    
    # 检查端口是否被占用
    def check_port(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('localhost', port))
                return True
            except OSError:
                return False
    
    # 检查端口状态
    if not check_port(8080):
        print("❌ 端口 8080 被占用")
        print("💡 请运行以下命令清理进程：")
        print("   taskkill /F /IM python.exe")
        print("   然后重新尝试启动")
        return
    
    if not check_port(8501):
        print("❌ 端口 8501 被占用")
        print("💡 请运行以下命令清理进程：")
        print("   taskkill /F /IM python.exe")
        print("   然后重新尝试启动")
        return
    
    try:
        print("🚀 启动后端服务...")
        
        # 使用更简单的启动方式
        backend_script = f"""
import sys
sys.path.insert(0, r"{project_root}")
import uvicorn
uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=False)
"""
        
        # 写入临时脚本
        script_path = project_root / "temp_backend.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(backend_script)
        
        # 启动后端进程
        backend_process = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=project_root
        )
        
        # 等待后端启动
        print("⏳ 等待后端服务启动...")
        time.sleep(8)
        
        # 检查后端是否启动成功
        if backend_process.poll() is not None:
            print("❌ 后端服务启动失败")
            return
        
        # 测试后端连接
        try:
            import requests
            response = requests.get("http://localhost:8080/health", timeout=10)
            if response.status_code == 200:
                print("✅ 后端服务启动成功")
            else:
                print("❌ 后端服务响应异常")
                return
        except Exception as e:
            print(f"❌ 无法连接到后端服务: {e}")
            return
        
        print("🚀 启动前端服务...")
        print("🎉 系统启动完成！")
        print("🔗 请访问:")
        print("   - 后端 API: http://localhost:8080") 
        print("   - 前端界面: http://localhost:8501")
        print("   - API 文档: http://localhost:8080/docs")
        print("\n按 Ctrl+C 停止服务")
        
        # 启动前端
        try:
            _run_frontend_process()
        except KeyboardInterrupt:
            print("\n🛑 收到停止信号...")
        finally:
            # 清理
            if backend_process.poll() is None:
                print("🛑 正在停止后端服务...")
                backend_process.terminate()
                backend_process.wait()
            
            # 删除临时文件
            try:
                script_path.unlink()
            except:
                pass
            
            print("👋 系统已停止")
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        print("💡 建议使用分步启动方式")

def run_both_unix():
    """Unix 系统的多进程启动方式"""
    import multiprocessing as mp
    import atexit
    
    # 设置多进程启动方法
    mp.set_start_method('fork', force=True)
    
    # 存储进程引用
    processes = []
    
    def cleanup_processes():
        """清理所有子进程"""
        print("\n🛑 正在停止服务...")
        for process in processes:
            if process.is_alive():
                try:
                    process.terminate()
                    process.join(timeout=5)
                    if process.is_alive():
                        process.kill()
                        process.join()
                except Exception as e:
                    print(f"清理进程时出错: {e}")
        print("👋 系统已停止")
    
    # 注册清理函数
    atexit.register(cleanup_processes)
    
    try:
        # 创建后端进程
        backend_process = mp.Process(target=_run_backend_process, name="FastAPI-Backend")
        backend_process.start()
        processes.append(backend_process)
        
        # 等待后端启动
        print("⏳ 等待后端服务启动...")
        time.sleep(5)
        
        # 检查后端是否正常启动
        if not backend_process.is_alive():
            print("❌ 后端服务启动失败")
            return
        
        print("✅ 后端服务启动成功")
        
        # 创建前端进程
        frontend_process = mp.Process(target=_run_frontend_process, name="Streamlit-Frontend")
        frontend_process.start()
        processes.append(frontend_process)
        
        print("✅ 前端服务启动成功")
        print("🎉 系统启动完成！")
        print("🔗 请访问:")
        print("   - 后端 API: http://localhost:8080")
        print("   - 前端界面: http://localhost:8501")
        print("   - API 文档: http://localhost:8080/docs")
        print("\n按 Ctrl+C 停止服务")
        
        # 等待进程结束或用户中断
        try:
            while True:
                # 检查进程状态
                if not backend_process.is_alive():
                    print("❌ 后端服务意外停止")
                    break
                if not frontend_process.is_alive():
                    print("❌ 前端服务意外停止")
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 收到停止信号...")
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
    finally:
        cleanup_processes()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Kompanion 阅读统计分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式:
  backend    启动 FastAPI 后端服务 (默认端口: 8080)
  frontend   启动 Streamlit 前端应用 (默认端口: 8501)
  both       同时启动后端和前端服务
  
示例:
  python main.py backend                # 仅启动后端
  python main.py frontend               # 仅启动前端
  python main.py both                   # 启动完整系统
  python main.py                        # 默认启动后端
        """
    )
    
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["backend", "frontend", "both"],
        default="backend",
        help="运行模式 (默认: backend)"
    )
    
    args = parser.parse_args()
    
    try:
        if args.mode == "backend":
            run_fastapi()
        elif args.mode == "frontend":
            run_streamlit()
        elif args.mode == "both":
            run_both()
        else:
            # 默认启动后端
            run_fastapi()
    except KeyboardInterrupt:
        print("\n👋 程序已停止")
    except Exception as e:
        print(f"❌ 程序执行出错: {e}")

if __name__ == "__main__":
    main() 