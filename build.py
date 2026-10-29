#!/usr/bin/env python3
"""
跨平台自动化构建脚本
用法: python build.py [--tool pyinstaller|nuitka] [--platform auto|macos|linux|windows] [--arch x64|arm64]
"""
import argparse
import os
import platform
import subprocess
import sys
import shutil
import sysconfig
import hashlib
from pathlib import Path
from typing import List, Optional

class CrossPlatformBuilder:
    def __init__(self):
        self.project_root = Path(__file__).parent.absolute()
        self.dist_dir = self.project_root / "dist"
        self.build_dir = self.project_root / "build"
        
        # 平台信息
        self.system = platform.system().lower()
        self.machine = platform.machine().lower()
        self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        
        # 架构标准化
        self.arch_map = {
            "x86_64": "x64", "amd64": "x64",
            "arm64": "arm64", "aarch64": "arm64",
        }
        self.arch = self.arch_map.get(self.machine, self.machine)
        
    def detect_platform(self) -> dict:
        """检测当前平台信息"""
        return {
            "system": self.system,
            "arch": self.arch,
            "python": self.python_version,
            "is_macos": self.system == "darwin",
            "is_linux": self.system == "linux",
            "is_windows": self.system == "windows",
        }
    
    def clean(self):
        """清理构建产物"""
        for path in [self.dist_dir, self.build_dir]:
            if path.exists():
                shutil.rmtree(path)
                print(f"🧹 清理: {path}")
        
        # 清理 .spec 文件
        for spec in self.project_root.glob("*.spec"):
            spec.unlink()
    
    def ensure_dependencies(self):
        """确保构建依赖已安装"""
        print("📦 检查构建依赖...")
        # pyinstaller 应该已经在 uv 环境中，通过 uv sync 安装
        subprocess.run([
            "uv", "sync", "--extra", "build"
        ], cwd=self.project_root, check=True)
    
    def get_pyinstaller_args(self, target_platform: str = "auto") -> List[str]:
        """生成 PyInstaller 参数"""
        # Windows 使用 onedir 模式避免 python312.dll 加载失败
        is_windows = target_platform == "windows" or (target_platform == "auto" and self.system == "windows")
        
        args = [
            "--name", "mem-analyzer-mcp",
            "--onedir" if is_windows else "--onefile",
            "--clean",
            "--noconfirm",
            "--optimize", "2",
        ]
        
        # 非 Windows 才用 strip
        if not is_windows:
            args.append("--strip")
        
        # 平台特定参数
        if target_platform == "macos" or (target_platform == "auto" and self.system == "darwin"):
            args.extend([
                "--codesign-identity", "",  # 生产环境配置证书
                "--osx-bundle-identifier", "com.wangdefu.mem-analyzer-mcp",
            ])
        elif target_platform == "windows" or (target_platform == "auto" and self.system == "windows"):
            version_file = self.project_root / "version_info.txt"
            if version_file.exists():
                args.extend(["--version-file", str(version_file)])
            # Windows 专用修复：解决 python312.dll 加载失败
            args.extend([
                "--noupx",                    # 禁用 UPX 压缩
                "--disable-windowed-traceback",  # 禁用窗口模式回溯
            ])
            # 显式添加 Python DLL - 尝试多个常见路径
            python_dll_name = f"python{sys.version_info.major}{sys.version_info.minor}.dll"
            python_dll_paths = [
                Path(sys.base_prefix) / python_dll_name,
                Path(sys.base_prefix) / "DLLs" / python_dll_name,
                Path(sysconfig.get_config_var("LIBDIR") or "") / python_dll_name,
                Path(sysconfig.get_config_var("INSTSONAME") or ""),
            ]
            for dll_path in python_dll_paths:
                if dll_path and dll_path.exists():
                    args.extend(["--add-binary", f"{dll_path};."])
                    break
        
        # 通用隐式导入 - 仅 mem-analyzer-mcp 服务需要的
        hidden_imports = [
            "fastmcp", "fastmcp.server", "fastmcp.client", "fastmcp.tools",
            "fastmcp.resources", "fastmcp.prompts",
            "starlette", "starlette.applications", "starlette.routing", "starlette.middleware",
            "uvicorn", "uvicorn.main", "uvicorn.config",
            "pydantic", "pydantic.v1", "pydantic_core",
            "rich", "rich.console", "rich.text", "rich.logging",
            "typer", "click", "shellingham",
            "typing_extensions", "annotated_types",
        ]
        for imp in hidden_imports:
            args.extend(["--hidden-import", imp])
        
        # 收集完整包
        for pkg in ["fastmcp", "starlette", "uvicorn"]:
            args.extend(["--collect-all", pkg])
        
        # 排除模块 - 减小体积
        excludes = [
            "tkinter", "matplotlib", "numpy", "pandas", "scipy", 
            "IPython", "jupyter", "pytest", "setuptools", "pip", 
            "wheel", "virtualenv", "networkx", "bs4", "beautifulsoup4", 
            "sqlite3", "email_validator", "jsonschema", "referencing", 
            "rpds_py",
        ]
        for exc in excludes:
            args.extend(["--exclude-module", exc])
        
        args.append(str(self.project_root / "main.py"))
        return args
    
    def build_pyinstaller(self, target_platform: str = "auto") -> Path:
        """使用 PyInstaller 构建"""
        print(f"🔨 PyInstaller 构建 ({target_platform})...")
        self.ensure_dependencies()
        
        # 判断是否为 Windows onedir 模式
        is_windows = target_platform == "windows" or (target_platform == "auto" and self.system == "windows")
        
        # 使用 uv run pyinstaller 确保使用正确的 Python 环境
        args = ["uv", "run", "pyinstaller"] + self.get_pyinstaller_args(target_platform)
        
        # 设置环境变量优化
        env = os.environ.copy()
        env["PYTHONOPTIMIZE"] = "2"
        env["PYINSTALLER_OPTIMIZE"] = "2"
        
        result = subprocess.run(args, cwd=self.project_root, env=env, check=True)
        
        # 确定输出路径
        if is_windows:
            # onedir 模式：返回目录路径
            output = self.dist_dir / "mem-analyzer-mcp"
            if not output.exists():
                # 尝试查找
                for f in self.dist_dir.glob("mem-analyzer-mcp*"):
                    if f.is_dir():
                        output = f
                        break
        else:
            # onefile 模式：返回可执行文件路径
            if self.system == "windows":
                exe_name = "mem-analyzer-mcp.exe"
            else:
                exe_name = "mem-analyzer-mcp"
            
            output = self.dist_dir / exe_name
            if not output.exists():
                # 尝试查找
                for f in self.dist_dir.rglob(exe_name):
                    output = f
                    break
        
        print(f"✅ PyInstaller 构建完成: {output}")
        return output
    
    def verify_binary(self, binary_path: Path) -> bool:
        """验证二进制文件基本功能"""
        print(f"🔍 验证二进制: {binary_path}")
        
        # 判断是目录还是文件
        is_dir = binary_path.is_dir()
        if is_dir:
            # onedir 模式：可执行文件在目录内
            if self.system == "windows":
                exe_name = "mem-analyzer-mcp.exe"
            else:
                exe_name = "mem-analyzer-mcp"
            actual_binary = binary_path / exe_name
        else:
            actual_binary = binary_path
        
        if not actual_binary.exists():
            print(f"❌ 可执行文件不存在: {actual_binary}")
            return False
        
        try:
            # 测试启动（超时 15 秒）
            result = subprocess.run(
                [str(actual_binary), "--help"],
                capture_output=True,
                text=True,
                timeout=20
            )
            
            if result.returncode in [0, 1, 2]:  # --help 可能返回 1 或 2
                print(f"✅ 启动测试通过 (exit code: {result.returncode})")
                if "mcp" in result.stdout.lower() or "fastmcp" in result.stdout.lower() or "usage" in result.stdout.lower():
                    print("✅ MCP 标识检测通过")
                return True
            else:
                print(f"❌ 启动失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ 启动超时")
            return False
        except Exception as e:
            print(f"❌ 验证异常: {e}")
            return False
    
    def package_release(self, binary_path: Path, tool: str) -> Path:
        """打包发布产物"""
        platform_info = self.detect_platform()
        version = "0.1.0"
        
        # 判断是否为 onedir 模式（Windows）
        is_dir = binary_path.is_dir()
        
        # 发布包命名: mem-analyzer-mcp-v0.1.0-macos-arm64-pyinstaller.tar.gz
        pkg_name = f"mem-analyzer-mcp-v{version}-{platform_info['system']}-{platform_info['arch']}-{tool}"
        pkg_dir = self.dist_dir / pkg_name
        pkg_dir.mkdir(exist_ok=True)
        
        if is_dir:
            # onedir 模式：复制整个目录
            dest_dir = pkg_dir / binary_path.name
            shutil.copytree(binary_path, dest_dir)
            # 计算主可执行文件的校验和
            if self.system == "windows":
                exe_name = "mem-analyzer-mcp.exe"
            else:
                exe_name = "mem-analyzer-mcp"
            main_exe = binary_path / exe_name
            sha256 = hashlib.sha256(main_exe.read_bytes()).hexdigest() if main_exe.exists() else ""
            archive_name = f"{binary_path.name}.zip" if self.system == "windows" else f"{binary_path.name}.tar.gz"
        else:
            # onefile 模式：复制单个文件
            exe_name = binary_path.name
            shutil.copy2(binary_path, pkg_dir / exe_name)
            sha256 = hashlib.sha256(binary_path.read_bytes()).hexdigest()
            archive_name = f"{exe_name}.zip" if self.system == "windows" else f"{exe_name}.tar.gz"
        
        # 生成校验和
        (pkg_dir / "SHA256SUMS").write_text(f"{sha256}  {exe_name}\n")
        
        # 生成元数据
        import json
        metadata = {
            "name": "mem-analyzer-mcp",
            "version": version,
            "platform": platform_info,
            "tool": tool,
            "python": platform_info["python"],
            "sha256": sha256,
            "build_date": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], 
                                       capture_output=True, text=True).stdout.strip(),
        }
        (pkg_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
        
        # 打包压缩
        if self.system == "windows":
            archive = shutil.make_archive(str(self.dist_dir / pkg_name), "zip", pkg_dir)
        else:
            archive = shutil.make_archive(str(self.dist_dir / pkg_name), "gztar", pkg_dir)
        
        print(f"📦 发布包已生成: {archive}")
        return Path(archive)

def main():
    parser = argparse.ArgumentParser(description="跨平台 MCP Server 构建工具")
    parser.add_argument("--tool", choices=["pyinstaller", "nuitka", "both"], default="pyinstaller")
    parser.add_argument("--platform", choices=["auto", "macos", "linux", "windows"], default="auto")
    parser.add_argument("--arch", choices=["x64", "arm64"], help="目标架构（交叉编译时指定）")
    parser.add_argument("--clean", action="store_true", help="构建前清理")
    parser.add_argument("--verify", action="store_true", default=True, help="构建后验证")
    parser.add_argument("--package", action="store_true", help="生成发布包")
    
    args = parser.parse_args()
    
    builder = CrossPlatformBuilder()
    platform_info = builder.detect_platform()
    
    print(f"🖥️  当前平台: {platform_info['system']}-{platform_info['arch']} (Python {platform_info['python']})")
    print(f"🎯 目标平台: {args.platform}-{args.arch or platform_info['arch']}")
    print(f"🔧 构建工具: {args.tool}")
    
    if args.clean:
        builder.clean()
    
    binaries = []
    
    try:
        if args.tool in ["pyinstaller", "both"]:
            binary = builder.build_pyinstaller(args.platform)
            binaries.append(("pyinstaller", binary))
            if args.verify:
                builder.verify_binary(binary)
            if args.package:
                builder.package_release(binary, "pyinstaller")
        
        print("\n🎉 所有构建任务完成！")
        for tool, binary in binaries:
            size_mb = binary.stat().st_size / (1024 * 1024)
            print(f"  📁 {tool}: {binary} ({size_mb:.1f} MB)")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断构建")
        sys.exit(130)

if __name__ == "__main__":
    main()