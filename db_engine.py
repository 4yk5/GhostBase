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
        try:
            self.conn.execute("PRAGMA foreign_keys = ON;")
        except Exception:
            pass

    def _connect_postgres(self, url: str):
        try:
            import psycopg2
        except ImportError:
            raise RuntimeError(
                "psycopg2 is not installed.\n"
                "Run:  pip install psycopg2-binary"
            )
        self.conn = psycopg2.connect(url)
        # Enable autocommit so write transactions are not left IDLE and RETURNING queries commit immediately
        self.conn.autocommit = True

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
        # Use SSDictCursor (Server-Side streaming cursor) to protect client memory on massive queries
        self.conn = pymysql.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=parsed.username or "root",
            password=parsed.password or "",
            database=parsed.path.lstrip("/"),
            cursorclass=pymysql.cursors.SSDictCursor,
            autocommit=True,
        )

    def set_read_only(self, enabled: bool) -> bool:
        """
        Configure database engine session-level Read-Only mode.
        Returns True if successful. Raises RuntimeError if enabling fails (fail-closed).
        """
        if not self.conn:
            return False
        try:
            cur = self.conn.cursor()
            if self.db_type == "sqlite":
                val = "ON" if enabled else "OFF"
                cur.execute(f"PRAGMA query_only = {val};")
            elif self.db_type == "postgresql":
                mode = "ON" if enabled else "OFF"
                cur.execute(f"SET default_transaction_read_only = {mode};")
            elif self.db_type == "mysql":
                mode = "READ ONLY" if enabled else "READ WRITE"
                cur.execute(f"SET SESSION TRANSACTION {mode};")
            return True
        except Exception as e:
            if enabled:
                raise RuntimeError(f"Database engine failed to activate Read-Only mode: {e}")
            return False

    def quote_table_name(self, table_name: str) -> str:
        """Properly quote table identifier for queries based on database engine."""
        if not table_name:
            return ""
        if self.db_type == "postgresql":
            if "." in table_name:
                s, t = table_name.split(".", 1)
                return f'"{s}"."{t}"'
            return f'"{table_name}"'
        elif self.db_type == "mysql":
            if "." in table_name:
                s, t = table_name.split(".", 1)
                return f"`{s}`.`{t}`"
            return f"`{table_name}`"
        else:  # sqlite
            return f"[{table_name}]"

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
                    "SELECT table_schema, table_name FROM information_schema.tables "
                    "WHERE table_schema NOT IN ('information_schema', 'pg_catalog') "
                    "  AND table_type='BASE TABLE' "
                    "ORDER BY table_schema, table_name;"
                )
                rows = cur.fetchall()
                tables = []
                for s, t in rows:
                    tables.append(t if s == "public" else f"{s}.{t}")
                return tables
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
                    "SELECT table_schema, table_name FROM information_schema.views "
                    "WHERE table_schema NOT IN ('information_schema', 'pg_catalog') "
                    "ORDER BY table_schema, table_name;"
                )
                rows = cur.fetchall()
                views = []
                for s, v in rows:
                    views.append(v if s == "public" else f"{s}.{v}")
                return views
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
                schema = "public"
                clean_name = table_name
                if "." in table_name:
                    schema, clean_name = table_name.split(".", 1)

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
                        AND tc.table_schema = c.table_schema
                    LEFT JOIN information_schema.key_column_usage kcu
                        ON kcu.constraint_name = tc.constraint_name
                        AND kcu.column_name = c.column_name
                        AND kcu.table_schema = c.table_schema
                    WHERE c.table_name = %s AND c.table_schema = %s
                    ORDER BY c.ordinal_position;
                    """,
                    (clean_name, schema),
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
                schema = "public"
                clean_name = table_name
                if "." in table_name:
                    schema, clean_name = table_name.split(".", 1)

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
                      AND tc.table_name = %s
                      AND tc.table_schema = %s;
                    """,
                    (clean_name, schema),
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

    def get_row_count(self, table_name: str, fast_estimate: bool = True) -> int:
        try:
            cur = self.conn.cursor()
            if self.db_type == "sqlite":
                cur.execute(f"SELECT COUNT(*) FROM [{table_name}];")
            elif self.db_type == "postgresql":
                schema = "public"
                tbl = table_name
                if "." in table_name:
                    schema, tbl = table_name.split(".", 1)

                if fast_estimate:
                    try:
                        cur.execute(
                            """
                            SELECT c.reltuples::bigint
                            FROM pg_class c
                            JOIN pg_namespace n ON n.oid = c.relnamespace
                            WHERE n.nspname = %s AND c.relname = %s;
                            """,
                            (schema, tbl),
                        )
                        r = cur.fetchone()
                        if r and r[0] is not None and r[0] >= 0:
                            return int(r[0])
                    except Exception:
                        pass
                cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{tbl}";')
            else:
                if fast_estimate:
                    try:
                        cur.execute(
                            "SELECT TABLE_ROWS FROM information_schema.tables "
                            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s;",
                            (table_name,),
                        )
                        r = cur.fetchone()
                        val = list(r.values())[0] if isinstance(r, dict) else r[0]
                        if val is not None:
                            return int(val)
                    except Exception:
                        pass
                cur.execute(f"SELECT COUNT(*) FROM `{table_name}`;")
            row = cur.fetchone()
            val = list(row.values())[0] if isinstance(row, dict) else row[0]
            return int(val) if val is not None else 0
        except Exception:
            return 0

    # --- Query safety and formatting ---

    @staticmethod
    def _mask_strings(sql: str) -> Tuple[str, List[str]]:
        """
        Extract and mask string literals (data values):
        - Plain untagged dollar-quotes: $$...$$
        - Tagged dollar-quotes: $tag$...$tag$
        - PostgreSQL E-strings: E'...'
        - Standard single-quoted strings: '...'
        """
        literals = []
        def _repl(m):
            idx = len(literals)
            literals.append(m.group(0))
            return f"___GB_STR_{idx}___"

        pattern = r"(\$\$[\s\S]*?\$\$|\$([a-zA-Z_]\w*)\$[\s\S]*?\$\2\$|E'(?:\\.|''|[^'\\])*'|'(?:\\.|''|[^'\\])*')"
        masked = re.sub(pattern, _repl, sql)
        return masked, literals

    @staticmethod
    def _strip_comments(sql: str) -> str:
        """Strip block comments /* ... */, line comments -- ..., and MySQL # ..."""
        c = re.sub(r"/\*[\s\S]*?\*/", " ", sql)
        c = re.sub(r"--[^\r\n]*", " ", c)
        c = re.sub(r"#[^\r\n]*", " ", c)
        return c

    @staticmethod
    def _mask_strings_and_literals(sql: str) -> Tuple[str, List[str]]:
        """
        Extract and mask all string literals and quoted identifiers:
        Used by SQL formatter to preserve both literal values and identifier cases.
        """
        literals = []
        def _repl(m):
            idx = len(literals)
            literals.append(m.group(0))
            return f" ___GB_LIT_{idx}___ "

        pattern = r"(\$\$[\s\S]*?\$\$|\$([a-zA-Z_]\w*)\$[\s\S]*?\$\2\$|E'(?:\\.|''|[^'\\])*'|'(?:\\.|''|[^'\\])*'|\"(?:\\.|\"\"|[^\"])*\"|`(?:``|[^`])*`|\[(?:\]\]|[^\]])*\])"
        masked = re.sub(pattern, _repl, sql)
        return masked, literals

    @classmethod
    def split_statements(cls, sql: str) -> List[str]:
        """
        Split a multi-statement SQL script into individual statements by semicolon.
        Guarantees that semicolons inside string literals, dollar quotes, comments,
        and quoted identifiers do not cause incorrect statement boundaries.
        """
        # Mask both strings and quoted identifiers so semicolons inside them are preserved
        tokens = []
        def _repl_tok(m):
            idx = len(tokens)
            tokens.append(m.group(0))
            return f"___GB_TOK_{idx}___"

        pattern = r"(\$\$[\s\S]*?\$\$|\$([a-zA-Z_]\w*)\$[\s\S]*?\$\2\$|E'(?:\\.|''|[^'\\])*'|'(?:\\.|''|[^'\\])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[(?:\]\]|[^\]])*\])"
        masked = re.sub(pattern, _repl_tok, sql)
        clean = cls._strip_comments(masked)
        parts = clean.split(";")
        stmts = []
        for p in parts:
            p_str = p.strip()
            if p_str:
                for idx, tok in enumerate(tokens):
                    p_str = p_str.replace(f"___GB_TOK_{idx}___", tok)
                stmts.append(p_str)
        return stmts

    @staticmethod
    def _normalize_identifiers_for_safety(sql: str) -> str:
        """
        Normalize quoted identifiers ("set_config", `setval`, [col]) for safety checks:
        - Quoted function/object names (e.g. "set_config", "setval", "delete") are unquoted
          so that identifier quotes cannot conceal restricted keywords or functions.
        - If an identifier is literally "WHERE", it represents a column/alias name and CANNOT
          act as a SQL clause keyword; it is masked to ___GB_ID_WHERE___ so it does not
          falsely satisfy the WHERE requirement of UPDATE/DELETE.
        """
        def _repl_ident(m):
            raw = m.group(0)
            inner = raw[1:-1]
            if raw.startswith('"'):
                inner = inner.replace('""', '"')
            elif raw.startswith('`'):
                inner = inner.replace('``', '`')
            elif raw.startswith('['):
                inner = inner.replace(']]', ']')

            if inner.strip().upper() == "WHERE":
                return " ___GB_ID_WHERE___ "
            return f" {inner} "

        ident_pattern = r"(\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[(?:\]\]|[^\]])*\])"
        return re.sub(ident_pattern, _repl_ident, sql)

    def _check_single_statement_safety(self, stmt: str, is_safe_mode: bool = False) -> Tuple[bool, str]:
        """Evaluate safety on an individual, isolated SQL statement."""
        # 1. Mask data literals (single quotes, dollar-quotes, E-strings)
        masked, _ = self._mask_strings(stmt)

        # 2. Strip comments
        q_no_comments = self._strip_comments(masked)

        # 3. Normalize identifiers (unquote "set_config", protect "where" columns)
        q_norm = self._normalize_identifiers_for_safety(q_no_comments).strip()
        if not q_norm:
            return False, ""

        q_upper = q_norm.upper()

        # SAFE MODE: STRICT READ-ONLY ENFORCEMENT
        if is_safe_mode:
            write_keywords = [
                (r"\bINSERT\b", "INSERT statement"),
                (r"\bUPDATE\b", "UPDATE statement"),
                (r"\bDELETE\b", "DELETE statement"),
                (r"\bDROP\b", "DROP statement"),
                (r"\bTRUNCATE\b", "TRUNCATE statement"),
                (r"\bALTER\b", "ALTER statement"),
                (r"\bCREATE\b", "CREATE statement"),
                (r"\bREPLACE\b", "REPLACE statement"),
                (r"\bGRANT\b", "GRANT statement"),
                (r"\bREVOKE\b", "REVOKE statement"),
                (r"\bVACUUM\b", "VACUUM statement"),
                (r"\bSET\b", "SET configuration change"),
                (r"\bRESET\b", "RESET configuration change"),
                (r"\bDO\b", "DO procedural block"),
                (r"\bCALL\b", "CALL stored procedure"),
                (r"\bMERGE\b", "MERGE statement"),
                (r"\bSET_CONFIG\b", "SET_CONFIG parameter modification"),
                (r"\bSETVAL\b", "SETVAL sequence mutation"),
                (r"\bNEXTVAL\b", "NEXTVAL sequence advance"),
                (r"\bCURRVAL\b", "CURRVAL sequence check"),
                (r"\bLASTVAL\b", "LASTVAL sequence check"),
                (r"\bPG_TERMINATE_BACKEND\b", "PG_TERMINATE_BACKEND admin call"),
                (r"\bPG_CANCEL_BACKEND\b", "PG_CANCEL_BACKEND admin call"),
                (r"\bLO_IMPORT\b", "LO_IMPORT filesystem read"),
                (r"\bLO_EXPORT\b", "LO_EXPORT filesystem write"),
                (r"\bDBLINK\b", "DBLINK external query execution"),
                (r"\bINTO\s+OUTFILE\b", "INTO OUTFILE export"),
                (r"\bINTO\s+DUMPFILE\b", "INTO DUMPFILE export"),
            ]
            for pattern, desc in write_keywords:
                if re.search(pattern, q_upper):
                    return True, f"Safe Mode is active: write or state-altering operations ({desc}) are strictly blocked"

            if re.search(r"\bPRAGMA\b\s+\w+\s*=", q_upper):
                return True, "Safe Mode is active: PRAGMA configuration writes are blocked"

            return False, ""

        # NORMAL MODE: Destructive Guard (Unconstrained modifications & schema drops per statement)
        if re.search(r"\bDROP\s+(TABLE|DATABASE|SCHEMA|VIEW)\b", q_upper):
            return True, "DROP operation detected"
        if re.search(r"\bTRUNCATE\b", q_upper):
            return True, "TRUNCATE operation detected"
        if re.search(r"\bDELETE\b", q_upper) and not re.search(r"\bWHERE\b", q_upper):
            return True, "DELETE without WHERE clause (will delete all rows)"
        if re.search(r"\bUPDATE\b", q_upper) and not re.search(r"\bWHERE\b", q_upper):
            return True, "UPDATE without WHERE clause (will modify all rows)"
        if re.search(r"\bALTER\s+TABLE\s+.*\bDROP\b", q_upper):
            return True, "ALTER TABLE DROP detected"

        return False, ""

    def check_safety(self, query: str, is_safe_mode: bool = False) -> Tuple[bool, str]:
        """
        Check script safety across all statements.
        Multi-statement queries are evaluated individually: if ANY statement is destructive
        or violates Safe Mode, the entire batch is flagged.
        """
        statements = self.split_statements(query)
        if not statements:
            return False, ""

        for stmt in statements:
            is_dest, reason = self._check_single_statement_safety(stmt, is_safe_mode=is_safe_mode)
            if is_dest:
                return True, reason

        return False, ""

    def explain_query(self, query: str) -> Dict[str, Any]:
        """
        Explain query execution plan.
        Strictly allows only a single read statement. Multi-statement batches or destructive
        operations are strictly rejected to prevent execution bypasses.
        """
        statements = self.split_statements(query)
        if not statements:
            return {"success": False, "error": "Query is empty"}
        if len(statements) > 1:
            return {
                "success": False,
                "error": "EXPLAIN only supports a single SQL statement. Multiple statements are not permitted.",
            }

        single_q = statements[0].strip().rstrip(";")

        # Validate safety on the single statement to be explained
        is_dest, reason = self.check_safety(single_q, is_safe_mode=False)

        # Detect EXPLAIN ANALYZE on destructive queries (PostgreSQL executes the query under ANALYZE)
        masked, _ = self._mask_strings(single_q)
        clean = self._strip_comments(masked).strip().upper()
        if re.search(r"\b(ANALYZE|EXECUTE)\b", clean) and is_dest:
            return {
                "success": False,
                "error": f"EXPLAIN with execution side-effects on destructive statements is blocked: {reason}",
            }

        if self.db_type == "sqlite":
            explain_sql = f"EXPLAIN QUERY PLAN {single_q};"
        else:
            explain_sql = f"EXPLAIN {single_q};"
        return self.execute_query(explain_sql)

    @staticmethod
    def format_sql(query: str) -> str:
        """Format and uppercase SQL keywords with line indents while preserving literals."""
        if not query or not query.strip():
            return query

        masked, literals = DatabaseEngine._mask_strings_and_literals(query)

        lines = masked.splitlines()
        comment_lines = []
        sql_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("--", "#")):
                comment_lines.append(stripped)
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

        # Restore original literals
        for idx, orig in enumerate(literals):
            sql_text = sql_text.replace(f"___GB_LIT_{idx}___", orig)

        result_parts = []
        if comment_lines:
            result_parts.append("\n".join(comment_lines))
        result_parts.append(sql_text.strip())
        return "\n".join(result_parts)

    @classmethod
    def is_mysql_select_needing_limit(cls, query: str) -> bool:
        """
        Check if a query is a top-level SELECT/WITH in MySQL that lacks a top-level LIMIT clause.
        Guarantees that SHOW, DESCRIBE, EXPLAIN, and subqueries with LIMIT are handled correctly.
        """
        masked, _ = cls._mask_strings(query)
        clean = cls._strip_comments(masked).strip()

        # Must start with SELECT or WITH
        if not re.match(r"^(SELECT|WITH)\b", clean, flags=re.IGNORECASE):
            return False

        # Check if there is a top-level LIMIT (at parenthesis depth 0)
        depth = 0
        tokens = re.split(r"(\(|\)|\bLIMIT\b)", clean, flags=re.IGNORECASE)
        for token in tokens:
            if token == "(":
                depth += 1
            elif token == ")":
                if depth > 0:
                    depth -= 1
            elif token.upper() == "LIMIT":
                if depth == 0:
                    return False  # Already has a top-level LIMIT
        return True

    # --- Query execution ---

    def execute_query(self, query: str, max_rows: int = 1000) -> Dict[str, Any]:
        start = time.perf_counter()
        cur = None
        try:
            # Check if query is DML/DDL write operation (even if it has RETURNING)
            masked, _ = self._mask_strings_and_literals(query)
            clean_q = re.sub(r"/\*[\s\S]*?\*/", " ", masked)
            clean_q = re.sub(r"--[^\r\n]*", " ", clean_q)
            clean_q = re.sub(r"#[^\r\n]*", " ", clean_q).strip().upper()
            is_write_dml = bool(
                re.search(r"\b(INSERT\s+INTO|UPDATE\s+|DELETE\s+FROM|DELETE\s+|REPLACE\s+INTO|CREATE\s+|DROP\s+|ALTER\s+|TRUNCATE\s+|DO\s+|CALL\s+|MERGE\s+)\b", clean_q)
            )

            # PostgreSQL streaming: Use server-side named cursor to prevent pulling entire table into client RAM
            if self.db_type == "postgresql" and not is_write_dml:
                stream_name = f"gb_stream_{int(time.perf_counter() * 1000000)}"
                # Disable autocommit temporarily for named cursor creation in psycopg2
                self.conn.autocommit = False
                try:
                    cur = self.conn.cursor(name=stream_name)
                    cur.itersize = max_rows + 1
                    cur.execute(query)
                    if cur.description:
                        columns = [d[0] for d in cur.description]
                        raw = cur.fetchmany(max_rows + 1)
                        truncated = len(raw) > max_rows
                        display_rows = raw[:max_rows]
                        rows = [list(r.values()) if isinstance(r, dict) else list(r) for r in display_rows]
                        cur.close()
                        self.conn.commit()  # Cleanly close read transaction without leaving idle connection
                        elapsed_ms = (time.perf_counter() - start) * 1000
                        return {
                            "success": True,
                            "columns": columns,
                            "rows": rows,
                            "row_count": len(rows),
                            "affected_rows": 0,
                            "truncated": truncated,
                            "elapsed_ms": round(elapsed_ms, 2),
                            "is_select": True,
                            "is_returning": False,
                        }
                except Exception as e:
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    raise e
                finally:
                    self.conn.autocommit = True

            # MySQL optimization: Auto-apply LIMIT on SELECTs without LIMIT to prevent server unbuffered socket drain
            exec_query = query
            if self.db_type == "mysql" and not is_write_dml:
                if self.is_mysql_select_needing_limit(query):
                    exec_query = query.rstrip().rstrip(";") + f" LIMIT {max_rows + 1};"

            cur = self.conn.cursor()
            cur.execute(exec_query)
            elapsed_ms = (time.perf_counter() - start) * 1000

            if cur.description:
                columns = [d[0] for d in cur.description]
                raw = cur.fetchmany(max_rows + 1)
                truncated = len(raw) > max_rows
                display_rows = raw[:max_rows]
                rows = []
                for r in display_rows:
                    if isinstance(r, dict):
                        rows.append(list(r.values()))
                    else:
                        rows.append(list(r))

                # For write queries that return data (e.g. INSERT ... RETURNING in SQLite)
                if self.db_type == "sqlite":
                    try:
                        self.conn.commit()
                    except Exception:
                        pass

                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                    "affected_rows": max(cur.rowcount, len(rows)) if is_write_dml else 0,
                    "truncated": truncated,
                    "elapsed_ms": round(elapsed_ms, 2),
                    "is_select": not is_write_dml,
                    "is_returning": is_write_dml,
                }
            else:
                if self.db_type in ("sqlite", "postgresql"):
                    self.conn.commit()
                return {
                    "success": True,
                    "affected_rows": max(cur.rowcount, 0),
                    "elapsed_ms": round(elapsed_ms, 2),
                    "is_select": False,
                    "is_returning": False,
                }
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            if self.db_type in ("postgresql", "sqlite"):
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            return {
                "success": False,
                "error": str(e),
                "elapsed_ms": round(elapsed_ms, 2),
            }
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass

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
