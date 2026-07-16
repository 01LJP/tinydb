# TinyDB

TinyDB is a lightweight embedded database engine implemented in Python.

## Features

- SQL lexer and parser
- Page-based storage with buffer pool management
- B-Tree indexing
- Transaction support with Write-Ahead Logging (WAL)
- Type system with INT, FLOAT, TEXT, and BOOL data types
- Command-line interface

## Installation

```bash
pip install -e .
```

## Usage

```python
from tinydb import Database, open

with open("mydb.tdb") as db:
    db.execute("CREATE TABLE users (id INT, name TEXT)")
    db.execute("INSERT INTO users VALUES (1, 'Alice')")
```

## Running Tests

```bash
pytest tests/ -v
```

## Architecture

```
tinydb/
├── cli.py          # Command-line interface
├── database.py     # Main Database class
├── lexer.py        # SQL tokenizer
├── parser.py       # SQL parser
├── ast_nodes.py    # AST node definitions
├── catalog.py      # Schema catalog
├── types.py        # Data types and serialization
├── storage/        # Storage layer
│   ├── page.py
│   ├── file_manager.py
│   └── buffer_pool.py
├── executor/       # Query execution
│   ├── scan.py
│   ├── filter.py
│   ├── sort.py
│   ├── aggregate.py
│   └── plan.py
├── index/          # Index structures
│   └── btree.py
└── transaction/    # Transaction management
    ├── wal.py
    └── txn.py
```
