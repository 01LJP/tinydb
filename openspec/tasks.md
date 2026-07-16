## 1. 项目初始化

- [x] 1.1 创建项目目录结构（src/tinydb/、各子模块、tests/）
- [x] 1.2 配置 setup.py（包名、入口点、零外部依赖）
- [x] 1.3 创建 `__init__.py` 和 `Database` 类骨架（execute 接口）

## 2. 类型系统

- [x] 2.1 实现 DataType 定义（INT、FLOAT、TEXT、BOOL）
- [x] 2.2 实现类型检查与转换逻辑
- [x] 2.3 实现列约束检查（PRIMARY KEY、NOT NULL、UNIQUE）

## 3. SQL 解析器

- [x] 3.1 实现 Lexer（词法分析器，生成 token 流）
- [x] 3.2 实现 Parser 基础结构（AST 节点定义）
- [x] 3.3 实现 DDL 解析（CREATE TABLE、DROP TABLE）
- [x] 3.4 实现 INSERT 解析
- [x] 3.5 实现 SELECT 解析（WHERE、ORDER BY、LIMIT/OFFSET）
- [x] 3.6 实现 UPDATE 和 DELETE 解析

## 4. 存储引擎

- [x] 4.1 实现 Page 数据结构（4096 字节页）
- [x] 4.2 实现 FileManager（单文件读写）
- [x] 4.3 实现 BufferPool（页缓存 + LRU 淘汰 + 脏页回写）
- [x] 4.4 实现 Record 序列化/反序列化
- [x] 4.5 实现表数据页管理（插入、扫描记录）

## 5. 查询执行器

- [x] 5.1 实现全表扫描（Sequential Scan）
- [x] 5.2 实现 WHERE 条件过滤（AND/OR 支持）
- [x] 5.3 实现 ORDER BY 排序
- [x] 5.4 实现 LIMIT/OFFSET 分页
- [x] 5.5 实现聚合函数（COUNT、SUM、AVG）
- [x] 5.6 实现 GROUP BY

## 6. B-tree 索引

- [x] 6.1 实现 B-tree 节点结构
- [x] 6.2 实现 B-tree 插入
- [x] 6.3 实现 B-tree 点查询（等值查找）
- [x] 6.4 实现 B-tree 范围扫描
- [x] 6.5 实现索引与存储引擎的集成（自动维护）

## 7. 事务管理器

- [x] 7.1 实现 WAL 日志格式与写入
- [x] 7.2 实现 BEGIN / COMMIT / ROLLBACK
- [x] 7.3 实现崩溃恢复（WAL 重放）
- [x] 7.4 实现事务与执行器的集成

## 8. CLI/REPL

- [x] 8.1 实现交互式 REPL 循环
- [x] 8.2 实现结果表格格式化输出
- [x] 8.3 实现多行输入支持（分号终止）

## 9. 集成与测试

- [x] 9.1 编写各模块单元测试
- [x] 9.2 编写端到端集成测试
- [x] 9.3 验证完整工作流（创建表→插入→查询→事务→持久化）
