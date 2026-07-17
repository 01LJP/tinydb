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

### Requirement: 多行输入改进
系统 SHALL 改进多行输入体验，显示续行提示符和行号。

#### Scenario: 多行 SQL 输入
- **WHEN** 用户输入不以分号结尾的 SQL 并按回车
- **THEN** 显示 `  ... ` 续行提示符，等待继续输入

#### Scenario: 分号结束执行
- **WHEN** 用户在多行输入后输入分号
- **THEN** 执行完整的 SQL 语句
