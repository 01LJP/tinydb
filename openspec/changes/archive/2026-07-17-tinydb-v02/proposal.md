## Why

TinyDB v0.1 已实现基础的单表 SQL 查询、B-Tree 索引、WAL 事务和简单 REPL。但作为一个实用的嵌入式数据库，缺少三个关键能力：多表关联查询（无法连接相关数据）、并发安全（无法在多线程/多进程环境中使用）、以及基础 CLI 体验（无语法高亮、无执行计划查看）。v0.2 补齐这些核心能力，使 TinyDB 达到可实际使用的门槛。

## What Changes

- **多表 JOIN 查询**：支持 INNER JOIN、LEFT JOIN、CROSS JOIN，支持 ON 条件和表别名，支持限定列名（`t.col`）
- **并发控制**：引入读写锁机制，BufferPool 和 Catalog 线程安全化，支持多线程同时读取、写入串行化
- **CLI 功能增强**：集成 readline 行编辑和历史、SQL 语法高亮、`.explain` 执行计划查看、`.dump` 导出等新命令

## Capabilities

### New Capabilities
- `join-query`: 多表 JOIN 查询能力，包括 INNER/LEFT/CROSS JOIN、ON 条件、表别名、限定列名解析
- `concurrency-control`: 并发控制能力，包括读写锁、线程安全的 BufferPool/Catalog、连接管理
- `cli-enhancement`: CLI 增强能力，包括 readline 集成、语法高亮、EXPLAIN 执行计划、新元命令

### Modified Capabilities
- `sql-parser`: 扩展词法分析器和语法分析器以支持 JOIN 语法、EXPLAIN 关键字、表别名（AS）
- `query-executor`: 扩展执行器管线以支持嵌套循环 JOIN 操作符
- `storage-engine`: BufferPool 增加线程安全锁机制
- `transaction-manager`: 事务管理器适配并发场景

## Impact

- **代码影响**：`lexer.py`、`parser.py`、`ast_nodes.py`、`database.py`、`cli.py` 需要修改；新增 `join.py`、`concurrency.py`、`explain.py`、`connection.py`
- **API 影响**：`Database.execute()` 签名不变，内部增加锁管理；新增 `EXPLAIN` 语句支持
- **依赖**：CLI 增强依赖 Python 标准库 `readline`，无外部依赖
- **向后兼容**：所有 v0.1 SQL 语法保持兼容，JOIN 和 EXPLAIN 为纯增量功能
