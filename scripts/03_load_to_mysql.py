# -*- coding: utf-8 -*-
"""
03_load_to_mysql.py — 在本地便携 MySQL 中新建 ganxiaopang_db 并导入清洗后数据
================================================================
流程：
  1) 用 root 账号连接（不指定 db），执行 sql/00_create_database.sql 建库建表
  2) 创建应用账号 gxp_app（仅授权 ganxiaopang_db，不触碰实例中其他库）
  3) 用 gxp_app 导入 data/processed/*.csv（TRUNCATE + 批量 INSERT）
  4) 执行 sql/01_metric_views.sql 固化四层指标视图
  5) 校验各表行数与核心指标

安全约束：仅操作 ganxiaopang_db；绝不 DROP/修改 diabetes_platform 等其他库。
"""
import os
import re
import subprocess
import sys
import time

import pandas as pd
import pymysql

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "config"))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
SQL_DIR = os.path.join(BASE_DIR, "sql")
LOG_DIR = os.path.join(BASE_DIR, "logs")

try:
    from db_config import DB_CONFIG, ROOT_DB_CONFIG
except ImportError:
    print("✗ 未找到 config/db_config.py，请先复制 config/db_config.example.py 并按本机环境修改。")
    sys.exit(1)

DB_NAME = DB_CONFIG["database"]
APP_USER = DB_CONFIG["user"]
APP_PWD = DB_CONFIG["password"]

# 表 → 导入列（与 00_create_database.sql 一致；fact_order_items.id 自增）
TABLES = {
    "dim_sku": ["sku_id", "sku_code", "sku_name", "category_l1", "category_l2",
                "brand_series", "spec", "unit", "cost_price", "retail_price",
                "gross_margin_rate", "supplier_id", "origin", "is_self_operated",
                "shelf_date", "status"],
    "dim_users": ["user_id", "nickname", "gender", "age", "province", "city_tier",
                  "register_date", "source", "is_fan", "member_level"],
    "dim_suppliers": ["supplier_id", "supplier_name", "supplier_type", "region",
                      "coop_years", "annual_supply_tons"],
    "dim_stores": ["store_id", "store_name", "city", "open_date", "area_sqm",
                   "rent_monthly", "staff_cnt", "staff_cost_monthly",
                   "util_monthly", "amort_months", "seats", "initial_investment"],
    "dim_warehouses": ["warehouse_id", "warehouse_name", "area_sqm", "location"],
    "fact_live_sessions": ["session_id", "live_date", "start_time", "duration_min",
                           "anchor", "theme", "is_festival", "total_exposure",
                           "total_enter", "total_stay", "total_interact",
                           "total_order_placed", "total_paid", "gmv",
                           "new_followers", "sku_cnt", "main_category"],
    "fact_live_minute_traffic": ["id", "session_id", "minute_index",
                                 "viewers_online", "exposure_delta", "enter_delta",
                                 "comment_cnt", "like_cnt", "follow_delta",
                                 "order_cnt", "pay_user_cnt"],
    "fact_orders": ["order_id", "user_id", "order_time", "channel", "session_id",
                    "order_status", "item_cnt", "pay_amount", "discount_amount",
                    "freight", "province"],
    "fact_order_items": ["order_id", "sku_id", "quantity", "unit_price",
                         "cost_price", "promotion_type"],
    "fact_b2b_orders": ["b2b_id", "customer_name", "customer_type", "order_date",
                        "sku_id", "quantity_kg", "unit_price", "amount"],
    "fact_purchases": ["purchase_id", "supplier_id", "purchase_date", "arrival_date",
                       "total_amount", "quality_grade", "status"],
    "fact_purchase_items": ["id", "purchase_id", "sku_id", "quantity_kg",
                            "unit_cost", "amount", "quality_grade", "rejected_kg"],
    "fact_warehouse_stock": ["id", "snapshot_date", "warehouse_id", "sku_id",
                             "stock_kg", "in_transit_kg", "avg_daily_outflow_kg",
                             "avg_days_in_stock"],
    "fact_deliveries": ["delivery_id", "biz_type", "ref_id", "from_warehouse",
                        "to_region", "ship_date", "arrive_date", "lead_time_days",
                        "box_cnt", "weight_kg", "loss_kg", "freight_cost",
                        "delivery_mode"],
    "fact_store_sales_daily": ["id", "store_id", "sale_date", "category",
                               "order_cnt", "customer_cnt", "foot_traffic",
                               "sales_amount", "discount_amount"],
}

BATCH = 1000


def conn(cfg, with_db=True):
    kw = dict(host=cfg["host"], port=cfg["port"], user=cfg["user"],
              password=cfg["password"], charset=cfg.get("charset", "utf8mb4"),
              autocommit=True)
    if with_db:
        kw["database"] = cfg.get("database", DB_NAME)
    return pymysql.connect(**kw)


def ensure_mysql_running():
    """检查 3306 端口是否监听；若未启动，尝试启动便携实例。"""
    MYSQL_BIN = r"D:\软件编写\基于机器学习的糖尿病风险预测与健康数据分析平台\mysql\bin\mysqld.exe"
    MYSQL_INI = r"D:\软件编写\基于机器学习的糖尿病风险预测与健康数据分析平台\mysql\my.ini"

    def listening():
        try:
            import socket
            with socket.create_connection(("127.0.0.1", 3306), timeout=2):
                return True
        except OSError:
            return False

    if listening():
        print("  MySQL 已在运行（端口 3306 监听中）")
        return True

    print(f"  MySQL 未运行，启动便携实例：{MYSQL_BIN}")
    try:
        subprocess.Popen([MYSQL_BIN, f"--defaults-file={MYSQL_INI}"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:
        print(f"  启动失败：{e}")
    for _ in range(30):
        time.sleep(1)
        if listening():
            print("  MySQL 启动成功")
            return True
    print("  ✗ MySQL 未启动，请手动启动后重试")
    return False


def run_sql_file(cur, path):
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    # 去掉注释行后按分号切分（本项目 SQL 无存储过程，切分安全）
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    clean = "\n".join(lines)
    stmts = [s.strip() for s in clean.split(";") if s.strip()]
    for s in stmts:
        cur.execute(s)
    return len(stmts)


def main():
    print("=" * 62)
    print("导入 MySQL：ganxiaopang_db（不影响实例中其他数据库）")
    print("=" * 62)

    print("[1/5] 检查 MySQL 服务 ...")
    if not ensure_mysql_running():
        sys.exit(2)

    print("[2/5] 建库建表 + 创建应用账号 ...")
    root = conn(ROOT_DB_CONFIG, with_db=False)
    rc = root.cursor()
    n = run_sql_file(rc, os.path.join(SQL_DIR, "00_create_database.sql"))
    print(f"  建表脚本执行完成（{n} 条语句）")
    rc.execute("SELECT DATABASE()")

    # 应用账号：仅授权 ganxiaopang_db（不授予全局权限，避免影响其他库）
    rc.execute(f"CREATE USER IF NOT EXISTS '{APP_USER}'@'localhost' IDENTIFIED BY '{APP_PWD}'")
    rc.execute(f"CREATE USER IF NOT EXISTS '{APP_USER}'@'127.0.0.1' IDENTIFIED BY '{APP_PWD}'")
    rc.execute(f"GRANT ALL PRIVILEGES ON `{DB_NAME}`.* TO '{APP_USER}'@'localhost'")
    rc.execute(f"GRANT ALL PRIVILEGES ON `{DB_NAME}`.* TO '{APP_USER}'@'127.0.0.1'")
    rc.execute("FLUSH PRIVILEGES")
    print(f"  应用账号 {APP_USER} 已创建并授权 {DB_NAME}.*（限本库）")
    rc.close(); root.close()

    print("[3/5] 导入数据 ...")
    c = conn(DB_CONFIG)
    cur = c.cursor()
    row_counts = {}
    for table, cols in TABLES.items():
        path = os.path.join(PROC_DIR, f"{table}.csv")
        if not os.path.exists(path):
            print(f"  ✗ 缺少 {table}.csv（请先运行 scripts/02_clean_data.py）")
            continue
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        missing = [x for x in cols if x not in df.columns]
        if missing:
            raise ValueError(f"{table} 缺少列: {missing}")
        df = df[cols]
        df = df.where(pd.notna(df), None)
        cur.execute(f"TRUNCATE TABLE `{table}`")
        placeholders = ",".join(["%s"] * len(cols))
        col_sql = ",".join(f"`{x}`" for x in cols)
        insert_sql = f"INSERT INTO `{table}` ({col_sql}) VALUES ({placeholders})"
        rows = [tuple(None if (v is None or v == "") else v for v in r)
                for r in df.itertuples(index=False, name=None)]
        for i in range(0, len(rows), BATCH):
            cur.executemany(insert_sql, rows[i:i + BATCH])
        row_counts[table] = len(rows)
        print(f"  {table:<28} {len(rows):>7,} 行")
    cur.close(); c.close()

    print("[4/5] 固化指标视图 ...")
    c = conn(DB_CONFIG)
    cur = c.cursor()
    n = run_sql_file(cur, os.path.join(SQL_DIR, "01_metric_views.sql"))
    cur.execute("SELECT COUNT(*) FROM information_schema.views "
                f"WHERE table_schema='{DB_NAME}'")
    n_views = cur.fetchone()[0]
    print(f"  视图脚本执行完成（{n} 条语句），当前视图数 {n_views}")

    print("[5/5] 校验 ...")
    for t in TABLES:
        cur.execute(f"SELECT COUNT(*) FROM `{t}`")
        print(f"  {t:<28} {cur.fetchone()[0]:>7,} 行")
    cur.execute("""SELECT ROUND(SUM(pay_amount),0) FROM fact_orders
                   WHERE order_status IN ('已付款','已发货','已完成')""")
    print(f"  电商 GMV(付款口径): {cur.fetchone()[0]:,.0f} 元")
    cur.close(); c.close()
    print("\n✔ 导入完成（模拟数据，仅用于方法复现，不代表真实经营结果）")


if __name__ == "__main__":
    main()
