## ADDED Requirements

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

### Requirement: BufferPool thread safety (v0.2)
BufferPool SHALL make all public methods thread-safe via internal locking.

#### Scenario: Concurrent get_page
- **WHEN** multiple threads call `get_page(page_id)` simultaneously
- **THEN** no data race occurs, each thread gets correct Page object

#### Scenario: Concurrent put
- **WHEN** one thread calls `put(page_id, data)` while another calls `get_page(page_id)`
- **THEN** read returns either old or new data, never corrupted data

#### Scenario: flush_all does not block reads
- **WHEN** one thread runs `flush_all()` while another reads a cached page
- **THEN** the read completes normally (operation-level locking)

### Requirement: Catalog thread safety (v0.2)
Catalog SHALL use recursive lock to protect metadata read/write operations.

#### Scenario: Concurrent create_table
- **WHEN** multiple threads call `create_table()` for different tables
- **THEN** each table is created correctly, `_next_table_id` has no duplicates

#### Scenario: Concurrent read and write
- **WHEN** one thread reads `catalog.tables` while another creates a table
- **THEN** the read sees a consistent snapshot
