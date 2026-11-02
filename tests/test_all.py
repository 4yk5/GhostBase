import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_engine import DatabaseEngine
from exporter import Exporter
from main import _load_env_file, detect_connection, parse_args
from app import GhostBaseApp
from textual.widgets import TextArea, DataTable, Label, ListView, Input


def test_engine():
    print("[*] 1. Testing Database Engine (SQLite, Views, FKs, Schema)...")
    db = DatabaseEngine(":memory:")
    
    # 1. Create tables with Foreign Key
    db.execute_query("""
        CREATE TABLE authors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
    """)
    db.execute_query("""
        CREATE TABLE books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER REFERENCES authors(id),
            title TEXT NOT NULL,
            price REAL DEFAULT 0.0
        );
    """)
    # 2. Create view
    db.execute_query("""
        CREATE VIEW book_details AS
        SELECT b.title, a.name AS author
        FROM books b JOIN authors a ON b.author_id = a.id;
    """)
    
    # Test tables & views
    tables = db.get_tables()
    assert "authors" in tables and "books" in tables, f"Tables missing: {tables}"
    
    views = db.get_views()
    assert "book_details" in views, f"Views missing: {views}"
    
    # Test Foreign Keys
    fks = db.get_foreign_keys("books")
    assert len(fks) == 1, f"Expected 1 FK, got {fks}"
    assert fks[0]["to_table"] == "authors"
    
    # Test Schema
    schema = db.get_table_schema("books")
    col_names = [c["name"] for c in schema]
    assert "id" in col_names and "author_id" in col_names and "title" in col_names
    
    # Test Insert & Row Count
    db.execute_query("INSERT INTO authors (name) VALUES ('H.P. Lovecraft');")
    db.execute_query("INSERT INTO books (author_id, title, price) VALUES (1, 'Call of Cthulhu', 19.99);")
    assert db.get_row_count("books") == 1
    
    # Test Select
    res = db.execute_query("SELECT * FROM book_details;")
    assert res["success"] and res["row_count"] == 1
    assert res["rows"][0] == ["Call of Cthulhu", "H.P. Lovecraft"]
    
    # 3. Test EXPLAIN Query Plan (Ctrl+P)
    explain_res = db.explain_query("SELECT * FROM books WHERE id = 1;")
    assert explain_res["success"], f"EXPLAIN failed: {explain_res.get('error')}"
    assert len(explain_res["rows"]) > 0
    
    # 4. Test Production Safety Guard
    unsafe, reason = db.check_safety("DELETE FROM books;")
    assert unsafe and "DELETE without WHERE" in reason, f"Safety check failed: {unsafe}, {reason}"
    
    unsafe, reason = db.check_safety("DROP TABLE authors;")
    assert unsafe and "DROP" in reason
    
    safe, _ = db.check_safety("DELETE FROM books WHERE id = 1;")
    assert not safe, "Safe query flagged as unsafe!"
    
    # 5. Test SQL Beautifier (Ctrl+B)
    raw_sql = "select id, title from books where price > 10 order by id desc limit 5;"
    formatted = DatabaseEngine.format_sql(raw_sql)
    assert "SELECT id, title" in formatted
    assert "FROM books" in formatted
    assert "WHERE price > 10" in formatted
    assert "ORDER BY id DESC" in formatted
    assert "LIMIT 5" in formatted
    
    print("  [+] DB Engine, Safety Guard & SQL Formatter: PASS")
    db.close()


def test_env():
    print("[*] 2. Testing .env Detection...")
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("# Sample env\n")
        f.write("DATABASE_URL=postgresql://user:secret@localhost:5432/ghostdb\n")
        f.write("OTHER_VAR=123\n")
        tmp_name = f.name
    
    try:
        env = _load_env_file(tmp_name)
        assert env.get("DATABASE_URL") == "postgresql://user:secret@localhost:5432/ghostdb"
        assert env.get("OTHER_VAR") == "123"
        assert env.get("NONEXISTENT") is None
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
            
    print("  [+] .env Detection: PASS")


def test_exporters():
    print("[*] 3. Testing Exporters (CSV, JSON, Markdown, SQL INSERTs)...")
    cols = ["id", "name", "price"]
    rows = [[1, "Ghost", 29.99], [2, "Base's Tool", 49.99]]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = os.path.join(tmpdir, "test.csv")
        json_file = os.path.join(tmpdir, "test.json")
        md_file = os.path.join(tmpdir, "test.md")
        sql_file = os.path.join(tmpdir, "test.sql")
        
        Exporter.to_csv(cols, rows, csv_file)
        assert os.path.exists(csv_file)
        
        Exporter.to_json(cols, rows, json_file)
        assert os.path.exists(json_file)
        
        Exporter.to_markdown(cols, rows, md_file)
        assert os.path.exists(md_file)
        with open(md_file, "r", encoding="utf-8") as fh:
            content = fh.read()
            assert "| id | name | price |" in content
            assert "Ghost" in content
            
        Exporter.to_sql_inserts("products", cols, rows, sql_file)
        assert os.path.exists(sql_file)
        with open(sql_file, "r", encoding="utf-8") as fh:
            sql_content = fh.read()
            assert "INSERT INTO products (id, name, price) VALUES" in sql_content
            assert "'Base''s Tool'" in sql_content  # Escape check
        
    print("  [+] Exporters (All 4 formats): PASS")


async def test_tui_app():
    print("[*] 4. Testing TUI App & Keyboard Shortcuts...")
    app = GhostBaseApp(db_path=":memory:", read_only=False)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.2)
        
        qa = app.query_one("#query-box", TextArea)
        dt = app.query_one("#data-table", DataTable)
        search = app.query_one("#table-search", Input)
        status = app.query_one("#status-label", Label)
        
        # 1. Run Query (Ctrl+R)
        qa.text = "SELECT id, name FROM users LIMIT 2;"
        await pilot.press("ctrl+r")
        await pilot.pause(0.1)
        assert dt.row_count == 2
        
        # 2. Explain Plan (Ctrl+P)
        await pilot.press("ctrl+p")
        await pilot.pause(0.1)
        assert "PLAN" in str(status.render())
        
        # 3. Beautify SQL (Ctrl+B)
        qa.text = "select 1 from users where id=1;"
        await pilot.press("ctrl+b")
        await pilot.pause(0.1)
        assert "SELECT 1" in qa.text
        assert "FROM users" in qa.text
        
        # 4. Safe Mode Toggle (Ctrl+S)
        assert app.safe_mode is False
        await pilot.press("ctrl+s")
        await pilot.pause(0.1)
        assert app.safe_mode is True
        
        # 5. Destructive query in Safe Mode blocked
        qa.text = "DROP TABLE users;"
        await pilot.press("ctrl+r")
        await pilot.pause(0.1)
        assert "BLOCKED BY SAFE MODE" in str(status.render())
        
        await pilot.press("ctrl+s")
        await pilot.pause(0.1)
        assert app.safe_mode is False
        
        # 6. New Query (Ctrl+N)
        await pilot.press("ctrl+n")
        await pilot.pause(0.1)
        assert qa.text == ""
        
        # 7. Quit (Ctrl+Q)
        await pilot.press("ctrl+q")
        await pilot.pause(0.1)
        
    print("  [+] TUI (All Shortcuts, Safety & Widgets): PASS")


if __name__ == "__main__":
    test_engine()
    test_env()
    test_exporters()
    asyncio.run(test_tui_app())
    print("\nALL GHOSTBASE CORE & TUI TESTS PASSED PERFECTLY!")
