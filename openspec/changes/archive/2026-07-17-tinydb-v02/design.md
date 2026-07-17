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

- **[嵌套循环性能]** → 对大数据集 JOIN 性能为 O(n*m)，但 TinyDB 定位为教学/嵌入式数据库，数据量小可接受。后续可通过索引扫描优化。
- **[读写锁粒度]** → 表级锁在高并发写入同一表时串行化严重，但比数据库级锁好。行级锁留待后续版本。
- **[readline 平台兼容]** → `readline` 在 Windows 上不可用（需要 `pyreadline3`），但主要目标平台是 Linux/macOS。Windows 上降级为基本输入。
- **[JOIN 列名冲突]** → 使用 `table.column` 限定格式解决，但增加了用户书写复杂度。支持无歧义时的短名引用作为折衷。

## Open Questions

- 是否需要支持表别名的 `AS` 关键字？（建议支持，SQL 标准且对 JOIN 场景有用）
- EXPLAIN 输出格式？（建议使用树形缩进格式，类似 PostgreSQL）
