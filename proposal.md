## Why

需要一个轻量级嵌入式关系型数据库，既能通过造轮子深入理解数据库核心原理（存储引擎、SQL 解析、查询优化、索引、事务），又能作为可嵌入的 Python 库在实际项目中使用。现有方案中 SQLite 过于庞大复杂不适合学习拆解，而 Python 生态中缺乏一个简洁、可读、可教学的嵌入式关系型数据库实现。

## What Changes

从零构建一个 Python 嵌入式关系型数据库 `tinydb`：

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

## Capabilities

### New Capabilities

- `sql-parser`: SQL 文本解析为 AST（lexer → parser → AST），支持 DDL/DML 语法
- `storage-engine`: 页式存储管理，单文件读写，缓冲池，文件管理器
- `query-executor`: 全表扫描 + 索引加速的查询计划与执行，支持过滤/排序/分页/聚合
- `btree-index`: 基于 B-tree 的索引结构，加速等值和范围查询
- `transaction-manager`: 基于 WAL 的 ACID 事务管理（BEGIN/COMMIT/ROLLBACK）
- `type-system`: INT/FLOAT/TEXT/BOOL 类型检查、存储与列约束（PK/NOT NULL/UNIQUE）
- `cli-repl`: 交互式 REPL，支持 SQL 输入和结果展示

### Modified Capabilities

（无）

## Impact

- 新增 Python 包 `tinydb`，零外部依赖
- 单一 `.db` 文件作为数据存储格式
- 用户通过 Python API（`db.execute()`）或 CLI 与数据库交互
- 影响范围限于 `tinydb` 项目目录内
