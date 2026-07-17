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
