# -*- coding: utf-8 -*-
"""
run_all.py — 一键执行全流程（01 生成 → 08 报告），并把完整日志写入 logs/。

用法：
    venv\\Scripts\\python scripts\\run_all.py

前置条件：本机 MySQL 8.x 已启动，且 config/db_config.py 已按 db_config.example.py 配置。
声明：本项目全部数据为 Faker 模拟数据，仅用于方法复现，不代表真实经营结果。
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_PATH = LOG_DIR / f"full_pipeline_{datetime.now():%Y%m%d_%H%M%S}.log"

STEPS = [
    ("01_generate_data",  "生成模拟数据（固定种子，含约2%脏数据注入）"),
    ("02_clean_data",     "清洗与标准化"),
    ("03_load_to_mysql",  "建库建表并导入 MySQL（幂等，可重跑）"),
    ("04_export_samples", "导出每表 ≤1000 行样例到 data/sample"),
    ("05_run_queries",    "执行 5 个分析 SQL + Pandas 复算一致性校验"),
    ("06_make_figures",   "生成 10 张分析图（SimHei 中文）"),
    ("07_make_dashboard", "生成 Excel 经营分析看板"),
    ("08_make_report",    "生成 Markdown 分析报告"),
]


def main() -> int:
    started = datetime.now()
    sep = "=" * 64
    with open(LOG_PATH, "w", encoding="utf-8") as log:
        def out(msg=""):
            print(msg)
            log.write(msg + "\n")

        out(sep)
        out(f"  甘小胖项目 全流程一键执行  开始于 {started:%Y-%m-%d %H:%M:%S}")
        out("  （模拟数据，仅用于方法复现，不代表真实经营结果）")
        out(sep)

        for i, (script, desc) in enumerate(STEPS, 1):
            out(f"\n########## [{i}/{len(STEPS)}] {script} — {desc} ##########")
            t0 = datetime.now()
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / f"{script}.py")],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                errors="replace",
            )
            for line in (proc.stdout or "").splitlines():
                out(line)
            if proc.returncode != 0:
                out(f"\n✘ 步骤 {script} 失败（returncode={proc.returncode}），流程中断。stderr：")
                for line in (proc.stderr or "").splitlines()[-30:]:
                    out(line)
                return 1
            out(f"########## [{i}/{len(STEPS)}] {script} 成功，耗时 {(datetime.now() - t0).seconds}s ##########")

        out(f"\n{sep}")
        out(f"  全流程执行成功，总耗时 {(datetime.now() - started).seconds}s")
        out(f"  日志文件：{LOG_PATH}")
        out(sep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
