# TinyDB

TinyDB is a lightweight embedded database engine implemented in Python.

## Features

- SQL lexer and parser
- Page-based storage with buffer pool management
- B-Tree indexing
- Transaction support with Write-Ahead Logging (WAL)
- Type system with INT, FLOAT, TEXT, and BOOL data types
- **Multi-table JOIN queries** (INNER JOIN, LEFT JOIN, CROSS JOIN)
- **Concurrency control** (read-write locks, thread-safe BufferPool/Catalog)
- **Enhanced CLI** (readline, syntax highlighting, EXPLAIN, .dump, .mode)

## Installation

```bash
pip install -e .
```

## Usage

```python
from tinydb import Database, open

with open("mydb.tdb") as db:
    db.execute("CREATE TABLE users (id INT, name TEXT)")
    db.execute("CREATE TABLE orders (id INT, user_id INT, amount FLOAT)")
    db.execute("INSERT INTO users VALUES (1, 'Alice')")
    db.execute("INSERT INTO orders VALUES (1, 1, 50.0)")

    # JOIN query
    result = db.execute(
        "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
    )
```

## CLI

```bash
tinydb mydb.tdb
tinydb> SELECT * FROM users JOIN orders ON users.id = orders.user_id;
tinydb> EXPLAIN SELECT * FROM users WHERE id = 1;
tinydb> .dump
tinydb> .mode csv
tinydb> .version
```

## Running Tests

```bash
pytest tests/ -v
```

## Architecture

```
tinydb/
├── cli.py          # Command-line interface (with readline, syntax highlighting)
├── database.py     # Main Database class (with lock management)
├── lexer.py        # SQL tokenizer
├── parser.py       # SQL parser (JOIN, EXPLAIN support)
├── ast_nodes.py    # AST node definitions
├── catalog.py      # Schema catalog (thread-safe)
├── types.py        # Data types and serialization
├── concurrency.py  # ReadWriteLock and LockManager
├── connection.py   # ConnectionPool and Connection
├── storage/        # Storage layer
│   ├── page.py
│   ├── file_manager.py
│   └── buffer_pool.py  # Thread-safe LRU buffer pool
├── executor/       # Query execution
│   ├── scan.py     # Sequential scan (with column prefixing)
│   ├── filter.py   # WHERE clause filter (qualified column support)
│   ├── sort.py
│   ├── aggregate.py
│   ├── join.py     # Nested-loop JOIN operator
│   ├── explain.py  # EXPLAIN execution plan formatter
│   └── plan.py     # Query plan selector
├── index/          # Index structures
│   └── btree.py
└── transaction/    # Transaction management
    ├── wal.py      # Write-Ahead Log (thread-safe)
    └── txn.py
```
