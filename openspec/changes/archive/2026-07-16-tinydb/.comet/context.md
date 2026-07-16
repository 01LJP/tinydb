# Comet Design Handoff

- Change: tinydb
- Phase: design
- Mode: compact
- Context hash: 4af34e427280b039fd66a6ae70ff621b17932bdb44c5334679f6fb6b4cd3cc4c

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/tinydb/proposal.md

- Source: openspec/changes/tinydb/proposal.md
- Lines: 1-43
- SHA256: 12f8ade66e83ee34b7b959d56048b42db7864ab5e073a8affab8d84d5b6b0e31

```md
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

```

## openspec/changes/tinydb/design.md

- Source: openspec/changes/tinydb/design.md
- Lines: 1-94
- SHA256: 0f9993df14ce81e121fc69b2565d976392e242e3a3d3a3b6976b40207eb9e2d2

[TRUNCATED]

```md
## Context

tinydb 是一个从零构建的 Python 嵌入式关系型数据库，目标是用于学习数据库原理并作为可嵌入的 Python 库使用。项目零外部依赖，单文件持久化。

当前状态：从零开始，无现有代码基础。
约束：纯 Python 实现，零外部依赖，代码需简洁可读（教学目的）。

## Goals / Non-Goals

**Goals:**
- 提供完整的 SQL 接口（DDL/DML）
- 实现页式存储引擎 + 缓冲池
- 实现 B-tree 索引加速查询
- 实现基于 WAL 的 ACID 事务
- 提供交互式 CLI/REPL

**Non-Goals:**
- 多表 JOIN、并发控制、ALTER TABLE
- 视图、触发器、外键、网络模式
- 高性能优化（以可读性优先）

## Decisions

### D1: 事务实现 — WAL（Write-Ahead Logging）

**决策**: 使用 WAL 而非影子分页。

| 方案 | 优点 | 缺点 |
|------|------|------|
| WAL | 实现简洁，崩溃恢复直观（重放日志），适合教学 | 日志文件会增长 |
| 影子分页 | 恢复速度快 | 实现复杂，需要页面级拷贝 |

**理由**: WAL 实现更简洁，日志重放的崩溃恢复逻辑易于理解和教学。

### D2: 页大小 — 4KB

**决策**: 默认页大小 4096 字节。

**理由**: 与操作系统页大小一致，是数据库系统的通用默认值（SQLite、PostgreSQL 均使用 4KB）。

### D3: SQL 方言 — 类 SQLite

**决策**: 语法尽量兼容 SQLite。

**理由**: SQLite 是最广泛使用的嵌入式数据库，用户熟悉度高，文档丰富。

### D4: 数据类型 — 静态类型 + 灵活转换

**决策**: 支持 INT、FLOAT、TEXT、BOOL 四种基本类型，插入时进行类型检查。

**理由**: 覆盖绝大多数使用场景，类型安全避免数据不一致。

### D5: 架构分层

**决策**: 采用经典数据库分层架构：

```
┌─────────────────────────────────────────┐
│              CLI / REPL                  │
├─────────────────────────────────────────┤
│           SQL Interface                  │
│         (db.execute)                     │
├─────────────────────────────────────────┤
│  SQL Parser  │  Query Executor          │
│  (lexer/     │  (scan/sort/             │
│   parser)    │   aggregate)             │
├──────────────┼──────────────────────────┤
│  B-tree Index│  Type System             │
├──────────────┴──────────────────────────┤
│         Storage Engine                   │
│  (Page Manager + Buffer Pool + File I/O) │
├─────────────────────────────────────────┤
│       Transaction Manager (WAL)          │
└─────────────────────────────────────────┘
```

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|

```

Full source: openspec/changes/tinydb/design.md

## openspec/changes/tinydb/tasks.md

- Source: openspec/changes/tinydb/tasks.md
- Lines: 1-64
- SHA256: 1533a579d013be56414cada431ae1675876b0da8061de7ce52c6878e3e4512b2

```md
## 1. 项目初始化

- [ ] 1.1 创建项目目录结构（src/tinydb/、各子模块、tests/）
- [ ] 1.2 配置 setup.py（包名、入口点、零外部依赖）
- [ ] 1.3 创建 `__init__.py` 和 `Database` 类骨架（execute 接口）

## 2. 类型系统

- [ ] 2.1 实现 DataType 定义（INT、FLOAT、TEXT、BOOL）
- [ ] 2.2 实现类型检查与转换逻辑
- [ ] 2.3 实现列约束检查（PRIMARY KEY、NOT NULL、UNIQUE）

## 3. SQL 解析器

- [ ] 3.1 实现 Lexer（词法分析器，生成 token 流）
- [ ] 3.2 实现 Parser 基础结构（AST 节点定义）
- [ ] 3.3 实现 DDL 解析（CREATE TABLE、DROP TABLE）
- [ ] 3.4 实现 INSERT 解析
- [ ] 3.5 实现 SELECT 解析（WHERE、ORDER BY、LIMIT/OFFSET）
- [ ] 3.6 实现 UPDATE 和 DELETE 解析

## 4. 存储引擎

- [ ] 4.1 实现 Page 数据结构（4096 字节页）
- [ ] 4.2 实现 FileManager（单文件读写）
- [ ] 4.3 实现 BufferPool（页缓存 + LRU 淘汰 + 脏页回写）
- [ ] 4.4 实现 Record 序列化/反序列化
- [ ] 4.5 实现表数据页管理（插入、扫描记录）

## 5. 查询执行器

- [ ] 5.1 实现全表扫描（Sequential Scan）
- [ ] 5.2 实现 WHERE 条件过滤（AND/OR 支持）
- [ ] 5.3 实现 ORDER BY 排序
- [ ] 5.4 实现 LIMIT/OFFSET 分页
- [ ] 5.5 实现聚合函数（COUNT、SUM、AVG）
- [ ] 5.6 实现 GROUP BY

## 6. B-tree 索引

- [ ] 6.1 实现 B-tree 节点结构
- [ ] 6.2 实现 B-tree 插入
- [ ] 6.3 实现 B-tree 点查询（等值查找）
- [ ] 6.4 实现 B-tree 范围扫描
- [ ] 6.5 实现索引与存储引擎的集成（自动维护）

## 7. 事务管理器

- [ ] 7.1 实现 WAL 日志格式与写入
- [ ] 7.2 实现 BEGIN / COMMIT / ROLLBACK
- [ ] 7.3 实现崩溃恢复（WAL 重放）
- [ ] 7.4 实现事务与执行器的集成

## 8. CLI/REPL

- [ ] 8.1 实现交互式 REPL 循环
- [ ] 8.2 实现结果表格格式化输出
- [ ] 8.3 实现多行输入支持（分号终止）

## 9. 集成与测试

- [ ] 9.1 编写各模块单元测试
- [ ] 9.2 编写端到端集成测试
- [ ] 9.3 验证完整工作流（创建表→插入→查询→事务→持久化）

```

## openspec/changes/tinydb/specs/btree-index/spec.md

- Source: openspec/changes/tinydb/specs/btree-index/spec.md
- Lines: 1-33
- SHA256: 4589cfa0a42e1c1ea80a3244282679094da4c33c0958ed9886bd120e98eecb53

```md
## ADDED Requirements

### Requirement: B-tree index creation
The system SHALL create a B-tree index on a specified table column.

#### Scenario: Create index on column
- **WHEN** an index is created on column `id` of table `users`
- **THEN** a B-tree structure is built containing all existing values from that column

### Requirement: Index-accelerated equality lookup
The system SHALL use B-tree index for equality queries when available.

#### Scenario: Point query via index
- **WHEN** executing `SELECT * FROM users WHERE id = 42` and an index on `id` exists
- **THEN** the system uses the B-tree to locate the row without full table scan

### Requirement: Index-accelerated range query
The system SHALL use B-tree index for range queries (>, <, >=, <=).

#### Scenario: Range query via index
- **WHEN** executing `SELECT * FROM users WHERE age >= 18 AND age <= 30` and an index on `age` exists
- **THEN** the system uses B-tree range scan to find matching rows

### Requirement: Index maintenance on data changes
The system SHALL automatically update indexes when data is inserted or deleted.

#### Scenario: Index updated on INSERT
- **WHEN** inserting a new row into a table with an index
- **THEN** the B-tree is updated to include the new value

#### Scenario: Index updated on DELETE
- **WHEN** deleting a row from a table with an index
- **THEN** the B-tree is updated to remove the corresponding entry

```

## openspec/changes/tinydb/specs/cli-repl/spec.md

- Source: openspec/changes/tinydb/specs/cli-repl/spec.md
- Lines: 1-30
- SHA256: 97bc9c446ec964b9662194b3fcdd987b18da5024f32f071bec6bb3ba073f885d

```md
## ADDED Requirements

### Requirement: Interactive REPL
The system SHALL provide an interactive Read-Eval-Print Loop for executing SQL.

#### Scenario: Start REPL
- **WHEN** running the tinydb CLI command
- **THEN** an interactive prompt appears accepting SQL input

#### Scenario: Execute SQL in REPL
- **WHEN** user types `SELECT * FROM users;` in the REPL
- **THEN** the system executes the query and displays results

### Requirement: Result display
The system SHALL display query results in a readable tabular format.

#### Scenario: Display SELECT results
- **WHEN** executing a SELECT query returning multiple rows
- **THEN** results are displayed as a formatted table with column headers

#### Scenario: Display confirmation for DML
- **WHEN** executing INSERT, UPDATE, or DELETE
- **THEN** the system shows the number of affected rows

### Requirement: Multi-line input
The system SHALL support SQL statements spanning multiple lines (terminated by semicolon).

#### Scenario: Multi-line query
- **WHEN** user enters a query across multiple lines ending with `;`
- **THEN** the system treats the entire input as one statement

```

## openspec/changes/tinydb/specs/query-executor/spec.md

- Source: openspec/changes/tinydb/specs/query-executor/spec.md
- Lines: 1-60
- SHA256: 10064bbf369299bc48c49b3c9509cbd07332a1cb9e50fb883318e645bae5f7ac

```md
## ADDED Requirements

### Requirement: Full table scan
The system SHALL support scanning all records in a table.

#### Scenario: SELECT all columns
- **WHEN** executing `SELECT * FROM users`
- **THEN** the executor returns all rows from the users table

#### Scenario: SELECT specific columns
- **WHEN** executing `SELECT name, age FROM users`
- **THEN** the executor returns only the name and age columns

### Requirement: WHERE clause filtering
The system SHALL filter rows based on WHERE conditions with AND/OR.

#### Scenario: Equality filter
- **WHEN** executing `SELECT * FROM users WHERE id = 1`
- **THEN** only rows where id equals 1 are returned

#### Scenario: AND condition
- **WHEN** executing `SELECT * FROM users WHERE age > 18 AND name = 'Alice'`
- **THEN** only rows matching both conditions are returned

#### Scenario: OR condition
- **WHEN** executing `SELECT * FROM users WHERE age < 18 OR age > 60`
- **THEN** rows matching either condition are returned

### Requirement: ORDER BY sorting
The system SHALL sort results by specified columns.

#### Scenario: Ascending order
- **WHEN** executing `SELECT * FROM users ORDER BY age`
- **THEN** results are sorted by age ascending

#### Scenario: Descending order
- **WHEN** executing `SELECT * FROM users ORDER BY age DESC`
- **THEN** results are sorted by age descending

### Requirement: LIMIT and OFFSET
The system SHALL support pagination via LIMIT and OFFSET.

#### Scenario: LIMIT only
- **WHEN** executing `SELECT * FROM users LIMIT 10`
- **THEN** at most 10 rows are returned

#### Scenario: LIMIT with OFFSET
- **WHEN** executing `SELECT * FROM users LIMIT 5 OFFSET 10`
- **THEN** rows 11-15 are returned

### Requirement: Aggregate functions
The system SHALL support COUNT, SUM, AVG with optional GROUP BY.

#### Scenario: COUNT all rows
- **WHEN** executing `SELECT COUNT(*) FROM users`
- **THEN** a single row with the total count is returned

#### Scenario: GROUP BY with aggregate
- **WHEN** executing `SELECT department, AVG(salary) FROM employees GROUP BY department`
- **THEN** each department with its average salary is returned

```

## openspec/changes/tinydb/specs/sql-parser/spec.md

- Source: openspec/changes/tinydb/specs/sql-parser/spec.md
- Lines: 1-34
- SHA256: ed47c1cf6b07126cf4a1c65bd2b301c06ce6b3901978ae29c688191333f5c77e

```md
## ADDED Requirements

### Requirement: Lexer tokenizes SQL input
The SQL lexer SHALL break input string into a stream of tokens (keywords, identifiers, literals, operators, punctuation).

#### Scenario: Tokenize a SELECT statement
- **WHEN** input is `SELECT name FROM users WHERE id = 1`
- **THEN** lexer produces tokens: [SELECT, name, FROM, users, WHERE, id, =, 1]

#### Scenario: Tokenize string literals
- **WHEN** input contains `'hello world'`
- **THEN** lexer produces a single TEXT_LITERAL token with value `hello world`

### Requirement: Parser builds AST from tokens
The SQL parser SHALL construct an Abstract Syntax Tree from the token stream.

#### Scenario: Parse CREATE TABLE
- **WHEN** input is `CREATE TABLE users (id INT, name TEXT)`
- **THEN** parser produces a CreateTable AST node with table name `users` and column definitions

#### Scenario: Parse INSERT
- **WHEN** input is `INSERT INTO users VALUES (1, 'Alice')`
- **THEN** parser produces an Insert AST node with values list

#### Scenario: Parse SELECT with clauses
- **WHEN** input is `SELECT name FROM users WHERE id > 1 ORDER BY name LIMIT 10`
- **THEN** parser produces a Select AST node with projection, source, where, order by, and limit fields

### Requirement: Parser reports syntax errors
The parser SHALL raise a clear error message when SQL syntax is invalid.

#### Scenario: Missing FROM clause
- **WHEN** input is `SELECT name`
- **THEN** parser raises error indicating missing FROM clause

```

## openspec/changes/tinydb/specs/storage-engine/spec.md

- Source: openspec/changes/tinydb/specs/storage-engine/spec.md
- Lines: 1-38
- SHA256: e056696d9e1362c2d5317c14200fd8d9d64a1d8ae00391055f77c4b997eab0e8

```md
## ADDED Requirements

### Requirement: Page-based file storage
The system SHALL store data in fixed-size pages (4096 bytes) within a single database file.

#### Scenario: Create new database file
- **WHEN** opening a non-existent database path
- **THEN** system creates a new file with initial page allocation

#### Scenario: Read and write pages
- **WHEN** writing data to page N then reading page N
- **THEN** the read returns the exact bytes previously written

### Requirement: Buffer pool management
The system SHALL maintain a page buffer pool to reduce disk I/O.

#### Scenario: Cache frequently accessed pages
- **WHEN** reading the same page multiple times
- **THEN** subsequent reads are served from cache without disk access

#### Scenario: Evict least-recently-used pages
- **WHEN** buffer pool is full and a new page is requested
- **THEN** the system evicts the least-recently-used page to make room

#### Scenario: Dirty page write-back
- **WHEN** a modified (dirty) page is evicted or checkpoint occurs
- **THEN** the system writes the dirty page to disk

### Requirement: Table data organization
The system SHALL store table records within pages, supporting variable-length records.

#### Scenario: Insert record into table
- **WHEN** a new record is inserted
- **THEN** the system places it in the first page with sufficient free space

#### Scenario: Read all records from table
- **WHEN** scanning a table
- **THEN** the system reads all pages belonging to that table and returns records

```

## openspec/changes/tinydb/specs/transaction-manager/spec.md

- Source: openspec/changes/tinydb/specs/transaction-manager/spec.md
- Lines: 1-44
- SHA256: 4370e96ee56f8e047b6f7fccf09c3f8c8dd8e2961b663dc83cd94091c2ff8e05

```md
## ADDED Requirements

### Requirement: Transaction begin
The system SHALL support starting a new transaction with BEGIN.

#### Scenario: Start transaction
- **WHEN** executing `BEGIN`
- **THEN** a new transaction is started and subsequent operations are part of it

### Requirement: Transaction commit
The system SHALL support committing a transaction with COMMIT, making all changes permanent.

#### Scenario: Commit transaction
- **WHEN** inserting rows then executing `COMMIT`
- **THEN** the inserted rows are persisted and visible to other connections

### Requirement: Transaction rollback
The system SHALL support rolling back a transaction with ROLLBACK, undoing all changes.

#### Scenario: Rollback after insert
- **WHEN** inserting rows then executing `ROLLBACK`
- **THEN** the inserted rows are not persisted

#### Scenario: Rollback after update
- **WHEN** updating rows then executing `ROLLBACK`
- **THEN** the rows retain their original values

### Requirement: WAL-based crash recovery
The system SHALL use Write-Ahead Logging to ensure durability and support crash recovery.

#### Scenario: Recover committed transactions after crash
- **WHEN** the system restarts after a crash with committed transactions in WAL
- **THEN** all committed changes are preserved

#### Scenario: Discard uncommitted transactions after crash
- **WHEN** the system restarts after a crash with uncommitted transactions in WAL
- **THEN** uncommitted changes are not applied

### Requirement: ACID properties
The system SHALL guarantee Atomicity, Consistency, Isolation (serializable single-connection), and Durability.

#### Scenario: Atomicity — all or nothing
- **WHEN** a transaction with multiple operations is rolled back
- **THEN** none of the operations take effect

```

## openspec/changes/tinydb/specs/type-system/spec.md

- Source: openspec/changes/tinydb/specs/type-system/spec.md
- Lines: 1-44
- SHA256: 01b37aafb2beef410a40359988ce01be8caccc673b59d004993713b014664f0a

```md
## ADDED Requirements

### Requirement: Basic data types
The system SHALL support INT, FLOAT, TEXT, and BOOL data types.

#### Scenario: Store and retrieve each type
- **WHEN** creating a table with columns of types INT, FLOAT, TEXT, BOOL and inserting values
- **THEN** each value is stored and retrieved with its correct type

### Requirement: Type checking on INSERT
The system SHALL validate that inserted values match the column's declared type.

#### Scenario: Reject type mismatch
- **WHEN** inserting a TEXT value into an INT column
- **THEN** the system raises a type error

#### Scenario: Accept valid type
- **WHEN** inserting an INT value into an INT column
- **THEN** the insert succeeds

### Requirement: PRIMARY KEY constraint
The system SHALL enforce uniqueness and non-null for PRIMARY KEY columns.

#### Scenario: Reject duplicate primary key
- **WHEN** inserting a row with a primary key value that already exists
- **THEN** the system raises a constraint violation error

#### Scenario: Reject null primary key
- **WHEN** inserting a row with NULL primary key
- **THEN** the system raises a constraint violation error

### Requirement: NOT NULL constraint
The system SHALL reject NULL values for columns declared NOT NULL.

#### Scenario: Reject null in NOT NULL column
- **WHEN** inserting NULL into a NOT NULL column
- **THEN** the system raises a constraint violation error

### Requirement: UNIQUE constraint
The system SHALL enforce uniqueness for columns declared UNIQUE.

#### Scenario: Reject duplicate in UNIQUE column
- **WHEN** inserting a duplicate value into a UNIQUE column
- **THEN** the system raises a constraint violation error

```
