## ADDED Requirements

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

### Requirement: Transaction manager concurrency safety (v0.2)
TransactionManager SHALL correctly manage transaction lifecycle in concurrent environments.

#### Scenario: Concurrent BEGIN
- **WHEN** multiple threads call `begin()` simultaneously
- **THEN** each transaction gets a unique txn_id, no conflicts

#### Scenario: Concurrent COMMIT
- **WHEN** multiple transactions commit simultaneously
- **THEN** WAL records are written in correct order, each COMMIT record is complete

#### Scenario: Concurrent ROLLBACK
- **WHEN** one transaction rolls back while another commits
- **THEN** the rollback does not affect the other transaction's state

### Requirement: WAL write atomicity (v0.2)
WAL SHALL guarantee single-record atomicity during concurrent writes.

#### Scenario: Concurrent log_write
- **WHEN** multiple transactions call `log_write()` simultaneously
- **THEN** each log record is written completely, not interleaved with others
