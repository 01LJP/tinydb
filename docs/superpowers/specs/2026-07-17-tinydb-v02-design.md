---
comet_change: tinydb-v02
role: technical-design
canonical_spec: openspec
---

# TinyDB v0.2 深度技术设计

## 1. JOIN 查询实现

### 1.1 词法分析器扩展

在 `lexer.py` 的 `KEYWORDS` 集合中添加：`JOIN`、`INNER`、`LEFT`、`RIGHT`、`CROSS`、`FULL`、`ON`、`AS`、`EXPLAIN`。

新增 `DOT` 标点类型用于 `table.column` 限定列名解析。

### 1.2 AST 节点

新增节点：

```python
@dataclass
class TableRef:
    name: str
    alias: Optional[str] = None

@dataclass
class JoinClause:
    table: str
    join_type: str  # 'INNER' | 'LEFT' | 'CROSS'
    on_condition: Optional[Expr] = None
    alias: Optional[str] = None

@dataclass
class Explain:
    statement: Any
```

修改 `Select` 节点：
- `table: str` → `tables: List[TableRef]`
- 新增 `joins: List[JoinClause] = field(default_factory=list)`

修改 `ColumnRef` 节点：
- 新增 `table: Optional[str] = None`（限定列名）

### 1.3 语法分析器

**FROM 子句解析** (`_parse_from_clause`)：
```
FROM table_ref [AS alias] {JOIN table_ref [AS alias] ON condition}
```

**JOIN 解析** (`_parse_join`)：
- 匹配 `[INNER|LEFT|CROSS] JOIN`
- 解析表名和可选别名
- INNER/LEFT JOIN 需要 `ON condition`
- CROSS JOIN 不需要 ON 子句

**限定列名解析**：
- 当 `_parse_term()` 遇到 IDENT 后跟 DOT 再跟 IDENT 时，生成 `ColumnRef(table=前标识, name=后标识)`

**EXPLAIN 解析**：
- 匹配 `EXPLAIN` 关键字后递归调用 `_parse_statement()`，包裹为 `Explain(statement=...)`

### 1.4 NestedLoopJoin 执行算子

```python
class NestedLoopJoin:
    def __init__(self, left_source, right_table, join_type, on_condition, catalog, buffer_pool):
        ...

    def __iter__(self):
        right_rows = list(self.right_scan)  # 物化右表

        for left_row in self.left_source:
            matched = False
            for right_row in right_rows:
                if self._eval_on(left_row, right_row):
                    yield self._merge_rows(left_row, right_row)
                    matched = True

            if not matched and self.join_type == 'LEFT':
                yield self._merge_rows(left_row, self._null_right_row())
```

**列名合并策略**：
- 左表列名：`{table_alias}.{column_name}` 或 `{table_name}.{column_name}`
- 右表列名：同上
- 无歧义时支持短名引用

### 1.5 执行器管线修改

`_exec_select` 修改：
```python
# 单表查询（现有逻辑不变）
if not ast.joins:
    scan = plan.select_scan(ast.tables[0].name, ast.where)
else:
    # JOIN 查询
    scan = plan.select_scan(ast.tables[0].name, None)
    for join in ast.joins:
        scan = NestedLoopJoin(
            left_source=scan,
            right_table=join.table,
            join_type=join.join_type,
            on_condition=join.on_condition,
            catalog=self.catalog,
            buffer_pool=self.buffer_pool,
        )
```

`Filter._eval` 修改：
- `ColumnRef` 解析时，如果 `expr.table` 不为 None，查找 `{expr.table}.{expr.name}` 键
- 否则先尝试短名查找，再尝试带表前缀查找

---

## 2. 并发控制实现

### 2.1 ReadWriteLock

```python
class ReadWriteLock:
    def __init__(self):
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0

    def acquire_read(self):
        with self._read_ready:
            self._readers += 1

    def release_read(self):
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self):
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()

    def release_write(self):
        self._read_ready.release()
```

### 2.2 LockManager

```python
class LockManager:
    def __init__(self):
        self._global_lock = ReadWriteLock()
        self._table_locks: Dict[str, ReadWriteLock] = {}
        self._lock_table_lock = threading.Lock()  # 保护 _table_locks 字典

    def get_table_lock(self, table_name: str) -> ReadWriteLock:
        with self._lock_table_lock:
            if table_name not in self._table_locks:
                self._table_locks[table_name] = ReadWriteLock()
            return self._table_locks[table_name]
```

### 2.3 BufferPool 线程安全

所有公共方法加 `threading.Lock`：
- `get_page()`: 获取锁后检查缓存，miss 时加载
- `put()`: 获取锁后更新缓存
- `mark_dirty()`: 获取锁后添加到脏页集合
- `flush_all()`: 获取锁后遍历脏页写回

### 2.4 Catalog 线程安全

使用 `threading.RLock`（递归锁）：
- `_save()` 和 `_load()` 在锁内执行
- `create_table()`、`drop_table()` 等公共方法在锁内执行
- 使用 RLock 因为 `create_table` → `_save` 可能递归获取锁

### 2.5 Database.execute() 锁策略

```python
def execute(self, sql: str):
    tokens = Lexer().tokenize(sql)
    ast = Parser(tokens).parse()

    if isinstance(ast, (CreateTable, DropTable, CreateIndex)):
        with self.lock_manager._global_lock:
            return self._dispatch(ast)

    if isinstance(ast, Select):
        tables = self._extract_tables(ast)
        locks = [self.lock_manager.get_table_lock(t) for t in tables]
        for lock in locks:
            lock.acquire_read()
        try:
            return self._dispatch(ast)
        finally:
            for lock in reversed(locks):
                lock.release_read()

    if isinstance(ast, (Insert, Update, Delete)):
        lock = self.lock_manager.get_table_lock(ast.table)
        lock.acquire_write()
        try:
            return self._dispatch(ast)
        finally:
            lock.release_write()
```

---

## 3. CLI 增强实现

### 3.1 readline 集成

```python
import readline
import atexit

HISTORY_FILE = os.path.expanduser("~/.tinydb_history")

def setup_readline():
    readline.parse_and_bind("tab: complete")
    readline.set_completer(completer)
    if os.path.exists(HISTORY_FILE):
        readline.read_history_file(HISTORY_FILE)
    atexit.register(readline.write_history_file, HISTORY_FILE)
```

**Tab 补全策略**：
- SQL 关键字补全（SELECT, FROM, WHERE, JOIN, ...）
- 表名补全（从 catalog.tables 获取）
- 元命令补全（.tables, .schema, .explain, .dump, ...）

### 3.2 语法高亮

使用 ANSI 转义码：
```python
KEYWORD_COLOR = "\033[1;34m"  # 蓝色粗体
STRING_COLOR = "\033[0;32m"   # 绿色
NUMBER_COLOR = "\033[0;33m"   # 黄色
RESET_COLOR = "\033[0m"

def highlight_sql(sql: str) -> str:
    # 正则匹配替换关键字、字符串、数字
    ...
```

### 3.3 EXPLAIN 执行计划

```python
class ExplainPlan:
    def __init__(self, db):
        self.db = db

    def explain(self, sql: str) -> str:
        tokens = Lexer().tokenize(sql)
        ast = Parser(tokens).parse()
        plan_tree = self._build_plan(ast)
        return self._format_plan(plan_tree)

    def _build_plan(self, ast) -> dict:
        if isinstance(ast, Select):
            nodes = []
            if ast.joins:
                nodes.append({"type": "SeqScan", "table": ast.tables[0].name})
                for join in ast.joins:
                    nodes.append({"type": "NestedLoopJoin", "table": join.table, "join_type": join.join_type})
            else:
                nodes.append({"type": "SeqScan", "table": ast.tables[0].name})
            if ast.where:
                nodes.append({"type": "Filter", "condition": str(ast.where)})
            if ast.order_by:
                nodes.append({"type": "Sort", "column": ast.order_by[0], "order": ast.order_by[1]})
            if ast.limit:
                nodes.append({"type": "Limit", "limit": ast.limit})
            return {"nodes": nodes}

    def _format_plan(self, plan) -> str:
        lines = []
        for i, node in enumerate(plan["nodes"]):
            prefix = "-> " if i > 0 else ""
            lines.append(f"{prefix}{node['type']}({', '.join(f'{k}={v}' for k,v in node.items() if k != 'type')})")
        return "\n".join(lines)
```

### 3.4 新元命令

- `.explain <sql>` — 调用 ExplainPlan 输出执行计划
- `.dump [table]` — 遍历 catalog 输出 CREATE TABLE + INSERT 语句
- `.version` — 输出 `TinyDB v0.2.0`
- `.mode table|csv` — 切换输出格式

---

## 4. 工作区隔离与合并策略

### 4.1 git worktree 分支

```
git worktree add worktree/feature-join feature/join
git worktree add worktree/feature-concurrency feature/concurrency
git worktree add worktree/feature-cli feature/cli
```

### 4.2 合并顺序

1. `feature/join` → `master`（基础层改动：lexer/parser/AST/executor）
2. `feature/concurrency` → `master`（横切关注点：锁机制）
3. `feature/cli` → `master`（CLI 增强，依赖前两个功能）

每次合并后运行全量测试确保无回归。

---

## 5. 详细任务依赖图

```
1.1 lexer 关键字 ──→ 1.2 AST 节点 ──→ 1.3 ColumnRef ──→ 1.4-1.7 parser
                                                                      ↓
                                                              2.1-2.7 executor
                                                                      ↓
                                                              3.1-3.7 JOIN 测试
                                                                      ↓
4.1-4.7 并发实现 ──→ 5.1-5.6 并发测试 ──→ 6.1-6.8 CLI ──→ 7.1-7.5 集成测试 ──→ 8.1-8.3 收尾
```
