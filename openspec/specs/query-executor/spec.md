# query-executor Specification

## Purpose
TBD - created by archiving change tinydb. Update Purpose after archive.
## Requirements
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

### Requirement: PlanSelector 支持多表扫描
PlanSelector SHALL 为 JOIN 查询构建多表扫描管线。

#### Scenario: JOIN 查询计划选择
- **WHEN** 查询包含 JOIN 子句
- **THEN** PlanSelector 返回 SeqScan(左表) → NestedLoopJoin(右表) 管线

