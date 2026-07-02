from __future__ import annotations

import decimal
import datetime

from config import config

try:
    import ibm_db as ibm_db  # noqa: PLC0414
    _ibm_db_available = True
except ImportError:
    ibm_db = None  # type: ignore[assignment]
    _ibm_db_available = False

_connection = None


def _require_ibm_db() -> None:
    if not _ibm_db_available:
        raise RuntimeError(
            "ibm_db is not installed. Install it with: pip install ibm_db"
        )


def _stmt_error(stmt=None) -> str:
    """Return the most recent ibm_db error message."""
    msg = ibm_db.stmt_errormsg(stmt) if stmt else None
    if not msg:
        msg = ibm_db.conn_errormsg(_connection) if _connection else None
    return msg or "Unknown ibm_db error"


def _serialize_value(v):
    """Convert non-JSON-serialisable ibm_db value types to plain Python."""
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (datetime.date, datetime.datetime, datetime.time)):
        return v.isoformat()
    return v


def _fetch_all(statement, limit: int = 100) -> tuple[list[str], list[dict]]:
    """Fetch up to *limit* rows from an ibm_db statement as (columns, rows)."""
    columns: list[str] = []
    rows: list[dict] = []

    row = ibm_db.fetch_assoc(statement)
    while row is not False and len(rows) < limit:
        if not columns:
            columns = list(row.keys())
        rows.append({k: _serialize_value(v) for k, v in row.items()})
        row = ibm_db.fetch_assoc(statement)

    return columns, rows


def get_connection():
    _require_ibm_db()
    global _connection

    if _connection is not None and ibm_db.active(_connection):
        return _connection

    _connection = ibm_db.connect(config.db2_connection_string, "", "")
    if not _connection:
        raise RuntimeError(
            f"Failed to connect to Db2: {ibm_db.conn_errormsg()}"
        )
    return _connection


def list_tables(schema: str = None) -> dict:
    target_schema = schema or config.db2_schema or None
    sql = (
        "SELECT TABSCHEMA, TABNAME, COALESCE(REMARKS, '') AS COMMENT "
        "FROM SYSCAT.TABLES WHERE TYPE = 'T'"
    )

    if target_schema:
        escaped_schema = target_schema.replace("'", "''").upper()
        sql += f" AND TABSCHEMA = '{escaped_schema}'"

    sql += " ORDER BY TABSCHEMA, TABNAME"

    conn = get_connection()
    statement = ibm_db.exec_immediate(conn, sql)
    if statement is False:
        return {"error": _stmt_error()}

    _, rows = _fetch_all(statement)
    tables = [
        {"schema": r["TABSCHEMA"], "name": r["TABNAME"], "comment": r["COMMENT"]}
        for r in rows
    ]
    return {"tables": tables}


def run_query(sql: str) -> dict:
    normalized_sql = sql.strip()
    upper_sql = normalized_sql.upper()

    if not upper_sql.startswith("SELECT") and not upper_sql.startswith("WITH"):
        return {"error": "Only SELECT queries are allowed"}

    conn = get_connection()
    statement = ibm_db.exec_immediate(conn, normalized_sql)
    if statement is False:
        return {"error": _stmt_error()}

    columns, rows = _fetch_all(statement, limit=100)
    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
    }

def run_query_city_distance(city1: str, city2: str) -> dict:
    sql = (
        "SELECT a.name AS city1, b.name AS city2,"
        " haversine(a.lat, a.long, b.lat, b.long) AS distance_km"
        " FROM cities a, cities b"
        f" WHERE a.name = '{city1}' AND b.name = '{city2}'"
    )
    conn = get_connection()
    statement = ibm_db.exec_immediate(conn, sql)
    if statement is False:
        return {"error": _stmt_error()}

    _, rows = _fetch_all(statement, limit=1)
    if not rows:
        return {"error": f"No data found for cities '{city1}' and '{city2}'"}

    row = rows[0]
    return {
        "city1": row["CITY1"],
        "city2": row["CITY2"],
        "distance_km": row["DISTANCE_KM"],
    }


def get_nearby_cities(city: str, limit: int = 10) -> dict:
    """Return the *limit* closest cities to *city* using vector distance + haversine."""
    escaped_city = city.replace("'", "''")
    sql = (
        "SELECT name, country, distance_km FROM ("
        "  SELECT a.name, a.country,"
        "         haversine(a.lat, a.long, b.lat, b.long) AS distance_km"
        "  FROM cities a, cities b"
        f" WHERE b.name = '{escaped_city}'"
        "  ORDER BY vector_distance(b.coord, a.coord, euclidean)"
        f" FETCH FIRST {limit} ROWS ONLY"
        ")"
    )

    conn = get_connection()
    statement = ibm_db.exec_immediate(conn, sql)
    if statement is False:
        return {"error": _stmt_error()}

    _, rows = _fetch_all(statement, limit=limit)
    if not rows:
        return {"error": f"No data found for city '{city}'"}

    return {
        "center_city": city,
        "nearby_cities": [
            {
                "name": r["NAME"],
                "country": r["COUNTRY"],
                "distance_km": r["DISTANCE_KM"],
            }
            for r in rows
        ],
    }
