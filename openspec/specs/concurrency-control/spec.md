# concurrency-control Specification

## Purpose
TBD - created by archiving change tinydb-v02. Update Purpose after archive.
## Requirements
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

