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
