#!/usr/bin/env python3
"""
Kompanion Python 安全检查脚本

用于验证安全配置、扫描潜在漏洞和生成安全报告的自动化工具。
"""

import os
import sys
import json
import subprocess
import re
import hashlib
import secrets
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import argparse
import asyncio

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from app.core.config import settings
    from app.core.security import SECURITY_CONFIG, input_validator
    APP_AVAILABLE = True
except ImportError:
    APP_AVAILABLE = False
    print("警告: 无法导入应用程序模块，某些检查可能无法执行")

class SecurityChecker:
    """安全检查器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "vulnerabilities": [],
            "recommendations": [],
            "summary": {
                "total_checks": 0,
                "passed_checks": 0,
                "failed_checks": 0,
                "warnings": 0
            }
        }
    
    def add_check_result(self, check_name: str, passed: bool, message: str, severity: str = "info"):
        """添加检查结果"""
        self.results["checks"][check_name] = {
            "passed": passed,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        }
        
        self.results["summary"]["total_checks"] += 1
        if passed:
            self.results["summary"]["passed_checks"] += 1
        else:
            self.results["summary"]["failed_checks"] += 1
            if severity == "warning":
                self.results["summary"]["warnings"] += 1
    
    def add_vulnerability(self, vuln_type: str, description: str, severity: str, file_path: str = ""):
        """添加漏洞记录"""
        self.results["vulnerabilities"].append({
            "type": vuln_type,
            "description": description,
            "severity": severity,
            "file_path": file_path,
            "timestamp": datetime.now().isoformat()
        })
    
    def add_recommendation(self, title: str, description: str, priority: str):
        """添加建议"""
        self.results["recommendations"].append({
            "title": title,
            "description": description,
            "priority": priority,
            "timestamp": datetime.now().isoformat()
        })

    def check_environment_variables(self):
        """检查环境变量安全配置"""
        print("🔒 检查环境变量安全配置...")
        
        required_vars = [
            "SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL"
        ]
        
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                self.add_check_result(
                    f"env_var_{var.lower()}",
                    False,
                    f"缺少必需的环境变量: {var}",
                    "error"
                )
                self.add_vulnerability(
                    "configuration",
                    f"未设置必需的环境变量 {var}",
                    "high"
                )
            else:
                # 检查密钥强度
                if "key" in var.lower() or "secret" in var.lower():
                    if len(value) < 32:
                        self.add_check_result(
                            f"env_var_{var.lower()}_strength",
                            False,
                            f"环境变量 {var} 密钥强度不足（少于32字符）",
                            "warning"
                        )
                    elif value == "your-secret-key-here" or "change" in value.lower():
                        self.add_check_result(
                            f"env_var_{var.lower()}_default",
                            False,
                            f"环境变量 {var} 使用默认值，存在安全风险",
                            "error"
                        )
                    else:
                        self.add_check_result(
                            f"env_var_{var.lower()}",
                            True,
                            f"环境变量 {var} 配置正确"
                        )

    def check_file_permissions(self):
        """检查关键文件权限"""
        print("📁 检查文件权限...")
        
        critical_files = [
            ".env",
            "app/core/security.py",
            "app/core/config.py",
            "scripts/install.sh",
            "scripts/update.sh"
        ]
        
        for file_path in critical_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                stat = full_path.stat()
                mode = oct(stat.st_mode)[-3:]
                
                # 检查是否对其他用户可写
                if mode[-1] in ['2', '3', '6', '7']:
                    self.add_check_result(
                        f"file_perm_{file_path.replace('/', '_')}",
                        False,
                        f"文件 {file_path} 对其他用户可写 (权限: {mode})",
                        "warning"
                    )
                    self.add_vulnerability(
                        "file_permissions",
                        f"文件 {file_path} 权限过于宽松",
                        "medium",
                        str(file_path)
                    )
                else:
                    self.add_check_result(
                        f"file_perm_{file_path.replace('/', '_')}",
                        True,
                        f"文件 {file_path} 权限配置正确 (权限: {mode})"
                    )

    def check_code_security(self):
        """检查代码安全问题"""
        print("🔍 扫描代码安全问题...")
        
        patterns = {
            "hardcoded_password": r"password\s*=\s*['\"][^'\"]+['\"]",
            "hardcoded_secret": r"secret\s*=\s*['\"][^'\"]+['\"]",
            "sql_injection": r"execute\s*\(\s*['\"].*%.*['\"]",
            "eval_usage": r"eval\s*\(",
            "pickle_usage": r"pickle\.loads?\s*\(",
        }
        
        python_files = list(self.project_root.rglob("*.py"))
        
        for file_path in python_files:
            if "venv" in str(file_path) or "__pycache__" in str(file_path):
                continue
                
            try:
                content = file_path.read_text(encoding="utf-8")
                
                for pattern_name, pattern in patterns.items():
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        self.add_vulnerability(
                            pattern_name,
                            f"在文件 {file_path.relative_to(self.project_root)} 第 {line_num} 行发现潜在安全问题",
                            "medium",
                            str(file_path.relative_to(self.project_root))
                        )
                        
            except Exception as e:
                print(f"无法读取文件 {file_path}: {e}")

    def check_dependencies(self):
        """检查依赖安全性"""
        print("📦 检查依赖安全性...")
        
        # 检查是否有 safety 工具
        try:
            result = subprocess.run(
                ["safety", "check", "--json"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if result.stdout:
                    try:
                        vulnerabilities = json.loads(result.stdout)
                        if vulnerabilities:
                            for vuln in vulnerabilities:
                                self.add_vulnerability(
                                    "dependency",
                                    f"依赖包 {vuln.get('package', 'unknown')} 存在安全漏洞: {vuln.get('advisory', 'N/A')}",
                                    vuln.get('severity', 'medium'),
                                    "requirements"
                                )
                        else:
                            self.add_check_result(
                                "dependency_security",
                                True,
                                "所有依赖包均无已知安全漏洞"
                            )
                    except json.JSONDecodeError:
                        self.add_check_result(
                            "dependency_security",
                            True,
                            "依赖安全检查完成，未发现已知漏洞"
                        )
            else:
                self.add_check_result(
                    "dependency_security",
                    False,
                    f"依赖安全检查失败: {result.stderr}",
                    "warning"
                )
                
        except subprocess.TimeoutExpired:
            self.add_check_result(
                "dependency_security",
                False,
                "依赖安全检查超时",
                "warning"
            )
        except FileNotFoundError:
            self.add_check_result(
                "dependency_security",
                False,
                "未安装 safety 工具，无法检查依赖安全性",
                "warning"
            )
            self.add_recommendation(
                "安装安全检查工具",
                "运行 'pip install safety' 安装依赖安全检查工具",
                "medium"
            )

    def check_docker_security(self):
        """检查 Docker 配置安全性"""
        print("🐳 检查 Docker 安全配置...")
        
        dockerfile_path = self.project_root / "Dockerfile"
        if dockerfile_path.exists():
            content = dockerfile_path.read_text()
            
            # 检查是否使用 root 用户
            if "USER root" in content or "USER 0" in content:
                self.add_check_result(
                    "docker_user_root",
                    False,
                    "Dockerfile 使用 root 用户运行，存在安全风险",
                    "warning"
                )
                self.add_vulnerability(
                    "docker_security",
                    "容器以 root 用户运行",
                    "medium",
                    "Dockerfile"
                )
            elif "USER " in content:
                self.add_check_result(
                    "docker_user",
                    True,
                    "Dockerfile 使用非 root 用户运行"
                )
            else:
                self.add_check_result(
                    "docker_user",
                    False,
                    "Dockerfile 未明确指定运行用户",
                    "warning"
                )
                
            # 检查是否暴露敏感端口
            if re.search(r"EXPOSE\s+(22|23|3389|5432|3306)", content):
                self.add_check_result(
                    "docker_exposed_ports",
                    False,
                    "Dockerfile 暴露敏感端口",
                    "warning"
                )
            
            # 检查基础镜像安全性
            base_image_match = re.search(r"FROM\s+([^\s]+)", content)
            if base_image_match:
                base_image = base_image_match.group(1)
                if ":latest" in base_image:
                    self.add_check_result(
                        "docker_base_image",
                        False,
                        "使用 latest 标签的基础镜像可能存在安全风险",
                        "warning"
                    )
                else:
                    self.add_check_result(
                        "docker_base_image",
                        True,
                        "使用固定版本的基础镜像"
                    )

    def check_configuration_security(self):
        """检查应用配置安全性"""
        print("⚙️ 检查应用配置安全性...")
        
        if not APP_AVAILABLE:
            self.add_check_result(
                "app_config",
                False,
                "无法访问应用配置，跳过配置安全检查",
                "warning"
            )
            return
        
        # 检查调试模式
        if getattr(settings, 'DEBUG', False):
            self.add_check_result(
                "debug_mode",
                False,
                "应用程序运行在调试模式，生产环境中应禁用",
                "error"
            )
            self.add_vulnerability(
                "configuration",
                "调试模式启用可能泄露敏感信息",
                "high"
            )
        else:
            self.add_check_result(
                "debug_mode",
                True,
                "调试模式已正确禁用"
            )
        
        # 检查密钥配置
        secret_key = getattr(settings, 'SECRET_KEY', '')
        if len(secret_key) < 32:
            self.add_check_result(
                "secret_key_length",
                False,
                "SECRET_KEY 长度不足，建议至少32字符",
                "error"
            )
        
        # 检查 CORS 配置
        cors_origins = getattr(settings, 'CORS_ORIGINS', [])
        if "*" in cors_origins:
            self.add_check_result(
                "cors_configuration",
                False,
                "CORS 配置允许所有源，可能存在安全风险",
                "warning"
            )
        
        # 检查速率限制配置
        rate_limit = SECURITY_CONFIG.get("RATE_LIMIT_REQUESTS", 0)
        if rate_limit == 0:
            self.add_check_result(
                "rate_limiting",
                False,
                "未配置速率限制",
                "warning"
            )
        elif rate_limit > 100:
            self.add_check_result(
                "rate_limiting",
                False,
                f"速率限制过高 ({rate_limit}/分钟)，建议降低",
                "warning"
            )
        else:
            self.add_check_result(
                "rate_limiting",
                True,
                f"速率限制配置合理 ({rate_limit}/分钟)"
            )

    def check_ssl_configuration(self):
        """检查 SSL/TLS 配置"""
        print("🔐 检查 SSL/TLS 配置...")
        
        # 检查 nginx 配置
        nginx_config = self.project_root / "docker" / "nginx.conf"
        if nginx_config.exists():
            content = nginx_config.read_text()
            
            if "ssl_certificate" in content:
                self.add_check_result(
                    "ssl_enabled",
                    True,
                    "SSL/TLS 配置已启用"
                )
                
                # 检查 SSL 协议版本
                if "TLSv1.3" in content:
                    self.add_check_result(
                        "ssl_protocol",
                        True,
                        "支持 TLS 1.3 协议"
                    )
                elif "TLSv1.2" in content:
                    self.add_check_result(
                        "ssl_protocol",
                        True,
                        "支持 TLS 1.2 协议"
                    )
                else:
                    self.add_check_result(
                        "ssl_protocol",
                        False,
                        "SSL 协议版本配置可能不安全",
                        "warning"
                    )
                
                # 检查 HSTS
                if "Strict-Transport-Security" in content:
                    self.add_check_result(
                        "hsts_enabled",
                        True,
                        "HSTS 已启用"
                    )
                else:
                    self.add_check_result(
                        "hsts_enabled",
                        False,
                        "建议启用 HSTS",
                        "warning"
                    )
            else:
                self.add_check_result(
                    "ssl_enabled",
                    False,
                    "未配置 SSL/TLS，生产环境必须启用",
                    "error"
                )

    def generate_recommendations(self):
        """生成安全建议"""
        print("💡 生成安全建议...")
        
        # 基于检查结果生成建议
        failed_checks = [name for name, result in self.results["checks"].items() if not result["passed"]]
        
        if any("env_var" in check for check in failed_checks):
            self.add_recommendation(
                "环境变量安全",
                "确保所有敏感配置通过环境变量设置，并使用强密码",
                "high"
            )
        
        if any("ssl" in check for check in failed_checks):
            self.add_recommendation(
                "SSL/TLS 配置",
                "在生产环境中启用 HTTPS，使用 TLS 1.2 或更高版本",
                "high"
            )
        
        if any("docker" in check for check in failed_checks):
            self.add_recommendation(
                "Docker 安全",
                "使用非 root 用户运行容器，定期更新基础镜像",
                "medium"
            )
        
        if self.results["vulnerabilities"]:
            self.add_recommendation(
                "漏洞修复",
                f"发现 {len(self.results['vulnerabilities'])} 个潜在安全问题，建议立即修复",
                "high"
            )

    def run_all_checks(self):
        """运行所有安全检查"""
        print("🚀 开始安全检查...")
        print("=" * 50)
        
        self.check_environment_variables()
        self.check_file_permissions()
        self.check_code_security()
        self.check_dependencies()
        self.check_docker_security()
        self.check_configuration_security()
        self.check_ssl_configuration()
        self.generate_recommendations()
        
        print("=" * 50)
        print("✅ 安全检查完成")

    def print_summary(self):
        """打印检查摘要"""
        summary = self.results["summary"]
        print(f"\n📊 检查摘要:")
        print(f"  总检查项: {summary['total_checks']}")
        print(f"  通过: {summary['passed_checks']}")
        print(f"  失败: {summary['failed_checks']}")
        print(f"  警告: {summary['warnings']}")
        
        if self.results["vulnerabilities"]:
            print(f"\n⚠️ 发现 {len(self.results['vulnerabilities'])} 个安全问题:")
            for vuln in self.results["vulnerabilities"]:
                print(f"  - [{vuln['severity'].upper()}] {vuln['description']}")
        
        if self.results["recommendations"]:
            print(f"\n💡 安全建议 ({len(self.results['recommendations'])} 项):")
            for rec in self.results["recommendations"]:
                print(f"  - [{rec['priority'].upper()}] {rec['title']}: {rec['description']}")

    def save_report(self, output_file: str):
        """保存检查报告"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 报告已保存到: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Kompanion Python 安全检查工具")
    parser.add_argument(
        "--output", "-o",
        default="security_report.json",
        help="输出报告文件路径 (默认: security_report.json)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细输出"
    )
    
    args = parser.parse_args()
    
    checker = SecurityChecker()
    checker.run_all_checks()
    checker.print_summary()
    checker.save_report(args.output)
    
    # 根据检查结果设置退出码
    if checker.results["summary"]["failed_checks"] > 0:
        high_severity_vulns = [
            v for v in checker.results["vulnerabilities"] 
            if v["severity"] == "high"
        ]
        if high_severity_vulns:
            print("\n❌ 发现高危安全问题，建议立即修复！")
            sys.exit(2)
        else:
            print("\n⚠️ 发现一些安全问题，建议及时修复。")
            sys.exit(1)
    else:
        print("\n✅ 所有安全检查通过！")
        sys.exit(0)

if __name__ == "__main__":
    main() 