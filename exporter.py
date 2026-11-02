import csv
import json
from typing import List, Any


class Exporter:
    @staticmethod
    def to_csv(columns: List[str], rows: List[List[Any]], output_path: str):
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)

    @staticmethod
    def to_json(columns: List[str], rows: List[List[Any]], output_path: str):
        data = []
        for r in rows:
            data.append(dict(zip(columns, r)))
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

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
        table = table_name or "exported_table"
        cols_str = ", ".join(columns)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"-- GhostBase SQL Export: {table}\n")
            f.write(f"-- Total: {len(rows)} row(s)\n\n")
            for r in rows:
                vals = []
                for v in r:
                    if v is None:
                        vals.append("NULL")
                    elif isinstance(v, (int, float)):
                        vals.append(str(v))
                    else:
                        escaped = str(v).replace("'", "''")
                        vals.append(f"'{escaped}'")
                vals_str = ", ".join(vals)
                f.write(f"INSERT INTO {table} ({cols_str}) VALUES ({vals_str});\n")
