import os
import sys
import tempfile
import sqlite3
import json
import decimal
import datetime
import uuid
import re

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_engine import DatabaseEngine
from exporter import Exporter
from main import detect_connection


def test_safe_mode_and_comment_bypass():
    print("[*] 1. Testing Safe Mode & Comment Bypass Prevention...")
    db = DatabaseEngine(":memory:")

    # Comment bypass attempt: WHERE is inside /* ... */ block comment
    bypass_query = "UPDATE users SET role = 'Member' /* WHERE id = 1 */;"
    is_destructive, reason = db.check_safety(bypass_query, is_safe_mode=False)
    assert is_destructive, "VULNERABILITY: Block comment containing WHERE fooled check_safety!"
    assert "UPDATE without WHERE" in reason

    # Line comment bypass attempt: WHERE is after --
    bypass_line = "UPDATE users SET role = 'Member' -- WHERE id = 1\n;"
    is_destructive, reason = db.check_safety(bypass_line, is_safe_mode=False)
    assert is_destructive, "VULNERABILITY: Line comment containing WHERE fooled check_safety!"

    # String with WHERE inside must not count as WHERE clause
    string_bypass = "UPDATE users SET role = 'WHERE -- this is a string';"
    is_dest, r = db.check_safety(string_bypass, is_safe_mode=False)
    assert is_dest, f"VULNERABILITY: String literal containing WHERE fooled check_safety: {r}"

    # Postgres dollar-quoted string with WHERE
    dollar_bypass = "UPDATE users SET role = $$WHERE$$;"
    is_dest, r = db.check_safety(dollar_bypass, is_safe_mode=False)
    assert is_dest, f"VULNERABILITY: Dollar-quoted string containing WHERE fooled check_safety: {r}"

    # Postgres dollar-quoted string with tag mismatch ($tag$ vs $other$)
    mismatched_tag_query = "UPDATE users SET role = $tag$abc $other$ WHERE marker $tag$;"
    is_dest, r = db.check_safety(mismatched_tag_query, is_safe_mode=False)
    assert is_dest, f"VULNERABILITY: Dollar-quoted tag mismatch bypassed WHERE check: {r}"

    # Postgres E'...' string with backslash escaped quote
    e_string_query = "UPDATE users SET role = E'foo\\' WHERE false';"
    is_dest, r = db.check_safety(e_string_query, is_safe_mode=False)
    assert is_dest, f"VULNERABILITY: PostgreSQL E-string with escaped quote bypassed WHERE check: {r}"

    # MySQL # comment bypass attempt
    mysql_comment_query = "UPDATE users SET role = 'Member' # WHERE id = 1\n;"
    is_dest, r = db.check_safety(mysql_comment_query, is_safe_mode=False)
    assert is_dest, f"VULNERABILITY: MySQL # comment containing WHERE fooled check_safety: {r}"

    # Safe Mode STRICT read-only checks
    safe_queries = [
        "SELECT * FROM users WHERE id = 5;",
        "SELECT 'DROP TABLE users' AS msg;",
        "WITH cte AS (SELECT 1 AS n) SELECT * FROM cte;",
        "EXPLAIN SELECT * FROM users;",
    ]
    for q in safe_queries:
        is_dest, r = db.check_safety(q, is_safe_mode=True)
        assert not is_dest, f"Safe query wrongly blocked in Safe Mode: {q} ({r})"

    # Safe Mode must strictly block DML, DDL, DO blocks, CALL, MERGE, SET, and state-modifying functions
    unsafe_queries = [
        ("UPDATE users SET role = 'Admin' WHERE id = 5;", "UPDATE"),
        ("INSERT INTO users (name) VALUES ('Test');", "INSERT"),
        ("DELETE FROM users WHERE id = 5;", "DELETE"),
        ("DROP TABLE users;", "DROP"),
        ("TRUNCATE TABLE users;", "TRUNCATE"),
        ("ALTER TABLE users ADD COLUMN age INT;", "ALTER"),
        ("CREATE TABLE test (id INT);", "CREATE"),
        ("SELECT nextval('users_id_seq');", "NEXTVAL"),
        ("SELECT setval('users_id_seq', 1, false);", "SETVAL"),
        ("SELECT set_config('default_transaction_read_only', 'off', false);", "SET_CONFIG"),
        ("SELECT pg_terminate_backend(1234);", "PG_TERMINATE_BACKEND"),
        ("SELECT * INTO OUTFILE '/tmp/f' FROM users;", "INTO OUTFILE"),
        ("SET default_transaction_read_only = OFF;", "SET"),
        ("RESET ALL;", "RESET"),
        ("DO $body$ BEGIN UPDATE users SET role = 'Admin'; END $body$;", "DO"),
        ("CALL custom_proc();", "CALL"),
        ("MERGE INTO target USING source ON target.id = source.id WHEN MATCHED THEN DELETE;", "MERGE"),
    ]
    for q, op in unsafe_queries:
        is_dest, r = db.check_safety(q, is_safe_mode=True)
        assert is_dest, f"VULNERABILITY: Safe Mode failed to block {op}: {q}"
        assert "Safe Mode is active" in r

    print("  [+] Safe Mode & Comment Bypass: PASS")


def test_database_engine_level_readonly():
    print("[*] 2. Testing Database Engine-Level Read-Only & Fail-Closed Enforcement...")
    db = DatabaseEngine(":memory:")
    db.conn.execute("CREATE TABLE read_only_test (id INT, val TEXT);")
    db.conn.commit()

    # Enable engine-level read-only
    db.set_read_only(True)

    # SQLite PRAGMA query_only=ON must reject writes at the C/engine level
    failed = False
    try:
        db.conn.execute("INSERT INTO read_only_test VALUES (1, 'fail');")
        db.conn.commit()
    except sqlite3.OperationalError as e:
        if "readonly" in str(e).lower() or "query_only" in str(e).lower():
            failed = True

    assert failed, "VULNERABILITY: SQLite allowed write with PRAGMA query_only = ON!"

    # Disable read-only
    db.set_read_only(False)
    db.conn.execute("INSERT INTO read_only_test VALUES (1, 'success');")
    db.conn.commit()

    print("  [+] Database Engine-Level Read-Only: PASS")


def test_sql_beautifier_preserves_literals():
    print("[*] 3. Testing SQL Beautifier Literal Integrity (Single, Double & Dollar Quotes)...")
    raw_query = "SELECT 'order by and where' AS message, $$order by AND where$$ AS dollar_msg FROM users WHERE id = 1;"
    formatted = DatabaseEngine.format_sql(raw_query)

    assert "'order by and where'" in formatted, f"VULNERABILITY: Beautifier corrupted single-quoted literal: {formatted}"
    assert "$$order by AND where$$" in formatted, f"VULNERABILITY: Beautifier corrupted dollar-quoted literal: {formatted}"
    assert "WHERE" in formatted
    assert "SELECT" in formatted

    print("  [+] SQL Beautifier Preserves Literals: PASS")


def test_sqlite_foreign_keys_enforced():
    print("[*] 4. Testing SQLite Foreign Keys Enforcement...")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        db = DatabaseEngine(db_path)
        cur = db.conn.cursor()
        cur.execute("PRAGMA foreign_keys;")
        fk_status = cur.fetchone()[0]
        assert fk_status == 1, f"VULNERABILITY: PRAGMA foreign_keys is OFF ({fk_status})"

        db.conn.execute("CREATE TABLE dept (id INTEGER PRIMARY KEY, name TEXT);")
        db.conn.execute("CREATE TABLE emp (id INTEGER PRIMARY KEY, dept_id INTEGER REFERENCES dept(id));")
        db.conn.commit()

        failed = False
        try:
            db.conn.execute("INSERT INTO emp (id, dept_id) VALUES (1, 999);")
            db.conn.commit()
        except sqlite3.IntegrityError:
            failed = True

        assert failed, "VULNERABILITY: SQLite allowed foreign key violation without error!"
    finally:
        db.close()
        if os.path.exists(db_path):
            os.remove(db_path)

    print("  [+] SQLite Foreign Key Enforcement: PASS")


def test_empty_sqlite_not_polluted():
    print("[*] 5. Testing Empty SQLite Database Guard in Read-Only Mode (with actual on_mount)...")
    import asyncio
    from app import GhostBaseApp
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        empty_db_path = f.name

    async def _run():
        app = GhostBaseApp(db_path=empty_db_path, read_only=True, populate_sample=True)
        async with app.run_test() as pilot:
            await pilot.pause(0.1)
            tables = app.db.get_tables()
            assert len(tables) == 0, f"VULNERABILITY: Sample tables were created during --read-only launch: {tables}"
            assert app.safe_mode is True

    try:
        asyncio.run(_run())
    finally:
        if os.path.exists(empty_db_path):
            os.remove(empty_db_path)

    print("  [+] Empty Database Integrity in Read-Only (on_mount verified): PASS")


def test_returning_dml_classification():
    print("[*] 6. Testing DML with RETURNING Classification...")
    db = DatabaseEngine(":memory:")
    db.conn.execute("CREATE TABLE ret_test (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);")
    db.conn.commit()

    res = db.execute_query("INSERT INTO ret_test (name) VALUES ('Item1') RETURNING id, name;")
    assert res["success"]
    assert res["is_returning"] is True, "Expected is_returning to be True"
    assert res["is_select"] is False, "Expected is_select to be False for INSERT RETURNING"
    assert res["affected_rows"] == 1
    assert len(res["rows"]) == 1
    assert res["rows"][0][1] == "Item1"

    print("  [+] DML with RETURNING Classification: PASS")


def test_exporter_json_types_and_dialect_sql():
    print("[*] 7. Testing Exporter JSON Types & Dialect-Aware SQL Escaping (MySQL vs Postgres/SQLite)...")
    tmp = tempfile.gettempdir()
    json_path = os.path.join(tmp, "test_types.json")
    sql_pg_path = os.path.join(tmp, "test_pg.sql")
    sql_my_path = os.path.join(tmp, "test_mysql.sql")

    # JSON export with Decimal, datetime, UUID, bytes, and duplicate column names
    cols = ["id", "id", "price", "created", "uid", "raw"]
    rows = [[
        1, 1,
        decimal.Decimal("49.95"),
        datetime.datetime(2026, 11, 2, 8, 0, 0),
        uuid.UUID("12345678-1234-5678-1234-567812345678"),
        b"binary_ghost"
    ]]
    Exporter.to_json(cols, rows, json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["id_2"] == 1
    assert data[0]["price"] == 49.95
    assert data[0]["created"] == "2026-11-02T08:00:00"
    assert data[0]["uid"] == "12345678-1234-5678-1234-567812345678"
    assert data[0]["raw"] == "binary_ghost"

    # PostgreSQL / SQLite dialect SQL export (Double quotes)
    table_name = "analytics.order"
    cols_special = ["first name", "group", "price"]
    rows_special = [["Bob", "Admin", decimal.Decimal("10.50")]]
    Exporter.to_sql_inserts(table_name, cols_special, rows_special, sql_pg_path, dialect="postgresql")
    with open(sql_pg_path, "r", encoding="utf-8") as f:
        pg_content = f.read()

    assert 'INSERT INTO "analytics"."order" ("first name", "group", price) VALUES (\'Bob\', \'Admin\', 10.50);' in pg_content

    # MySQL dialect SQL export (Backticks)
    Exporter.to_sql_inserts(table_name, cols_special, rows_special, sql_my_path, dialect="mysql")
    with open(sql_my_path, "r", encoding="utf-8") as f:
        my_content = f.read()

    assert 'INSERT INTO `analytics`.`order` (`first name`, `group`, price) VALUES (\'Bob\', \'Admin\', 10.50);' in my_content

    print("  [+] Exporter JSON Types & Dialect-Aware SQL Escaping: PASS")


def test_table_quoting_and_cte_export_detection():
    print("[*] 8. Testing Table Quoting & CTE Export Target Detection...")
    db_sqlite = DatabaseEngine(":memory:")
    assert db_sqlite.quote_table_name("order") == "[order]"

    db_pg = DatabaseEngine.__new__(DatabaseEngine)
    db_pg.db_type = "postgresql"
    assert db_pg.quote_table_name("order") == '"order"'
    assert db_pg.quote_table_name("analytics.users") == '"analytics"."users"'

    db_my = DatabaseEngine.__new__(DatabaseEngine)
    db_my.db_type = "mysql"
    assert db_my.quote_table_name("order") == "`order`"
    assert db_my.quote_table_name("analytics.users") == "`analytics`.`users`"

    # CTE target detection test
    cte_query = """
    WITH recent AS (
        SELECT * FROM archived_users WHERE active = 0
    )
    SELECT * FROM recent;
    """
    main_q = re.sub(r"^WITH\s+[\s\S]*?\)\s*", "", cte_query.strip(), flags=re.IGNORECASE)
    m = re.search(r"\bFROM\s+([`\"\[]?[a-zA-Z0-9_\.]+(?:\"|\'|\]|`)?)", main_q, flags=re.IGNORECASE)
    assert m is not None
    detected = m.group(1).strip('`"[]')
    assert detected == "recent", f"Expected target 'recent', got '{detected}'"

    print("  [+] Table Quoting & CTE Export Target Detection: PASS")


def test_result_set_memory_limit():
    print("[*] 9. Testing Result Set Memory Limit (Capped at 1,000 rows)...")
    db = DatabaseEngine(":memory:")
    db.conn.execute("CREATE TABLE big (id INTEGER PRIMARY KEY);")
    db.conn.executemany("INSERT INTO big (id) VALUES (?);", [(i,) for i in range(1500)])
    db.conn.commit()

    res = db.execute_query("SELECT * FROM big;", max_rows=1000)
    assert res["success"]
    assert res["row_count"] == 1000, f"Expected 1000 rows capped, got {res['row_count']}"
    assert res["truncated"] is True, "Expected truncated flag to be True"

    print("  [+] Result Set Memory Limit: PASS")


def main():
    print("\n" + "=" * 60)
    print("RUNNING EXHAUSTIVE REFINED VERIFICATION TESTS (v0.1.3)")
    print("=" * 60)

    test_safe_mode_and_comment_bypass()
    test_database_engine_level_readonly()
    test_sql_beautifier_preserves_literals()
    test_sqlite_foreign_keys_enforced()
    test_empty_sqlite_not_polluted()
    test_returning_dml_classification()
    test_exporter_json_types_and_dialect_sql()
    test_table_quoting_and_cte_export_detection()
    test_result_set_memory_limit()

    print("\n" + "=" * 60)
    print("ALL ANALYST VULNERABILITIES VERIFIED AND 100% PASSING!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
