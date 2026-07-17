"""Interactive REPL / CLI for tinydb.

Features:
    - readline line editing and history
    - SQL syntax highlighting
    - Multi-line input with continuation prompt
    - .explain, .dump, .version, .mode meta commands
"""

import os
import sys
import atexit

VERSION = "0.2.0"

# ANSI color codes
_KEYWORD_COLOR = "\033[1;34m"   # bold blue
_STRING_COLOR = "\033[0;32m"    # green
_NUMBER_COLOR = "\033[0;33m"    # yellow
_RESET = "\033[0m"

# SQL keywords for highlighting
_SQL_KEYWORDS = {
    'SELECT', 'FROM', 'WHERE', 'INSERT', 'INTO', 'VALUES',
    'UPDATE', 'SET', 'DELETE', 'CREATE', 'TABLE', 'DROP',
    'ORDER', 'BY', 'LIMIT', 'OFFSET', 'AND', 'OR', 'NOT',
    'NULL', 'PRIMARY', 'KEY', 'UNIQUE', 'INDEX', 'ON',
    'ASC', 'DESC', 'BEGIN', 'COMMIT', 'ROLLBACK',
    'INT', 'FLOAT', 'TEXT', 'BOOL',
    'COUNT', 'SUM', 'AVG', 'GROUP',
    'JOIN', 'INNER', 'LEFT', 'RIGHT', 'CROSS', 'FULL', 'OUTER',
    'AS', 'EXPLAIN', 'HAVING', 'DISTINCT',
}

HISTORY_FILE = os.path.expanduser("~/.tinydb_history")


def _highlight_sql(sql: str) -> str:
    """Apply ANSI syntax highlighting to SQL input."""
    import re
    result = []
    i = 0
    n = len(sql)

    while i < n:
        ch = sql[i]

        # String literal
        if ch == "'":
            start = i
            i += 1
            while i < n and sql[i] != "'":
                if sql[i] == "'" and i + 1 < n and sql[i + 1] == "'":
                    i += 2
                    continue
                i += 1
            i += 1  # closing quote
            result.append(f"{_STRING_COLOR}{sql[start:i]}{_RESET}")
            continue

        # Number
        if ch.isdigit():
            start = i
            while i < n and (sql[i].isdigit() or sql[i] == '.'):
                i += 1
            result.append(f"{_NUMBER_COLOR}{sql[start:i]}{_RESET}")
            continue

        # Identifier or keyword
        if ch.isalpha() or ch == '_':
            start = i
            while i < n and (sql[i].isalnum() or sql[i] == '_'):
                i += 1
            word = sql[start:i]
            if word.upper() in _SQL_KEYWORDS:
                result.append(f"{_KEYWORD_COLOR}{word}{_RESET}")
            else:
                result.append(word)
            continue

        # Dot (for table.column)
        if ch == '.':
            result.append(ch)
            i += 1
            continue

        # Other characters
        result.append(ch)
        i += 1

    return ''.join(result)


def _setup_readline():
    """Configure readline for line editing and history."""
    try:
        import readline
        readline.parse_and_bind("tab: complete")
        readline.set_completer(_completer)
        if os.path.exists(HISTORY_FILE):
            readline.read_history_file(HISTORY_FILE)
        atexit.register(lambda: readline.write_history_file(HISTORY_FILE))
    except ImportError:
        pass  # readline not available on Windows


def _completer(text, state):
    """Tab completer for SQL keywords and meta commands."""
    import readline
    line = readline.get_line_buffer()
    words = line.split()

    # Meta commands
    meta_cmds = ['.tables', '.schema', '.index', '.explain', '.dump',
                  '.version', '.mode', '.help', '.exit', '.quit']

    candidates = []

    if text.startswith('.'):
        candidates = [c for c in meta_cmds if c.startswith(text)]
    else:
        # SQL keywords
        candidates = [k.lower() for k in _SQL_KEYWORDS if k.lower().startswith(text.lower())]

    if state < len(candidates):
        return candidates[state]
    return None


def display_result(result):
    """Format and print the output of a Database.execute call."""
    if isinstance(result, list):
        _display_rows(result)
    elif isinstance(result, dict):
        if "plan" in result:
            _display_plan(result["plan"])
        else:
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


def _display_rows_csv(rows: list):
    """Render rows as CSV."""
    if not rows:
        return
    columns = list(rows[0].keys())
    print(",".join(columns))
    for row in rows:
        print(",".join(str(row.get(col, "")) for col in columns))


def _display_status(result: dict):
    """Render a status/affected-rows dict."""
    if "affected_rows" in result:
        n = result["affected_rows"]
        print(f"{n} row(s) affected")
    elif "status" in result:
        print(result["status"])
    else:
        for key, val in result.items():
            print(f"{key}: {val}")


def _display_plan(plan: list):
    """Render an execution plan."""
    for i, node in enumerate(plan):
        prefix = "-> " if i > 0 else ""
        ntype = node.get("type", "?")
        extras = {k: v for k, v in node.items() if k != "type"}
        if extras:
            extra_str = ", ".join(f"{k}={v}" for k, v in extras.items())
            print(f"{prefix}{ntype} ({extra_str})")
        else:
            print(f"{prefix}{ntype}")


def handle_meta_command(db, cmd: str, output_mode: str = "table"):
    """Process a dot-prefixed meta command.

    Returns (handled, output_mode) tuple.
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
        return True, output_mode

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
        return True, output_mode

    if name == ".index":
        if len(parts) < 2:
            print("Usage: .index <table_name>")
            return True, output_mode
        tname = parts[1]
        info = db.catalog.get_table(tname)
        if info is None:
            print(f"table {tname!r} does not exist")
            return True, output_mode
        idxs = [(t, c) for (t, c) in db.index_manager.indices if t == tname]
        if not idxs:
            print(f"(no indexes on {tname})")
        else:
            for _, col in idxs:
                print(f"CREATE INDEX ON {tname} ({col});")
        return True, output_mode

    if name == ".explain":
        if len(parts) < 2:
            print("Usage: .explain <sql>")
            return True, output_mode
        sql = " ".join(parts[1:])
        if not sql.strip().upper().startswith("EXPLAIN"):
            sql = "EXPLAIN " + sql
        try:
            result = db.execute(sql)
            display_result(result)
        except Exception as e:
            print(f"Error: {e}")
        return True, output_mode

    if name == ".dump":
        _dump_db(db, parts[1] if len(parts) > 1 else None)
        return True, output_mode

    if name == ".version":
        print(f"TinyDB v{VERSION}")
        return True, output_mode

    if name == ".mode":
        if len(parts) < 2:
            print(f"Current mode: {output_mode}")
            print("Available modes: table, csv")
            return True, output_mode
        mode = parts[1].lower()
        if mode in ("table", "csv"):
            output_mode = mode
            print(f"Output mode set to {mode}")
        else:
            print(f"Unknown mode: {mode}. Use 'table' or 'csv'.")
        return True, output_mode

    if name == ".help":
        print("Meta commands:")
        print("   .tables              list tables")
        print("   .schema              show CREATE TABLE statements")
        print("   .index <table>       show indexes for a table")
        print("   .explain <sql>       show execution plan")
        print("   .dump [table]        export SQL for table or all tables")
        print("   .version             show TinyDB version")
        print("   .mode table|csv      set output format")
        print("   .exit / .quit        close the database and exit")
        print("   .help                show this help")
        return True, output_mode

    print(f"unknown meta command: {cmd!r}  (try .help)")
    return True, output_mode


def _dump_db(db, table_name=None):
    """Export SQL for tables."""
    tables = [table_name] if table_name else sorted(db.catalog.tables.keys())

    for tname in tables:
        info = db.catalog.get_table(tname)
        if info is None:
            print(f"-- table {tname!r} does not exist")
            continue

        # CREATE TABLE
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

        # INSERT statements
        table_obj = db.catalog.get_table_object(tname)
        if table_obj:
            for row in table_obj.scan():
                vals = []
                for v in row.values:
                    if v is None:
                        vals.append("NULL")
                    elif isinstance(v, str):
                        vals.append(f"'{v}'")
                    elif isinstance(v, bool):
                        vals.append("TRUE" if v else "FALSE")
                    else:
                        vals.append(str(v))
                print(f"INSERT INTO {tname} VALUES ({', '.join(vals)});")


def repl(db):
    """Run the interactive read-eval-print loop."""
    _setup_readline()
    output_mode = "table"

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
                _, output_mode = handle_meta_command(db, stripped, output_mode)
            except SystemExit:
                break
            except Exception as e:
                print(f"Error: {e}")
            continue

        # Highlight the input line
        try:
            import readline
            # readline handles display; we just highlight in the prompt
        except ImportError:
            pass

        # Accumulate lines until a semicolon is seen.
        sql = line
        while not sql.strip().endswith(";"):
            try:
                sql += "\n" + input("  ...> ")
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

        if output_mode == "csv" and isinstance(result, list):
            _display_rows_csv(result)
        else:
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
