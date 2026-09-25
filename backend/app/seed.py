from app.db import connect


def init_db():
    conn = connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS rooms(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            length REAL NOT NULL,
            width REAL NOT NULL,
            data_quality TEXT NOT NULL DEFAULT 'clean',
            note TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS tiles(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            tile_l REAL NOT NULL,
            tile_w REAL NOT NULL,
            data_quality TEXT NOT NULL DEFAULT 'clean'
        );
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS calc_runs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            tile_id INTEGER,
            waste_pct REAL,
            result_json TEXT NOT NULL,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        """
    )
    if conn.execute("SELECT COUNT(*) c FROM rooms").fetchone()["c"] == 0:
        conn.executemany(
            "INSERT INTO rooms(name,length,width,data_quality,note) VALUES (?,?,?,?,?)",
            [
                ("客餐厅", 6.0, 4.5, "clean", "标准矩形，可测算"),
                ("狭长走廊", 8.0, 1.2, "clean", ""),
                ("脏数据-负宽", 5.0, -0.5, "dirty", "宽度为负，详情页应标红"),
            ],
        )
        conn.executemany(
            "INSERT INTO tiles(name,tile_l,tile_w,data_quality) VALUES (?,?,?,?)",
            [
                ("600x600", 0.6, 0.6, "clean"),
                ("800x800", 0.8, 0.8, "clean"),
                ("脏数据-零面积", 0.0, 0.6, "dirty"),
            ],
        )
        conn.execute("INSERT INTO settings(key,value) VALUES ('waste_pct','8')")
        conn.commit()
    conn.close()
