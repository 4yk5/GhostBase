import asyncio
import os
import sys
import tempfile
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from db_engine import DatabaseEngine
from exporter import Exporter
from app import GhostBaseApp
from textual.widgets import TextArea, DataTable, Label, ListView, Input, Static


def create_realistic_database(db_path: str):
    """Build an eCommerce relational database with foreign keys, indexes, and views."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        );

        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER DEFAULT 0
        );

        CREATE INDEX idx_products_sku ON products(sku);

        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            tier TEXT DEFAULT 'Standard',
            balance REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
            total_amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_orders_customer ON orders(customer_id);

        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL
        );

        CREATE VIEW v_order_summary AS
        SELECT
            o.id AS order_id,
            c.full_name AS customer,
            c.email,
            o.total_amount,
            o.status,
            o.created_at
        FROM orders o
        JOIN customers c ON o.customer_id = c.id;

        CREATE VIEW v_low_stock AS
        SELECT sku, name, price, stock
        FROM products
        WHERE stock < 20;

        -- Seed Categories
        INSERT INTO categories (name, description) VALUES
        ('Electronics', 'Gadgets, hardware, and tech gear'),
        ('Books', 'Technical books and developer guides'),
        ('Software', 'Developer tools and terminal utilities');

        -- Seed Products
        INSERT INTO products (category_id, sku, name, price, stock) VALUES
        (1, 'ELEC-001', 'Mechanical Keyboard 65%', 119.99, 45),
        (1, 'ELEC-002', 'USB-C Portable Hub', 34.50, 12),
        (2, 'BOOK-101', 'Designing Data-Intensive Applications', 42.00, 8),
        (2, 'BOOK-102', 'Database Internals', 49.95, 25),
        (3, 'SOFT-201', 'GhostBase Terminal Pro', 29.00, 999),
        (3, 'SOFT-202', 'Terminal Cyberpunk Theme Pack', 9.99, 500);

        -- Seed Customers
        INSERT INTO customers (email, full_name, tier, balance) VALUES
        ('alex.rivers@example.com', 'Alex Rivers', 'VIP', 250.00),
        ('sam.vance@example.com', 'Sam Vance', 'Standard', 45.50),
        ('jordan.lee@example.com', 'Jordan Lee', 'VIP', 1200.00),
        ('morgan.blake@example.com', 'Morgan Blake', 'Standard', 0.00);

        -- Seed Orders
        INSERT INTO orders (customer_id, total_amount, status) VALUES
        (1, 154.49, 'delivered'),
        (1, 29.00,  'shipped'),
        (2, 42.00,  'delivered'),
        (3, 119.99, 'processing');

        -- Seed Order Items
        INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
        (1, 1, 1, 119.99),
        (1, 2, 1, 34.50),
        (2, 5, 1, 29.00),
        (3, 3, 1, 42.00),
        (4, 1, 1, 119.99);
    """)

    conn.commit()
    conn.close()


def test_real_database_engine(db_path: str):
    print("\n--- Testing Real Database Engine Operations ---")
    engine = DatabaseEngine(db_path)

    # 1. Tables and Views
    tables = engine.get_tables()
    assert "categories" in tables
    assert "products" in tables
    assert "customers" in tables
    assert "orders" in tables
    assert "order_items" in tables
    print(f"  [+] Tables discovered: {tables}")

    views = engine.get_views()
    assert "v_order_summary" in views
    assert "v_low_stock" in views
    print(f"  [+] Views discovered: {views}")

    # 2. Schema and Foreign Keys
    order_items_schema = engine.get_table_schema("order_items")
    col_names = [c["name"] for c in order_items_schema]
    assert col_names == ["id", "order_id", "product_id", "quantity", "unit_price"]
    assert order_items_schema[0]["pk"] == 1  # id is PK

    fks = engine.get_foreign_keys("order_items")
    assert len(fks) == 2
    fk_targets = {fk["to_table"] for fk in fks}
    assert "orders" in fk_targets and "products" in fk_targets
    print("  [+] Schema & Foreign Keys verified (orders & products FKs found)")

    # 3. Complex Aggregation Query
    complex_sql = """
        SELECT
            c.full_name,
            c.tier,
            COUNT(o.id) AS total_orders,
            ROUND(SUM(o.total_amount), 2) AS total_spend
        FROM customers c
        JOIN orders o ON c.id = o.customer_id
        GROUP BY c.id
        HAVING total_spend > 50
        ORDER BY total_spend DESC;
    """
    res = engine.execute_query(complex_sql)
    assert res["success"] is True
    assert res["row_count"] == 2
    assert res["rows"][0][0] == "Alex Rivers"
    assert res["rows"][0][3] == 183.49
    print(f"  [+] Complex multi-table JOIN & Aggregation: PASS ({res['elapsed_ms']}ms)")

    # 4. View Query
    v_res = engine.execute_query("SELECT * FROM v_order_summary WHERE status = 'delivered';")
    assert v_res["success"] is True
    assert v_res["row_count"] == 2
    print("  [+] View execution: PASS")

    # 5. Indexed EXPLAIN Query Plan
    explain_res = engine.explain_query("SELECT * FROM products WHERE sku = 'ELEC-001';")
    assert explain_res["success"] is True
    plan_text = " ".join(str(r) for r in explain_res["rows"])
    assert "INDEX" in plan_text
    print(f"  [+] EXPLAIN query plan verified (Indexed lookup): PASS")

    # 6. SQL Formatter on Real Query
    ugly = "select c.name, count(p.id) from categories c left join products p on c.id=p.category_id group by c.id order by c.name asc limit 10;"
    pretty = DatabaseEngine.format_sql(ugly)
    assert "SELECT c.name, COUNT(p.id)" in pretty
    assert "\nFROM categories c" in pretty
    assert "\nLEFT JOIN products p" in pretty
    assert "\nGROUP BY c.id" in pretty
    assert "\nORDER BY c.name ASC" in pretty
    print("  [+] SQL Formatter on complex statement: PASS")

    # 7. Safety Interception on Real Table
    is_safe, reason = engine.check_safety("DELETE FROM products;")
    assert is_safe is True
    assert "DELETE without WHERE" in reason

    is_safe, reason = engine.check_safety("UPDATE products SET price = 0.0;")
    assert is_safe is True
    assert "UPDATE without WHERE" in reason
    print("  [+] Safety Guard on real tables: PASS")

    engine.close()


async def test_real_database_tui(db_path: str):
    print("\n--- Testing TUI Interface Against Real Database ---")
    app = GhostBaseApp(db_path=db_path, read_only=False)

    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause(0.2)

        qa = app.query_one("#query-box", TextArea)
        dt = app.query_one("#data-table", DataTable)
        search = app.query_one("#table-search", Input)
        status = app.query_one("#status-label", Label)
        schema_panel = app.query_one("#schema-panel")
        schema_content = app.query_one("#schema-content", Static)

        # 1. Sidebar Explorer populated
        lv = app.query_one("#tables-list", ListView)
        assert len(lv.children) >= 7  # 5 tables + 2 views + headers
        print("  [+] Real database tables & views mounted in Explorer")

        # 2. Select order_items from sidebar and verify schema inspector
        items = [item for item in lv.children if getattr(item, "table_name", None) == "order_items"]
        assert len(items) == 1
        await pilot.click(items[0])
        await pilot.pause(0.2)
        assert schema_panel.has_class("visible")
        assert "orders.id" in str(schema_content.render())
        assert "products.id" in str(schema_content.render())
        print("  [+] Schema inspector correctly displayed Foreign Keys for order_items")

        # 3. Execute Custom Complex Query via Ctrl+R
        qa.text = """SELECT p.name, p.price, c.name AS category
FROM products p
JOIN categories c ON p.category_id = c.id
ORDER BY p.price DESC;"""
        await pilot.press("ctrl+r")
        await pilot.pause(0.2)
        assert dt.row_count == 6
        assert "OK" in str(status.render())
        print("  [+] Complex query executed and rendered in DataTable (6 rows)")

        # 4. 1-Key EXPLAIN (Ctrl+P)
        await pilot.press("ctrl+p")
        await pilot.pause(0.2)
        assert dt.row_count > 0
        assert "PLAN" in str(status.render())
        print("  [+] Ctrl+P EXPLAIN Plan executed on real query")

        # 5. SQL Beautifier (Ctrl+B)
        qa.text = "select id, name, price from products where price > 30 and stock > 5 order by price desc;"
        await pilot.press("ctrl+b")
        await pilot.pause(0.1)
        assert "SELECT id, name, price" in qa.text
        assert "\nFROM products" in qa.text
        assert "\nWHERE price > 30" in qa.text
        assert "\n  AND stock > 5" in qa.text
        print("  [+] Ctrl+B Beautify SQL formatted editor text perfectly")

        # 6. Run query & Export all 4 formats
        await pilot.press("ctrl+r")
        await pilot.pause(0.2)
        assert dt.row_count == 4

        dir_path = os.path.dirname(os.path.abspath(db_path))
        csv_file = os.path.join(dir_path, "ghostbase_export.csv")
        json_file = os.path.join(dir_path, "ghostbase_export.json")
        md_file = os.path.join(dir_path, "ghostbase_export.md")
        sql_file = os.path.join(dir_path, "ghostbase_export.sql")

        # CSV
        await pilot.press("ctrl+e")
        await pilot.pause(0.1)
        assert os.path.exists(csv_file)
        with open(csv_file, "r", encoding="utf-8") as f:
            assert "Mechanical Keyboard" in f.read()
        os.remove(csv_file)

        # JSON
        await pilot.press("ctrl+j")
        await pilot.pause(0.1)
        assert os.path.exists(json_file)
        with open(json_file, "r", encoding="utf-8") as f:
            assert '"price": 119.99' in f.read()
        os.remove(json_file)

        # Markdown
        await pilot.press("ctrl+m")
        await pilot.pause(0.1)
        assert os.path.exists(md_file)
        with open(md_file, "r", encoding="utf-8") as f:
            assert "| id | name | price |" in f.read()
        os.remove(md_file)

        # SQL
        await pilot.press("ctrl+i")
        await pilot.pause(0.1)
        assert os.path.exists(sql_file)
        with open(sql_file, "r", encoding="utf-8") as f:
            assert "INSERT INTO" in f.read()
        os.remove(sql_file)
        print("  [+] All 4 exports verified with real query results")

        # 7. Safe Mode Interception
        await pilot.press("ctrl+s")
        await pilot.pause(0.1)
        assert app.safe_mode is True

        qa.text = "DROP TABLE order_items;"
        await pilot.press("ctrl+r")
        await pilot.pause(0.1)
        assert "BLOCKED BY SAFE MODE" in str(status.render())

        # Turn Safe Mode OFF
        await pilot.press("ctrl+s")
        await pilot.pause(0.1)
        assert app.safe_mode is False

        # First destructive attempt -> DANGER warning
        await pilot.press("ctrl+r")
        await pilot.pause(0.1)
        assert "DANGER" in str(status.render())

        # Second attempt -> confirms and drops table
        await pilot.press("ctrl+r")
        await pilot.pause(0.2)
        assert "order_items" not in app.db.get_tables()
        print("  [+] Safe Mode and Double-Confirmation Guard verified on real table DROP")

        # 8. Quit cleanly
        await pilot.press("ctrl+q")
        await pilot.pause(0.1)
        print("  [+] Clean quit & disconnect: PASS")


def main():
    print("=" * 70)
    print("GHOSTBASE REAL DATABASE COMPREHENSIVE VERIFICATION")
    print("=" * 70)

    db_path = os.path.abspath("real_ecom.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    try:
        create_realistic_database(db_path)
        test_real_database_engine(db_path)
        asyncio.run(test_real_database_tui(db_path))

        print("\n" + "=" * 70)
        print("ALL REAL DATABASE ENGINE & TUI FUNCTIONS VERIFIED 100%!")
        print("=" * 70)
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass


if __name__ == "__main__":
    main()
