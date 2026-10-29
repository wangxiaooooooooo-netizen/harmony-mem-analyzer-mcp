import os
import subprocess
from fastmcp import FastMCP

# 1. 初始化 FastMCP 服务端
mcp = FastMCP("mem-analyzer-mcp")

# ============================================================
# mem-analyzer-mcp（鸿蒙内存泄漏分析）相关工具
# ============================================================

# mem-analyzer-mcp 及 rawheap_translator 可执行文件路径（可通过环境变量覆盖）
MEM_ANALYZER_PATH = os.environ.get("MEM_ANALYZER_PATH", "mem-analyzer")
RAWHEAP_TRANSLATOR_PATH = os.environ.get("RAWHEAP_TRANSLATOR_PATH", "rawheap_translator")


def _run_cmd(cmd: list, timeout: int = 300) -> tuple:
    """执行外部命令，返回 (是否成功, stdout+stderr)"""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode == 0, output.strip()
    except FileNotFoundError:
        return False, f"未找到可执行文件：{cmd[0]}。请先安装 mem-analyzer（官方仓库 developtools_dfx_mem_analyzer），或通过环境变量 MEM_ANALYZER_PATH / RAWHEAP_TRANSLATOR_PATH 指定路径。"
    except subprocess.TimeoutExpired:
        return False, f"命令执行超时（>{timeout}s）：{' '.join(cmd)}"


@mcp.tool(tags={"mem-analyzer-mcp"})
def rawheap_translate(input_rawheap_path: str, output_path: str) -> str:
    """【分组：内存分析 mem-analyzer-mcp】使用 SDK 自带的 rawheap_translator 将 .rawheap 原始内存文件转换为 .heapsnapshot 堆快照文件，供后续 jsleak 分析或 Chrome DevTools 使用。注意：若文件来自 HiAppEvent 采集，初始后缀可能是 .log，需先重命名为 .rawheap。"""
    if not os.path.exists(input_rawheap_path):
        return f"错误：输入文件不存在：{input_rawheap_path}"
    ok, output = _run_cmd([RAWHEAP_TRANSLATOR_PATH, input_rawheap_path, output_path])
    if ok:
        return f"转换成功！\n输入: {input_rawheap_path}\n输出: {output_path}\n{output}"
    return f"转换失败：\n{output}"


@mcp.tool(tags={"mem-analyzer-mcp"})
def mem_analyzer_jsleak(jsleaklist_path: str, heapsnapshot_path: str, outPutDir: str, top_n: int = 20) -> str:
    """【分组：内存分析 mem-analyzer-mcp】调用 mem-analyzer 的 jsleak 子命令，将 .jsleaklist 泄漏对象列表与同一会话的 .heapsnapshot 堆快照关联分析。output_format 可选 json（结构化结果，推荐供 agent 解析）或 html（生成可视化报告，含组件泄漏识别与最短 GC_ROOT 引用链）。两个文件必须来自同一会话并通过内部 Hash 匹配。"""
    for p in (jsleaklist_path, heapsnapshot_path):
        if not os.path.exists(p):
            return f"错误：文件不存在：{p}"
    cmd = [MEM_ANALYZER_PATH, "jsleak", "-n", str(top_n), "-l", jsleaklist_path, heapsnapshot_path, "-o", "-d", outPutDir]

    ok, output = _run_cmd(cmd, timeout=600)
    if ok:
        return f"分析完成（top_n={top_n}, format=HTML）：\n{output}"
    return f"分析失败：\n{output}\n提示：-n/-l/-o/-j 参数含义以官方仓库 README 为准（wiki 沉淀时官方文档未完整说明，如有出入请核对参数）。"


@mcp.tool(tags={"mem-analyzer-mcp"})
def memleak_files_list(directory: str) -> str:
    """【分组：内存分析 mem-analyzer-mcp】扫描指定目录，找出所有 .jsleaklist / .rawheap / .heapsnapshot 文件，并按文件名中的时间戳自动配对（JsLeakWatcher 生成的文件名时间戳相差毫秒级即为同一会话）。HiAppEvent 采集的 .log 文件也会被提示需重命名为 .rawheap。"""
    if not os.path.isdir(directory):
        return f"错误：目录不存在：{directory}"
    import re
    jsleaklists, rawheaps, heapsnapshots, logs = [], [], [], []
    for name in os.listdir(directory):
        ts = re.search(r"(\d{13})", name)
        entry = {"file": name, "timestamp": ts.group(1) if ts else None}
        if name.endswith(".jsleaklist"):
            jsleaklists.append(entry)
        elif name.endswith(".rawheap"):
            rawheaps.append(entry)
        elif name.endswith(".heapsnapshot"):
            heapsnapshots.append(entry)
        elif name.endswith(".log"):
            logs.append(entry)
    lines = [f"目录 {directory} 扫描结果：",
             f"jsleaklist 文件 ({len(jsleaklists)}): {[e['file'] for e in jsleaklists]}",
             f"rawheap 文件 ({len(rawheaps)}): {[e['file'] for e in rawheaps]}",
             f"heapsnapshot 文件 ({len(heapsnapshots)}): {[e['file'] for e in heapsnapshots]}"]
    if logs:
        lines.append(f"注意：发现 {len(logs)} 个 .log 文件 {[e['file'] for e in logs]}，若来自 HiAppEvent 内存泄漏采集，请先重命名为 .rawheap 再分析。")
    # 按时间戳配对
    pairs = []
    for jl in jsleaklists:
        match = next((r for r in rawheaps if r["timestamp"] and jl["timestamp"] and abs(int(r["timestamp"]) - int(jl["timestamp"])) < 5000), None)
        if match:
            pairs.append(f"{jl['file']} <-> {match['file']}")
    if pairs:
        lines.append("疑似同一会话配对（jsleaklist <-> rawheap）：")
        lines += [f"  - {p}" for p in pairs]
    return "\n".join(lines)


@mcp.tool(tags={"mem-analyzer-mcp"})
def memleak_pair_validate(jsleaklist_path: str, heap_file_path: str) -> str:
    """【分组：内存分析 mem-analyzer-mcp】校验 .jsleaklist 与 .heapsnapshot/.rawheap 是否可配对分析：检查两个文件是否存在、非空、后缀合法，并尝试比对文件名时间戳是否为同一会话（JsLeakWatcher 要求同会话、内部 Hash 匹配，Hash 校验需由 mem-analyzer-mcp 分析时完成，此工具做前置筛查）。"""
    problems = []
    for p in (jsleaklist_path, heap_file_path):
        if not os.path.exists(p):
            problems.append(f"文件不存在：{p}")
        elif os.path.getsize(p) == 0:
            problems.append(f"文件为空：{p}")
        elif os.path.getsize(p) > 1.5 * 1024 ** 3:
            problems.append(f"文件超过 1.5G（Profiler 单文件解析上限）：{p}")
    if not jsleaklist_path.endswith(".jsleaklist"):
        problems.append(f"第一个文件后缀不是 .jsleaklist：{jsleaklist_path}")
    if not (heap_file_path.endswith(".rawheap") or heap_file_path.endswith(".heapsnapshot")):
        problems.append(f"第二个文件后缀应为 .rawheap 或 .heapsnapshot：{heap_file_path}")
    # 时间戳比对
    import re
    ts1 = re.search(r"(\d{13})", os.path.basename(jsleaklist_path))
    ts2 = re.search(r"(\d{13})", os.path.basename(heap_file_path))
    session_hint = "无法从文件名判断（无13位时间戳），请依赖 mem-analyzer-mcp 的 Hash 匹配"
    if ts1 and ts2:
        diff = abs(int(ts1.group(1)) - int(ts2.group(1)))
        session_hint = f"文件名时间戳相差 {diff}ms，{'疑似同一会话' if diff < 5000 else '可能不是同一会话，注意校验'}"
    if problems:
        return "校验未通过：\n" + "\n".join(f"  - {p}" for p in problems) + f"\n{session_hint}"
    return f"前置校验通过，可以调用 mem_analyzer_jsleak 分析。\n{session_hint}"


if __name__ == "__main__":
    mcp.run()

