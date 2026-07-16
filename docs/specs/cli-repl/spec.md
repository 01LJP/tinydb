## ADDED Requirements

### Requirement: Interactive REPL
The system SHALL provide an interactive Read-Eval-Print Loop for executing SQL.

#### Scenario: Start REPL
- **WHEN** running the tinydb CLI command
- **THEN** an interactive prompt appears accepting SQL input

#### Scenario: Execute SQL in REPL
- **WHEN** user types `SELECT * FROM users;` in the REPL
- **THEN** the system executes the query and displays results

### Requirement: Result display
The system SHALL display query results in a readable tabular format.

#### Scenario: Display SELECT results
- **WHEN** executing a SELECT query returning multiple rows
- **THEN** results are displayed as a formatted table with column headers

#### Scenario: Display confirmation for DML
- **WHEN** executing INSERT, UPDATE, or DELETE
- **THEN** the system shows the number of affected rows

### Requirement: Multi-line input
The system SHALL support SQL statements spanning multiple lines (terminated by semicolon).

#### Scenario: Multi-line query
- **WHEN** user enters a query across multiple lines ending with `;`
- **THEN** the system treats the entire input as one statement
