## Why

需要一个轻量级嵌入式关系型数据库，既能通过造轮子深入理解数据库核心原理（存储引擎、SQL 解析、查询优化、索引、事务），又能作为可嵌入的 Python 库在实际项目中使用。现有方案中 SQLite 过于庞大复杂不适合学习拆解，而 Python 生态中缺乏一个简洁、可读、可教学的嵌入式关系型数据库实现。

v0.1 已实现基础的单表 SQL 查询、B-Tree 索引、WAL 事务和简单 REPL。v0.2 在此基础上补齐三个核心能力：多表关联查询、并发安全、CLI 体验增强。

## What Changes

**v0.1 基础功能：**
- 纯 SQL 字符串接口（`db.execute("SELECT ...")`）
- DDL：`CREATE TABLE`、`DROP TABLE`
- DML：`INSERT`、`SELECT`、`UPDATE`、`DELETE`
- WHERE 条件过滤（AND/OR）
- ORDER BY、LIMIT、OFFSET
- 列约束：PRIMARY KEY、NOT NULL、UNIQUE
- 聚合函数：COUNT、SUM、AVG + GROUP BY
- B-tree 索引，加速等值和范围查询
- 数据类型系统：INT、FLOAT、TEXT、BOOL 及类型检查
- ACID 事务：BEGIN、COMMIT、ROLLBACK
- 单文件磁盘持久化（页式存储 + 缓冲池）
- CLI/REPL 交互界面

**v0.2 新增功能：**
- 多表 JOIN 查询（INNER JOIN、LEFT JOIN、CROSS JOIN）
- 表别名（AS）和限定列名（table.column）
- 多线程并发控制（ReadWriteLock + 表级锁粒度）
- 线程安全的 BufferPool、Catalog、WAL
- ConnectionPool 连接池管理
- CLI readline 行编辑和历史
- SQL 语法高亮（ANSI 颜色码）
- EXPLAIN 执行计划查看
- .dump、.version、.mode 元命令

## Capabilities

### New Capabilities

**v0.1：**
- `sql-parser`: SQL 文本解析为 AST（lexer → parser → AST），支持 DDL/DML 语法
- `storage-engine`: 页式存储管理，单文件读写，缓冲池，文件管理器
- `query-executor`: 全表扫描 + 索引加速的查询计划与执行，支持过滤/排序/分页/聚合
- `btree-index`: 基于 B-tree 的索引结构，加速等值和范围查询
- `transaction-manager`: 基于 WAL 的 ACID 事务管理（BEGIN/COMMIT/ROLLBACK）
- `type-system`: INT/FLOAT/TEXT/BOOL 类型检查、存储与列约束（PK/NOT NULL/UNIQUE）
- `cli-repl`: 交互式 REPL，支持 SQL 输入和结果展示

**v0.2：**
- `join-query`: 多表 JOIN 查询（INNER/LEFT/CROSS JOIN、表别名、限定列名）
- `concurrency-control`: 并发控制（ReadWriteLock、表级锁、线程安全组件）
- `cli-enhancement`: CLI 增强（readline、语法高亮、EXPLAIN、新元命令）

### Modified Capabilities

**v0.2 修改：**
- `sql-parser`: 扩展支持 JOIN 语法、EXPLAIN、表别名、限定列名
- `query-executor`: 新增 NestedLoopJoin 算子、ExplainPlan
- `storage-engine`: BufferPool 线程安全化
- `transaction-manager`: WAL 写入锁、事务并发安全

## Impact

- 新增 Python 包 `tinydb`，零外部依赖
- 单一 `.tdb` 文件作为数据存储格式
- 用户通过 Python API（`db.execute()`）或 CLI 与数据库交互
- v0.2 新增 `concurrency.py`、`connection.py`、`executor/join.py`、`executor/explain.py` 四个模块
- v0.2 修改 `lexer.py`、`parser.py`、`ast_nodes.py`、`database.py`、`cli.py` 等 13 个模块
