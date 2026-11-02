# Changelog

All notable changes to **GhostBase** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
