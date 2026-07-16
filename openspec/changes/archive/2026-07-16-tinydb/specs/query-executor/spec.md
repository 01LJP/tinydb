## ADDED Requirements

### Requirement: Full table scan
The system SHALL support scanning all records in a table.

#### Scenario: SELECT all columns
- **WHEN** executing `SELECT * FROM users`
- **THEN** the executor returns all rows from the users table

#### Scenario: SELECT specific columns
- **WHEN** executing `SELECT name, age FROM users`
- **THEN** the executor returns only the name and age columns

### Requirement: WHERE clause filtering
The system SHALL filter rows based on WHERE conditions with AND/OR.

#### Scenario: Equality filter
- **WHEN** executing `SELECT * FROM users WHERE id = 1`
- **THEN** only rows where id equals 1 are returned

#### Scenario: AND condition
- **WHEN** executing `SELECT * FROM users WHERE age > 18 AND name = 'Alice'`
- **THEN** only rows matching both conditions are returned

#### Scenario: OR condition
- **WHEN** executing `SELECT * FROM users WHERE age < 18 OR age > 60`
- **THEN** rows matching either condition are returned

### Requirement: ORDER BY sorting
The system SHALL sort results by specified columns.

#### Scenario: Ascending order
- **WHEN** executing `SELECT * FROM users ORDER BY age`
- **THEN** results are sorted by age ascending

#### Scenario: Descending order
- **WHEN** executing `SELECT * FROM users ORDER BY age DESC`
- **THEN** results are sorted by age descending

### Requirement: LIMIT and OFFSET
The system SHALL support pagination via LIMIT and OFFSET.

#### Scenario: LIMIT only
- **WHEN** executing `SELECT * FROM users LIMIT 10`
- **THEN** at most 10 rows are returned

#### Scenario: LIMIT with OFFSET
- **WHEN** executing `SELECT * FROM users LIMIT 5 OFFSET 10`
- **THEN** rows 11-15 are returned

### Requirement: Aggregate functions
The system SHALL support COUNT, SUM, AVG with optional GROUP BY.

#### Scenario: COUNT all rows
- **WHEN** executing `SELECT COUNT(*) FROM users`
- **THEN** a single row with the total count is returned

#### Scenario: GROUP BY with aggregate
- **WHEN** executing `SELECT department, AVG(salary) FROM employees GROUP BY department`
- **THEN** each department with its average salary is returned
