# btree-index Specification

## Purpose
TBD - created by archiving change tinydb. Update Purpose after archive.
## Requirements
### Requirement: B-tree index creation
The system SHALL create a B-tree index on a specified table column.

#### Scenario: Create index on column
- **WHEN** an index is created on column `id` of table `users`
- **THEN** a B-tree structure is built containing all existing values from that column

### Requirement: Index-accelerated equality lookup
The system SHALL use B-tree index for equality queries when available.

#### Scenario: Point query via index
- **WHEN** executing `SELECT * FROM users WHERE id = 42` and an index on `id` exists
- **THEN** the system uses the B-tree to locate the row without full table scan

### Requirement: Index-accelerated range query
The system SHALL use B-tree index for range queries (>, <, >=, <=).

#### Scenario: Range query via index
- **WHEN** executing `SELECT * FROM users WHERE age >= 18 AND age <= 30` and an index on `age` exists
- **THEN** the system uses B-tree range scan to find matching rows

### Requirement: Index maintenance on data changes
The system SHALL automatically update indexes when data is inserted or deleted.

#### Scenario: Index updated on INSERT
- **WHEN** inserting a new row into a table with an index
- **THEN** the B-tree is updated to include the new value

#### Scenario: Index updated on DELETE
- **WHEN** deleting a row from a table with an index
- **THEN** the B-tree is updated to remove the corresponding entry

