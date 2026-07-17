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
