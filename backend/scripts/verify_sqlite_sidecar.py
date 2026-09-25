"""
SQLite 侧车（sidecar）拷贝核验
==============================

验证目标
--------
1. 在「运行库（主库）」落一条测算后，把库文件复制到「旁路目录」，用**只读连接**
   打开拷贝，从中查出与主库该次完全相同的 order_count（下单片数，简称“片数”）。
2. 主库随后再落一条测算，旁路拷贝里的**行数与片数**必须仍停在复制当下——
   拷贝是静态快照，不能跟着主库变多。
3. 任一处对不上立即失败，并写明不匹配出在「主库侧」还是「拷贝侧」。
4. 上述整段流程**连跑两轮**都要成功（第二轮复用同一个主库，此时主库已在持续
   增长，验证每一轮的快照都各自冻结在自己的复制时刻）。

片数算法（app/engines/tile_math.py 的 tile_count / layout_preview）**禁止改动**，
本脚本只 import 调用，不修改其源码。

复制做法
--------
- 复制前用一条短连接对主库执行 ``PRAGMA wal_checkpoint(TRUNCATE)``：WAL 模式下把
  -wal 合入主库文件并截断；本项目默认是 delete 回滚日志模式（无 -wal），此调用无
  副作用，但保留它可让复制在两种日志模式下都拿到“单文件即全量”的一致快照。
- 随后用 ``shutil.copy2(DB_PATH, 旁路路径)`` 整体复制库文件；并断言旁路目录中
  只有这一个文件（没有遗漏的 -wal/-shm/-journal）。

只读打开做法
------------
- 用只读 URI 打开拷贝::

      sqlite3.connect("file:<绝对路径>?mode=ro", uri=True)

  ``mode=ro`` 让 SQLite 以只读方式打开该文件：任何写/建表操作都会抛
  OperationalError，也不会在旁路目录生成 -wal/-shm/-journal。
- 再叠加 ``PRAGMA query_only=ON`` 做连接级双保险。
- 该只读连接全程不关闭，一直贯穿“主库落第二条之后”的复查：若拷贝会跟随主库
  变化，此刻必然暴露。

运行::

    cd backend
    python3 scripts/verify_sqlite_sidecar.py
退出码 0 表示两轮全部通过；非 0 表示失败（输出会标明主库侧 / 拷贝侧）。
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.request import pathname2url

# 让脚本能 import app.*（scripts/ 在 backend/ 下，注入 backend 根到 sys.path）
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 【必须在 import app.config 之前】把 DATA_DIR 指到临时目录，得到一个独立主库，
# 不污染 backend/data/app.db 真实运行库。
_main_data_dir = tempfile.TemporaryDirectory(prefix="sidecar-main-")
os.environ["DATA_DIR"] = _main_data_dir.name

from app import seed  # noqa: E402
from app.config import DB_PATH  # noqa: E402
from app.db import connect as main_connect  # noqa: E402
from app.engines.tile_math import tile_count  # noqa: E402
from app.repositories import history  # noqa: E402

ROOM_ID = 1  # seed: 客餐厅 6.0 x 4.5（clean，可测算）
FIRST_TILE_ID = 1  # seed: 600x600
SECOND_TILE_ID = 2  # seed: 800x800（与第一条片数不同，便于暴露“拷贝跟变”）
WASTE_PCT = 8.0
SNAPSHOT_NAME = "app.snapshot.db"


class CheckFailed(AssertionError):
    """带“侧别”的核验失败：side 为 '主库侧' 或 '拷贝侧'。"""

    def __init__(self, side: str, message: str):
        self.side = side
        super().__init__(f"[{side}] {message}")


def require(condition: bool, side: str, message: str) -> None:
    if not condition:
        raise CheckFailed(side, message)


def dims_for(conn, tile_id: int):
    """从主库读取房间/瓷砖尺寸，片数仍交给未改动的 tile_count 计算。"""
    room = conn.execute(
        "SELECT length, width FROM rooms WHERE id=?", (ROOM_ID,)
    ).fetchone()
    tile = conn.execute(
        "SELECT tile_l, tile_w FROM tiles WHERE id=?", (tile_id,)
    ).fetchone()
    require(room is not None, "主库侧", f"seed 房间 id={ROOM_ID} 不存在")
    require(tile is not None, "主库侧", f"seed 瓷砖 id={tile_id} 不存在")
    return room["length"], room["width"], tile["tile_l"], tile["tile_w"]


def save_one_run(conn, round_no: int, which: str, tile_id: int):
    """走生产落库路径 history.insert_run 落一条测算，返回 (run_id, calc)。"""
    rl, rw, tl, tw = dims_for(conn, tile_id)
    calc = tile_count(rl, rw, tl, tw, WASTE_PCT)
    # 与 estimate_service 完全一致的 payload 形状
    payload = {**calc, "room_id": ROOM_ID, "tile_id": tile_id}
    note = f"round{round_no}-{which}"
    run_id = history.insert_run(ROOM_ID, tile_id, WASTE_PCT, payload, note)
    return run_id, calc


def latest_run(conn) -> tuple[int, int, str]:
    """返回 (calc_runs 行数, 最新一条 id, 最新一条 result_json 原文)。"""
    count = conn.execute("SELECT COUNT(*) c FROM calc_runs").fetchone()["c"]
    row = conn.execute(
        "SELECT id, result_json FROM calc_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return int(count), -1, ""
    return int(count), int(row["id"]), row["result_json"]


def checkpoint_main_db() -> None:
    """WAL 下合入并截断 -wal；delete 日志模式下为无副作用的空操作。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    finally:
        conn.close()


def make_snapshot(side_dir: Path) -> Path:
    """把主库文件整体复制到旁路目录，并断言旁路只有这一个文件。"""
    checkpoint_main_db()
    side_dir.mkdir(parents=True, exist_ok=True)
    copy_path = side_dir / SNAPSHOT_NAME
    shutil.copy2(DB_PATH, copy_path)
    present = sorted(p.name for p in side_dir.iterdir())
    require(
        present == [SNAPSHOT_NAME],
        "拷贝侧",
        f"旁路目录应只有单个快照文件，实际为 {present}（可能遗漏 -wal/-shm）",
    )
    return copy_path


def open_readonly(copy_path: Path) -> sqlite3.Connection:
    """以只读 URI 打开拷贝，并设 query_only=ON。"""
    uri = "file:" + pathname2url(str(copy_path)) + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def assert_readonly(ro_conn: sqlite3.Connection) -> None:
    """自证只读确实生效：建表/写入必须被拒。"""
    try:
        ro_conn.execute("CREATE TABLE ro_probe(x)")
    except sqlite3.OperationalError:
        return
    raise CheckFailed("拷贝侧", "只读连接竟然允许写入，mode=ro 未生效")


def run_round(round_no: int, main_conn: sqlite3.Connection, side_root: Path) -> None:
    prefix = f"[轮{round_no}]"
    base_count, _, _ = latest_run(main_conn)
    print(f"{prefix} 开始：复制当下之前主库已有行数 = {base_count}")

    # 1) 主库落第一条测算 -----------------------------------------------------
    run_a, calc_a = save_one_run(main_conn, round_no, "first", FIRST_TILE_ID)
    order_a = calc_a["order_count"]
    print(
        f"{prefix} 主库落第1条 run_id={run_a}（tile={FIRST_TILE_ID}），"
        f"片数 order_count={order_a}（片数算法 tile_count 未改动）"
    )

    # 主库侧自查：行数 +1，最新一条即刚落的 run_a 且片数一致
    m_count, m_id, m_json = latest_run(main_conn)
    m_order = json.loads(m_json)["order_count"]
    require(m_count == base_count + 1, "主库侧",
            f"落第1条后行数应为 {base_count + 1}，实际 {m_count}")
    require(m_id == run_a, "主库侧",
            f"最新 id 应为 {run_a}，实际 {m_id}")
    require(m_order == order_a, "主库侧",
            f"主库片数 {m_order} 与算法结果 {order_a} 不一致")
    print(f"{prefix} 主库侧核对通过：行数={m_count}，最新片数={m_order}")

    # 2) 复制库文件到旁路目录 --------------------------------------------------
    side_dir = side_root / f"round{round_no}"
    copy_path = make_snapshot(side_dir)
    print(f"{prefix} 已 checkpoint 并 copy2 主库 -> 旁路快照：{copy_path}")

    # 3) 只读打开拷贝，核对与主库该次相同 -------------------------------------
    ro_conn = open_readonly(copy_path)
    try:
        print(f"{prefix} 已用只读 URI 打开：file:{copy_path}?mode=ro（uri=True，query_only=ON）")
        assert_readonly(ro_conn)
        print(f"{prefix} 只读自证：对拷贝执行写操作被 SQLite 拒绝 ✔")

        c_count, c_id, c_json = latest_run(ro_conn)
        require(c_count == m_count, "拷贝侧",
                f"拷贝行数 {c_count} 与复制当下主库行数 {m_count} 不一致")
        require(c_id == m_id == run_a, "拷贝侧",
                f"拷贝最新 id={c_id}，应为复制当下的 {run_a}")
        require(c_json == m_json, "拷贝侧", "拷贝最新一条 result_json 与主库复制当下不一致")
        c_order = json.loads(c_json)["order_count"]
        require(c_order == order_a, "拷贝侧",
                f"拷贝片数 {c_order} 与主库片数 {order_a} 不一致")
        print(f"{prefix} 拷贝侧核对通过：行数={c_count}，最新片数={c_order}，与主库该次相同 ✔")

        # 4) 主库再落一条（片数与第一条不同）----------------------------------
        run_b, calc_b = save_one_run(main_conn, round_no, "second", SECOND_TILE_ID)
        order_b = calc_b["order_count"]
        print(
            f"{prefix} 主库再落第2条 run_id={run_b}（tile={SECOND_TILE_ID}），"
            f"片数 order_count={order_b}"
        )

        # 主库侧：行数再 +1，最新变成 run_b
        m2_count, m2_id, m2_json = latest_run(main_conn)
        require(m2_count == base_count + 2, "主库侧",
                f"落第2条后行数应为 {base_count + 2}，实际 {m2_count}")
        require(m2_id == run_b, "主库侧",
                f"主库最新 id 应变为 {run_b}，实际 {m2_id}")
        require(json.loads(m2_json)["order_count"] == order_b, "主库侧",
                "主库第2条片数与算法结果不一致")
        print(f"{prefix} 主库侧核对通过：行数={m2_count}，最新片数={order_b}（主库确实变多）")

        # 5) 拷贝侧复查：必须停在复制当下，不能跟着变多 ------------------------
        c2_count, c2_id, c2_json = latest_run(ro_conn)
        require(c2_count == m_count == base_count + 1, "拷贝侧",
                f"拷贝行数应停在 {base_count + 1}，实际变为 {c2_count}（快照跟随了主库）")
        require(c2_id == run_a, "拷贝侧",
                f"拷贝最新 id 应停在 {run_a}，实际变为 {c2_id}（快照跟随了主库）")
        require(c2_json == m_json, "拷贝侧", "拷贝最新一条内容发生变化，未停在复制当下")
        frozen_order = json.loads(c2_json)["order_count"]
        require(frozen_order == order_a, "拷贝侧",
                f"拷贝片数应停在 {order_a}，实际变为 {frozen_order}")
        print(
            f"{prefix} 拷贝侧复查通过：行数仍={c2_count}，最新片数仍={frozen_order}，"
            f"停在复制当下、未跟随主库变多 ✔"
        )
    finally:
        ro_conn.close()


def main() -> int:
    print(f"主库（运行库）文件：{DB_PATH}")
    seed.init_db()  # 建表 + seed 房间/瓷砖
    side_root_mgr = tempfile.TemporaryDirectory(prefix="sidecar-copy-")
    side_root = Path(side_root_mgr.name)
    print(f"旁路快照根目录：{side_root}\n")

    main_conn = main_connect()
    try:
        for round_no in (1, 2):
            run_round(round_no, main_conn, side_root)
            print()
    except CheckFailed as exc:
        print(f"\n核验失败（{exc.side}）：{exc}", file=sys.stderr)
        return 1
    finally:
        main_conn.close()
        side_root_mgr.cleanup()
        _main_data_dir.cleanup()

    print("结果：整段流程连跑两轮，主库侧 / 拷贝侧核对全部 PASS。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
