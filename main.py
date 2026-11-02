import sys
import os
import urllib.parse


def _load_env_file(path: str) -> dict:
    """Parse a .env file without any external dependency."""
    env: dict = {}
    if not os.path.isfile(path):
        return env
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                env[key] = val
    except Exception:
        pass
    return env


def parse_args():
    read_only = False
    conn_arg = None
    for a in sys.argv[1:]:
        arg_lower = a.strip().lower()
        if arg_lower in ("-r", "--read-only", "--safe"):
            read_only = True
        elif arg_lower in ("-h", "--help"):
            print("GhostBase 👻 - Terminal Database Studio\n")
            print("Usage:")
            print("  ghostbase                       (Auto-detect .env or sample.db)")
            print("  ghostbase <db_path_or_url>      (Connect to SQLite, Postgres or MySQL)")
            print("  ghostbase --read-only           (Launch in Safe Mode)\n")
            print("Keyboard Shortcuts:")
            print("  Ctrl+R     Execute query")
            print("  Ctrl+P     1-Key EXPLAIN query plan")
            print("  Ctrl+B     Beautify & format SQL query")
            print("  Ctrl+S     Toggle Safe Mode / Production Guard")
            print("  Ctrl+N     New / clear query")
            print("  Ctrl+I     Export results as SQL INSERTs")
            print("  Ctrl+M     Export results as Markdown table")
            print("  Ctrl+E     Export results as CSV")
            print("  Ctrl+J     Export results as JSON")
            print("  Ctrl+F     Filter / search tables")
            print("  Ctrl+Up    Previous query from history")
            print("  Ctrl+Down  Next query from history")
            print("  Ctrl+Q     Quit\n")
            sys.exit(0)
        else:
            conn_arg = a.strip()
    return conn_arg, read_only


def detect_connection(cli_arg: str = None) -> str:
    """
    Resolve the database connection string in priority order:

    1. Command-line argument  (ghostbase mydb.sqlite | ghostbase postgresql://...)
    2. DATABASE_URL  in .env (current working directory)
    3. DB_HOST + DB_NAME + DB_USER  in .env  -> builds a PostgreSQL URL (credentials URL-encoded)
    4. DATABASE_URL  environment variable
    5. Fallback: sample.db  (SQLite, inside GhostBase directory)
    """
    if cli_arg:
        return cli_arg

    # 2 & 3. .env file
    env = _load_env_file(os.path.join(os.getcwd(), ".env"))

    url = env.get("DATABASE_URL")
    if url:
        return url

    host = env.get("DB_HOST") or env.get("PGHOST")
    port = env.get("DB_PORT") or env.get("PGPORT") or "5432"
    name = env.get("DB_NAME") or env.get("PGDATABASE")
    user = env.get("DB_USER") or env.get("PGUSER")
    pwd  = env.get("DB_PASSWORD") or env.get("PGPASSWORD") or ""

    if host and name and user:
        safe_user = urllib.parse.quote_plus(user)
        safe_pwd = urllib.parse.quote_plus(pwd) if pwd else ""
        auth = f"{safe_user}:{safe_pwd}" if pwd else safe_user
        return f"postgresql://{auth}@{host}:{port}/{name}"

    # 4. OS environment variable
    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    # 5. Fallback
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample.db")


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    from app import GhostBaseApp

    conn_arg, read_only = parse_args()
    conn = detect_connection(conn_arg)
    try:
        app = GhostBaseApp(db_path=conn, read_only=read_only)
        app.run()
        ret = getattr(app, "return_code", 0)
        if isinstance(ret, int) and ret != 0:
            sys.exit(ret)
    except Exception as e:
        print(f"\n[GhostBase Error] Failed to connect to database: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
