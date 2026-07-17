# Comet Design Handoff

- Change: tinydb-v02
- Phase: design
- Mode: compact
- Context hash: ba9a4861776b0941830f1d4892efd5df17d0c683043d2e141c3ce4bb6affb996

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/tinydb-v02/proposal.md

- Source: openspec/changes/tinydb-v02/proposal.md
- Lines: 1-29
- SHA256: ff84e10d4b32a6cb52cce04e3f5b7219534cf1b766f3aaee04072bf657370b6d

```md
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

```

## openspec/changes/tinydb-v02/design.md

- Source: openspec/changes/tinydb-v02/design.md
- Lines: 1-90
- SHA256: bf8145fef52804864c925d03e9a5c50a338e89a4ad21369f5881145b1ce88972

[TRUNCATED]

```md
## Context

TinyDB v0.1 实现了完整的单表 SQL 查询管线：Lexer → Parser → AST → PlanSelector → SeqScan → Filter → Sort → Aggregate → Limit。存储层基于页式文件管理 + LRU BufferPool，事务层基于 WAL。所有组件均非线程安全，仅支持单连接串行执行。

v0.2 需要在此基础上增量添加三个能力，不改变现有架构的核心设计。

## Goals / Non-Goals

**Goals:**
- 支持 INNER JOIN、LEFT JOIN、CROSS JOIN 的多表关联查询
- 支持多线程并发读写，读操作并行、写操作串行
- CLI 支持 readline 行编辑、语法高亮、EXPLAIN 执行计划
- 所有 v0.1 功能和 SQL 语法保持向后兼容

**Non-Goals:**
- 不实现 RIGHT JOIN / FULL OUTER JOIN（优先级低，可后续版本添加）
- 不实现基于锁的事务隔离级别（MVCC 等）
- 不实现分布式/网络访问
- 不实现索引扫描优化（JOIN 场景仍使用全表扫描）
- 不添加外部依赖（仅使用 Python 标准库）

## Decisions

### Decision 1: JOIN 实现 — 嵌套循环连接（Nested-Loop Join）

**选择**: 使用嵌套循环连接算法，将右表物化后逐行与左表匹配。

**理由**: TinyDB 是教学型嵌入式数据库，数据量小，嵌套循环连接实现简单、正确性高。排序合并连接（Sort-Merge Join）和哈希连接（Hash Join）需要更复杂的内存管理和排序逻辑，投入产出比不高。

**替代方案**: 哈希连接 — 性能更好但实现复杂，需要哈希表构建和探查，对教学数据库过度设计。

**输出列名策略**: JOIN 结果的列名使用 `table.column` 限定格式（如 `users.id`、`orders.amount`），避免多表列名冲突。当无歧义时也支持不带表名前缀的列引用。

### Decision 2: JOIN 在执行器管线中的位置

**选择**: JOIN 作为独立的执行器算子，插入在 SeqScan 之后、Filter 之前。

**管线**: `SeqScan(左表) → NestedLoopJoin(右表, ON条件) → Filter(WHERE) → Sort → Limit`

**理由**: 保持现有执行器管线的组合式设计。每个算子仍是迭代器（`__iter__`），JOIN 算子消费左表行流，对每行扫描右表并合并。

**多表链式 JOIN**: 多个 JOIN 通过链式组合实现：`Scan(t1) → Join(t2) → Join(t3) → ...`

### Decision 3: 并发控制 — 读写锁 + 表级粒度

**选择**: 实现 `ReadWriteLock`（多读单写锁），以表为粒度管理锁。

**锁策略**:
- SELECT: 获取相关表的读锁（共享）
- INSERT/UPDATE/DELETE: 获取目标表的写锁（排他）
- DDL (CREATE/DROP): 获取全局写锁
- BEGIN/COMMIT/ROLLBACK: 获取全局写锁

**理由**: 表级锁粒度适中，实现简单。行级锁虽然并发度更高但需要死锁检测，对教学数据库过度设计。数据库级锁并发度太低。

**线程安全组件**:
- `BufferPool`: 所有方法加 `threading.Lock`
- `Catalog`: 使用 `threading.RLock`（递归锁，因为 `_save` 可能被 `create_table` 等方法间接递归调用）
- `WAL`: 写入操作加锁

### Decision 4: CLI 增强 — 纯标准库实现

**选择**: 使用 Python 标准库 `readline` 实现行编辑和历史，使用 ANSI 转义码实现语法高亮，不引入 `pygments` 等外部依赖。

**语法高亮方案**: 在输入回显时对 SQL 关键字应用 ANSI 颜色码。使用简单的正则匹配替换，不依赖完整的语法高亮引擎。

**EXPLAIN 实现**: 新增 `Explain` AST 节点，Parser 识别 `EXPLAIN SELECT ...` 语句。执行时不实际运行查询，而是构建执行计划树并格式化输出算子名称和参数。

### Decision 5: 工作区隔离 — git worktree

**选择**: 使用 git worktree 为每个功能模块创建隔离的工作分支，并行开发后合并。

**分支规划**:
- `feature/join` — JOIN 查询功能
- `feature/concurrency` — 并发控制
- `feature/cli` — CLI 增强

**合并顺序**: `join` → `concurrency` → `cli`（JOIN 改动基础层，并发添加横切关注点，CLI 依赖所有前序功能）

## Risks / Trade-offs

```

Full source: openspec/changes/tinydb-v02/design.md

## openspec/changes/tinydb-v02/tasks.md

- Source: openspec/changes/tinydb-v02/tasks.md
- Lines: 1-74
- SHA256: 657ad0a6b8f810fec64df20c66a15870ec271aa2eb3b23b3724bedd608c5ea70

```md
## 1. 基础层扩展（词法/语法/AST）

- [ ] 1.1 lexer.py 添加 JOIN 相关关键字：JOIN、INNER、LEFT、RIGHT、CROSS、FULL、ON、AS、EXPLAIN
- [ ] 1.2 ast_nodes.py 添加 JoinClause、TableRef、Explain AST 节点，修改 Select 添加 joins/tables 字段
- [ ] 1.3 ast_nodes.py 修改 ColumnRef 支持 table 属性（限定列名）
- [ ] 1.4 parser.py 实现 _parse_from_clause() 解析 FROM 表名、表别名
- [ ] 1.5 parser.py 实现 _parse_join() 解析 JOIN/LEFT JOIN/CROSS JOIN + ON 条件
- [ ] 1.6 parser.py 实现限定列名解析（table.column → ColumnRef(table, name)）
- [ ] 1.7 parser.py 实现 EXPLAIN 语句解析
- [ ] 1.8 types.py 添加 JoinError 异常类

## 2. JOIN 执行器实现

- [ ] 2.1 executor/join.py 实现 NestedLoopJoin 算子（INNER/LEFT/CROSS 三种模式）
- [ ] 2.2 executor/scan.py 修改 SeqScan 输出列名带表前缀（table.column 格式）
- [ ] 2.3 executor/filter.py 修改 _eval() 支持限定列名解析
- [ ] 2.4 executor/plan.py PlanSelector 支持 JOIN 查询的多表扫描管线构建
- [ ] 2.5 executor/__init__.py 导出新增的 Join 算子
- [ ] 2.6 database.py 修改 _exec_select() 处理 JOIN 查询管线组装
- [ ] 2.7 database.py 修改 _exec_select() 处理 SELECT 列表中的限定列名

## 3. JOIN 测试

- [ ] 3.1 tests/test_join.py 编写 INNER JOIN 基本测试
- [ ] 3.2 tests/test_join.py 编写 LEFT JOIN 测试（含无匹配行 NULL 填充）
- [ ] 3.3 tests/test_join.py 编写 CROSS JOIN 测试
- [ ] 3.4 tests/test_join.py 编写表别名测试
- [ ] 3.5 tests/test_join.py 编写多表（3+）链式 JOIN 测试
- [ ] 3.6 tests/test_join.py 编写 JOIN + WHERE + 聚合组合测试
- [ ] 3.7 运行全部测试确认 JOIN 功能正确且不影响现有功能

## 4. 并发控制实现

- [ ] 4.1 concurrency.py 实现 ReadWriteLock（多读单写锁）
- [ ] 4.2 concurrency.py 实现 LockManager（表级锁管理 + 全局锁）
- [ ] 4.3 storage/buffer_pool.py 所有公共方法加 threading.Lock 保护
- [ ] 4.4 catalog.py 使用 threading.RLock 保护元数据读写
- [ ] 4.5 transaction/wal.py WAL 写入操作加锁保证原子性
- [ ] 4.6 database.py execute() 方法根据语句类型获取相应锁
- [ ] 4.7 connection.py 实现 ConnectionPool 和 Connection 类

## 5. 并发测试

- [ ] 5.1 tests/test_concurrency.py 编写多线程并发 SELECT 测试
- [ ] 5.2 tests/test_concurrency.py 编写写操作阻塞读操作测试
- [ ] 5.3 tests/test_concurrency.py 编写并发 INSERT 串行化测试
- [ ] 5.4 tests/test_concurrency.py 编写不同表并发写测试
- [ ] 5.5 tests/test_concurrency.py 编写 ConnectionPool 生命周期测试
- [ ] 5.6 运行全部测试确认并发功能正确且不引入死锁

## 6. CLI 增强实现

- [ ] 6.1 cli.py 集成 readline：行编辑、历史持久化、Tab 补全
- [ ] 6.2 cli.py 实现 SQL 语法高亮（ANSI 颜色码）
- [ ] 6.3 cli.py 实现多行输入续行提示符改进
- [ ] 6.4 executor/explain.py 实现 ExplainPlan 执行计划构建和格式化输出
- [ ] 6.5 cli.py 实现 .explain 元命令（调用 ExplainPlan）
- [ ] 6.6 cli.py 实现 .dump 元命令（导出 SQL）
- [ ] 6.7 cli.py 实现 .version 元命令
- [ ] 6.8 cli.py 实现 .mode 元命令（table/csv 切换）

## 7. CLI 测试与集成测试

- [ ] 7.1 tests/test_cli.py 编写 EXPLAIN 执行计划输出测试
- [ ] 7.2 tests/test_cli.py 编写 .dump 导出测试
- [ ] 7.3 tests/test_cli.py 编写 .version 和 .mode 测试
- [ ] 7.4 tests/test_e2e.py 编写 v0.2 端到端集成测试（JOIN + 并发 + CLI）
- [ ] 7.5 运行全量测试套件，确保所有 v0.1 测试仍然通过

## 8. 文档与收尾

- [ ] 8.1 更新 README.md 反映 v0.2 新功能
- [ ] 8.2 更新 openspec/specs/ 目录下的主规格文件（合并 delta specs）
- [ ] 8.3 清理 mydb.tdb 等运行时文件，更新 .gitignore

```

## openspec/changes/tinydb-v02/specs/cli-enhancement/spec.md

- Source: openspec/changes/tinydb-v02/specs/cli-enhancement/spec.md
- Lines: 1-90
- SHA256: b5a900183c2c40daf9cced8e7d21f8bc8ecda668f6b5aa5a631a6918c4170dfe

[TRUNCATED]

```md
## ADDED Requirements

### Requirement: readline 行编辑
系统 SHALL 集成 readline 库，支持行编辑、历史命令和 Tab 补全。

#### Scenario: 历史命令导航
- **WHEN** 用户按上箭头键
- **THEN** 显示上一条历史命令

#### Scenario: Tab 补全 SQL 关键字
- **WHEN** 用户输入 `SEL` 并按 Tab
- **THEN** 补全为 `SELECT`

#### Scenario: Tab 补全表名
- **WHEN** 用户输入 `SELECT * FROM ` 并按 Tab
- **THEN** 显示已创建的表名列表

#### Scenario: 历史持久化
- **WHEN** 用户退出 CLI 并重新启动
- **THEN** 之前的命令历史仍然可用

### Requirement: SQL 语法高亮
系统 SHALL 在用户输入 SQL 时实时显示语法高亮。

#### Scenario: 关键字高亮
- **WHEN** 用户输入 `SELECT * FROM users`
- **THEN** `SELECT`、`FROM` 以蓝色粗体显示

#### Scenario: 字符串高亮
- **WHEN** 用户输入 `WHERE name = 'Alice'`
- **THEN** `'Alice'` 以绿色显示

#### Scenario: 数字高亮
- **WHEN** 用户输入 `WHERE age > 25`
- **THEN** `25` 以黄色显示

### Requirement: .explain 执行计划查看
系统 SHALL 支持 EXPLAIN 关键字和 .explain 元命令，显示 SQL 的执行计划。

#### Scenario: EXPLAIN SELECT
- **WHEN** 执行 `EXPLAIN SELECT * FROM users WHERE id = 1`
- **THEN** 输出执行计划树，显示 SeqScan、Filter 等算子及参数

#### Scenario: EXPLAIN JOIN
- **WHEN** 执行 `EXPLAIN SELECT * FROM users JOIN orders ON users.id = orders.user_id`
- **THEN** 输出包含 NestedLoopJoin 算子的执行计划

#### Scenario: .explain 元命令
- **WHEN** 用户输入 `.explain SELECT * FROM users`
- **THEN** 与 `EXPLAIN SELECT * FROM users` 行为相同

### Requirement: .dump 导出
系统 SHALL 支持 .dump 元命令，导出数据库的 SQL 重建语句。

#### Scenario: .dump 输出
- **WHEN** 用户执行 `.dump`
- **THEN** 输出所有表的 CREATE TABLE 语句和 INSERT 语句

#### Scenario: .dump 指定表
- **WHEN** 用户执行 `.dump users`
- **THEN** 只输出 users 表的 CREATE TABLE 和 INSERT 语句

### Requirement: .version 版本信息
系统 SHALL 支持 .version 元命令，显示 TinyDB 版本信息。

#### Scenario: .version 输出
- **WHEN** 用户执行 `.version`
- **THEN** 显示 `TinyDB v0.2.0`

### Requirement: .mode 输出格式
系统 SHALL 支持 .mode 元命令，切换查询结果的输出格式。

#### Scenario: 切换到 CSV 模式
- **WHEN** 用户执行 `.mode csv`
- **THEN** 后续查询结果以 CSV 格式输出

#### Scenario: 切换到默认表格模式
- **WHEN** 用户执行 `.mode table`
- **THEN** 后续查询结果以 ASCII 表格格式输出


```

Full source: openspec/changes/tinydb-v02/specs/cli-enhancement/spec.md

## openspec/changes/tinydb-v02/specs/concurrency-control/spec.md

- Source: openspec/changes/tinydb-v02/specs/concurrency-control/spec.md
- Lines: 1-71
- SHA256: 94e4063cbbd61a6ae9184cdd69f060eebcd073221829dd32f561f89e808584cc

```md
## ADDED Requirements

### Requirement: 读写锁机制
系统 SHALL 实现 ReadWriteLock，支持多读者并发、单写者排他。

#### Scenario: 多线程并发读
- **WHEN** 多个线程同时执行 SELECT 查询
- **THEN** 所有读操作并行执行，不互相阻塞

#### Scenario: 写操作阻塞读
- **WHEN** 一个线程正在执行 INSERT，另一个线程尝试 SELECT 同一表
- **THEN** 读操作等待写操作完成后才执行

#### Scenario: 写操作串行化
- **WHEN** 多个线程同时执行 INSERT/UPDATE/DELETE 同一表
- **THEN** 写操作串行执行，不发生数据竞争

### Requirement: 表级锁粒度
系统 SHALL 以表为粒度管理锁，不同表的写操作可以并发。

#### Scenario: 不同表并发写
- **WHEN** 线程 A 写入表 X，线程 B 写入表 Y
- **THEN** 两个写操作并发执行，不互相阻塞

#### Scenario: 同一表写冲突
- **WHEN** 线程 A 写入表 X，线程 B 同时写入表 X
- **THEN** 一个写操作等待另一个完成

### Requirement: BufferPool 线程安全
系统 SHALL 使 BufferPool 的所有公共方法线程安全。

#### Scenario: 并发 get_page
- **WHEN** 多个线程同时调用 `buffer_pool.get_page()`
- **THEN** 不发生数据竞争，返回正确的 Page 对象

#### Scenario: 并发 mark_dirty
- **WHEN** 多个线程同时标记不同页面为脏
- **THEN** 脏页集合正确更新，无竞态条件

#### Scenario: flush_all 与 get_page 并发
- **WHEN** 一个线程执行 flush_all，另一个线程读取页面
- **THEN** 不发生数据损坏

### Requirement: Catalog 线程安全
系统 SHALL 使 Catalog 的元数据操作线程安全。

#### Scenario: 并发 create_table
- **WHEN** 多个线程同时创建不同表
- **THEN** 各表正确创建，元数据一致

#### Scenario: 读写并发
- **WHEN** 一个线程读取 catalog，另一个线程创建表
- **THEN** 读操作看到一致的快照

### Requirement: WAL 写入串行化
系统 SHALL 保证 WAL 日志写入的原子性和顺序性。

#### Scenario: 并发事务写 WAL
- **WHEN** 多个事务同时提交
- **THEN** WAL 记录按提交顺序写入，不交错

### Requirement: 连接管理
系统 SHALL 支持多线程通过同一 Database 实例并发执行 SQL。

#### Scenario: 多线程共享 Database
- **WHEN** 创建一个 Database 实例，多个线程分别调用 execute()
- **THEN** 所有操作正确执行，无数据损坏

#### Scenario: 连接池复用
- **WHEN** 使用 ConnectionPool 管理多个连接
- **THEN** 连接可以复用，超过上限时等待

```

## openspec/changes/tinydb-v02/specs/join-query/spec.md

- Source: openspec/changes/tinydb-v02/specs/join-query/spec.md
- Lines: 1-78
- SHA256: cc11e973c861fde9351cac90ae0a8cf0d8a9f0095d90579943117e50a72f28ac

```md
## ADDED Requirements

### Requirement: INNER JOIN 查询
系统 SHALL 支持 INNER JOIN 语法，返回两表中满足 ON 条件的匹配行。

#### Scenario: 基本 INNER JOIN
- **WHEN** 执行 `SELECT * FROM users INNER JOIN orders ON users.id = orders.user_id`
- **THEN** 返回 users.id = orders.user_id 的所有匹配行，列名使用 `table.column` 格式

#### Scenario: INNER JOIN 无匹配行
- **WHEN** 两表中无满足 ON 条件的行
- **THEN** 返回空结果集

#### Scenario: INNER JOIN 省略 INNER 关键字
- **WHEN** 执行 `SELECT * FROM users JOIN orders ON users.id = orders.user_id`
- **THEN** 行为等同于 INNER JOIN

### Requirement: LEFT JOIN 查询
系统 SHALL 支持 LEFT JOIN 语法，返回左表所有行，右表无匹配时填充 NULL。

#### Scenario: LEFT JOIN 有匹配
- **WHEN** 执行 `SELECT * FROM users LEFT JOIN orders ON users.id = orders.user_id`
- **THEN** 返回左表所有行，右表匹配列填充对应值

#### Scenario: LEFT JOIN 无匹配
- **WHEN** 左表某行在右表中无匹配
- **THEN** 该行的右表列全部填充 NULL

#### Scenario: LEFT JOIN 多表
- **WHEN** 执行 `SELECT * FROM t1 LEFT JOIN t2 ON ... LEFT JOIN t3 ON ...`
- **THEN** 链式 LEFT JOIN 正确保留所有左表行

### Requirement: CROSS JOIN 查询
系统 SHALL 支持 CROSS JOIN 语法，返回两表的笛卡尔积。

#### Scenario: CROSS JOIN 结果行数
- **WHEN** 左表有 m 行，右表有 n 行
- **THEN** CROSS JOIN 返回 m * n 行

#### Scenario: CROSS JOIN 省略 ON 条件
- **WHEN** 执行 `SELECT * FROM t1 CROSS JOIN t2`
- **THEN** 不需要 ON 子句，返回笛卡尔积

### Requirement: 表别名支持
系统 SHALL 支持使用 AS 关键字为表指定别名，并在查询中使用别名引用列。

#### Scenario: 使用 AS 定义别名
- **WHEN** 执行 `SELECT * FROM users AS u JOIN orders AS o ON u.id = o.user_id`
- **THEN** 可以使用 `u.id`、`o.amount` 等别名限定列名

#### Scenario: 无歧义列名省略表前缀
- **WHEN** 列名在 JOIN 结果中无歧义
- **THEN** 可以直接使用列名不带表前缀

### Requirement: 限定列名解析
系统 SHALL 在 WHERE 子句和 SELECT 列表中支持 `table.column` 格式的限定列名。

#### Scenario: WHERE 中使用限定列名
- **WHEN** 执行 `SELECT * FROM users JOIN orders ON users.id = orders.user_id WHERE users.name = 'Alice'`
- **THEN** WHERE 条件正确使用 `users.name` 限定列名过滤

#### Scenario: SELECT 列表使用限定列名
- **WHEN** 执行 `SELECT users.name, orders.amount FROM users JOIN orders ON users.id = orders.user_id`
- **THEN** 结果只包含指定的限定列

### Requirement: 多表 JOIN 链式组合
系统 SHALL 支持 3 个及以上表的链式 JOIN。

#### Scenario: 三表 INNER JOIN
- **WHEN** 执行 `SELECT * FROM t1 JOIN t2 ON t1.id = t2.t1_id JOIN t3 ON t2.id = t3.t2_id`
- **THEN** 返回三表关联的匹配结果

### Requirement: JOIN 与聚合函数组合
系统 SHALL 支持在 JOIN 查询中使用 GROUP BY 和聚合函数。

#### Scenario: JOIN + GROUP BY + COUNT
- **WHEN** 执行 `SELECT users.name, COUNT(orders.id) FROM users LEFT JOIN orders ON users.id = orders.user_id GROUP BY users.name`
- **THEN** 按用户名分组统计订单数量

```

## openspec/changes/tinydb-v02/specs/query-executor/spec.md

- Source: openspec/changes/tinydb-v02/specs/query-executor/spec.md
- Lines: 1-43
- SHA256: 088a9b486e9bcc67bfb0ea9218bea43a2584e8dae34f15607ca93b3e7ded1f5f

```md
## ADDED Requirements

### Requirement: NestedLoopJoin 执行算子
系统 SHALL 实现 NestedLoopJoin 算子，支持 INNER JOIN、LEFT JOIN 和 CROSS JOIN 的嵌套循环连接。

#### Scenario: INNER JOIN 执行
- **WHEN** Pipeline 为 SeqScan(t1) → NestedLoopJoin(t2, INNER, ON条件)
- **THEN** 对每行 t1 行扫描 t2，只输出满足 ON 条件的合并行

#### Scenario: LEFT JOIN 执行
- **WHEN** Pipeline 为 SeqScan(t1) → NestedLoopJoin(t2, LEFT, ON条件)
- **THEN** 对每行 t1 行扫描 t2，无匹配时输出 t1 行 + t2 列全 NULL

#### Scenario: CROSS JOIN 执行
- **WHEN** Pipeline 为 SeqScan(t1) → NestedLoopJoin(t2, CROSS, None)
- **THEN** 输出 t1 和 t2 的笛卡尔积

### Requirement: JOIN 结果列名限定
系统 SHALL 在 JOIN 结果中使用 `table.column` 格式作为列名。

#### Scenario: 限定列名输出
- **WHEN** 两表 JOIN，左表有列 `id`、`name`，右表有列 `id`、`amount`
- **THEN** 结果行 dict 的 key 为 `users.id`、`users.name`、`orders.id`、`orders.amount`

### Requirement: EXPLAIN 执行计划构建
系统 SHALL 实现 ExplainPlan 能够构建并格式化输出执行计划树。

#### Scenario: 单表查询计划
- **WHEN** EXPLAIN `SELECT * FROM users WHERE id = 1`
- **THEN** 输出包含 SeqScan → Filter 的计划树

#### Scenario: JOIN 查询计划
- **WHEN** EXPLAIN `SELECT * FROM users JOIN orders ON ...`
- **THEN** 输出包含 SeqScan → NestedLoopJoin 的计划树

## MODIFIED Requirements

### Requirement: PlanSelector 支持多表扫描
PlanSelector SHALL 为 JOIN 查询构建多表扫描管线。

#### Scenario: JOIN 查询计划选择
- **WHEN** 查询包含 JOIN 子句
- **THEN** PlanSelector 返回 SeqScan(左表) → NestedLoopJoin(右表) 管线

```

## openspec/changes/tinydb-v02/specs/sql-parser/spec.md

- Source: openspec/changes/tinydb-v02/specs/sql-parser/spec.md
- Lines: 1-51
- SHA256: fba77e9833823ec0860ffa822bbfba8fe043a73ae3ea212939c4da3276fd0dce

```md
## MODIFIED Requirements

### Requirement: SQL 词法分析器关键字集合
词法分析器 SHALL 识别以下新增关键字：`JOIN`、`INNER`、`LEFT`、`RIGHT`、`CROSS`、`FULL`、`ON`、`AS`、`EXPLAIN`。新增关键字与现有关键字一样，不区分大小写。

#### Scenario: JOIN 关键字识别
- **WHEN** 词法分析器遇到 `JOIN`、`join`、`Join` 等变体
- **THEN** 生成类型为 `JOIN` 的 Token

#### Scenario: EXPLAIN 关键字识别
- **WHEN** 词法分析器遇到 `EXPLAIN`
- **THEN** 生成类型为 `EXPLAIN` 的 Token

## ADDED Requirements

### Requirement: JOIN 语法解析
语法分析器 SHALL 解析 JOIN 子句，生成 JoinClause AST 节点。

#### Scenario: 解析 INNER JOIN
- **WHEN** 输入 `SELECT * FROM t1 INNER JOIN t2 ON t1.id = t2.t1_id`
- **THEN** AST 中 Select.joins 包含一个 JoinClause(join_type='INNER', table='t2', on_condition=...)

#### Scenario: 解析 LEFT JOIN
- **WHEN** 输入 `SELECT * FROM t1 LEFT JOIN t2 ON t1.id = t2.t1_id`
- **THEN** AST 中 JoinClause.join_type = 'LEFT'

#### Scenario: 解析 CROSS JOIN
- **WHEN** 输入 `SELECT * FROM t1 CROSS JOIN t2`
- **THEN** AST 中 JoinClause.join_type = 'CROSS'，on_condition 为 None

#### Scenario: 解析表别名
- **WHEN** 输入 `SELECT * FROM users AS u`
- **THEN** AST 中 table alias = 'u'

### Requirement: EXPLAIN 语句解析
语法分析器 SHALL 解析 EXPLAIN 前缀，生成 Explain AST 节点包裹内部语句。

#### Scenario: EXPLAIN SELECT
- **WHEN** 输入 `EXPLAIN SELECT * FROM users`
- **THEN** AST 为 Explain(statement=Select(...))

### Requirement: 限定列名解析
语法分析器 SHALL 解析 `table.column` 格式的限定列名引用。

#### Scenario: 限定列名 AST
- **WHEN** 输入 `SELECT users.name FROM users`
- **THEN** ColumnRef 节点包含 table='users', name='name'

#### Scenario: WHERE 中限定列名
- **WHEN** 输入 `WHERE users.id = 1`
- **THEN** BinaryExpr 左侧为 ColumnRef(table='users', name='id')

```

## openspec/changes/tinydb-v02/specs/storage-engine/spec.md

- Source: openspec/changes/tinydb-v02/specs/storage-engine/spec.md
- Lines: 1-27
- SHA256: b8e5bd6e8e685ebd6e3edd5d55a827ad0c91a26dd2e41b9fd1eefca4fead55cd

```md
## MODIFIED Requirements

### Requirement: BufferPool 线程安全
BufferPool SHALL 使所有公共方法线程安全，通过内部锁保护共享状态。

#### Scenario: 并发 get_page 安全
- **WHEN** 多个线程同时调用 `get_page(page_id)`
- **THEN** 不发生数据竞争，每个线程获得正确的 Page 对象

#### Scenario: 并发 put 安全
- **WHEN** 一个线程调用 `put(page_id, data)`，另一个线程调用 `get_page(page_id)`
- **THEN** 读取操作要么看到旧数据要么看到新数据，不会看到损坏的数据

#### Scenario: flush_all 不阻塞读
- **WHEN** 一个线程执行 `flush_all()`，另一个线程读取已缓存页面
- **THEN** 读取操作可以正常完成（锁粒度为操作级，非全局）

### Requirement: Catalog 线程安全
Catalog SHALL 使用递归锁保护元数据的读写操作。

#### Scenario: 并发 create_table
- **WHEN** 多个线程同时调用 `create_table()` 创建不同表
- **THEN** 每个表正确创建，`_next_table_id` 不重复

#### Scenario: 并发读写 catalog
- **WHEN** 一个线程读取 `catalog.tables`，另一个线程执行 `create_table()`
- **THEN** 读取操作看到一致的快照，不读到半写状态

```

## openspec/changes/tinydb-v02/specs/transaction-manager/spec.md

- Source: openspec/changes/tinydb-v02/specs/transaction-manager/spec.md
- Lines: 1-23
- SHA256: 8438fcfd41080d3f97fdfa20fb697e36d308d7e4f36cb0e5c72c114695531dc2

```md
## MODIFIED Requirements

### Requirement: 事务管理器并发安全
TransactionManager SHALL 在并发环境下正确管理事务生命周期。

#### Scenario: 并发 BEGIN
- **WHEN** 多个线程同时调用 `begin()`
- **THEN** 每个事务获得唯一的 txn_id，不冲突

#### Scenario: 并发 COMMIT
- **WHEN** 多个事务同时提交
- **THEN** WAL 记录按正确顺序写入，每个事务的 COMMIT 记录完整

#### Scenario: 并发 ROLLBACK
- **WHEN** 一个事务回滚，另一个事务正常提交
- **THEN** 回滚不影响其他事务的状态

### Requirement: WAL 写入原子性
WAL SHALL 在并发写入时保证单条记录的原子性。

#### Scenario: 并发 log_write
- **WHEN** 多个事务同时调用 `log_write()`
- **THEN** 每条日志记录完整写入，不与其他记录交错

```
