## ADDED Requirements

### Requirement: Basic data types
The system SHALL support INT, FLOAT, TEXT, and BOOL data types.

#### Scenario: Store and retrieve each type
- **WHEN** creating a table with columns of types INT, FLOAT, TEXT, BOOL and inserting values
- **THEN** each value is stored and retrieved with its correct type

### Requirement: Type checking on INSERT
The system SHALL validate that inserted values match the column's declared type.

#### Scenario: Reject type mismatch
- **WHEN** inserting a TEXT value into an INT column
- **THEN** the system raises a type error

#### Scenario: Accept valid type
- **WHEN** inserting an INT value into an INT column
- **THEN** the insert succeeds

### Requirement: PRIMARY KEY constraint
The system SHALL enforce uniqueness and non-null for PRIMARY KEY columns.

#### Scenario: Reject duplicate primary key
- **WHEN** inserting a row with a primary key value that already exists
- **THEN** the system raises a constraint violation error

#### Scenario: Reject null primary key
- **WHEN** inserting a row with NULL primary key
- **THEN** the system raises a constraint violation error

### Requirement: NOT NULL constraint
The system SHALL reject NULL values for columns declared NOT NULL.

#### Scenario: Reject null in NOT NULL column
- **WHEN** inserting NULL into a NOT NULL column
- **THEN** the system raises a constraint violation error

### Requirement: UNIQUE constraint
The system SHALL enforce uniqueness for columns declared UNIQUE.

#### Scenario: Reject duplicate in UNIQUE column
- **WHEN** inserting a duplicate value into a UNIQUE column
- **THEN** the system raises a constraint violation error

### Requirement: Exception hierarchy
The system SHALL provide a structured exception hierarchy for different error types.

#### Scenario: JoinError for JOIN failures
- **WHEN** a JOIN references a non-existent table
- **THEN** the system raises a JoinError

#### Scenario: ParseError for syntax errors
- **WHEN** SQL syntax is invalid
- **THEN** the system raises a ParseError with line/column context

#### Scenario: ConstraintError for violations
- **WHEN** a constraint is violated
- **THEN** the system raises a ConstraintError with descriptive message
