import sys
import os
import time
import re

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Footer, Label, Button, ListView, ListItem,
    DataTable, TextArea, Static, Input
)
from textual.binding import Binding
from textual.reactive import reactive
from rich.text import Text

from db_engine import DatabaseEngine
from exporter import Exporter

TCSS = """
Screen {
    background: #0d1117;
    color: #c9d1d9;
}

/* Header */
#header-bar {
    height: 3;
    dock: top;
    background: #161b22;
    border-bottom: solid #30363d;
    align: left middle;
    padding: 0 1;
}
#title-label {
    color: #79c0ff;
    text-style: bold;
    margin-right: 2;
}
#db-type-label {
    color: #3fb950;
    text-style: bold;
    margin-right: 1;
}
#db-name-label {
    color: #8b949e;
    margin-right: 2;
}
#safe-badge {
    color: #3fb950;
    text-style: bold;
    margin-right: 2;
}
#safe-badge.unsafe {
    color: #f85149;
}
#version-label {
    color: #484f58;
}

/* Layout */
#main-container {
    height: 1fr;
}

/* Sidebar */
#sidebar {
    width: 22;
    background: #0d1117;
    border-right: solid #30363d;
}
#sidebar-header {
    height: 3;
    background: #161b22;
    border-bottom: solid #30363d;
    align: left middle;
    padding: 0 1;
}
#sidebar-title {
    color: #f0883e;
    text-style: bold;
}
#sidebar-count {
    color: #484f58;
    margin-left: 1;
}
#table-search {
    height: 3;
    background: #010409;
    border: none;
    border-bottom: solid #30363d;
    color: #c9d1d9;
    padding: 0 1;
}
#table-search:focus {
    border-bottom: solid #388bfd;
}
#tables-list {
    height: 1fr;
    background: #0d1117;
}
ListItem {
    padding: 0 1;
    background: #0d1117;
    color: #c9d1d9;
}
ListItem:hover {
    background: #161b22;
    color: #79c0ff;
}
ListItem.--highlight {
    background: #1c2128;
    color: #79c0ff;
}
ListItem.section-header {
    color: #484f58;
    background: #0d1117;
    text-style: bold;
    padding: 1 1 0 1;
}

/* Schema panel */
#schema-panel {
    height: auto;
    max-height: 14;
    background: #010409;
    border-top: solid #30363d;
    padding: 1 1;
    display: none;
}
#schema-panel.visible {
    display: block;
}
#schema-title {
    color: #f0883e;
    text-style: bold;
}
#schema-content {
    color: #8b949e;
}

/* Content Area */
#content-area {
    width: 1fr;
    background: #0d1117;
}

/* Query Editor */
#query-box {
    height: 9;
    background: #010409;
    border-bottom: solid #30363d;
    color: #e6edf3;
}
#query-box:focus {
    border-bottom: solid #388bfd;
}

/* Toolbar */
#toolbar {
    height: 3;
    background: #161b22;
    border-bottom: solid #30363d;
    align: left middle;
    padding: 0 1;
}
#toolbar Button {
    margin-right: 1;
    min-width: 8;
    height: 1;
    border: none;
}
#btn-run {
    background: #238636;
    color: #ffffff;
}
#btn-run:hover {
    background: #2ea043;
}
#btn-explain {
    background: #1f6feb;
    color: #ffffff;
}
#btn-explain:hover {
    background: #388bfd;
}
#btn-format {
    background: #21262d;
    color: #c9d1d9;
}
#btn-format:hover {
    background: #30363d;
}
#btn-clear {
    background: #21262d;
    color: #8b949e;
}
#btn-clear:hover {
    background: #30363d;
    color: #f85149;
}
#btn-safe {
    background: #21262d;
    color: #3fb950;
}
#btn-safe:hover {
    background: #30363d;
}
#status-label {
    margin-left: 2;
    color: #8b949e;
}

/* Results Bar */
#results-bar {
    height: 3;
    background: #161b22;
    border-bottom: solid #30363d;
    align: left middle;
    padding: 0 1;
}
#results-title {
    color: #58a6ff;
    text-style: bold;
}
#results-count {
    color: #484f58;
    margin-left: 1;
}
.export-sep {
    color: #30363d;
    margin: 0 1;
}
.export-label {
    color: #484f58;
    margin-right: 1;
}
#results-bar Button {
    margin-right: 1;
    min-width: 6;
    height: 1;
    border: none;
    background: #21262d;
    color: #8b949e;
}
#results-bar Button:hover {
    background: #30363d;
    color: #c9d1d9;
}

/* Data Table */
#data-table {
    height: 1fr;
    background: #0d1117;
}

/* Status Bar */
#status-bar {
    height: 1;
    dock: bottom;
    background: #161b22;
    border-top: solid #30363d;
    align: left middle;
    padding: 0 2;
}
#status-bar-text {
    color: #484f58;
}

Footer {
    background: #010409;
    color: #484f58;
    height: 1;
}
Footer > .footer--key {
    color: #79c0ff;
    background: #21262d;
}
"""


class GhostBaseApp(App):
    TITLE = "GhostBase 👻 - Terminal Database Studio"
    CSS = TCSS
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("ctrl+r", "run_query",       "Run Query",     priority=True),
        Binding("ctrl+p", "explain_query",   "Explain Plan", priority=True),
        Binding("ctrl+b", "beautify_sql",    "Beautify SQL", priority=True),
        Binding("ctrl+s", "toggle_safe_mode", "Safe Mode",    priority=True),
        Binding("ctrl+n", "clear_query",     "New Query",    priority=True),
        Binding("ctrl+e", "export_csv",      "Export CSV",   priority=True, show=False),
        Binding("ctrl+j", "export_json",     "Export JSON",  priority=True, show=False),
        Binding("ctrl+m", "export_markdown", "Export MD",    priority=True, show=False),
        Binding("ctrl+i", "export_sql",      "Export SQL",   priority=True, show=False),
        Binding("ctrl+f", "focus_filter",    "Find Table",   priority=True, show=False),
        Binding("ctrl+up",   "history_prev", "Prev Query",   priority=True, show=False),
        Binding("ctrl+down", "history_next", "Next Query",   priority=True, show=False),
        Binding("ctrl+q", "quit",            "Quit",         priority=True),
    ]

    selected_table: reactive[str] = reactive("")
    safe_mode: reactive[bool] = reactive(False)

    def __init__(self, db_path: str = None, read_only: bool = False, populate_sample: bool = False):
        super().__init__()
        self.db_path = db_path or "sample.db"
        self.populate_sample = populate_sample
        self.db = DatabaseEngine(self.db_path)
        self._cli_read_only = bool(read_only)
        self.safe_mode = bool(read_only)
        self.last_columns: list = []
        self.last_rows:    list = []
        self.last_query_table: str = None
        self.query_history: list = []
        self.history_index: int = -1
        self.all_tables: list = []
        self.all_views:  list = []
        self._row_count_cache: dict = {}
        self._pending_destructive_query = None
        self._pending_destructive_time = 0.0

    # Layout

    def compose(self) -> ComposeResult:
        db_label = (
            self.db.db_name
            if self.db.db_type != "sqlite"
            else os.path.basename(self.db_path)
        )
        if self._cli_read_only:
            safe_text = "[SAFE: LOCKED]"
            safe_class = ""
        else:
            safe_text = "[SAFE: ON]" if self.safe_mode else "[SAFE: OFF]"
            safe_class = "" if self.safe_mode else "unsafe"

        with Horizontal(id="header-bar"):
            yield Label("GHOSTBASE", id="title-label")
            yield Label(f"[{self.db.db_type_label()}]", id="db-type-label")
            yield Label(db_label, id="db-name-label")
            yield Label(safe_text, id="safe-badge", classes=safe_class)
            yield Label("v0.1.5", id="version-label")

        with Horizontal(id="main-container"):
            with Vertical(id="sidebar"):
                with Horizontal(id="sidebar-header"):
                    yield Label("EXPLORER", id="sidebar-title")
                    yield Label("", id="sidebar-count")
                yield Input(placeholder="Filter (Ctrl+F)...", id="table-search")
                yield ListView(id="tables-list")
                with Vertical(id="schema-panel"):
                    yield Label("", id="schema-title")
                    yield Static("", id="schema-content")

            with Vertical(id="content-area"):
                yield TextArea(
                    id="query-box",
                    language="sql",
                    text="SELECT * FROM users LIMIT 50;",
                )
                with Horizontal(id="toolbar"):
                    yield Button("RUN",      id="btn-run", variant="success")
                    yield Button("EXPLAIN",  id="btn-explain")
                    yield Button("FORMAT",   id="btn-format")
                    yield Button("CLEAR",    id="btn-clear")
                    yield Button("SAFE",     id="btn-safe")
                    yield Label("Ready", id="status-label")

                with Horizontal(id="results-bar"):
                    yield Label("RESULTS", id="results-title")
                    yield Label("", id="results-count")
                    yield Label("|", classes="export-sep")
                    yield Label("Export:", classes="export-label")
                    yield Button("CSV",  id="btn-csv")
                    yield Button("JSON", id="btn-json")
                    yield Button("MD",   id="btn-md")
                    yield Button("SQL",  id="btn-sql")

                yield DataTable(id="data-table", zebra_stripes=True, cursor_type="row")

        with Horizontal(id="status-bar"):
            yield Label("", id="status-bar-text")

        yield Footer()

    # Lifecycle

    async def on_mount(self):
        # Configure database engine level Read-Only mode if safe_mode is enabled (strictly fail-closed)
        if self.safe_mode:
            try:
                self.db.set_read_only(True)
            except Exception as e:
                self.notify(f"Security Alert: Failed to enforce Read-Only mode on database: {e}", severity="error")
                self.exit(return_code=1)
                return

        tables = self.db.get_tables()
        # Only populate demo tables when explicitly requested, in-memory, or default sample.db AND NOT in safe_mode
        is_default_sample = (
            self.populate_sample
            or self.db_path == ":memory:"
            or os.path.basename(os.path.abspath(self.db_path)) == "sample.db"
        )
        if not tables and self.db.db_type == "sqlite" and is_default_sample and not self.safe_mode:
            self._create_sample_data()
            tables = self.db.get_tables()

        self.all_tables = tables
        self.all_views  = self.db.get_views()
        self._refresh_row_counts()
        self._refresh_sidebar(self.all_tables, self.all_views)

        if self.all_tables:
            first = self.all_tables[0]
            self.selected_table = first
            quoted = self.db.quote_table_name(first)
            self.query_one("#query-box", TextArea).text = (
                f"SELECT * FROM {quoted} LIMIT 50;"
            )
            self.action_run_query()
            self._show_schema(first)
        else:
            self.query_one("#query-box", TextArea).text = (
                "-- Connected to database.\n-- Write a query and press Ctrl+R to execute.\n"
            )

        self._update_status_bar()

    # Row count caching

    def _refresh_row_counts(self):
        self._row_count_cache = {}
        for t in self.all_tables:
            self._row_count_cache[t] = self.db.get_row_count(t)

    # Sample schema

    def _create_sample_data(self):
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                role TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.db.execute_query("""
            INSERT OR IGNORE INTO users (name, email, role) VALUES
            ('Alice Smith',   'alice@example.com',   'Admin'),
            ('Bob Johnson',   'bob@example.com',     'Developer'),
            ('Charlie Brown', 'charlie@example.com', 'Analyst'),
            ('Diana Prince',  'diana@example.com',   'Manager');
        """)
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER REFERENCES users(id),
                name TEXT NOT NULL,
                price REAL,
                stock INTEGER DEFAULT 0
            );
        """)
        self.db.execute_query("""
            INSERT OR IGNORE INTO products (owner_id, name, price, stock) VALUES
            (1, 'Ghost CLI',     29.99, 100),
            (2, 'GhostBase Pro', 49.99,  50),
            (1, 'Dark Terminal',  9.99, 200);
        """)
        self.db.execute_query("""
            CREATE VIEW IF NOT EXISTS admin_products AS
            SELECT p.name, p.price, u.name AS owner
            FROM products p JOIN users u ON p.owner_id = u.id
            WHERE u.role = 'Admin';
        """)

    # Sidebar and table search

    def _refresh_sidebar(self, tables: list, views: list):
        lv    = self.query_one("#tables-list", ListView)
        count = self.query_one("#sidebar-count", Label)
        lv.clear()

        total = len(tables) + len(views)
        count.update(f"({total})")

        if tables:
            _sep_tables = ListItem(Label(f"TABLES ({len(tables)})"))
            _sep_tables.table_name = None        # type: ignore
            _sep_tables.is_view = False          # type: ignore
            _sep_tables.is_separator = True      # type: ignore
            _sep_tables.add_class("section-header")
            lv.append(_sep_tables)

            for t in tables:
                rc   = self._row_count_cache.get(t, 0)
                item = ListItem(Label(f"  {t}  ({rc})"))
                item.table_name  = t    # type: ignore
                item.is_view     = False  # type: ignore
                item.is_separator = False  # type: ignore
                lv.append(item)

        if views:
            _sep_views = ListItem(Label(f"VIEWS ({len(views)})"))
            _sep_views.table_name  = None   # type: ignore
            _sep_views.is_view     = True   # type: ignore
            _sep_views.is_separator = True  # type: ignore
            _sep_views.add_class("section-header")
            lv.append(_sep_views)

            for v in views:
                item = ListItem(Label(f"  {v}"))
                item.table_name  = v    # type: ignore
                item.is_view     = True  # type: ignore
                item.is_separator = False  # type: ignore
                lv.append(item)

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "table-search":
            q = event.value.strip().lower()
            if not q:
                filtered_tables = self.all_tables
                filtered_views  = self.all_views
            else:
                filtered_tables = [t for t in self.all_tables if q in t.lower()]
                filtered_views  = [v for v in self.all_views if q in v.lower()]
            self._refresh_sidebar(filtered_tables, filtered_views)

    def on_text_area_changed(self, event: TextArea.Changed):
        if event.text_area.id == "query-box" and self._pending_destructive_query is not None:
            self._pending_destructive_query = None
            self._pending_destructive_time = 0.0

    # Schema panel

    def _show_schema(self, table_name: str, is_view: bool = False):
        panel   = self.query_one("#schema-panel")
        title   = self.query_one("#schema-title", Label)
        content = self.query_one("#schema-content", Static)

        schema = self.db.get_table_schema(table_name)
        fks    = [] if is_view else self.db.get_foreign_keys(table_name)

        if not schema:
            panel.remove_class("visible")
            return

        kind = "VIEW" if is_view else "TABLE"
        title.update(f"{table_name.upper()}  [{kind}]")

        lines = Text()
        for col in schema:
            pk       = col.get("pk", 0)
            name     = col.get("name", "")
            col_type = col.get("type", "TEXT")
            notnull  = col.get("notnull", 0)

            if pk:
                lines.append(" [PK] ", style="bold #ffa657")
                lines.append(f"{name}", style="bold #e6edf3")
                lines.append(f"  {col_type}\n", style="#58a6ff")
            else:
                lines.append("      ", style="#484f58")
                lines.append(f"{name}", style="#c9d1d9")
                lines.append(f"  {col_type}", style="#3fb950")
                if notnull:
                    lines.append("  NOT NULL", style="#484f58")
                lines.append("\n")

        if fks:
            lines.append("\nFOREIGN KEYS\n", style="bold #8b949e")
            for fk in fks:
                lines.append(
                    f"  {fk['from']} -> {fk['to_table']}.{fk['to_col']}\n",
                    style="#6e7681",
                )

        content.update(lines)
        panel.add_class("visible")

    # Event handlers

    def on_list_view_selected(self, event: ListView.Selected):
        item = event.item
        if getattr(item, "is_separator", False):
            return
        t = getattr(item, "table_name", None)
        if not t:
            return
        is_view = getattr(item, "is_view", False)
        self.selected_table = t
        self._pending_destructive_query = None
        self._pending_destructive_time = 0.0

        quoted = self.db.quote_table_name(t)
        self.query_one("#query-box", TextArea).text = (
            f"SELECT * FROM {quoted} LIMIT 50;"
        )
        self.action_run_query()
        self._show_schema(t, is_view=is_view)

    def on_button_pressed(self, event: Button.Pressed):
        dispatch = {
            "btn-run":     self.action_run_query,
            "btn-explain": self.action_explain_query,
            "btn-format":  self.action_beautify_sql,
            "btn-clear":   self.action_clear_query,
            "btn-safe":    self.action_toggle_safe_mode,
            "btn-csv":     self.action_export_csv,
            "btn-json":    self.action_export_json,
            "btn-md":      self.action_export_markdown,
            "btn-sql":     self.action_export_sql,
        }
        fn = dispatch.get(event.button.id)
        if fn:
            fn()

    # Query actions

    def action_run_query(self):
        raw   = self.query_one("#query-box", TextArea).text.strip()
        lines = [l for l in raw.splitlines() if not l.strip().startswith("--")]
        query = "\n".join(lines).strip()
        if not query:
            self.notify("Query is empty", severity="warning")
            return

        status = self.query_one("#status-label", Label)
        res_cnt = self.query_one("#results-count", Label)

        # Safety guard check (strict read-only in safe mode, destructive guard in normal mode)
        is_destructive, reason = self.db.check_safety(query, is_safe_mode=self.safe_mode)
        if is_destructive:
            if self.safe_mode:
                self.notify(f"BLOCKED BY SAFE MODE: {reason}", severity="error", timeout=5)
                status.update(f"[bold red]BLOCKED BY SAFE MODE:[/] {reason}")
                return

            now = time.time()
            if self._pending_destructive_query == query and (now - self._pending_destructive_time) <= 10.0:
                # Double confirmation received within 10s window
                self._pending_destructive_query = None
                self._pending_destructive_time = 0.0
            else:
                self._pending_destructive_query = query
                self._pending_destructive_time = now
                self.notify(
                    f"DANGER: {reason}!\nPress Ctrl+R within 10s to confirm.",
                    severity="warning",
                    timeout=5,
                )
                status.update(f"[bold red]DANGER:[/] {reason} -> Press Ctrl+R to CONFIRM")
                return
        else:
            self._pending_destructive_query = None
            self._pending_destructive_time = 0.0

        if not self.query_history or self.query_history[-1] != query:
            self.query_history.append(query)
            if len(self.query_history) > 20:
                self.query_history.pop(0)
        self.history_index = len(self.query_history)

        dt  = self.query_one("#data-table", DataTable)
        res = self.db.execute_query(query)
        dt.clear(columns=True)

        if not res["success"]:
            # Clear export cache on error
            self.last_columns = []
            self.last_rows    = []
            self.last_query_table = None
            err = res.get("error", "Unknown error")
            status.update(f"[bold red]ERROR[/] {err}")
            res_cnt.update("(Error)")
            self.notify(f"SQL Error: {err}", severity="error")
            return

        if res["is_select"]:
            self.last_columns = res["columns"]
            self.last_rows    = res["rows"]

            # Detect target table for export from final SELECT statement (ignoring CTE definitions)
            main_q = re.sub(r"^WITH\s+[\s\S]*?\)\s*", "", query, flags=re.IGNORECASE)
            m = re.search(r"\bFROM\s+([`\"\[]?[a-zA-Z0-9_\.]+(?:\"|\'|\]|`)?)", main_q, flags=re.IGNORECASE)
            self.last_query_table = m.group(1).strip('`"[]') if m else (self.selected_table or "query_result")

            dt.add_columns(*self.last_columns)
            for row in self.last_rows:
                styled = []
                for val in row:
                    if val is None:
                        styled.append(Text("NULL", style="dim #6e7681"))
                    elif isinstance(val, (int, float)):
                        styled.append(Text(str(val), style="#79c0ff"))
                    else:
                        s = str(val).replace("\r\n", " ").replace("\n", " ").replace("\t", " ")
                        if len(s) > 200:
                            s = s[:197] + "..."
                        styled.append(Text(s, style="#c9d1d9"))
                dt.add_row(*styled)

            rc = res["row_count"]
            ms = res["elapsed_ms"]
            status.update(f"[bold green]OK[/] ({ms}ms)")

            if res.get("truncated"):
                res_cnt.update(f"({rc}+ rows, capped at 1,000)")
                self.notify("Displaying first 1,000 rows (use LIMIT / OFFSET for more)", severity="information", timeout=4)
            else:
                res_cnt.update(f"({rc} rows)")

            self._update_status_bar(row_count=rc, ms=ms)
        elif res.get("is_returning"):
            # DML with RETURNING: Render returned rows in DataTable, but treat as write operation
            self.last_columns = res["columns"]
            self.last_rows    = res["rows"]

            # Extract target table from INSERT/UPDATE
            m = re.search(r"\b(?:INTO|UPDATE)\s+([`\"\[]?[a-zA-Z0-9_\.]+(?:\"|\'|\]|`)?)", query, flags=re.IGNORECASE)
            self.last_query_table = m.group(1).strip('`"[]') if m else (self.selected_table or "query_result")

            dt.add_columns(*self.last_columns)
            for row in self.last_rows:
                styled = []
                for val in row:
                    if val is None:
                        styled.append(Text("NULL", style="dim #6e7681"))
                    elif isinstance(val, (int, float)):
                        styled.append(Text(str(val), style="#79c0ff"))
                    else:
                        s = str(val).replace("\r\n", " ").replace("\n", " ").replace("\t", " ")
                        if len(s) > 200:
                            s = s[:197] + "..."
                        styled.append(Text(s, style="#c9d1d9"))
                dt.add_row(*styled)

            aff = res.get("affected_rows", len(self.last_rows))
            rc = res.get("row_count", len(self.last_rows))
            ms = res["elapsed_ms"]
            status.update(f"[bold green]OK[/] ({ms}ms)")
            res_cnt.update(f"({rc} rows returned, {aff} affected)")
            self.notify(f"Done — {aff} row(s) affected (RETURNING {rc} rows)")

            # Refresh schema & row counts
            self.all_tables = self.db.get_tables()
            self.all_views  = self.db.get_views()
            self._refresh_row_counts()
            self._refresh_sidebar(self.all_tables, self.all_views)
            self._update_status_bar(row_count=rc, ms=ms)
        else:
            # Pure DML / DDL statement -> clear export cache so previous SELECT results are not mistakenly exported
            self.last_columns = []
            self.last_rows    = []
            self.last_query_table = None

            aff = res.get("affected_rows", 0)
            ms  = res["elapsed_ms"]
            status.update(f"[bold green]OK[/] ({ms}ms)")
            res_cnt.update(f"({aff} rows affected)")
            self.notify(f"Done — {aff} row(s) affected")

            self.all_tables = self.db.get_tables()
            self.all_views  = self.db.get_views()
            self._refresh_row_counts()
            self._refresh_sidebar(self.all_tables, self.all_views)
            self._update_status_bar(ms=ms)

    def action_beautify_sql(self):
        """Format and Beautify SQL query (Ctrl+B)"""
        qa = self.query_one("#query-box", TextArea)
        raw = qa.text
        formatted = DatabaseEngine.format_sql(raw)
        qa.text = formatted
        self.notify("SQL formatted and prettified")

    def action_explain_query(self):
        """Execute 1-Key EXPLAIN Query Plan (Ctrl+P)"""
        raw   = self.query_one("#query-box", TextArea).text.strip()
        lines = [l for l in raw.splitlines() if not l.strip().startswith(("--", "#"))]
        query = "\n".join(lines).strip()
        if not query:
            self.notify("No query to explain", severity="warning")
            return

        dt      = self.query_one("#data-table", DataTable)
        status  = self.query_one("#status-label", Label)
        res_cnt = self.query_one("#results-count", Label)

        # Central safety verification before EXPLAIN
        statements = self.db.split_statements(query)
        if len(statements) > 1:
            status.update("[bold red]EXPLAIN ERROR[/] Multiple statements not allowed in EXPLAIN")
            self.notify("EXPLAIN only supports a single SQL statement.", severity="error", timeout=4)
            return

        is_destructive, reason = self.db.check_safety(query, is_safe_mode=self.safe_mode)
        if self.safe_mode and is_destructive:
            status.update(f"[bold red]BLOCKED[/] {reason}")
            self.notify(f"Cannot explain query in Safe Mode: {reason}", severity="error", timeout=5)
            return

        res = self.db.explain_query(query)
        dt.clear(columns=True)

        if not res["success"]:
            err = res.get("error", "Unknown error")
            status.update(f"[bold red]EXPLAIN ERROR[/] {err}")
            self.notify(f"Explain Error: {err}", severity="error")
            return

        self.last_columns = res["columns"]
        self.last_rows    = res["rows"]
        dt.add_columns(*self.last_columns)
        for row in self.last_rows:
            styled = []
            for val in row:
                styled.append(Text(str(val), style="#58a6ff" if str(val).isdigit() else "#c9d1d9"))
            dt.add_row(*styled)

        ms = res["elapsed_ms"]
        status.update(f"[bold cyan]PLAN[/] ({ms}ms)")
        res_cnt.update(f"({len(self.last_rows)} steps)")
        self.notify("Execution Plan analyzed successfully")

    def action_toggle_safe_mode(self):
        """Toggle Production Safe Mode (Ctrl+S) - Fail-closed"""
        if getattr(self, "_cli_read_only", False):
            self.notify("CLI --read-only flag is active. Safe Mode is locked and cannot be disabled.", severity="warning", timeout=4)
            return

        new_mode = not self.safe_mode
        self._pending_destructive_query = None
        self._pending_destructive_time = 0.0

        # Enforce/revoke database session level Read-Only (Fail-closed)
        try:
            self.db.set_read_only(new_mode)
            self.safe_mode = new_mode
        except Exception as e:
            self.notify(f"Cannot enable Safe Mode: {e}", severity="error", timeout=5)
            return

        badge = self.query_one("#safe-badge", Label)
        if self.safe_mode:
            badge.update("[SAFE: ON]")
            badge.remove_class("unsafe")
            self.notify("Safe Mode ENABLED: Modifications strictly blocked (Read-Only)", timeout=3)
        else:
            badge.update("[SAFE: OFF]")
            badge.add_class("unsafe")
            self.notify("Safe Mode DISABLED: Destructive queries require confirmation", severity="warning", timeout=3)
        self._update_status_bar()

    def action_focus_filter(self):
        self.query_one("#table-search", Input).focus()

    def action_clear_query(self):
        self._pending_destructive_query = None
        self._pending_destructive_time = 0.0
        self.query_one("#query-box", TextArea).text = ""
        self.query_one("#status-label", Label).update("Ready")
        self.query_one("#query-box", TextArea).focus()

    def action_history_prev(self):
        if not self.query_history:
            return
        self.history_index = max(0, self.history_index - 1)
        self.query_one("#query-box", TextArea).text = (
            self.query_history[self.history_index]
        )

    def action_history_next(self):
        if not self.query_history:
            return
        self.history_index = min(len(self.query_history) - 1, self.history_index + 1)
        self.query_one("#query-box", TextArea).text = (
            self.query_history[self.history_index]
        )

    def action_export_csv(self):
        if not self.last_columns:
            self.notify("Run a SELECT query first", severity="warning")
            return
        db_dir = (
            os.path.dirname(os.path.abspath(self.db_path))
            if (self.db.db_type == "sqlite" and self.db_path != ":memory:")
            else os.getcwd()
        )
        out = os.path.join(db_dir, "ghostbase_export.csv")
        Exporter.to_csv(self.last_columns, self.last_rows, out)
        self.notify(f"Saved: {out}", timeout=5)

    def action_export_json(self):
        if not self.last_columns:
            self.notify("Run a SELECT query first", severity="warning")
            return
        db_dir = (
            os.path.dirname(os.path.abspath(self.db_path))
            if (self.db.db_type == "sqlite" and self.db_path != ":memory:")
            else os.getcwd()
        )
        out = os.path.join(db_dir, "ghostbase_export.json")
        Exporter.to_json(self.last_columns, self.last_rows, out)
        self.notify(f"Saved: {out}", timeout=5)

    def action_export_markdown(self):
        if not self.last_columns:
            self.notify("Run a SELECT query first", severity="warning")
            return
        db_dir = (
            os.path.dirname(os.path.abspath(self.db_path))
            if (self.db.db_type == "sqlite" and self.db_path != ":memory:")
            else os.getcwd()
        )
        out = os.path.join(db_dir, "ghostbase_export.md")
        Exporter.to_markdown(self.last_columns, self.last_rows, out)
        self.notify(f"Saved: {out}", timeout=5)

    def action_export_sql(self):
        if not self.last_columns:
            self.notify("Run a SELECT query first", severity="warning")
            return
        table_name = getattr(self, "last_query_table", None) or self.selected_table or "exported_table"
        db_dir = (
            os.path.dirname(os.path.abspath(self.db_path))
            if (self.db.db_type == "sqlite" and self.db_path != ":memory:")
            else os.getcwd()
        )
        out = os.path.join(db_dir, "ghostbase_export.sql")
        Exporter.to_sql_inserts(table_name, self.last_columns, self.last_rows, out, dialect=self.db.db_type)
        self.notify(f"Saved: {out}", timeout=5)

    # Status bar

    def _update_status_bar(self, row_count: int = None, ms: float = None):
        tables  = self.all_tables
        views   = self.all_views
        db_type = self.db.db_type_label()
        parts   = [
            f"{db_type}",
            f"Tables: {len(tables)}",
            f"Views: {len(views)}",
        ]
        if self.selected_table:
            parts.append(f"Active: {self.selected_table}")
        if row_count is not None:
            parts.append(f"Rows: {row_count}")
        if ms is not None:
            parts.append(f"{ms}ms")
        self.query_one("#status-bar-text", Label).update("  |  ".join(parts))

    def on_unmount(self):
        self.db.close()
