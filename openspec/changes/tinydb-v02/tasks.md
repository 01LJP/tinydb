## 1. 基础层扩展（词法/语法/AST）

- [x] 1.1 lexer.py 添加 JOIN 相关关键字：JOIN、INNER、LEFT、RIGHT、CROSS、FULL、ON、AS、EXPLAIN
- [x] 1.2 ast_nodes.py 添加 JoinClause、TableRef、Explain AST 节点，修改 Select 添加 joins/tables 字段
- [x] 1.3 ast_nodes.py 修改 ColumnRef 支持 table 属性（限定列名）
- [x] 1.4 parser.py 实现 _parse_from_clause() 解析 FROM 表名、表别名
- [x] 1.5 parser.py 实现 _parse_join() 解析 JOIN/LEFT JOIN/CROSS JOIN + ON 条件
- [x] 1.6 parser.py 实现限定列名解析（table.column → ColumnRef(table, name)）
- [x] 1.7 parser.py 实现 EXPLAIN 语句解析
- [x] 1.8 types.py 添加 JoinError 异常类

## 2. JOIN 执行器实现

- [x] 2.1 executor/join.py 实现 NestedLoopJoin 算子（INNER/LEFT/CROSS 三种模式）
- [x] 2.2 executor/scan.py 修改 SeqScan 输出列名带表前缀（table.column 格式）
- [x] 2.3 executor/filter.py 修改 _eval() 支持限定列名解析
- [x] 2.4 executor/plan.py PlanSelector 支持 JOIN 查询的多表扫描管线构建
- [x] 2.5 executor/__init__.py 导出新增的 Join 算子
- [x] 2.6 database.py 修改 _exec_select() 处理 JOIN 查询管线组装
- [x] 2.7 database.py 修改 _exec_select() 处理 SELECT 列表中的限定列名

## 3. JOIN 测试

- [x] 3.1 tests/test_join.py 编写 INNER JOIN 基本测试
- [x] 3.2 tests/test_join.py 编写 LEFT JOIN 测试（含无匹配行 NULL 填充）
- [x] 3.3 tests/test_join.py 编写 CROSS JOIN 测试
- [x] 3.4 tests/test_join.py 编写表别名测试
- [x] 3.5 tests/test_join.py 编写多表（3+）链式 JOIN 测试
- [x] 3.6 tests/test_join.py 编写 JOIN + WHERE + 聚合组合测试
- [x] 3.7 运行全部测试确认 JOIN 功能正确且不影响现有功能

## 4. 并发控制实现

- [x] 4.1 concurrency.py 实现 ReadWriteLock（多读单写锁）
- [x] 4.2 concurrency.py 实现 LockManager（表级锁管理 + 全局锁）
- [x] 4.3 storage/buffer_pool.py 所有公共方法加 threading.Lock 保护
- [x] 4.4 catalog.py 使用 threading.RLock 保护元数据读写
- [x] 4.5 transaction/wal.py WAL 写入操作加锁保证原子性
- [x] 4.6 database.py execute() 方法根据语句类型获取相应锁
- [x] 4.7 connection.py 实现 ConnectionPool 和 Connection 类

## 5. 并发测试

- [x] 5.1 tests/test_concurrency.py 编写多线程并发 SELECT 测试
- [x] 5.2 tests/test_concurrency.py 编写写操作阻塞读操作测试
- [x] 5.3 tests/test_concurrency.py 编写并发 INSERT 串行化测试
- [x] 5.4 tests/test_concurrency.py 编写不同表并发写测试
- [x] 5.5 tests/test_concurrency.py 编写 ConnectionPool 生命周期测试
- [x] 5.6 运行全部测试确认并发功能正确且不引入死锁

## 6. CLI 增强实现

- [x] 6.1 cli.py 集成 readline：行编辑、历史持久化、Tab 补全
- [x] 6.2 cli.py 实现 SQL 语法高亮（ANSI 颜色码）
- [x] 6.3 cli.py 实现多行输入续行提示符改进
- [x] 6.4 executor/explain.py 实现 ExplainPlan 执行计划构建和格式化输出
- [x] 6.5 cli.py 实现 .explain 元命令（调用 ExplainPlan）
- [x] 6.6 cli.py 实现 .dump 元命令（导出 SQL）
- [x] 6.7 cli.py 实现 .version 元命令
- [x] 6.8 cli.py 实现 .mode 元命令（table/csv 切换）

## 7. CLI 测试与集成测试

- [x] 7.1 tests/test_cli.py 编写 EXPLAIN 执行计划输出测试
- [x] 7.2 tests/test_cli.py 编写 .dump 导出测试
- [x] 7.3 tests/test_cli.py 编写 .version 和 .mode 测试
- [x] 7.4 tests/test_e2e.py 编写 v0.2 端到端集成测试（JOIN + 并发 + CLI）
- [x] 7.5 运行全量测试套件，确保所有 v0.1 测试仍然通过

## 8. 文档与收尾

- [x] 8.1 更新 README.md 反映 v0.2 新功能
- [ ] 8.2 更新 openspec/specs/ 目录下的主规格文件（合并 delta specs）
- [ ] 8.3 清理 mydb.tdb 等运行时文件，更新 .gitignore
