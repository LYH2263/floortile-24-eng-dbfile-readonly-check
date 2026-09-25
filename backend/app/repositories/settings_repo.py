from app.config import DEFAULT_WASTE_PCT
from app.db import connect


def get_all() -> dict:
    conn = connect()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        out = {r["key"]: r["value"] for r in rows}
        if "waste_pct" not in out:
            out["waste_pct"] = str(DEFAULT_WASTE_PCT)
        return out
    finally:
        conn.close()


def get_waste_pct() -> float:
    raw = get_all().get("waste_pct", str(DEFAULT_WASTE_PCT))
    return float(raw)
