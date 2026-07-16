"""Interactive REPL / CLI for tinydb.

Usage::

    $ tinydb mydb.db
    tinydb> CREATE TABLE users (id INT PRIMARY KEY, name TEXT);
    ok
    tinydb> .exit

Alternatively pass a SQL string directly::

    $ tinydb mydb.db "SELECT * FROM users"
"""

import sys


def display_result(result):
    """Format and print the output of a :meth:`Database.execute` call."""
    if isinstance(result, list):
        _display_rows(result)
    elif isinstance(result, dict):
        _display_status(result)
    elif result is None:
        print("ok")
    else:
        print(result)


def _display_rows(rows: list):
    """Render a list of row-dicts as an ASCII table."""
    if not rows:
        print("(0 rows)")
        return

    columns = list(rows[0].keys())
    # Compute per-column display widths.
    widths = {}
    for col in columns:
        max_w = max(len(str(row.get(col, ""))) for row in rows)
        widths[col] = max(len(col), max_w)

    def _format_row(row):
        return " | ".join(
            str(row.get(col, "")).ljust(widths[col]) for col in columns
        )

    header = _format_row({col: col for col in columns})
    separator = "-" * len(header)
    print(header)
    print(separator)
    for row in rows:
        print(_format_row(row))
    print(f"\n{len(rows)} row(s)")


def _display_status(result: dict):
    """Render a status/affected-rows dict."""
    if "affected_rows" in result:
        n = result["affected_rows"]
        print(f"{n} row(s) affected")
    elif "status" in result:
        print(result["status"])
    else:
        # Fallback: print the dict itself.
        for key, val in result.items():
            print(f"{key}: {val}")


def handle_meta_command(db, cmd: str):
    """Process a dot-prefixed meta command.

    Supported:
        .schema            – print every table's CREATE statement
        .tables            – list table names
        .index <name>      – show indexes for a table
        .help              – show usage
        .exit / .quit      – handled by the caller
    """
    parts = cmd.split()
    name = parts[0].lower()

    if name in (".exit", ".quit"):
        raise SystemExit

    if name == ".tables":
        tables = sorted(db.catalog.tables.keys())
        if not tables:
            print("(no tables)")
        else:
            for t in tables:
                print(t)
        return

    if name == ".schema":
        for tname in sorted(db.catalog.tables.keys()):
            info = db.catalog.tables[tname]
            cols = db.catalog.columns.get(info.table_id, [])
            col_parts = []
            for c in cols:
                parts_str = c.name + " " + c.data_type.value
                if c.is_pk:
                    parts_str += " PRIMARY KEY"
                elif not c.nullable:
                    parts_str += " NOT NULL"
                if c.is_unique and not c.is_pk:
                    parts_str += " UNIQUE"
                col_parts.append(parts_str)
            print(f"CREATE TABLE {tname} ({', '.join(col_parts)});")
        return

    if name == ".index":
        if len(parts) < 2:
            print("Usage: .index <table_name>")
            return
        tname = parts[1]
        info = db.catalog.get_table(tname)
        if info is None:
            print(f"table {tname!r} does not exist")
            return
        idxs = [(t, c) for (t, c) in db.index_manager.indices if t == tname]
        if not idxs:
            print(f"(no indexes on {tname})")
        else:
            for _, col in idxs:
                print(f"CREATE INDEX ON {tname} ({col});")
        return

    if name == ".help":
        print("Meta commands:")
        print("   .tables            list tables")
        print("   .schema            show CREATE TABLE statements")
        print("   .index <table>     show indexes for a table")
        print("   .exit / .quit      close the database and exit")
        print("   .help              show this help")
        return

    print(f"unknown meta command: {cmd!r}  (try .help)")


def repl(db):
    """Run the interactive read-eval-print loop on *db*."""
    while True:
        try:
            line = input("tinydb> ")
        except EOFError:
            print()
            break

        stripped = line.strip()
        if not stripped:
            continue

        # Meta commands.
        if stripped.startswith("."):
            if stripped.lower() in (".exit", ".quit"):
                break
            try:
                handle_meta_command(db, stripped)
            except SystemExit:
                break
            except Exception as e:
                print(f"Error: {e}")
            continue

        # Accumulate lines until a semicolon is seen.
        sql = line
        while not sql.strip().endswith(";"):
            try:
                sql += "\n" + input("     > ")
            except EOFError:
                print()
                break

        sql = sql.strip().rstrip(";").strip()
        if not sql:
            continue

        try:
            result = db.execute(sql)
        except Exception as e:
            print(f"Error: {e}")
            continue

        display_result(result)


def main():
    """CLI entry point."""
    args = sys.argv[1:]
    if not args:
        print("Usage: tinydb <db_path> [sql]")
        sys.exit(1)

    db_path = args[0]
    if len(args) >= 2:
        # Direct SQL mode: execute and exit.
        import tinydb
        with tinydb.open(db_path) as db:
            display_result(db.execute(" ".join(args[1:])))
        return

    import tinydb
    with tinydb.open(db_path) as db:
        repl(db)


if __name__ == "__main__":
    main()
