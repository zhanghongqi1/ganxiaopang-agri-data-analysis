# -*- coding: utf-8 -*-
"""
02_clean_data.py — 数据清洗与标准化（data/raw → data/processed）
================================================================
原始层由 01_generate_data.py 注入约 2% 脏数据，本脚本按以下规则处理并全程留痕：

  fact_orders      去重 / 时间格式标准化 / 金额异常用明细重算 / 非法状态剔除 / 省份缺失填充
  fact_order_items 数量≤0 剔除 / 价格异常用 SKU 主数据回填 / 孤儿行清理
  dim_users        年龄越界→中位数填充 / 性别非法→未知 / 省份格式统一
  fact_deliveries  损耗超重→截断 / 时效为负→按日期差重算
  fact_store_sales 重复(店,日,品类)去重 / 负销售额剔除

输出：data/processed/*.csv + logs/cleaning_stats.json
"""
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(PROC_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

VALID_STATUS = {"已付款", "已发货", "已完成", "已取消", "已退款"}
PAID_STATUS = {"已付款", "已发货", "已完成"}          # 付款口径（GMV 统计口径）
PROVINCE_STD = {  # 常见格式 → 标准省份简称
    "甘肃省": "甘肃", " GANSU": "甘肃", "甘肃 ": "甘肃", "gansu": "甘肃",
    "陕西省": "陕西", "四川省": "四川", "广东省": "广东", "江苏省": "江苏",
    "浙江省": "浙江", "北京市": "北京", "上海市": "上海", "山东省": "山东",
    "河南省": "河南", "湖北省": "湖北", "福建省": "福建", "重庆市": "重庆",
    "新疆维吾尔自治区": "新疆", "青海省": "青海",
}


def load(name):
    return pd.read_csv(os.path.join(RAW_DIR, f"{name}.csv"),
                       dtype=str, keep_default_na=False)


def save(df, name):
    df.to_csv(os.path.join(PROC_DIR, f"{name}.csv"), index=False,
              encoding="utf-8-sig")


def main():
    stats = {"cleaned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    print("=" * 62)
    print("数据清洗与标准化  data/raw → data/processed")
    print("=" * 62)

    # ---------- 0. 维度表（无注入脏数据，做类型与轻校验） ----------
    print("[1/8] 维度表标准化 ...")
    sku = load("dim_sku")
    for col in ("cost_price", "retail_price", "gross_margin_rate"):
        sku[col] = pd.to_numeric(sku[col], errors="coerce")
    n_margin_fix = int((sku["gross_margin_rate"] >= 1).sum())
    sku.loc[sku["gross_margin_rate"] >= 1, "gross_margin_rate"] = 0.5   # 越界毛利修正
    sku["is_self_operated"] = pd.to_numeric(sku["is_self_operated"])
    stats["dim_sku_毛利越界修正"] = n_margin_fix

    users = load("dim_users")
    users["age"] = pd.to_numeric(users["age"], errors="coerce")
    n_age = int(((users["age"] < 16) | (users["age"] > 80)).sum())
    age_median = float(users.loc[(users["age"] >= 16) & (users["age"] <= 80),
                                 "age"].median())
    users.loc[(users["age"] < 16) | (users["age"] > 80), "age"] = int(age_median)
    n_gender = int((~users["gender"].isin(["男", "女"])).sum())
    users.loc[~users["gender"].isin(["男", "女"]), "gender"] = "未知"
    n_prov = int(users["province"].isin(PROVINCE_STD).sum())
    users["province"] = users["province"].replace(PROVINCE_STD)
    stats.update({"dim_users_年龄越界填充": n_age, "dim_users_性别非法填充": n_gender,
                  "dim_users_省份格式统一": n_prov})
    users["city_tier"] = pd.to_numeric(users["city_tier"])
    users["is_fan"] = pd.to_numeric(users["is_fan"])

    suppliers = load("dim_suppliers")
    stores = load("dim_stores")
    if "daily_base" in stores.columns:      # 生成参数列，不进入数据仓库
        stores = stores.drop(columns=["daily_base"])
    warehouses = load("dim_warehouses")
    sessions = load("fact_live_sessions")
    for col in ("duration_min", "total_exposure", "total_enter", "total_stay",
                "total_interact", "total_order_placed", "total_paid",
                "new_followers", "sku_cnt", "is_festival"):
        sessions[col] = pd.to_numeric(sessions[col])
    sessions["gmv"] = pd.to_numeric(sessions["gmv"])
    minutes = load("fact_live_minute_traffic")
    for col in ("id", "minute_index", "viewers_online", "exposure_delta",
                "enter_delta", "comment_cnt", "like_cnt", "follow_delta",
                "order_cnt", "pay_user_cnt"):
        minutes[col] = pd.to_numeric(minutes[col])
    minutes["session_id"] = pd.to_numeric(minutes["session_id"])
    b2b = load("fact_b2b_orders")
    for col in ("quantity_kg", "unit_price", "amount"):
        b2b[col] = pd.to_numeric(b2b[col])
    purchases = load("fact_purchases")
    purchases["total_amount"] = pd.to_numeric(purchases["total_amount"])
    purchase_items = load("fact_purchase_items")
    for col in ("quantity_kg", "unit_cost", "amount", "rejected_kg"):
        purchase_items[col] = pd.to_numeric(purchase_items[col])
    stock = load("fact_warehouse_stock")
    for col in ("stock_kg", "in_transit_kg", "avg_daily_outflow_kg",
                "avg_days_in_stock"):
        stock[col] = pd.to_numeric(stock[col])
    print(f"  维度表/事实表类型标准化完成（毛利越界 {n_margin_fix}，年龄越界 {n_age}，"
          f"性别非法 {n_gender}，省份格式 {n_prov}）")

    # ---------- 1. 订单明细：数量/价格异常 ----------
    print("[2/8] 清洗订单明细 ...")
    items = load("fact_order_items")
    items["quantity"] = pd.to_numeric(items["quantity"])
    items["unit_price"] = pd.to_numeric(items["unit_price"])
    items["cost_price"] = pd.to_numeric(items["cost_price"])
    n_qty = int((items["quantity"] <= 0).sum())
    items = items[items["quantity"] > 0].copy()
    # 价格异常（≤0.1）→ 用 SKU 主数据零售价/成本价回填
    sku_price = dict(zip(sku["sku_id"].astype(str), sku["retail_price"]))
    sku_cost = dict(zip(sku["sku_id"].astype(str), sku["cost_price"]))
    bad_price = items["unit_price"] <= 0.1
    n_price = int(bad_price.sum())
    items.loc[bad_price, "unit_price"] = items.loc[bad_price, "sku_id"].map(sku_price)
    items["unit_price"] = items["unit_price"].fillna(
        items["sku_id"].map(sku_price)).astype(float)
    bad_cost = items["cost_price"] <= 0.1
    n_cost = int(bad_cost.sum())
    items.loc[bad_cost, "cost_price"] = items.loc[bad_cost, "sku_id"].map(sku_cost)
    items["cost_price"] = items["cost_price"].fillna(
        items["sku_id"].map(sku_cost)).astype(float)
    stats.update({"items_数量非正剔除": n_qty, "items_价格异常回填": n_price,
                  "items_成本异常回填": n_cost})
    print(f"  数量非正剔除 {n_qty}，价格异常回填 {n_price}，成本异常回填 {n_cost}")

    # ---------- 2. 订单：去重/状态/时间/金额/省份 ----------
    print("[3/8] 清洗订单 ...")
    orders = load("fact_orders")
    n_before = len(orders)
    orders = orders.drop_duplicates(subset="order_id", keep="first").copy()
    n_dedup = n_before - len(orders)
    # 状态标准化：去首尾/内部空格 + 映射 + 非法剔除
    orders["order_status"] = (orders["order_status"].str.strip()
                              .str.replace(" ", "", regex=False)
                              .replace({"PAID": "已付款"}))
    n_status = int((~orders["order_status"].isin(VALID_STATUS)).sum())
    orders = orders[orders["order_status"].isin(VALID_STATUS)].copy()
    # 时间标准化（含 2024/3/5 等脏格式）
    n_bad_time = int((~orders["order_time"].str.match(
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")).sum())
    orders["order_time"] = pd.to_datetime(orders["order_time"],
                                          errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    orders = orders[orders["order_time"].notna()].copy()
    # 金额异常（≤0 或 >1000）→ 用明细重算
    orders["pay_amount"] = pd.to_numeric(orders["pay_amount"])
    orders["freight"] = pd.to_numeric(orders["freight"], errors="coerce").fillna(0)
    orders["discount_amount"] = pd.to_numeric(orders["discount_amount"],
                                              errors="coerce").fillna(0)
    item_amount = (items.assign(amount=lambda x: x["quantity"] * x["unit_price"])
                    .groupby("order_id")["amount"].sum())
    bad_amt = (orders["pay_amount"] <= 0) | (orders["pay_amount"] > 1000)
    n_amt = int(bad_amt.sum())
    orders.loc[bad_amt, "pay_amount"] = (
        orders.loc[bad_amt, "order_id"].map(item_amount)
        + orders.loc[bad_amt, "freight"]).round(2)
    # 重算后仍异常 → 剔除
    n_amt_drop = int(((orders["pay_amount"] <= 0) |
                      (orders["pay_amount"] > 1000)).sum())
    orders = orders[(orders["pay_amount"] > 0) & (orders["pay_amount"] <= 1000)].copy()
    # 省份缺失填充
    n_prov_o = int((orders["province"] == "").sum())
    orders["province"] = orders["province"].replace("", "未知")
    orders["province"] = orders["province"].replace(PROVINCE_STD)
    # session_id 规范化为可空整数
    orders["session_id"] = (pd.to_numeric(orders["session_id"], errors="coerce")
                            .astype("Int64"))
    orders["user_id"] = pd.to_numeric(orders["user_id"])
    orders["item_cnt"] = pd.to_numeric(orders["item_cnt"])
    stats.update({"orders_重复剔除": n_dedup, "orders_非法状态剔除": n_status,
                  "orders_时间格式修复": n_bad_time,
                  "orders_金额异常重算": n_amt, "orders_重算后仍异常剔除": n_amt_drop,
                  "orders_省份缺失填充": n_prov_o})
    print(f"  去重 {n_dedup}，非法状态剔除 {n_status}，时间修复 {n_bad_time}，"
          f"金额重算 {n_amt}（仍异常剔除 {n_amt_drop}），省份填充 {n_prov_o}")

    # ---------- 3. 孤儿清理（订单 ↔ 明细） ----------
    print("[4/8] 孤儿行清理 ...")
    valid_order_ids = set(orders["order_id"])
    n_orphan_i = int((~items["order_id"].isin(valid_order_ids)).sum())
    items = items[items["order_id"].isin(valid_order_ids)].copy()
    # 剔除后无明细的订单（极少数：全部明细被数量清洗剔除）
    has_items = set(items["order_id"])
    n_orphan_o = int((~orders["order_id"].isin(has_items)).sum())
    orders = orders[orders["order_id"].isin(has_items)].copy()
    items["sku_id"] = pd.to_numeric(items["sku_id"])
    items["order_id"] = items["order_id"].astype(str)
    stats.update({"items_孤儿行剔除": n_orphan_i, "orders_无明细剔除": n_orphan_o})
    print(f"  明细孤儿行 {n_orphan_i}，无明细订单 {n_orphan_o}")

    # ---------- 4. 配送 ----------
    print("[5/8] 清洗配送 ...")
    deliveries = load("fact_deliveries")
    for col in ("lead_time_days", "box_cnt"):
        deliveries[col] = pd.to_numeric(deliveries[col])
    for col in ("weight_kg", "loss_kg", "freight_cost"):
        deliveries[col] = pd.to_numeric(deliveries[col])
    n_loss = int((deliveries["loss_kg"] > deliveries["weight_kg"]).sum())
    deliveries.loc[deliveries["loss_kg"] > deliveries["weight_kg"],
                   "loss_kg"] = (deliveries.loc[deliveries["loss_kg"] >
                                                 deliveries["weight_kg"], "weight_kg"]
                                 * 0.05).round(2)          # 截断为 5% 上限
    ship = pd.to_datetime(deliveries["ship_date"], errors="coerce")
    arrive = pd.to_datetime(deliveries["arrive_date"], errors="coerce")
    n_neg = int((deliveries["lead_time_days"] < 0).sum())
    deliveries["lead_time_days"] = ((arrive - ship).dt.days)
    deliveries.loc[deliveries["lead_time_days"] < 0, "lead_time_days"] = 1
    stats.update({"deliveries_损耗超重截断": n_loss, "deliveries_时效重算": n_neg})
    print(f"  损耗超重截断 {n_loss}，时效重算 {n_neg}")

    # ---------- 5. 门店日销售 ----------
    print("[6/8] 清洗门店日销售 ...")
    store_sales = load("fact_store_sales_daily")
    for col in ("store_id", "order_cnt", "customer_cnt", "foot_traffic"):
        store_sales[col] = pd.to_numeric(store_sales[col])
    for col in ("sales_amount", "discount_amount"):
        store_sales[col] = pd.to_numeric(store_sales[col])
    n_before = len(store_sales)
    store_sales = store_sales.drop_duplicates(subset=["store_id", "sale_date",
                                                      "category"], keep="first")
    n_ss_dedup = n_before - len(store_sales)
    n_ss_neg = int((store_sales["sales_amount"] <= 0).sum())
    store_sales = store_sales[store_sales["sales_amount"] > 0].copy()
    stats.update({"store_sales_重复剔除": n_ss_dedup,
                  "store_sales_非正销售额剔除": n_ss_neg})
    print(f"  重复剔除 {n_ss_dedup}，非正销售额剔除 {n_ss_neg}")

    # ---------- 6. 落盘 ----------
    print("[7/8] 写出 processed ...")
    tables = {
        "dim_sku": sku, "dim_users": users, "dim_suppliers": suppliers,
        "dim_stores": stores, "dim_warehouses": warehouses,
        "fact_live_sessions": sessions, "fact_live_minute_traffic": minutes,
        "fact_orders": orders, "fact_order_items": items,
        "fact_b2b_orders": b2b, "fact_purchases": purchases,
        "fact_purchase_items": purchase_items,
        "fact_warehouse_stock": stock, "fact_deliveries": deliveries,
        "fact_store_sales_daily": store_sales,
    }
    for name, df in tables.items():
        save(df, name)
        print(f"  {name}.csv  {len(df):>7,} 行")

    # ---------- 7. 汇总校验 ----------
    print("[8/8] 清洗后核心指标 ...")
    paid = orders[orders["order_status"].isin(PAID_STATUS)]
    ecom_gmv = float(paid["pay_amount"].sum())
    sku_l1 = dict(zip(sku["sku_id"].astype(str), sku["category_l1"]))
    ecom_cat = (items[items["order_id"].isin(set(paid["order_id"]))]
                .assign(amount=lambda x: x["quantity"] * x["unit_price"],
                        l1=lambda x: x["sku_id"].astype(str).map(sku_l1))
                .groupby("l1")["amount"].sum())
    print(f"  有效订单(付款口径) {len(paid):,} 单，电商 GMV {ecom_gmv:,.0f} 元")
    print(f"  电商 Top3 品类: " + " / ".join(
        f"{k}({v / ecom_cat.sum():.1%})"
        for k, v in ecom_cat.sort_values(ascending=False).head(3).items()))
    stats["after_cleaning"] = {
        "fact_orders": len(orders), "fact_order_items": len(items),
        "fact_store_sales_daily": len(store_sales),
        "paid_orders": len(paid), "ecom_gmv": round(ecom_gmv, 2),
    }
    with open(os.path.join(LOG_DIR, "cleaning_stats.json"), "w",
              encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    total_dirty = sum(v for k, v in stats.items()
                      if isinstance(v, int) and k != "cleaned_at")
    print(f"\n清洗留痕已写入 logs/cleaning_stats.json（共处理 {total_dirty} 处问题）")
    print("✔ 清洗完成（模拟数据，仅用于方法复现，不代表真实经营结果）")


if __name__ == "__main__":
    main()
