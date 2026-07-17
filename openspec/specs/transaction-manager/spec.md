# transaction-manager Specification

## Purpose
TBD - created by archiving change tinydb. Update Purpose after archive.
## Requirements
### Requirement: Transaction begin
The system SHALL support starting a new transaction with BEGIN.

#### Scenario: Start transaction
- **WHEN** executing `BEGIN`
- **THEN** a new transaction is started and subsequent operations are part of it

### Requirement: Transaction commit
The system SHALL support committing a transaction with COMMIT, making all changes permanent.

#### Scenario: Commit transaction
- **WHEN** inserting rows then executing `COMMIT`
- **THEN** the inserted rows are persisted and visible to other connections

### Requirement: Transaction rollback
The system SHALL support rolling back a transaction with ROLLBACK, undoing all changes.

#### Scenario: Rollback after insert
- **WHEN** inserting rows then executing `ROLLBACK`
- **THEN** the inserted rows are not persisted

#### Scenario: Rollback after update
- **WHEN** updating rows then executing `ROLLBACK`
- **THEN** the rows retain their original values

### Requirement: WAL-based crash recovery
The system SHALL use Write-Ahead Logging to ensure durability and support crash recovery.

#### Scenario: Recover committed transactions after crash
- **WHEN** the system restarts after a crash with committed transactions in WAL
- **THEN** all committed changes are preserved

#### Scenario: Discard uncommitted transactions after crash
- **WHEN** the system restarts after a crash with uncommitted transactions in WAL
- **THEN** uncommitted changes are not applied

### Requirement: ACID properties
The system SHALL guarantee Atomicity, Consistency, Isolation (serializable single-connection), and Durability.

#### Scenario: Atomicity — all or nothing
- **WHEN** a transaction with multiple operations is rolled back
- **THEN** none of the operations take effect

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

