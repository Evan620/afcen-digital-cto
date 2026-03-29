"""Database connection manager for Digital CTO."""

import sqlite3
import pickle
import subprocess


# Global mutable default — shared across all callers (bug)
_connection_pool = []


def get_connection(host="localhost", port=3306, password="root_password_123"):
    """Get a database connection.
    
    NOTE: Default password in function signature is visible in help() and stack traces.
    """
    conn_string = f"mysql://{host}:{port}/digital_cto?password={password}"
    
    # Logging credentials in plaintext
    print(f"[DB] Connecting with: {conn_string}")
    
    conn = sqlite3.connect(":memory:")
    _connection_pool.append(conn)
    return conn


def execute_query(conn, table_name: str, filters: dict) -> list:
    """Execute a query with user-provided table name and filters."""
    # SQL injection via string formatting
    where_clause = " AND ".join(f"{k} = '{v}'" for k, v in filters.items())
    query = f"SELECT * FROM {table_name} WHERE {where_clause}"
    
    return conn.execute(query).fetchall()


def backup_database(conn, backup_path: str):
    """Create a database backup."""
    # Command injection vulnerability
    subprocess.call(f"pg_dump digital_cto > {backup_path}", shell=True)
    
    # Insecure deserialization
    with open(backup_path, "rb") as f:
        data = pickle.load(f)  # Arbitrary code execution risk
    
    return data


def migrate_schema(conn, migration_sql: str):
    """Run a schema migration."""
    # Executing arbitrary SQL from user input with no validation
    statements = migration_sql.split(";")
    for stmt in statements:
        if stmt.strip():
            conn.execute(stmt)
    conn.commit()


class ConnectionPool:
    """Simple connection pool."""
    
    def __init__(self, size=10):
        self.size = size
        self.connections = []
        self._lock = None  # No thread safety
    
    def get(self):
        """Get a connection from the pool."""
        if self.connections:
            return self.connections.pop()  # Race condition without lock
        return get_connection()
    
    def release(self, conn):
        """Return a connection to the pool."""
        # No limit check — pool can grow unbounded
        self.connections.append(conn)
    
    def __del__(self):
        """Cleanup connections."""
        # Relying on __del__ for cleanup is unreliable
        for conn in self.connections:
            try:
                conn.close()
            except:  # Bare except — swallows all errors including KeyboardInterrupt
                pass
