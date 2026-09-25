from app.db import connect


def list_tiles():
    conn = connect()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM tiles ORDER BY id").fetchall()]
    finally:
        conn.close()


def get_tile(tile_id: int):
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM tiles WHERE id=?", (tile_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
