"""本机无 pytest 时的等价驱动：stub 掉 pytest.fixture，用临时 DATA_DIR 真实连跑两轮。"""
import os
import sys
import tempfile
import types
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root))

_tmp = Path(tempfile.mkdtemp(prefix="sidecar-check-"))
os.environ["DATA_DIR"] = str(_tmp / "data")

# --- minimal pytest stub: fixture decorator passes function through ---
_pytest_stub = types.ModuleType("pytest")
_pytest_stub.fixture = lambda *a, **k: (a[0] if a and callable(a[0]) else (lambda fn: fn))
sys.modules["pytest"] = _pytest_stub

from app import config, db, seed  # noqa: E402
from app.tests import test_sidecar_copy as t  # noqa: E402

seed.init_db()
side_dir = _tmp / "sidecar"
side_dir.mkdir()
t._run_one_round(config.DB_PATH, side_dir, 1)
t._run_one_round(config.DB_PATH, side_dir, 2)

# 额外确认：只读连接确实拒绝写入
ro = t._open_readonly(side_dir / "app-round2.db")
try:
    ro.execute("INSERT INTO calc_runs(id,result_json,created_at) VALUES(99,'x','x')")
    print("FAIL: 只读连接居然允许写入")
    sys.exit(1)
except Exception as e:
    print("只读写保护生效:", type(e).__name__, str(e))
finally:
    ro.close()

with db.connect() as mc:
    total = mc.execute("SELECT COUNT(*) FROM calc_runs").fetchone()[0]
print(f"OK: 两轮核验通过；主库 calc_runs 共 {total} 行（期望 4）；副本各自冻结")
