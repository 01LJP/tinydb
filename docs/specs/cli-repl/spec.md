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

### Requirement: readline line editing (v0.2)
The system SHALL integrate readline for line editing, command history, and tab completion.

#### Scenario: History navigation
- **WHEN** user presses the up arrow key
- **THEN** the previous command is shown

#### Scenario: Tab completion
- **WHEN** user types `SEL` and presses Tab
- **THEN** it completes to `SELECT`

#### Scenario: History persistence
- **WHEN** user exits and restarts the CLI
- **THEN** previous command history is available

### Requirement: SQL syntax highlighting (v0.2)
The system SHALL highlight SQL keywords, strings, and numbers with ANSI colors.

#### Scenario: Keyword highlighting
- **WHEN** user inputs `SELECT * FROM users`
- **THEN** `SELECT` and `FROM` are displayed in bold blue

#### Scenario: String highlighting
- **WHEN** user inputs `WHERE name = 'Alice'`
- **THEN** `'Alice'` is displayed in green

#### Scenario: Number highlighting
- **WHEN** user inputs `WHERE age > 25`
- **THEN** `25` is displayed in yellow

### Requirement: EXPLAIN execution plan (v0.2)
The system SHALL support EXPLAIN keyword and .explain meta command to display execution plans.

#### Scenario: EXPLAIN SELECT
- **WHEN** executing `EXPLAIN SELECT * FROM users WHERE id = 1`
- **THEN** output shows SeqScan → Filter plan tree

#### Scenario: EXPLAIN JOIN
- **WHEN** executing `EXPLAIN SELECT * FROM users JOIN orders ON users.id = orders.user_id`
- **THEN** output shows SeqScan → NestedLoopJoin plan tree

### Requirement: .dump meta command (v0.2)
The system SHALL support .dump to export SQL重建语句.

#### Scenario: .dump all tables
- **WHEN** user executes `.dump`
- **THEN** output contains CREATE TABLE and INSERT statements for all tables

#### Scenario: .dump specific table
- **WHEN** user executes `.dump users`
- **THEN** output contains only users table SQL

### Requirement: .version meta command (v0.2)
The system SHALL support .version to display version information.

#### Scenario: .version output
- **WHEN** user executes `.version`
- **THEN** displays `TinyDB v0.2.0`

### Requirement: .mode meta command (v0.2)
The system SHALL support .mode to switch output format.

#### Scenario: Switch to CSV
- **WHEN** user executes `.mode csv`
- **THEN** subsequent results are output in CSV format

#### Scenario: Switch to table
- **WHEN** user executes `.mode table`
- **THEN** subsequent results are output in ASCII table format
