from app.db import connect


def list_rooms():
    conn = connect()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM rooms ORDER BY id").fetchall()]
    finally:
        conn.close()


def get_room(room_id: int):
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
