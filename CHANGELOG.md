# Changelog

All notable changes to **GhostBase** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.4] - 2026-11-02

### Fixed
- **Safe Mode Function Hardening (Security):** Explicitly blocked `set_config()`, `setval()`, `nextval()`, `currval()`, `lastval()`, `pg_terminate_backend()`, `pg_cancel_backend()`, `lo_import()`, and `lo_export()` in Safe Mode, closing configuration and sequence manipulation vectors.
- **Fail-Closed Startup Guarantee (Security):** When launched with `--read-only`, failure to enforce database-level read-only immediately terminates the process with an error code to guarantee database immutability.
- **PostgreSQL E-String & Escape Literal Masking:** Enhanced tokenizer to match PostgreSQL `E'...'` backslash-escaped strings (`E'(?:\\.|''|[^'\\])*'`), ensuring escaped quotes (`\'`) do not leak unconstrained `WHERE` strings.
- **MySQL `#` Comment Stripping:** Included MySQL single-line `#` comments in comment sanitization, preventing `# WHERE` from bypassing normal-mode double confirmation.
- **True PostgreSQL Server-Side Streaming:** Resolved named cursor autocommit conflict in `psycopg2` by explicitly scoping named cursor read transactions with instant commits, preventing client memory buffering on massive SELECTs.
- **MySQL Socket Drain Protection:** Automatically appended `LIMIT 1001` on unconstrained MySQL SELECT queries to eliminate unnecessary network socket draining in `SSDictCursor`.

## [0.1.3] - 2026-11-02

### Fixed
- **Safe Mode Privilege & Procedural Blocks (Security):** Explicitly blocked `SET`, `RESET`, `DO` procedural anonymous blocks, `CALL` stored procedures, and `MERGE` statements in Safe Mode, preventing bypassing session read-only parameters or running procedural mutations.
- **Fail-Closed Session Read-Only:** `set_read_only()` is now strictly fail-closed; if the underlying database engine fails to activate read-only mode, Safe Mode fails safely with a user alert and does not engage.
- **Dollar-Quote Tag Matching & Parser Security:** Added exact tag backreference matching (`\$([a-zA-Z_]\w*)\$[\s\S]*?\$\2\$`) to prevent tag mismatching (e.g. `$tag$ ... $other$ ... $tag$`), closing the destructive double-confirmation bypass.
- **Streaming Server-Side Cursors:** Implemented named server-side streaming cursors in PostgreSQL (`psycopg2`) and unbuffered streaming cursors (`SSDictCursor`) in MySQL (`pymysql`) to guarantee true client memory protection on massive datasets.
- **Dialect-Aware SQL Export:** Added dialect awareness to `Exporter.to_sql_inserts()`, automatically generating backticks (`` `analytics`.`order` ``) for MySQL and double quotes (`"analytics"."order"`) for PostgreSQL and SQLite.

## [0.1.2] - 2026-11-02

### Fixed
- **Database Engine-Level Read-Only Mode (Security):** Safe Mode now sets native database session-level read-only constraints (`PRAGMA query_only = ON` in SQLite, `SET default_transaction_read_only = ON` in PostgreSQL, `SET SESSION TRANSACTION READ ONLY` in MySQL) preventing sequence advancement (`nextval`), filesystem writes (`INTO OUTFILE`), and mutations at the database core.
- **`--read-only` Startup Integrity (Security):** Guarded `on_mount` to ensure sample demo tables and mock records are never written when opening SQLite in Safe Mode / Read-Only.
- **String Tokenizer & Normal Mode Safety:** Masked string literals, double quotes, and PostgreSQL dollar-quoted blocks (`$$...$$`, `$tag$...$tag$`) before comment stripping, ensuring strings containing `WHERE` (e.g. `'WHERE -- str'` or `$$WHERE$$`) cannot bypass double-confirmation barriers.
- **`RETURNING` DML Query Classification:** Correctly classified `INSERT / UPDATE / DELETE ... RETURNING` as data modification operations (`is_returning=True`, `is_select=False`), rendering returned rows while refreshing table counts and row statistics.
- **PostgreSQL Schema & Identifier Management:** Corrected `get_row_count()` to join `pg_namespace` with `pg_class` by schema and table, quoting schema-qualified tables separately (`"schema"."table"`).
- **SQL Export Target Detection:** Filtered out CTE definitions (`WITH ... AS (...)`) to resolve the true target table from the primary `FROM` clause while preserving schemas (`"schema"."table"`).
- **JSON Serialization for Database Types:** Added custom serialization in `Exporter.to_json()` for `Decimal`, `datetime`, `date`, `time`, `UUID`, and `bytes` to prevent `TypeError`.
- **SQL Beautifier Dollar-Quote Support:** Added support for PostgreSQL dollar-quoted string literals (`$$...$$`) to ensure inner SQL content is preserved verbatim without casing modifications.
- **Explorer Identifier Quoting:** Added engine-specific identifier quoting for table clicks and queries (`[table]` in SQLite, `"schema"."table"` in PostgreSQL, and `` `table` `` in MySQL) avoiding syntax errors on reserved names like `order` or `group`.

## [0.1.1] - 2026-11-02

### Fixed
- **Safe Mode Enforcement (Security):** Safe Mode now strictly enforces Read-Only queries, rejecting all DML (`INSERT`, `UPDATE`, `DELETE`) and DDL (`DROP`, `TRUNCATE`, `ALTER`, `CREATE`).
- **Comment Injection & Safety Bypass (Security):** Stripped both C-style block comments (`/* ... */`) and line comments (`--`) before safety analysis so commented clauses like `/* WHERE */` cannot bypass destructive guards.
- **PostgreSQL Autocommit & Transaction State:** Enabled connection autocommit on PostgreSQL (`psycopg2`), guaranteeing queries with `RETURNING` commit immediately and connections are not held in `IDLE in transaction`.
- **SQLite Foreign Key Enforcement:** Enabled `PRAGMA foreign_keys = ON;` upon connection initialization.
- **Confirmation State Timeout & Invalidation:** Added a 10-second expiration window and automatic state reset on text changes or editor clear.
- **SQL Beautifier Literal Preservation:** Masked quoted literals and identifiers during beautification to prevent modifying strings or whitespace inside user data.
- **Sidebar Performance & Row Count Caching:** Cached table row counts to eliminate redundant `SELECT COUNT(*)` queries on every search filter keystroke.
- **Large Result Set Memory Protection:** Capped query result fetching to 1,000 rows in memory with user notification to prevent terminal UI freezing on massive datasets.
- **Export Consistency & Escaping:** Cleared stale SELECT results on DML/error queries, auto-deduplicated duplicate JSON column names, and added identifier escaping for SQL exports.
- **Empty SQLite Database Integrity:** Prevented automatically injecting sample demo tables into empty user-specified SQLite database files.
- **Credential URL Encoding:** Safely encoded `.env` database usernames and passwords containing special characters (`@`, `#`, etc.).

## [0.1.0] - 2026-11-02

### Added
- **Universal Database Engine:** Native support for SQLite, PostgreSQL (`psycopg2`), and MySQL (`pymysql`).
- **Production Safety Guard & Safe Mode (`Ctrl + S`):**
  - Automatic interception of unbounded `DELETE` / `UPDATE` statements, `DROP`, and `TRUNCATE`.
  - Normal mode double-confirmation safety barrier.
  - Safe Mode strict rejection of all destructive operations.
- **1-Key EXPLAIN Query Plan (`Ctrl + P`):** Instant execution plan analysis rendered directly into the results grid.
- **1-Key SQL Beautifier (`Ctrl + B`):** Zero-dependency SQL parser that standardizes keywords, cleans whitespace, and indents major clauses.
- **Multi-Format Data Exporters:**
  - `Ctrl + E`: CSV export.
  - `Ctrl + J`: JSON export.
  - `Ctrl + M`: GitHub Flavored Markdown table export.
  - `Ctrl + I`: Executable SQL `INSERT INTO` statements.
- **Explorer & Schema Inspector:** Sidebar tree for tables and views with live row counts, primary key markers, column types, nullability, and foreign key references.
- **Real-Time Table Search (`Ctrl + F`):** Live filter for filtering across dozens of tables and views.
- **Query History (`Ctrl + Up` / `Ctrl + Down`):** Navigation through recent queries.
- **Zero-Config `.env` Auto-Connect:** Auto-detection of `DATABASE_URL`, `DB_HOST`, `DB_NAME`, `DB_USER`.
- **Responsive Dual-Bar Layout:** Compact layout with zero horizontal overflow down to 80-column minimal terminals.
