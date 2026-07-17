## ADDED Requirements

### Requirement: Lexer tokenizes SQL input
The SQL lexer SHALL break input string into a stream of tokens (keywords, identifiers, literals, operators, punctuation).

#### Scenario: Tokenize a SELECT statement
- **WHEN** input is `SELECT name FROM users WHERE id = 1`
- **THEN** lexer produces tokens: [SELECT, name, FROM, users, WHERE, id, =, 1]

#### Scenario: Tokenize string literals
- **WHEN** input contains `'hello world'`
- **THEN** lexer produces a single STRING token with value `hello world`

### Requirement: Parser builds AST from tokens
The SQL parser SHALL construct an Abstract Syntax Tree from the token stream.

#### Scenario: Parse CREATE TABLE
- **WHEN** input is `CREATE TABLE users (id INT, name TEXT)`
- **THEN** parser produces a CreateTable AST node with table name `users` and column definitions

#### Scenario: Parse INSERT
- **WHEN** input is `INSERT INTO users VALUES (1, 'Alice')`
- **THEN** parser produces an Insert AST node with values list

#### Scenario: Parse SELECT with clauses
- **WHEN** input is `SELECT name FROM users WHERE id > 1 ORDER BY name LIMIT 10`
- **THEN** parser produces a Select AST node with projection, source, where, order by, and limit fields

### Requirement: Parser reports syntax errors
The parser SHALL raise a clear error message when SQL syntax is invalid.

#### Scenario: Missing FROM clause
- **WHEN** input is `SELECT name`
- **THEN** parser raises error indicating missing FROM clause

### Requirement: JOIN keyword recognition (v0.2)
The lexer SHALL recognize JOIN, INNER, LEFT, RIGHT, CROSS, FULL, OUTER, ON, AS, EXPLAIN keywords.

#### Scenario: JOIN keyword tokenization
- **WHEN** lexer encounters `JOIN`, `join`, `Join` variants
- **THEN** produces a JOIN token (case-insensitive)

#### Scenario: EXPLAIN keyword tokenization
- **WHEN** lexer encounters `EXPLAIN`
- **THEN** produces an EXPLAIN token

### Requirement: JOIN syntax parsing (v0.2)
The parser SHALL parse JOIN clauses into JoinClause AST nodes.

#### Scenario: Parse INNER JOIN
- **WHEN** input is `SELECT * FROM t1 INNER JOIN t2 ON t1.id = t2.t1_id`
- **THEN** AST contains JoinClause(join_type='INNER', table='t2', on_condition=...)

#### Scenario: Parse LEFT JOIN
- **WHEN** input is `SELECT * FROM t1 LEFT JOIN t2 ON t1.id = t2.t1_id`
- **THEN** JoinClause.join_type = 'LEFT'

#### Scenario: Parse CROSS JOIN
- **WHEN** input is `SELECT * FROM t1 CROSS JOIN t2`
- **THEN** JoinClause.join_type = 'CROSS', on_condition is None

#### Scenario: Parse table alias
- **WHEN** input is `SELECT * FROM users AS u`
- **THEN** table alias = 'u'

### Requirement: EXPLAIN statement parsing (v0.2)
The parser SHALL parse EXPLAIN prefix into Explain AST node.

#### Scenario: EXPLAIN SELECT
- **WHEN** input is `EXPLAIN SELECT * FROM users`
- **THEN** AST is Explain(statement=Select(...))

### Requirement: Qualified column name parsing (v0.2)
The parser SHALL parse `table.column` format column references.

#### Scenario: Qualified column in SELECT
- **WHEN** input is `SELECT users.name FROM users`
- **THEN** ColumnRef node has table='users', name='name'

#### Scenario: Qualified column in WHERE
- **WHEN** input is `WHERE users.id = 1`
- **THEN** BinaryExpr left side is ColumnRef(table='users', name='id')

#### Scenario: Qualified column in GROUP BY
- **WHEN** input is `GROUP BY users.name`
- **THEN** group_by value is 'users.name'

#### Scenario: Qualified column in ORDER BY
- **WHEN** input is `ORDER BY users.name DESC`
- **THEN** order_by column is 'users.name'
