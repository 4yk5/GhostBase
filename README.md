```
   ____ _               _   ____                 
  / ___| |__   ___  ___| |_| __ )  __ _ ___  ___ 
 | |  _| '_ \ / _ \/ __| __|  _ \ / _` / __|/ _ \
 | |_| | | | | (_) \__ \ |_| |_) | (_| \__ \  __/
  \____|_| |_|\___/|___/\__|____/ \__,_|___/\___|
                                                 
```

# GhostBase 👻🗄️

> **A fast, keyboard-driven terminal database studio for SQLite, PostgreSQL, and MySQL.**  
> *No Java runtimes. No 1.5GB RAM bloat. Built-in production safety guard, instant SQL beautifier & zero-config `.env` connect.*

[![CI](https://github.com/4yk5/GhostBase/actions/workflows/ci.yml/badge.svg)](https://github.com/4yk5/GhostBase/actions)
[![PyPI](https://img.shields.io/pypi/v/ghostbase-cli.svg)](https://pypi.org/project/ghostbase-cli/)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![UI: Textual](https://img.shields.io/badge/UI-Textual-bd93f9.svg)](https://github.com/Textualize/textual)

---

## ⚡ Why GhostBase?

Opening **DBeaver** or **DataGrip** just to run a quick `SELECT`, inspect an index, or check foreign keys is painful:
- ❌ **1.5 GB+ RAM bloat:** Heavy Java/Eclipse runtimes that spin your laptop fans.  
  👉 **GhostBase idles at ~25 MB RAM.**
- ❌ **15-Second Cold Starts:** Splash screens, driver updates, and workspace indexing.  
  👉 **GhostBase starts in under 120 ms directly in your terminal.**
- ❌ **Accidental Destructive Queries on Production:** Running `DELETE` or `UPDATE` without a `WHERE` clause can wipe production tables.  
  👉 **GhostBase intercepts destructive queries automatically with double-confirmation and one-key Read-Only Safe Mode (`Ctrl + S`).**
- ❌ **Messy, Unformatted Queries:** Manually formatting and indenting long SQL statements.  
  👉 **GhostBase auto-formats and beautifies messy SQL queries with one keypress (`Ctrl + B`).**
- ❌ **Tedious Connection Setup:** Typing credentials into multi-tab dialogs.  
  👉 **GhostBase auto-detects `DATABASE_URL` from your local `.env` file.**
- ❌ **Seeding & Migrating Data:** Manually writing `INSERT INTO` statements to replicate test rows.  
  👉 **GhostBase exports query results directly into executable SQL `INSERT` statements (`Ctrl + I`).**
- ❌ **Exporting for GitHub / Jira / Notion:** Exporting CSV, then finding a website to convert to Markdown.  
  👉 **One-key instant Markdown table export (`Ctrl + M`) directly into clean GitHub Flavored Markdown.**

---

## 🚀 Killer Features

- 🛡️ **Production Safety Guard & Safe Mode (`Ctrl + S`):**
  - Intercepts dangerous statements (`DELETE`/`UPDATE` without `WHERE`, `DROP TABLE`, `TRUNCATE`).
  - In **Safe Mode**, all destructive operations are strictly blocked.
  - In normal mode, requires explicit double-confirmation before execution.
- ✨ **1-Key SQL Beautifier (`Ctrl + B`):**
  - Instantly cleans up whitespace, capitalizes SQL keywords, and indents sub-clauses (`FROM`, `WHERE`, `AND`, `OR`, `JOIN`, `ORDER BY`).
- ⚡ **1-Key Query Plan (`Ctrl + P`):**
  - Run instant execution plans (`EXPLAIN QUERY PLAN` / `EXPLAIN`) on any query to see index usage and bottlenecks.
- 🔌 **Universal Database Support:** Connects natively to **SQLite**, **PostgreSQL**, and **MySQL**.
- 🔍 **Zero-Config `.env` Auto-Connect:** Just run `ghostbase` in any project folder; it automatically picks up `DATABASE_URL` or standard database environment variables.
- 🔎 **Real-time Table Search (`Ctrl + F`):** Type in the search bar to filter dozens of tables and views instantly.
- 📊 **Explorer with Tables & Views:** Browse tables and views with live row counts.
- 📐 **Instant Schema & Foreign Keys:** See primary keys, column types, nullability, and foreign key references at a glance.
- 💾 **Multi-Format Exports:** Instant SQL `INSERT`s (`Ctrl + I`), Markdown (`Ctrl + M`), CSV (`Ctrl + E`), and JSON (`Ctrl + J`).
- 📜 **Query History:** Cycle through your last 20 queries with `Ctrl + ↑` and `Ctrl + ↓`.
- 🎨 **Clean Cyberpunk Aesthetic:** Fast, high-contrast, zero-flicker terminal interface.

---

## 📦 Installation & Quick Start

### Via pip

```bash
pip install ghostbase-cli
```

### From Source

```bash
git clone https://github.com/4yk5/GhostBase.git
cd GhostBase
pip install -r requirements.txt
```

---

## 💻 How to Use

### 1. Auto-connect to current project (`.env`)
```bash
# Automatically finds DATABASE_URL or DB_HOST in your current directory's .env
ghostbase
```

### 2. Connect to SQLite
```bash
ghostbase path/to/database.db
```

### 3. Connect to PostgreSQL
```bash
ghostbase postgresql://user:password@localhost:5432/my_database
```

### 4. Connect to MySQL
```bash
ghostbase mysql://user:password@localhost:3306/my_database
```

### 5. Launch in Safe / Read-Only Mode
```bash
ghostbase postgresql://prod-db:5432/main --read-only
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Description |
| :--- | :--- |
| `Ctrl + R` | **Execute SQL Query** (runs the query with safety validation) |
| `Ctrl + P` | **1-Key EXPLAIN** (instant query execution plan and performance inspector) |
| `Ctrl + B` | **Beautify SQL** (auto-formats, capitalizes keywords and indents clauses) |
| `Ctrl + S` | **Toggle Safe Mode** (enable/disable destructive query protection) |
| `Ctrl + N` | **New Query** (clears editor for a clean query) |
| `Ctrl + F` | **Find Table** (focuses table search filter) |
| `Ctrl + I` | **Export to SQL INSERTs** (generates executable `INSERT INTO` statements) |
| `Ctrl + M` | **Export to Markdown** (GitHub / Jira / Notion ready table) |
| `Ctrl + E` | **Export to CSV** (exports current table/query to CSV) |
| `Ctrl + J` | **Export to JSON** (exports current table/query to JSON) |
| `Ctrl + ↑` / `Ctrl + ↓` | **Query History** (cycle through previous queries) |
| `Tab` / `Shift + Tab` | Navigate between explorer, search, editor, and data table |
| `Ctrl + Q` | **Quit GhostBase** |

---

## 📬 Contact & Inquiries

For partnerships, feature requests, or business inquiries:  
📧 **[contact.4yk5@proton.me](mailto:contact.4yk5@proton.me)**

---

## 📄 License

Released under the [MIT License](LICENSE).
