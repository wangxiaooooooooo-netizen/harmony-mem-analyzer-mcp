import sqlite3
from datetime import datetime

import networkx as nx

# 1. 数据库路径
db_path = "/Users/wx/workspace/projs/harmony/LR35.10_Harmony_ZhaoHuUI/HarmonyZhaoHuUI/.codegraph/codegraph.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def just_edges():
    try:
        # cursor.execute("SELECT DISTINCT kind FROM edges;")
        # kinds = cursor.fetchall()
        # print("=========================================")
        # print(f"✨ 成功连接！该 CodeGraph edges表中有如下关系：")
        # print("=========================================")
        # for kind in kinds:
        #     kind_name = kind[0]
        #     print(f"\n📋 关系名: 【{kind_name}】")



        # 2. 查询 sqlite_master 获取所有表名
        # cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        # tables = cursor.fetchall()
        #
        # print("=========================================")
        # print(f"✨ 成功连接！该 CodeGraph 数据库中包含以下内部表：")
        # print("=========================================")
        #
        # for table in tables:
        #     table_name = table[0]
        #     print(f"\n📋 表名: 【{table_name}】")
        #
        #     # 3. 打印该表具体的列结构
        #     cursor.execute(f"PRAGMA table_info({table_name});")
        #     columns = cursor.fetchall()
        #     print(f"   └─ 字段: ", ", ".join([f"{col[1]} ({col[2]})" for col in columns]))

        query = """
        SELECT 
            n1.name AS source_name, 
            n2.name AS target_name, 
            e.kind 
        FROM edges e
        JOIN nodes n1 ON e.source = n1.id
        JOIN nodes n2 ON e.target = n2.id
        WHERE e.kind IN ('extends', 
        'calls',
        'contains',
        'decorates',
        'imports',
        'instantiates',
        'references',
        'implements', 
        'inherits', 
        'dependency')
        """

        G = nx.DiGraph()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()

            # 3. 循环读取流式数据，构建 NetworkX 图
            for row in rows:
                source_class = row[0]  # 可读的源类名
                target_class = row[1]  # 可读的目标类名
                relation_type = row[2]  # 关系类型

                G.add_edge(source_class, target_class, relation=relation_type)

            print("=========================================")
            print(f"✨ 成功解析出【可读类名】并加载至 NetworkX！")
            print(f"📊 节点(类)数量: {G.number_of_nodes()}")
            print(f"📊 边(关系)数量: {G.number_of_edges()}")
            print("=========================================")

            nx.write_graphml(G, "just_edges" + datetime.now().strftime("%m-%d_%H:%M:%S") + ".graphml")

        except sqlite3.Error as e:
            # 容错处理：如果你的另一个表不叫 nodes，或者字段叫 symbols，这里会报错
            print(f"❌ 数据库查询出错，请检查是否有 nodes 表。错误信息: {e}")
            print("💡 提示：如果刚才扫描时发现有其他表（如 symbols），请将 SQL 中的 'nodes' 替换为对应的表名。")

        finally:
            cursor.close()
            conn.close()

        # 4. 打印前 5 个解析出的真实类名关系进行验证
        print("\n解析后的可读类关系示例:")
        for u, v, data in list(G.edges(data=True))[:50]:
            print(f"类 [{u}] --({data['relation']})--> 类 [{v}]")
    except Exception as e:
        print(f"❌ 读取数据库失败: {e}")
    finally:
        conn.close()
    # 2. 通过 JOIN nodes 表，把 edges 的 source 和 target 的 ID 转换成真实的可读名称 (n1.name 和 n2.name)
    # 注意：如果你想要带命名空间/包名的完整类名，可以把 n1.name 改为 n1.qualified_name



def node_with_attribute():
    # 2. 初始化 NetworkX 有向图 (因为调用、定义、继承等关系都是有方向的)
    G = nx.DiGraph()
    try:
        # 3. 查询并添加所有节点及其属性
        # 把 id 作为图的节点唯一标识，其他维度作为节点属性附着
        print("⏳ 正在读取节点 (Nodes)...")
        node_query = "SELECT id, name, kind, file_path, start_line, end_line, qualified_name FROM nodes;"
        cursor.execute(node_query)
        nodes_rows = cursor.fetchall()

        for node_id, name, kind, file_path, start_line, end_line, q_name in nodes_rows:
            G.add_node(
                node_id,
                name=name,
                kind=kind,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                qualified_name=q_name
            )

        # 4. 查询并添加所有关系边
        # 提取 src_id, dst_id，并将关系类型 kind 作为边的属性
        print("⏳ 正在读取边 (Edges)...")
        edge_query = "SELECT source, target, kind FROM edges;"
        cursor.execute(edge_query)
        edges_rows = cursor.fetchall()

        for src_id, dst_id, edge_kind in edges_rows:
            # 确保源节点和目标节点在图里（容错处理）
            if G.has_node(src_id) and G.has_node(dst_id):
                G.add_edge(src_id, dst_id, kind=edge_kind)
            else:
                # 偶尔会有指向未解析引用的边，直接添加也会自动创建空属性节点
                G.add_edge(src_id, dst_id, kind=edge_kind)

        print(f"✅ 成功构建 NetworkX 图结构！")
        print(f"📊 图统计信息：包含 {G.number_of_nodes()} 个节点，{G.number_of_edges()} 条关系边。")

        output_path = "node_with_attribute" + datetime.now().strftime("%m-%d_%H:%M:%S") + ".graphml"
        nx.write_graphml(G, output_path)
        print(f"💾 成功将带完整属性的图数据导出至: {output_path}")

    except sqlite3.OperationalError as e:
        print(f"❌ 数据库读取失败，请检查表结构：{e}")
    finally:
        conn.close()

if __name__ == "__main__":
    node_with_attribute()
    # just_edges()