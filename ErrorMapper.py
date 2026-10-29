import re
from pathlib import Path

import networkx as nx


class ErrorMapper:
    def __init__(self, codegraph_graphml):
        print(f"📂 正在从 GraphML 加载代码地图...")
        self.G = codegraph_graphml
        print(f"📊 地图加载成功！包含 {self.G.number_of_nodes()} 个代码节点")

    def parse_stack_trace(self, stack_trace: str):
        """
        从报错堆栈中提取 (文件名, 行号)
        适用于多数主流语言的异常堆栈，可根据实际日志格式微调正则
        """
        # 示例匹配: File "paths/to/file.py", line 42, in my_func
        pattern = r"File\s(.*?),?\s+line\s+(\d+)"
        matches = re.findall(pattern, stack_trace)
        results = []
        # if matches:
        #     file_name = matches.group(1)
        #     line = int(matches.group(2))
        #     results.append({
        #         "file_path": file_name,
        #         "line": int(line)
        #     })
        #     print(f"File {file_name} line {line}")
        for file_path, line_num in matches:
            results.append({
                "file_path": file_path,
                "line": int(line_num)
            })
        # 通常堆栈最底部（最后一条）是真正抛出异常的核心报错点
        return results[::-1]

    def find_node_by_location(self, file_path: str, line_num: int):
        """
        核心算法：根据文件名和行号，在 NetworkX 图谱中定位到最精确的节点
        """
        target_node_data = None
        target_node_id = None
        min_range = float('inf')  # 用于锁定嵌套关系中最内层的函数
        file_name = Path(file_path).name
        file_name = file_name.replace(".ts", "")
        # 2. 遍历 NetworkX 中的所有节点及其属性
        for node_id, node_attrs in self.G.nodes(data=True):
            node_file = node_attrs.get("qualified_name", "")
            kind = node_attrs.get("kind")

            if not kind == "method":
                continue
            # 路径匹配（处理相对路径/绝对路径差异）
            if not file_name in node_file:
                continue

            # 3. 检查行号是否落在节点的生命周期区间内
            # 注意：从 GraphML 读取出的数字属性可能是字符串，必须强转为 int
            try:
                start = int(node_attrs.get("start_line", 0))
                end = int(node_attrs.get("end_line", 0))
            except (ValueError, TypeError):
                continue  # 如果节点没有行号属性，跳过

            if start <= line_num <= end:
                # 计算区间大小，处理“类包含函数”的情况，优先取范围更小、更精确的函数节点
                node_range = end - start
                if node_range < min_range:
                    min_range = node_range
                    target_node_id = node_id
                    target_node_data = dict(node_attrs)
                    # 将节点 ID 顺便塞进字典，方便下游定位
                    target_node_data["id"] = node_id

        return target_node_data

    def map_error_to_context(self, stack_trace: str):
        """
        入口函数：输入堆栈，输出 Agent 所需的图节点上下文
        """
        error_points = self.parse_stack_trace(stack_trace)
        if not error_points:
            return None

        # 我们重点关注引发崩溃的源头节点（堆栈最内层）
        core_error = error_points[0]

        matched_node = self.find_node_by_location(core_error["file_path"], core_error["line"])

        if matched_node:
            print(f"🎯 成功映射报错点！定位到节点: [{matched_node.get('type')}] {matched_node.get('name')}")
            return matched_node
        else:
            print("⚠️ 未能在图中找到精确节点，可能报错在匿名块或未解析区域。")
            return None

    def parse_arkts_hybrid_stack(self, stack_trace: str):
        """
        全域扫描版：无视换行丢失，100% 抓取鸿蒙混淆路径中的业务代码
        """
        results = []

        # 🎯 极其宽容的全局扫描正则：只抓取以 .ts 或 .ets 结尾且带有 :行号:列号 的特征片段
        # 自动斩断左侧的 # 号或括号，确保只留下纯净的相对路径
        global_pattern = r'([^\s\(#]+?\.[e]?ts):(\d+):(\d+)'

        matches = re.finditer(global_pattern, stack_trace)

        for match in matches:
            file_path = match.group(1)   # 捕获到的路径
            line_num = int(match.group(2)) # 行号
            col_num = int(match.group(3))  # 列号

            # 🛡️ 过滤：排除系统状态管理库干扰 (stateMgmt)
            if "stateMgmt" in file_path or "hmos_for_system" in file_path:
                continue

            # 🧹 清洗：如果路径前面仍然夹杂着碎片化的包名残余，强制截取 src/ 之后的真正源码路径
            if "src/" in file_path and not file_path.startswith("src/"):
                idx = file_path.find("src/")
                if idx != -1:
                    file_path = file_path[idx:]

            results.append({
                "file_path": file_path,
                "line": line_num,
                "column": col_num
            })

        return results

    # ================= 演示测试 =================
    # if __name__ == "__main__":
    #     test_stack = """
    #     Tid: 57237, Name: bchina.hmoffice
    #     00 pc 00000000001fa894 /system/lib64/platformsdk/libark_jsruntime.so
    #     10 at asyncRegisterToFinalizationRegistry (/usr1/hmos_for_system/.../stateMgmt.js:4061:1)
    #     12 at ZHEmojiShopPackageIconModel (@lr35_10/zhbusinesscomponent#@lr35_10/zhbusinesscomponent#1.0.202608271948#src/main/ets/bizservice/keyboard/emoji_keyboard/model/ZHEmojiShopPackageIconModel.ts:49:1)
    #     13 at observedClass (/usr1/hmos_for_system/.../stateMgmt.js:12211:1)
    #     """
    #
    #     parsed_points = parse_arkts_hybrid_stack(test_stack)
    #     for pt in parsed_points:
    #         print(f"🎯 清洗定位成功 -> 文件: {pt['file_path']}, 行号: {pt['line']}")

     # ================= 演示使用 =================
        # if __name__ == "__main__":
        #     # 初始化映射器，直接读取 graphml 文件
        #     mapper = ErrorMapper("project_codegraph.graphml")
        #
        #     stack_log = 'Traceback:\n File "app/services/billing.py", line 125, in process_payment\n ZeroDivisionError: division by zero'
        #     node = mapper.map_error_to_context(stack_log)
        #     if node:
        #         print("节点详细数据:", node)