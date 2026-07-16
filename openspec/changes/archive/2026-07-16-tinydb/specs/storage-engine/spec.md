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
