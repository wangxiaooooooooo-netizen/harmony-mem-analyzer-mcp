# MCP Server - HarmonyOS 内存泄漏分析服务

> **项目**：mem-analyzer-mcp MCP Server  
> **版本**：0.1.0  
> **最后更新**：2026-10-29  
> **Python 要求**：>= 3.12  
> **打包工具**：PyInstaller 6.22.3  
> **目标平台**：macOS x86_64 (Darwin)  
> **二进制大小**：~26.9 MB

---

## 📦 项目概览

| 项目信息 | 详情 |
|----------|------|
| **项目名称** | mcp-server (mem-analyzer-mcp) |
| **核心依赖** | fastmcp>=4.1.3 |
| **服务名称** | mem-analyzer-mcp |
| **注册工具** | rawheap_translate, mem_analyzer_jsleak, memleak_files_list, memleak_pair_validate |
| **分组标签** | mem-analyzer-mcp |
| **外部依赖** | mem-analyzer-mcp, rawheap_translator (通过环境变量配置路径) |

---

## 🏗️ 构建架构

```
项目结构
├── main.py                    # 入口文件 (mem-analyzer-mcp MCP 服务)
├── pyproject.toml            # 依赖配置 + 打包配置
├── build.py                  # 跨平台自动化构建脚本
├── package_release.py        # 发布包生成脚本
├── PACKAGING_GUIDE.md        # 打包指南 (跨会话记忆文档)
└── README.md                 # 本文档
```

---

## ⚙️ 核心配置文件

### 1. pyproject.toml (依赖与打包配置)
```toml
[project]
name = "mcp-server"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=4.1.3",           # 仅核心依赖
]

[project.optional-dependencies]
build = [
    "pyinstaller>=6.5",         # 打包工具
    "typer>=0.9",               # fastmcp 依赖的 CLI 库
]
dev = [
    "pytest>=7.4",
    "pytest-asyncio>=0.21",
    "ruff>=0.1",
    "mypy>=1.5",
]
```

> **关键点**：相比旧版 Dash_Doc 服务，移除了 `networkx`、`beautifulsoup4` 等不再需要的依赖。

### 2. main.py 关键点
- **服务名称**：`FastMCP("mem-analyzer-mcp")`
- **依赖导入**：fastmcp, os, subprocess, re, typing
- **环境变量**：
  - `MEM_ANALYZER_PATH` (默认: `mem-analyzer-mcp`)
  - `RAWHEAP_TRANSLATOR_PATH` (默认: `rawheap_translator`)
- **工具函数**：
  - `rawheap_translate` - .rawheap → .heapsnapshot 转换
  - `mem_analyzer_jsleak` - jsleaklist + heapsnapshot 关联分析
  - `memleak_files_list` - 目录扫描、时间戳配对、文件分类
  - `memleak_pair_validate` - 文件存在性、后缀、大小、时间戳前置校验

### 3. build.py 关键隐式导入
```python
hidden_imports = [
    # fastmcp 全家桶
    "fastmcp", "fastmcp.server", "fastmcp.client", "fastmcp.tools",
    "fastmcp.resources", "fastmcp.prompts",
    # starlette & uvicorn
    "starlette", "starlette.applications", "starlette.routing", "starlette.middleware",
    "uvicorn", "uvicorn.main", "uvicorn.config",
    # pydantic
    "pydantic", "pydantic.v1", "pydantic_core",
    # rich & CLI
    "rich", "rich.console", "rich.text", "rich.logging",
    "typer", "click", "shellingham",
    # pydantic 依赖 (必须包含，否则运行时报 ModuleNotFoundError)
    "typing_extensions", "annotated_types",
]
```

### 4. 排除模块 (excludes) - 减小体积
```python
excludes = [
    "tkinter", "matplotlib", "numpy", "pandas", "scipy", 
    "IPython", "jupyter", "pytest", "setuptools", "pip", 
    "wheel", "virtualenv", 
    "networkx", "bs4", "beautifulsoup4",   # 旧版依赖，已移除
    "sqlite3", "email_validator", "jsonschema", "referencing", 
    "rpds_py",
]
```

---

## 📋 打包前配置比对清单 (必做)

> **目的**：确保 main.py 的代码变更与打包配置文件同步，避免遗漏依赖导致运行时错误

### 快速验证命令
```bash
# 1. 检查 main.py 导入的第三方依赖
grep -E "^(import|from) " main.py | grep -vE "^(import os|from typing|from pathlib)" | sed 's/import //;s/from //;s/ .*//' | sort -u

# 2. 检查 pyproject.toml dependencies
grep -A 10 "dependencies = " pyproject.toml | grep '"' | sed 's/.*"\([^"]*\)".*/\1/' | sed 's/>=.*//' | sort -u

# 3. 检查 build.py hidden_imports
grep -A 30 "hidden_imports = " build.py | grep '"' | sed 's/.*"\([^"]*\)".*/\1/' | sort -u

# 4. 检查版本一致性
grep 'version = ' pyproject.toml build.py package_release.py
```

### 必须同步的配置项对照表
| 配置项 | main.py | pyproject.toml | build.py | package_release.py |
|--------|---------|----------------|----------|-------------------|
| 服务名称 | ✅ | N/A | N/A | ✅ metadata |
| 版本号 | N/A | ✅ | ✅ | ✅ |
| fastmcp | ✅ | ✅ | ✅ | N/A |
| typer/click/shellingham | 间接 | 通过 fastmcp | ✅ | N/A |
| pydantic 依赖 | 间接 | 通过 fastmcp | ✅ | N/A |
| typing_extensions | 间接 | 无 | ✅ | N/A |
| Starlette/Uvicorn | 间接 | 通过 fastmcp | ✅ | N/A |
| Rich/Click/Typer | 间接 | 通过 fastmcp | ✅ | N/A |
| networkx/bs4/sqlite3 | ❌ 已移除 | ❌ | ❌ | N/A |

---

## 📋 打包构建

### 一键构建命令
```bash
cd /Users/wangdefu/Documents/projects/VibeCodingAI/baseline/mcp/mcp_server

# 清理旧产物 + 构建 + 验证 + 打包发布
rm -rf dist build *.spec && python3 build.py --tool pyinstaller --verify --package
```

### 构建步骤拆解
| 步骤 | 命令 | 说明 |
|------|------|------|
| 1. 清理 | `rm -rf dist build *.spec` | 删除旧产物 |
| 2. 同步依赖 | `uv sync --extra build` | 安装 pyinstaller 等构建依赖 |
| 3. 执行打包 | `uv run pyinstaller ...` | 使用 uv 环境确保依赖一致 |
| 4. 验证 | `./dist/mcp-server --help` | 启动测试 (exit code 0 为成功) |
| 5. 打包发布 | `python3 package_release.py` | 生成 .tar.gz |

### 预期输出示例
```
╭──────────────────────────────────────────────────────────────────────────────╮
│                                FastMCP 4.1.3                                 │
│                  🖥  Server:      mem-analyzer-mcp, 4.1.3                         │
╰──────────────────────────────────────────────────────────────────────────────╯
[10/29/26 11:10:41] INFO     Starting MCP server 'mem-analyzer-mcp' with transport 'stdio'
```

---

## 🔧 关键技术点 (避坑指南)

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 必须使用 `uv run pyinstaller` | 系统 Python 3.13 vs uv 环境 3.12 | build.py 中使用 `["uv", "run", "pyinstaller"]` |
| `ModuleNotFoundError: typing_extensions` | pydantic 依赖漏包 | 加入 `hidden_imports` |
| `ModuleNotFoundError: annotated_types` | pydantic 依赖漏包 | 加入 `hidden_imports` |
| 二进制启动极慢 (>5s) | PyInstaller 单文件解压开销 | 考虑 Nuitka 或 `--onedir` 模式 |
| 体积过大 (>50MB) | 未排除大依赖 | 检查 `excludes` 列表 |
| 签名/公证失败 (macOS) | 无开发者证书 | 去掉 `--codesign-identity` 或配置证书 |

---

## 🛠️ 注册的 MCP 工具

| 工具名 | 标签 | 功能描述 | 参数 |
|--------|------|----------|------|
| `rawheap_translate` | mem-analyzer-mcp | .rawheap → .heapsnapshot 转换 | input_rawheap_path, output_path |
| `mem_analyzer_jsleak` | mem-analyzer-mcp | jsleaklist + heapsnapshot 关联分析 (HTML/JSON) | jsleaklist_path, heapsnapshot_path, top_n |
| `memleak_files_list` | mem-analyzer-mcp | 目录扫描、时间戳配对、文件分类 | directory |
| `memleak_pair_validate` | mem-analyzer-mcp | 文件存在性、后缀、大小、时间戳前置校验 | jsleaklist_path, heap_file_path |

### 使用示例
```json
// 转换 .rawheap 文件
{
  "input_rawheap_path": "/path/to/memory.rawheap",
  "output_path": "/path/to/output.heapsnapshot"
}

// 内存泄漏分析
{
  "jsleaklist_path": "/path/to/leak.jsleaklist",
  "heapsnapshot_path": "/path/to/heap.heapsnapshot",
  "top_n": 20
}

// 扫描目录查找内存分析文件
{
  "directory": "/path/to/memory/logs"
}

// 验证文件配对
{
  "jsleaklist_path": "/path/to/leak.jsleaklist",
  "heap_file_path": "/path/to/heap.heapsnapshot"
}
```

### 环境变量配置 (可选)
```bash
# 指定外部工具路径 (若不在 PATH 中)
export MEM_ANALYZER_PATH="/opt/harmony/sdk/mem-analyzer-mcp"
export RAWHEAP_TRANSLATOR_PATH="/opt/harmony/sdk/rawheap_translator"
./mcp-server
```

---

## 🌍 跨平台构建 (扩展)

当前仅支持 macOS x86_64 原生构建。其他平台需对应环境：

```bash
# Linux x64 (需在 Linux 或 Docker)
python3 build.py --tool pyinstaller --platform linux --arch x64

# Linux ARM64
python3 build.py --tool pyinstaller --platform linux --arch arm64

# Windows x64 (需在 Windows)
python3 build.py --tool pyinstaller --platform windows --arch x64

# 高性能版本 (Nuitka，启动快 10x，但构建慢)
python3 build.py --tool nuitka --verify --package
```

---

## 📥 MCP 客户端接入配置

### 快速配置 (以 Claude Desktop 为例)

**配置文件路径**：`~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mem-analyzer": {
      "command": "/opt/mcp-servers/mem-analyzer/mcp-server",
      "args": [],
      "env": {
        "MEM_ANALYZER_PATH": "/opt/harmony/sdk/mem-analyzer",
        "RAWHEAP_TRANSLATOR_PATH": "/opt/harmony/sdk/rawheap_translator"
      }
    }
  }
}
```

### 部署步骤
```bash
# 1. 解压发布包到固定目录
tar -xzf dist/mcp-server-v0.1.0-darwin-x64-pyinstaller.tar.gz -C /opt/mcp-servers/mem-analyzer
chmod +x /opt/mcp-servers/mem-analyzer/mcp-server

# 2. 配置 MCP 客户端 (修改 command 为实际路径)
# 3. 重启客户端即可使用
```

### 支持的客户端
- **Claude Desktop** - `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Cursor** - `~/.cursor/mcp.json`
- **VSCode MCP** - `.vscode/mcp.json`

---

## 🔗 相关文件快速引用

```bash
# 配置文件
pyproject.toml
build.py
package_release.py
PACKAGING_GUIDE.md

# 入口代码
main.py

# 产物目录
dist/
```

---

## 📝 更新日志

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-10-29 | 0.1.0 | 初版：mem-analyzer MCP 服务打包成功，26.9 MB，支持 HarmonyOS 内存泄漏分析 |

---

## 🏷️ 标签

#mcp #pyinstaller #packaging #harmony #mem-analyzer #memory-leak
