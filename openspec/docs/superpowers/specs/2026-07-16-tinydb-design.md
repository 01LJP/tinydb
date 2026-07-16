---
comet_change: tinydb
role: technical-design
canonical_spec: openspec
---

# tinydb 深度技术设计

## 1. 概述

tinydb 是一个从零构建的 Python 嵌入式关系型数据库，以教学可读性为首要目标，同时提供实用的 SQL 接口。

**核心设计哲学**：
- 每个模块职责单一、接口清晰
- 代码简洁可读，优先考虑教学价值
- 零外部依赖，纯 Python 实现
- 所有数据持久化为单一 `.db` 文件

## 2. 模块结构

```
tinydb/
├── __init__.py          # Database 类、公共 API
├── database.py          # Database 核心（execute 入口）
├── types.py             # 数据类型与约束定义
├── lexer.py             # SQL 词法分析器
├── parser.py            # SQL 语法分析器
├── ast_nodes.py         # AST 节点定义
├── catalog.py           # 系统 catalog（表/列元数据）
├── storage/
│   ├── page.py          # Slotted Page 数据结构
│   ├── file_manager.py  # 单文件读写
│   └── buffer_pool.py   # 页缓存（LRU 淘汰）
├── executor/
│   ├── scan.py          # 全表扫描
│   ├── filter.py        # WHERE 过滤
│   ├── sort.py          # ORDER BY 排序
│   ├── aggregate.py     # 聚合函数
│   └── plan.py          # 查询计划选择
├── index/
│   └── btree.py         # B-tree 索引
├── transaction/
│   ├── wal.py           # Write-Ahead Log
│   └── txn.py           # 事务管理
└── cli.py               # REPL 交互界面
```

## 3. 核心数据结构

### 3.1 Page (页)

固定 4096 字节。采用 **Slotted Page** 组织：

```
┌──────────────────────────────────────────────┐
│ Page Header (12 bytes)                        │
│   - page_id:      4 bytes                     │
│   - slot_count:   2 bytes                     │
│   - free_space:   2 bytes                     │
│   - flags:        4 bytes                     │
├──────────────────────────────────────────────┤
│ Slot Array (变长，每个 slot = 4 bytes)        │
│   - [offset: 2 bytes, length: 2 bytes]        │
│   - [offset: 2 bytes, length: 2 bytes]        │
│   - ...                                       │
├──────────────────────────────────────────────┤
│ Free Space (空隙)                            │
├──────────────────────────────────────────────┤
│ Records (从页尾向前增长)                     │
│   - record_N: [header + data]                 │
│   - record_N-1: [header + data]               │
│   - ...                                       │
└──────────────────────────────────────────────┘
```

**页类型**：
- `TABLE_DATA`: 存储表记录
- `INDEX_DATA`: 存储 B-tree 节点
- `CATALOG`: 存储系统元数据

### 3.2 Record (记录)

记录格式：
```
┌────────────┬────────────┬─────────────────┐
│ null_bitmap│ column_sizes│ column_values   │
│ (变长)     │ (变长)      │ (变长)           │
└────────────┴────────────┴─────────────────┘
```

- `null_bitmap`: 位图，标记哪些列为 NULL
- `column_sizes`: 各列值在 values 区域的字节偏移
- `column_values`: 各列值的序列化字节

**类型序列化规则**：
| 类型 | 编码 |
|------|------|
| INT | 4 bytes, big-endian signed |
| FLOAT | 8 bytes, IEEE 754 double |
| TEXT | length-prefixed UTF-8 |
| BOOL | 1 byte (0x00/0x01) |

### 3.3 B-tree 节点

B-tree 节点 = 一个页 (4096 bytes)：

```
┌──────────────────────────────────────────────┐
│ Header (16 bytes)                             │
│   - is_leaf:    1 byte                        │
│   - key_count:  2 bytes                       │
│   - page_id:    4 bytes                       │
│   - parent_id:  4 bytes                       │
│   - right_ptr:  4 bytes (叶子层链表)          │
│   - padding:    1 byte                        │
├──────────────────────────────────────────────┤
│ Keys: [key, key, ...]                         │
│ Child Pointers: [page_id, page_id, ...]       │
│ (叶子节点: [key, record_pointer, ...])        │
└──────────────────────────────────────────────┘
```

4KB 页大小下，假设 INT 键占 4 字节 + record pointer 4 字节 = 8 字节/条目，阶数约为 **250**。

## 4. 存储引擎

### 4.1 FileManager

- 单文件 `.db` 存储所有页
- 文件布局：`[catalog_page | table_pages | index_pages]`
- 页分配：首次适应策略，从空闲页列表获取或追加新页

### 4.2 BufferPool

- LRU 淘汰策略
- 默认容量：100 页
- 脏页标记：修改时置 dirty 标记
- 写回策略：淘汰时写回 或 checkpoint 时批量写回

### 4.3 Catalog (系统目录)

系统表 `__tinydb_tables__` 和 `__tinydb_columns__` 存储元数据：

```sql
-- 内部系统表（用户不可直接操作）
__tinydb_tables__:.table_id | table_name | root_page_id
__tinydb_columns__:column_id | table_id | col_name | col_type | nullable | is_unique | is_pk
```

数据库启动时从 catalog 页加载元数据到内存。

## 5. SQL 解析器

### 5.1 词法分析 (Lexer)

Token 类型：
```
关键字: SELECT, FROM, WHERE, INSERT, INTO, VALUES, UPDATE, SET, DELETE,
        CREATE, TABLE, DROP, ORDER, BY, LIMIT, OFFSET, AND, OR, NOT, NULL,
        PRIMARY, KEY, UNIQUE, INT, FLOAT, TEXT, BOOL, BEGIN, COMMIT, ROLLBACK,
        INDEX, ON, ASC, DESC, VALUES, COUNT, SUM, AVG, GROUP
标识符: [a-zA-Z_][a-zA-Z0-9_]*
数值:   [0-9]+(\.[0-9]+)?
字符串: '...'
运算符: =, !=, <>, <, >, <=, >=
标点:   ;, (, ), ,, *
```

### 5.2 语法分析 (Parser)

采用递归下降，文法规则：

```
statement   := ddl | dml | txn_cmd
ddl         := CREATE TABLE table_name ( column_defs )
             | DROP TABLE table_name
             | CREATE INDEX ON table_name ( column_name )
dml         => INSERT INTO table_name VALUES ( value_list )
             | INSERT INTO table_name ( columns ) VALUES ( value_list )
             | SELECT select_list FROM table_ref [WHERE condition]
               [ORDER BY col [ASC|DESC]] [LIMIT n] [OFFSET n]
             | UPDATE table_name SET set_list [WHERE condition]
             | DELETE FROM table_name [WHERE condition]
txn_cmd     := BEGIN | COMMIT | ROLLBACK
condition   := expr [(AND | OR) expr]*
expr        := term comp_op term
comp_op     := = | != | <> | < | > | <= | >=
```

### 5.3 AST 节点

```python
@dataclass
class Select:
    columns: List[str]          # * 或列名列表
    table: str
    where: Optional[Expr]       # 条件表达式树
    order_by: Optional[Tuple[str, str]]  # (column, ASC|DESC)
    limit: Optional[int]
    offset: Optional[int]

@dataclass
class Insert:
    table: str
    columns: Optional[List[str]]
    values: List[List[Value]]

@dataclass
class CreateTable:
    table: str
    columns: List[ColumnDef]    # (name, type, constraints)

# ... 其他 AST 节点
```

## 6. 查询执行器

### 6.1 查询计划选择

基于**选择率估算**的策略（阈值 30%）：

```
输入: SELECT * FROM t WHERE col = value

1. 检查 col 上是否存在索引
   - 不存在 → 全表扫描
   - 存在 → 继续

2. 估算选择率
   - 等值查询: 估计选择率 ≈ 1 / (不同值数量)
   - 范围查询: 估计选择率 ≈ (high - low) / total_range
   - 无法估算时默认 30%

3. 选择率 < 30% → B-tree 索引扫描
   选择率 >= 30% → 全表扫描
```

### 6.2 执行流程

```
SQL String
    │
    ▼
Lexer → Token Stream
    │
    ▼
Parser → AST
    │
    ▼
Catalog Lookup → 验证表和列存在
    │
    ▼
Plan Selection → 选择扫描策略
    │
    ▼
Executor → 执行算子链
    │
    ▼
Result (List[Dict])
```

### 6.3 算子链

```
Scan (B-tree Index Scan | Table Scan)
  │
  ▼
Filter (WHERE 条件)
  │
  ▼
Sort (ORDER BY, 可选)
  │
  ▼
Aggregate (GROUP BY + 聚合, 可选)
  │
  ▼
Limit (LIMIT/OFFSET, 可选)
  │
  ▼
Project (列投影)
```

## 7. B-tree 索引

### 7.1 操作

| 操作 | 时间复杂度 | 描述 |
|------|-----------|------|
| Search | O(log n) | 从根节点递归向下查找 |
| Insert | O(log n) | 找到叶子插入，必要时节点分裂 |
| Delete | O(log n) | 找到叶子删除，必要时合并/重平衡 |
| Range Scan | O(log n + k) | 找到起始点，沿叶子链表扫描 k 条 |

### 7.2 节点分裂

当节点键数超过阶数 (约 250)：
1. 创建新节点
2. 中位数 key 提升到父节点
3. 原节点保留前半部分，新节点获得后半部分
4. 如果是叶子层，新节点加入叶子链表

### 7.3 索引维护

- INSERT: 遍历所有索引，插入新键
- DELETE: 遍历所有索引，删除对应键
- UPDATE: 对更新的列，先删后插

## 8. 事务管理 (WAL)

### 8.1 WAL 格式

```
WAL 文件: mydb.db.wal

┌──────────────────────────────────────────────┐
│ WAL Header                                    │
│   - magic:       4 bytes ("WAL\0")            │
│   - version:     2 bytes                      │
│   - page_size:   2 bytes                      │
│   - checkpoint:  4 bytes                      │
│   - padding:     ...                          │
├──────────────────────────────────────────────┤
│ Log Records (循环)                            │
│   - txn_id:     4 bytes                       │
│   - op_type:    1 byte (INSERT/UPDATE/DELETE) │
│   - page_id:    4 bytes                       │
│   - data_len:   2 bytes                       │
│   - old_data:   [data_len bytes]              │
│   - new_data:   [data_len bytes]              │
│   - checksum:   4 bytes                       │
└──────────────────────────────────────────────┘
```

### 8.2 事务流程

```
BEGIN → 分配 txn_id, 记录 BEGIN 到 WAL
  │
  ▼
执行操作 → 写 WAL log (old_data + new_data), 修改 buffer pool 中的页
  │
  ▼
COMMIT → 写 COMMIT 到 WAL, 刷新 WAL 到磁盘, 标记事务完成
  │        如果事务数达到阈值 → CHECKPOINT
ROLLBACK → 按 WAL 逆序用 old_data 恢复页, 写 ABORT 记录
```

### 8.3 Checkpoint

每 **100 个事务**自动触发：
1. 暂停新事务开始
2. 将 WAL 中已提交的所有修改刷回主数据库文件
3. 清空 WAL 文件
4. 更新 checkpoint 指针

### 8.4 崩溃恢复

启动时检查 WAL：
1. 找到最后一个 checkpoint 位置
2. 从 checkpoint 开始重放 WAL（应用已提交事务）
3. 丢弃未提交事务的记录

## 9. Python API 设计

### 9.1 使用方式

```python
import tinydb

# 方式 1: 直接操作
db = tinydb.Database("mydb.db")
result = db.execute("SELECT * FROM users WHERE id = 1")
db.close()

# 方式 2: 上下文管理器
with tinydb.open("mydb.db") as db:
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")
    db.execute("INSERT INTO users VALUES (1, 'Alice')")
    result = db.execute("SELECT * FROM users")
    print(result)  # [{'id': 1, 'name': 'Alice'}]
```

### 9.2 接口定义

```python
class Database:
    def __init__(self, path: str): ...
    def execute(self, sql: str) -> List[Dict]: ...
    def close(self): ...

def open(path: str) -> ContextManager[Database]: ...
```

### 9.3 返回格式

- `SELECT`: 返回 `List[Dict[str, Any]]`，每个 dict 是一行
- `INSERT`/`UPDATE`/`DELETE`: 返回 `{"affected_rows": int}`
- `CREATE TABLE`/`DROP TABLE`: 返回 `{"status": "ok"}`

## 10. CLI 设计

```
$ tinydb mydb.db
tinydb> CREATE TABLE users (id INT PRIMARY KEY, name TEXT, age INT);
ok
tinydb> INSERT INTO users VALUES (1, 'Alice', 30);
1 row affected
tinydb> SELECT * FROM users WHERE age > 25;
+----+-------+-----+
| id | name  | age |
+----+-------+-----+
|  1 | Alice |  30 |
+----+-------+-----+
1 row
tinydb> .schema
CREATE TABLE users (id INT PRIMARY KEY, name TEXT, age INT);
tinydb> .exit
```

**REPL 特性**：
- 多行输入（分号终止）
- 元命令: `.schema`, `.tables`, `.exit`
- 语法高亮（可选）
- 历史记录（可选）

## 11. 错误处理

异常层次：
```
TinydbError (基类)
├── ParseError          # SQL 语法错误
├── TypeMismatchError   # 类型不匹配
├── ConstraintError     # 约束违反 (PK/NOT NULL/UNIQUE)
├── TableNotFoundError  # 表不存在
├── ColumnNotFoundError # 列不存在
├── TransactionError    # 事务相关错误
└── StorageError        # 磁盘 I/O 错误
```

错误信息格式：`[ERROR_TYPE] 具体描述 (context: 补充信息)`

示例：
```
[CONSTRAINT_ERROR] PRIMARY KEY violation: value 1 already exists in table 'users'
[PARSE_ERROR] Unexpected token 'WHERE' at line 1, column 15
[TYPE_MISMATCH] Cannot insert TEXT 'abc' into INT column 'age'
```

## 12. 测试策略

### 12.1 单元测试

每个模块对应测试文件：
```
tests/
├── test_lexer.py        # 词法分析
├── test_parser.py       # 语法分析
├── test_page.py         # 页操作
├── test_buffer_pool.py  # 缓冲池
├── test_btree.py        # B-tree
├── test_executor.py     # 查询执行
├── test_wal.py          # WAL
├── test_types.py        # 类型系统
└── test_catalog.py      # 系统目录
```

### 12.2 集成测试

```
tests/
├── test_ddl.py          # CREATE/DROP TABLE
├── test_dml.py          # INSERT/SELECT/UPDATE/DELETE
├── test_transaction.py  # BEGIN/COMMIT/ROLLBACK + 崩溃恢复
├── test_index.py        # 索引创建与查询加速
├── test_constraints.py  # PK/NOT NULL/UNIQUE
└── test_e2e.py          # 端到端场景
```

### 12.3 测试方法

- 使用临时数据库文件（`tempfile`），测试后自动清理
- 事务测试: 模拟崩溃（不调用 close）后验证恢复
- 索引测试: 对比有/无索引的查询结果一致性

## 13. 技术风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|---------|
| B-tree 节点分裂实现复杂 | 高 | 先写伪代码验证，参考《Database Internals》第 6、7 章 |
| WAL 重放逻辑 bug 导致数据丢失 | 高 | 详尽的崩溃恢复测试 + checksum 校验 |
| 纯 Python 性能差 | 中 | 以教学为首要目标，文档中明确说明 |
| Slotted Page 碎片化 | 低 | 实现定期碎片整理（vacuum），非 MVP 必须 |
| SQL 解析器覆盖不全 | 中 | 先支持核心语法，迭代扩展 |

## 14. 未来扩展（非本次范围）

- 多表 JOIN（需要 join 算子）
- 并发控制（MVCC 或锁管理器）
- ALTER TABLE、外键、视图
- 网络模式（CS 架构）
- Python DB-API 2.0 兼容
- `LIKE` 模糊匹配、`IN` 子查询
