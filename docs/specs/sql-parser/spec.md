## ADDED Requirements

### Requirement: Lexer tokenizes SQL input
The SQL lexer SHALL break input string into a stream of tokens (keywords, identifiers, literals, operators, punctuation).

#### Scenario: Tokenize a SELECT statement
- **WHEN** input is `SELECT name FROM users WHERE id = 1`
- **THEN** lexer produces tokens: [SELECT, name, FROM, users, WHERE, id, =, 1]

#### Scenario: Tokenize string literals
- **WHEN** input contains `'hello world'`
- **THEN** lexer produces a single TEXT_LITERAL token with value `hello world`

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
