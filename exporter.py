import csv
import json
import decimal
import datetime
import uuid
from typing import List, Any


class Exporter:
    @staticmethod
    def _json_serial(obj: Any) -> Any:
        """Serialize non-standard types (Decimal, datetime, UUID, bytes) for JSON export."""
        if isinstance(obj, (datetime.date, datetime.datetime, datetime.time)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return int(obj) if (obj % 1 == 0) else float(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, (bytes, bytearray)):
            try:
                return obj.decode("utf-8")
            except Exception:
                return obj.hex()
        if hasattr(obj, "__str__"):
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @staticmethod
    def _dedup_columns(columns: List[str]) -> List[str]:
        seen = {}
        deduped = []
        for c in columns:
            col_str = str(c)
            if col_str in seen:
                seen[col_str] += 1
                deduped.append(f"{col_str}_{seen[col_str]}")
            else:
                seen[col_str] = 1
                deduped.append(col_str)
        return deduped

    @staticmethod
    def _escape_ident(ident: str) -> str:
        s = str(ident).strip()
        if "." in s:
            parts = s.split(".")
            return ".".join(f'"{p.replace(chr(34), chr(34)*2)}"' for p in parts)

        reserved = {
            "ALL", "ALTER", "AND", "ANY", "AS", "ASC", "BETWEEN", "BY", "CASE",
            "CHECK", "COLUMN", "CONSTRAINT", "CREATE", "CROSS", "CURRENT_DATE",
            "CURRENT_TIME", "CURRENT_TIMESTAMP", "DEFAULT", "DELETE", "DESC",
            "DISTINCT", "DROP", "ELSE", "END", "EXISTS", "FALSE", "FOR",
            "FOREIGN", "FROM", "FULL", "GROUP", "HAVING", "IN", "INDEX",
            "INNER", "INSERT", "INTERSECT", "INTO", "IS", "JOIN", "KEY",
            "LEFT", "LIKE", "LIMIT", "NOT", "NULL", "ON", "OR", "ORDER",
            "OUTER", "PRIMARY", "REFERENCES", "RIGHT", "SELECT", "SET",
            "TABLE", "THEN", "TO", "TRUE", "UNION", "UNIQUE", "UPDATE",
            "USER", "VALUES", "VIEW", "WHEN", "WHERE", "WITH"
        }
        if not s.isidentifier() or s.upper() in reserved:
            escaped = s.replace('"', '""')
            return f'"{escaped}"'
        return s

    @staticmethod
    def to_csv(columns: List[str], rows: List[List[Any]], output_path: str):
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)

    @staticmethod
    def to_json(columns: List[str], rows: List[List[Any]], output_path: str):
        clean_cols = Exporter._dedup_columns(columns)
        data = []
        for r in rows:
            data.append(dict(zip(clean_cols, r)))
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=Exporter._json_serial)

    @staticmethod
    def to_markdown(columns: List[str], rows: List[List[Any]], output_path: str):
        with open(output_path, "w", encoding="utf-8") as f:
            # Header
            f.write("| " + " | ".join(str(c) for c in columns) + " |\n")
            # Separator
            f.write("| " + " | ".join("---" for _ in columns) + " |\n")
            # Rows
            for r in rows:
                clean_cells = [
                    (str(val).replace("|", "\\|").replace("\n", " ") if val is not None else "NULL")
                    for val in r
                ]
                f.write("| " + " | ".join(clean_cells) + " |\n")

    @staticmethod
    def to_sql_inserts(table_name: str, columns: List[str], rows: List[List[Any]], output_path: str):
        table = (table_name or "exported_table").strip()
        escaped_table = Exporter._escape_ident(table)
        escaped_cols = [Exporter._escape_ident(c) for c in columns]
        cols_str = ", ".join(escaped_cols)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"-- GhostBase SQL Export: {table}\n")
            f.write(f"-- Total: {len(rows)} row(s)\n\n")
            for r in rows:
                vals = []
                for v in r:
                    if v is None:
                        vals.append("NULL")
                    elif isinstance(v, bool):
                        vals.append("TRUE" if v else "FALSE")
                    elif isinstance(v, (int, float, decimal.Decimal)):
                        vals.append(str(v))
                    else:
                        escaped = str(v).replace("'", "''")
                        vals.append(f"'{escaped}'")
                vals_str = ", ".join(vals)
                f.write(f"INSERT INTO {escaped_table} ({cols_str}) VALUES ({vals_str});\n")
