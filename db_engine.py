import sqlite3
import time
import urllib.parse
import re
from typing import List, Dict, Any, Tuple


class DatabaseEngine:
    """Database connection and query handler for SQLite, Postgres, and MySQL."""

    def __init__(self, connection_string: str = None):
        self.connection_string = (connection_string or "sample.db").strip()
        self.db_type = "sqlite"
        self.db_name = ""
        self.conn = None
        self._parse_and_connect()

    # --- Connection handling ---

    def _parse_and_connect(self):
        cs = self.connection_string
        if cs.startswith(("postgresql://", "postgres://")):
            self.db_type = "postgresql"
            parsed = urllib.parse.urlparse(cs)
            self.db_name = parsed.path.lstrip("/")
            self._connect_postgres(cs)
        elif cs.startswith("mysql://"):
            self.db_type = "mysql"
            parsed = urllib.parse.urlparse(cs)
            self.db_name = parsed.path.lstrip("/")
            self._connect_mysql(cs)
        else:
            self.db_type = "sqlite"
            path = cs.removeprefix("sqlite:///")
            self.db_name = path
            self._connect_sqlite(path)

    def _connect_sqlite(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def _connect_postgres(self, url: str):
        try:
            import psycopg2
        except ImportError:
            raise RuntimeError(
                "psycopg2 is not installed.\n"
                "Run:  pip install psycopg2-binary"
            )
        self.conn = psycopg2.connect(url)
        self.conn.autocommit = False

    def _connect_mysql(self, url: str):
        try:
            import pymysql
            import pymysql.cursors
        except ImportError:
            raise RuntimeError(
                "pymysql is not installed.\n"
                "Run:  pip install pymysql"
            )
        parsed = urllib.parse.urlparse(url)
        self.conn = pymysql.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=parsed.username or "root",
            password=parsed.password or "",
            database=parsed.path.lstrip("/"),
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )

    # --- Schema discovery ---

    def get_tables(self) -> List[str]:
        try:
            cur = self.conn.cursor()
            if self.db_type == "sqlite":
                cur.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name;"
                )
                return [r[0] for r in cur.fetchall()]
            elif self.db_type == "postgresql":
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_type='BASE TABLE' "
                    "ORDER BY table_name;"
                )
                return [r[0] for r in cur.fetchall()]
            elif self.db_type == "mysql":
                cur.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE';")
                rows = cur.fetchall()
                return [list(r.values())[0] if isinstance(r, dict) else r[0] for r in rows]
        except Exception:
            return []
        return []

    def get_views(self) -> List[str]:
        try:
            cur = self.conn.cursor()
            if self.db_type == "sqlite":
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name;"
                )
                return [r[0] for r in cur.fetchall()]
            elif self.db_type == "postgresql":
                cur.execute(
                    "SELECT table_name FROM information_schema.views "
                    "WHERE table_schema='public' ORDER BY table_name;"
                )
                return [r[0] for r in cur.fetchall()]
            elif self.db_type == "mysql":
                cur.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW';")
                rows = cur.fetchall()
                return [list(r.values())[0] if isinstance(r, dict) else r[0] for r in rows]
        except Exception:
            return []
        return []

    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        try:
            cur = self.conn.cursor()
            if self.db_type == "sqlite":
                cur.execute(f"PRAGMA table_info([{table_name}]);")
                return [
                    {"name": r[1], "type": r[2], "notnull": r[3],
                     "dflt_value": r[4], "pk": r[5]}
                    for r in cur.fetchall()
                ]
            elif self.db_type == "postgresql":
                cur.execute(
                    """
                    SELECT
                        c.column_name,
                        c.data_type,
                        CASE WHEN c.is_nullable = 'NO' THEN 1 ELSE 0 END,
                        c.column_default,
                        CASE WHEN kcu.column_name IS NOT NULL THEN 1 ELSE 0 END
                    FROM information_schema.columns c
                    LEFT JOIN information_schema.table_constraints tc
                        ON tc.table_name = c.table_name
                        AND tc.constraint_type = 'PRIMARY KEY'
                        AND tc.table_schema = 'public'
                    LEFT JOIN information_schema.key_column_usage kcu
                        ON kcu.constraint_name = tc.constraint_name
                        AND kcu.column_name = c.column_name
                    WHERE c.table_name = %s AND c.table_schema = 'public'
                    ORDER BY c.ordinal_position;
                    """,
                    (table_name,),
                )
                return [
                    {"name": r[0], "type": r[1], "notnull": r[2],
                     "dflt_value": r[3], "pk": r[4]}
                    for r in cur.fetchall()
                ]
            elif self.db_type == "mysql":
                cur.execute(f"DESCRIBE `{table_name}`;")
                rows = cur.fetchall()
                result = []
                for r in rows:
                    d = r if isinstance(r, dict) else dict(
                        zip(["Field", "Type", "Null", "Key", "Default", "Extra"], r)
                    )
                    result.append({
                        "name": d.get("Field", ""),
                        "type": d.get("Type", ""),
                        "notnull": 1 if d.get("Null") == "NO" else 0,
                        "dflt_value": d.get("Default"),
                        "pk": 1 if d.get("Key") == "PRI" else 0,
                    })
                return result
        except Exception:
            return []
        return []

    def get_foreign_keys(self, table_name: str) -> List[Dict[str, str]]:
        try:
            cur = self.conn.cursor()
            if self.db_type == "sqlite":
                cur.execute(f"PRAGMA foreign_key_list([{table_name}]);")
                return [
                    {"from": r[3], "to_table": r[2], "to_col": r[4]}
                    for r in cur.fetchall()
                ]
            elif self.db_type == "postgresql":
                cur.execute(
                    """
                    SELECT kcu.column_name,
                           ccu.table_name AS to_table,
                           ccu.column_name AS to_col
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage ccu
                        ON ccu.constraint_name = tc.constraint_name
                        AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_name = %s;
                    """,
                    (table_name,),
                )
                return [
                    {"from": r[0], "to_table": r[1], "to_col": r[2]}
                    for r in cur.fetchall()
                ]
            elif self.db_type == "mysql":
                cur.execute("SELECT DATABASE();")
                row = cur.fetchone()
                db = list(row.values())[0] if isinstance(row, dict) else row[0]
                cur.execute(
                    """
                    SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                    FROM information_schema.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                      AND REFERENCED_TABLE_NAME IS NOT NULL;
                    """,
                    (db, table_name),
                )
                rows = cur.fetchall()
                return [
                    {
                        "from": (r.get("COLUMN_NAME") if isinstance(r, dict) else r[0]),
                        "to_table": (r.get("REFERENCED_TABLE_NAME") if isinstance(r, dict) else r[1]),
                        "to_col": (r.get("REFERENCED_COLUMN_NAME") if isinstance(r, dict) else r[2]),
                    }
                    for r in rows
                ]
        except Exception:
            return []
        return []

    def get_row_count(self, table_name: str) -> int:
        try:
            cur = self.conn.cursor()
            if self.db_type == "sqlite":
                cur.execute(f"SELECT COUNT(*) FROM [{table_name}];")
            elif self.db_type == "postgresql":
                cur.execute(f'SELECT COUNT(*) FROM "{table_name}";')
            else:
                cur.execute(f"SELECT COUNT(*) FROM `{table_name}`;")
            row = cur.fetchone()
            val = list(row.values())[0] if isinstance(row, dict) else row[0]
            return int(val)
        except Exception:
            return 0

    # --- Query safety and formatting ---

    def check_safety(self, query: str) -> Tuple[bool, str]:
        """Detect destructive operations without WHERE clauses or schema drops."""
        q_clean = re.sub(r"--.*$", "", query, flags=re.MULTILINE)
        q_upper = q_clean.strip().upper()

        if re.search(r"\bDROP\s+(TABLE|DATABASE|SCHEMA|VIEW)\b", q_upper):
            return True, "DROP operation detected"
        if re.search(r"\bTRUNCATE\b", q_upper):
            return True, "TRUNCATE operation detected"
        if re.search(r"\bDELETE\s+FROM\b", q_upper) and not re.search(r"\bWHERE\b", q_upper):
            return True, "DELETE without WHERE clause (will delete all rows)"
        if re.search(r"\bUPDATE\b", q_upper) and not re.search(r"\bWHERE\b", q_upper):
            return True, "UPDATE without WHERE clause (will modify all rows)"
        if re.search(r"\bALTER\s+TABLE\s+.*\bDROP\b", q_upper):
            return True, "ALTER TABLE DROP detected"

        return False, ""

    def explain_query(self, query: str) -> Dict[str, Any]:
        clean_q = re.sub(r"--.*$", "", query, flags=re.MULTILINE).strip().rstrip(";")
        if not clean_q:
            return {"success": False, "error": "Query is empty"}

        if self.db_type == "sqlite":
            explain_sql = f"EXPLAIN QUERY PLAN {clean_q};"
        else:
            explain_sql = f"EXPLAIN {clean_q};"
        return self.execute_query(explain_sql)

    @staticmethod
    def format_sql(query: str) -> str:
        """Format and uppercase SQL keywords with line indents."""
        if not query or not query.strip():
            return query

        lines = query.strip().splitlines()
        comment_lines = []
        sql_lines = []
        for line in lines:
            if line.strip().startswith("--"):
                comment_lines.append(line.strip())
            else:
                sql_lines.append(line)

        sql_text = " ".join(sql_lines)
        sql_text = re.sub(r"\s+", " ", sql_text).strip()

        keywords = [
            "SELECT", "FROM", "WHERE", "AND", "OR", "ORDER BY",
            "GROUP BY", "HAVING", "LEFT JOIN", "RIGHT JOIN",
            "INNER JOIN", "CROSS JOIN", "JOIN", "ON", "INSERT INTO",
            "VALUES", "UPDATE", "SET", "DELETE FROM", "DELETE",
            "LIMIT", "OFFSET", "AS", "CREATE TABLE", "CREATE VIEW",
            "DROP TABLE", "DROP VIEW", "ALTER TABLE", "PRIMARY KEY",
            "FOREIGN KEY", "REFERENCES", "DEFAULT", "NOT NULL",
            "AUTOINCREMENT", "DESC", "ASC", "UNION ALL", "UNION",
            "DISTINCT", "EXPLAIN QUERY PLAN", "EXPLAIN", "IN", "IS NULL",
            "IS NOT NULL", "LIKE", "BETWEEN", "CASE", "WHEN", "THEN", "ELSE", "END",
            "COUNT", "SUM", "AVG", "MIN", "MAX"
        ]
        keywords.sort(key=len, reverse=True)

        for kw in keywords:
            pattern = rf"\b{re.escape(kw)}\b"
            sql_text = re.sub(pattern, kw, sql_text, flags=re.IGNORECASE)

        major_clauses = [
            "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "CROSS JOIN",
            "FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT",
            "OFFSET", "SET", "VALUES"
        ]
        for clause in major_clauses:
            sql_text = re.sub(rf"\b({clause})\b", r"\n\1", sql_text)
        sql_text = re.sub(r"(?<!LEFT\s)(?<!RIGHT\s)(?<!INNER\s)(?<!CROSS\s)\bJOIN\b", r"\nJOIN", sql_text)

        sql_text = re.sub(r"\b(AND|OR)\b", r"\n  \1", sql_text)

        result_parts = []
        if comment_lines:
            result_parts.append("\n".join(comment_lines))
        result_parts.append(sql_text.strip())
        return "\n".join(result_parts)

    # --- Query execution ---

    def execute_query(self, query: str) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            cur = self.conn.cursor()
            cur.execute(query)
            elapsed_ms = (time.perf_counter() - start) * 1000

            if cur.description:
                columns = [d[0] for d in cur.description]
                raw = cur.fetchall()
                rows = []
                for r in raw:
                    if isinstance(r, dict):
                        rows.append(list(r.values()))
                    else:
                        rows.append(list(r))
                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                    "elapsed_ms": round(elapsed_ms, 2),
                    "is_select": True,
                }
            else:
                if self.db_type in ("sqlite", "postgresql"):
                    self.conn.commit()
                return {
                    "success": True,
                    "affected_rows": max(cur.rowcount, 0),
                    "elapsed_ms": round(elapsed_ms, 2),
                    "is_select": False,
                }
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            if self.db_type == "postgresql":
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            return {
                "success": False,
                "error": str(e),
                "elapsed_ms": round(elapsed_ms, 2),
            }

    # --- Helpers ---

    def db_type_label(self) -> str:
        return {"sqlite": "SQLite", "postgresql": "PostgreSQL", "mysql": "MySQL"}.get(
            self.db_type, self.db_type.upper()
        )

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
