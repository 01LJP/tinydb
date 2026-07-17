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

### Requirement: NestedLoopJoin executor (v0.2)
The system SHALL implement nested-loop join for INNER, LEFT, and CROSS JOIN.

#### Scenario: INNER JOIN execution
- **WHEN** pipeline is SeqScan(t1) → NestedLoopJoin(t2, INNER, ON condition)
- **THEN** only matching row pairs are yielded

#### Scenario: LEFT JOIN execution
- **WHEN** pipeline is SeqScan(t1) → NestedLoopJoin(t2, LEFT, ON condition)
- **THEN** all left rows are yielded, unmatched right columns are NULL

#### Scenario: CROSS JOIN execution
- **WHEN** pipeline is SeqScan(t1) → NestedLoopJoin(t2, CROSS, None)
- **THEN** cartesian product is yielded

### Requirement: JOIN result column naming (v0.2)
The system SHALL use `table.column` format for JOIN result column names.

#### Scenario: Qualified column names
- **WHEN** two tables are JOINed with overlapping column names
- **THEN** result dict keys use `users.id`, `orders.id` format

### Requirement: EXPLAIN execution plan (v0.2)
The system SHALL build and format execution plan trees.

#### Scenario: Single table plan
- **WHEN** EXPLAIN `SELECT * FROM users WHERE id = 1`
- **THEN** output contains SeqScan → Filter

#### Scenario: JOIN plan
- **WHEN** EXPLAIN `SELECT * FROM users JOIN orders ON ...`
- **THEN** output contains SeqScan → NestedLoopJoin

### Requirement: PlanSelector multi-table support (v0.2)
PlanSelector SHALL build multi-table scan pipelines for JOIN queries.

#### Scenario: JOIN query plan selection
- **WHEN** query contains JOIN clauses
- **THEN** PlanSelector returns SeqScan(left) → NestedLoopJoin(right) pipeline
