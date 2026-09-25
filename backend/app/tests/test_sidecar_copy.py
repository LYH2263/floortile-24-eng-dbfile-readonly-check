"""SQLite 侧车（旁路）拷贝核验。

每一轮流程：
1. 在运行库（主库）落一条测算；
2. 把库文件复制到旁路目录；
3. 用只读连接打开拷贝，查出与主库该次相同的 order_count；
4. 主库再落一条测算；
5. 旁路拷贝里的行数与片数必须仍停在复制当下，不能跟着主库变多。

对不上即失败，断言信息统一以 [主库侧] / [拷贝侧] 标明出错一侧。
片数算法 app.engines.tile_math.tile_count 全程不改动，只调用。
整段流程在同一主库上连跑两轮都必须成功。

复制做法见 _copy_database_file；只读打开做法见 _open_readonly。
"""

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from app import config, db, seed
from app.engines.tile_math import tile_count
from app.repositories import history

ROOM_ID, TILE_ID, WASTE_PCT = 1, 1, 8.0


@pytest.fixture()
def primary_db(tmp_path, monkeypatch):
    """隔离的运行库：把 app.config/app.db 里的 DB_PATH 指到临时文件并建表塞种子数据。"""
    db_file = tmp_path / "data" / "app.db"
    db_file.parent.mkdir(parents=True)
    monkeypatch.setattr(config, "DB_PATH", db_file)
    monkeypatch.setattr(db, "DB_PATH", db_file)  # db.py 是 `from config import DB_PATH`
    seed.init_db()
    return db_file


def _drop_one_estimate(note: str) -> dict:
    """在主库落一条测算，返回 {run_id, order_count}。

    与 estimate_service.run_estimate(save=True) 完全相同的落库链路：
    tile_count(...) 算片数 -> history.insert_run(...) 写 calc_runs。
    片数怎么算由 tile_count 决定，这里不复制、不修改其算法。
    """
    calc = tile_count(6.0, 4.5, 0.6, 0.6, WASTE_PCT)
    payload = {**calc, "room_id": ROOM_ID, "tile_id": TILE_ID}
    run_id = history.insert_run(ROOM_ID, TILE_ID, WASTE_PCT, payload, note)
    return {"run_id": run_id, "order_count": calc["order_count"]}


def _copy_database_file(src: Path, dst: Path) -> None:
    """把运行中的库文件复制到旁路目录，得到复制当下的一致快照。

    做法：
    1. 先在源库执行 PRAGMA wal_checkpoint(TRUNCATE)，把 WAL 里已提交的页
       合并回主库文件（DELETE 日志模式下这一步是空操作）。否则在 WAL 模式下
       只复制主 .db 文件会丢掉还留在 -wal 里的已提交数据；
    2. 用 shutil.copy2 做字节级文件复制。本应用每条测算都是独立短连接、
       提交即关闭，复制瞬间没有活跃写事务，因此副本与源库事务一致。
       若复制时可能仍有连接在写，应改用 sqlite3 在线备份 API：
       ``sqlite3.connect(src)`` 后 ``src_conn.backup(sqlite3.connect(dst))``，
       它能在有并发写入时也拷出一致快照。
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = sqlite3.connect(f"file:{src}?mode=rw", uri=True)
    try:
        mode = checkpoint.execute("PRAGMA journal_mode").fetchone()[0]
        if mode.lower() == "wal":
            checkpoint.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        checkpoint.close()
    shutil.copy2(src, dst)


def _open_readonly(path: Path) -> sqlite3.Connection:
    """以只读方式打开拷贝：URI 连接串 file:<path>?mode=ro。

    mode=ro 禁止一切写操作（连临时表都要配 immutable 之外的额外设置），
    任何 INSERT/PRAGMA 写操作都会抛 OperationalError，保证核验过程不污染副本。
    """
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _snapshot(conn: sqlite3.Connection) -> tuple[int, list[int]]:
    """返回 (calc_runs 行数, 每条测算的 order_count 片数列表)，按 id 排序。"""
    rows = conn.execute("SELECT result_json FROM calc_runs ORDER BY id").fetchall()
    pieces = [json.loads(r[0])["order_count"] for r in rows]
    return len(rows), pieces


def _order_count_by_run_id(conn: sqlite3.Connection, run_id: int) -> int:
    row = conn.execute(
        "SELECT result_json FROM calc_runs WHERE id=?", (run_id,)
    ).fetchone()
    assert row is not None, f"查不到 run_id={run_id} 的测算"
    return json.loads(row[0])["order_count"]


def _run_one_round(primary_db_file: Path, side_dir: Path, round_no: int) -> None:
    tag = f"round{round_no}"

    # 1) 主库落第一条测算
    first = _drop_one_estimate(f"{tag}-first")

    # 2) 复制库文件到旁路目录
    copy_path = side_dir / f"app-{tag}.db"
    if copy_path.exists():
        copy_path.unlink()
    _copy_database_file(primary_db_file, copy_path)

    # 3) 只读打开拷贝：拷贝里该次 order_count 必须与主库该次相同
    with _open_readonly(copy_path) as ro:
        copy_row = ro.execute(
            "SELECT result_json FROM calc_runs WHERE id=?", (first["run_id"],)
        ).fetchone()
        assert copy_row is not None, (
            f"[拷贝侧] 第{round_no}轮：副本中找不到复制当次测算 run_id={first['run_id']}"
        )
        copy_order = json.loads(copy_row[0])["order_count"]
        frozen_rows, frozen_pieces = _snapshot(ro)

    with db.connect() as mc:
        primary_order = _order_count_by_run_id(mc, first["run_id"])
        primary_rows_at_copy, primary_pieces_at_copy = _snapshot(mc)

    assert primary_order == first["order_count"], (
        f"[主库侧] 第{round_no}轮：主库回读 order_count={primary_order}，"
        f"与落库返回值 {first['order_count']} 不一致"
    )
    assert copy_order == primary_order, (
        f"[拷贝侧] 第{round_no}轮：副本 order_count={copy_order} "
        f"与主库该次 order_count={primary_order} 不一致"
    )
    assert (frozen_rows, frozen_pieces) == (primary_rows_at_copy, primary_pieces_at_copy), (
        f"[主库侧] 第{round_no}轮：复制当下主库 "
        f"(行数={primary_rows_at_copy}, 片数={primary_pieces_at_copy}) "
        f"与副本冻结值 (行数={frozen_rows}, 片数={frozen_pieces}) 不一致"
    )

    # 4) 主库再落一条
    second = _drop_one_estimate(f"{tag}-second")

    # 5) 主库应当变多；旁路拷贝必须仍停在复制当下
    with _open_readonly(copy_path) as ro:
        copy_rows_after, copy_pieces_after = _snapshot(ro)
    with db.connect() as mc:
        primary_rows_after, primary_pieces_after = _snapshot(mc)

    assert (copy_rows_after, copy_pieces_after) == (frozen_rows, frozen_pieces), (
        f"[拷贝侧] 第{round_no}轮：主库追加后副本跟着变多——"
        f"复制当下 (行数={frozen_rows}, 片数={frozen_pieces})，"
        f"复查副本 (行数={copy_rows_after}, 片数={copy_pieces_after})"
    )
    assert primary_rows_after == frozen_rows + 1, (
        f"[主库侧] 第{round_no}轮：追加后主库行数应为 {frozen_rows + 1}，"
        f"实际 {primary_rows_after}"
    )
    assert primary_pieces_after == frozen_pieces + [second["order_count"]], (
        f"[主库侧] 第{round_no}轮：追加后主库片数序列异常，"
        f"期望 {frozen_pieces + [second['order_count']]}，实际 {primary_pieces_after}"
    )


def test_sidecar_copy_frozen_twice(primary_db, tmp_path):
    """同一主库上整段流程连跑两次，副本始终冻结在各自的复制当下。"""
    side_dir = tmp_path / "sidecar"
    side_dir.mkdir()
    _run_one_round(primary_db, side_dir, 1)
    _run_one_round(primary_db, side_dir, 2)
