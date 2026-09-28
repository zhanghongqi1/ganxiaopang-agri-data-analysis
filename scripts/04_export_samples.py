# -*- coding: utf-8 -*-
"""
04_export_samples.py — 导出每表 ≤1000 行样例到 data/sample/（入 GitHub 仓库）
完整模拟数据（data/raw，约 12 万条）不入库，由 01_generate_data.py 一条命令重新生成。
样例策略：维度表全量导出（均 ≤1000 行）；事实表取前 1000 行（生成顺序已含随机性）。
"""
import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
SAMPLE_DIR = os.path.join(BASE_DIR, "data", "sample")
os.makedirs(SAMPLE_DIR, exist_ok=True)

TABLES = [
    "dim_sku", "dim_users", "dim_suppliers", "dim_stores", "dim_warehouses",
    "fact_live_sessions", "fact_live_minute_traffic",
    "fact_orders", "fact_order_items", "fact_b2b_orders",
    "fact_purchases", "fact_purchase_items",
    "fact_warehouse_stock", "fact_deliveries", "fact_store_sales_daily",
]
MAX_ROWS = 1000


def main():
    print("导出样例数据（每表 ≤ %d 行）→ data/sample/" % MAX_ROWS)
    for name in TABLES:
        src = os.path.join(RAW_DIR, f"{name}.csv")
        if not os.path.exists(src):
            print(f"  ✗ 缺少 {name}.csv（请先运行 scripts/01_generate_data.py）")
            continue
        df = pd.read_csv(src, dtype=str, keep_default_na=False)
        sample = df.head(MAX_ROWS)
        dst = os.path.join(SAMPLE_DIR, f"{name}.csv")
        sample.to_csv(dst, index=False, encoding="utf-8-sig")
        print(f"  {name}.csv  {len(sample):>5} / {len(df):>6,} 行"
              + ("  (全量)" if len(df) <= MAX_ROWS else "  (截样)"))
    print("✔ 样例导出完成（模拟数据，仅用于方法复现，不代表真实经营结果）")


if __name__ == "__main__":
    main()
