# storage-engine Specification

## Purpose
TBD - created by archiving change tinydb. Update Purpose after archive.
## Requirements
### Requirement: Page-based file storage
The system SHALL store data in fixed-size pages (4096 bytes) within a single database file.

#### Scenario: Create new database file
- **WHEN** opening a non-existent database path
- **THEN** system creates a new file with initial page allocation

#### Scenario: Read and write pages
- **WHEN** writing data to page N then reading page N
- **THEN** the read returns the exact bytes previously written

### Requirement: Buffer pool management
The system SHALL maintain a page buffer pool to reduce disk I/O.

#### Scenario: Cache frequently accessed pages
- **WHEN** reading the same page multiple times
- **THEN** subsequent reads are served from cache without disk access

#### Scenario: Evict least-recently-used pages
- **WHEN** buffer pool is full and a new page is requested
- **THEN** the system evicts the least-recently-used page to make room

#### Scenario: Dirty page write-back
- **WHEN** a modified (dirty) page is evicted or checkpoint occurs
- **THEN** the system writes the dirty page to disk

### Requirement: Table data organization
The system SHALL store table records within pages, supporting variable-length records.

#### Scenario: Insert record into table
- **WHEN** a new record is inserted
- **THEN** the system places it in the first page with sufficient free space

#### Scenario: Read all records from table
- **WHEN** scanning a table
- **THEN** the system reads all pages belonging to that table and returns records

### Requirement: BufferPool 线程安全
BufferPool SHALL 使所有公共方法线程安全，通过内部锁保护共享状态。

#### Scenario: 并发 get_page 安全
- **WHEN** 多个线程同时调用 `get_page(page_id)`
- **THEN** 不发生数据竞争，每个线程获得正确的 Page 对象

#### Scenario: 并发 put 安全
- **WHEN** 一个线程调用 `put(page_id, data)`，另一个线程调用 `get_page(page_id)`
- **THEN** 读取操作要么看到旧数据要么看到新数据，不会看到损坏的数据

#### Scenario: flush_all 不阻塞读
- **WHEN** 一个线程执行 `flush_all()`，另一个线程读取已缓存页面
- **THEN** 读取操作可以正常完成（锁粒度为操作级，非全局）

### Requirement: Catalog 线程安全
Catalog SHALL 使用递归锁保护元数据的读写操作。

#### Scenario: 并发 create_table
- **WHEN** 多个线程同时调用 `create_table()` 创建不同表
- **THEN** 每个表正确创建，`_next_table_id` 不重复

#### Scenario: 并发读写 catalog
- **WHEN** 一个线程读取 `catalog.tables`，另一个线程执行 `create_table()`
- **THEN** 读取操作看到一致的快照，不读到半写状态

