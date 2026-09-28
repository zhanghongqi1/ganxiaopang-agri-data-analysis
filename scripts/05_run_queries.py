# -*- coding: utf-8 -*-
"""
05_run_queries.py — 执行 5 个分析 SQL 并导出结果，同时用 Pandas 独立复算校验一致性
================================================================
输出：
  data/processed/analysis_a_category_roi.csv
  data/processed/analysis_b_user_rfm.csv
  data/processed/analysis_c_live_funnel.csv
  data/processed/analysis_d_supply_chain.csv
  data/processed/analysis_e_store_pnl.csv
  logs/analysis_results.json（核心结论数字，供报告/看板引用）
最后做 SQL ↔ Pandas 复算的一致性校验并打印结论。
"""
import json
import os
import sys
import decimal
from datetime import datetime

import numpy as np
import pandas as pd
import pymysql

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "config"))
SQL_DIR = os.path.join(BASE_DIR, "sql")
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
LOG_DIR = os.path.join(BASE_DIR, "logs")
from db_config import DB_CONFIG           # noqa: E402

# 门店品类综合毛利率参数（与 docs/指标口径.md、sql/e_store_pnl.sql 保持一致）
STORE_MARGIN = {"宽粉麻辣烫": 0.60, "特色小吃": 0.45, "饮品": 0.55, "伴手礼盒": 0.42}


def to_num(df):
    """把结果集里所有 decimal.Decimal 列转为 float，避免后续运算类型报错。"""
    for c in df.columns:
        if df[c].map(lambda x: isinstance(x, decimal.Decimal)).any():
            df[c] = pd.to_numeric(df[c].astype(str), errors="coerce")
    return df


def run_sql_file(cur, fname, keep="largest"):
    """执行 SQL 文件中的所有语句，返回指定结果集。

    keep:
      "largest"      → 行数最多的结果集（主明细）
      "last"         → 最后一个结果集
      "first"        → 第一个结果集
      "store_detail" → 含『月净利』列的结果集（e_store_pnl 单店测算明细）
    """
    with open(os.path.join(SQL_DIR, fname), "r", encoding="utf-8") as f:
        raw = f.read()
    lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
    stmts = [s.strip() for s in "\n".join(lines).split(";") if s.strip()]
    dfs = []
    for s in stmts:
        cur.execute(s)
        if cur.description:                      # 是 SELECT
            cols = [d[0] for d in cur.description]
            d = pd.DataFrame(cur.fetchall(), columns=cols)
            if len(d.columns) == 1 and str(d.columns[0]) in ("1",):
                continue                         # 忽略 SELECT 1 之类的健康检查
            d = d.dropna(how="all")
            if len(d):
                dfs.append(to_num(d))
    if not dfs:
        return None
    if keep == "store_detail":
        cand = [d for d in dfs if "月净利" in d.columns]
        return cand[0] if cand else dfs[-1]
    if keep == "largest":
        return max(dfs, key=len)
    if keep == "last":
        return dfs[-1]
    return dfs[0]


def main():
    print("=" * 62)
    print("执行分析 SQL + Pandas 复算校验")
    print("=" * 62)
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    results = {}

    # ---------- A 品类 ROI ----------
    print("[1/5] 品类 ROI 拆解 ...")
    df_a = run_sql_file(cur, "a_category_roi.sql", keep="largest")
    df_a = df_a[df_a["品类"].notna()].copy()
    df_a.to_csv(os.path.join(PROC_DIR, "analysis_a_category_roi.csv"),
                index=False, encoding="utf-8-sig")
    total_gmv = float(df_a["品类GMV"].sum())
    df_a["GMV占比_pct"] = (df_a["品类GMV"] / total_gmv * 100).round(2)
    top3 = df_a.nlargest(3, "品类GMV")
    print(f"  品类数 {len(df_a)}，全渠道 GMV {total_gmv:,.0f} 元")
    print("  Top3: " + " / ".join(
        f"{row['品类']}({row['GMV占比_pct']:.1f}%)" for _, row in top3.iterrows()))
    print(f"  Top3 合计占比 {top3['GMV占比_pct'].sum():.2f}%")

    # ---------- B 用户 RFM ----------
    print("[2/5] 用户 RFM 分层 ...")
    df_b = run_sql_file(cur, "b_user_rfm.sql", keep="largest")  # 用户级 RFM 明细
    df_b.to_csv(os.path.join(PROC_DIR, "analysis_b_user_rfm_detail.csv"),
                index=False, encoding="utf-8-sig")
    # 单独取分层汇总与复购率
    cur.execute("SELECT * FROM v_user_segment_summary")
    cols = [d[0] for d in cur.description]
    seg = pd.DataFrame(cur.fetchall(), columns=cols)
    cur.execute("SELECT * FROM v_repurchase")
    cols = [d[0] for d in cur.description]
    rep = pd.DataFrame(cur.fetchall(), columns=cols)
    seg.to_csv(os.path.join(PROC_DIR, "analysis_b_user_rfm.csv"),
               index=False, encoding="utf-8-sig")
    print(f"  分层数 {len(seg)}；复购率 {float(rep['复购率_pct'][0]):.2f}%")

    # ---------- C 直播漏斗 ----------
    print("[3/5] 直播漏斗与时段 ...")
    run_sql_file(cur, "c_live_funnel.sql", keep="last")   # 执行验证，不取数
    cur.execute("""SELECT '曝光' AS 环节, SUM(total_exposure) AS 人次 FROM fact_live_sessions
        UNION ALL SELECT '进入', SUM(total_enter) FROM fact_live_sessions
        UNION ALL SELECT '停留', SUM(total_stay) FROM fact_live_sessions
        UNION ALL SELECT '互动', SUM(total_interact) FROM fact_live_sessions
        UNION ALL SELECT '下单', SUM(total_order_placed) FROM fact_live_sessions
        UNION ALL SELECT '付款', SUM(total_paid) FROM fact_live_sessions""")
    funnel = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])
    cur.execute("SELECT * FROM v_live_traffic_slot")
    slot = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])
    funnel.to_csv(os.path.join(PROC_DIR, "analysis_c_live_funnel.csv"),
                  index=False, encoding="utf-8-sig")
    slot.to_csv(os.path.join(PROC_DIR, "analysis_c_live_slot.csv"),
                index=False, encoding="utf-8-sig")
    print("  漏斗: " + " → ".join(
        f"{row['环节']}{int(row['人次']):,}" for _, row in funnel.iterrows()))

    # ---------- D 供应链 ----------
    print("[4/5] 供应链周转与损耗 ...")
    run_sql_file(cur, "d_supply_chain.sql", keep="last")   # 执行验证，不取数
    cur.execute("SELECT * FROM v_delivery_mode_compare")
    mode = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])
    cur.execute("SELECT * FROM v_supply_chain_loss")
    loss = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])
    cur.execute("SELECT * FROM v_purchase_cycle ORDER BY 平均到货周期_天 DESC")
    pcycle = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])
    cur.execute("SELECT * FROM v_stock_turnover")
    turnover = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])
    mode.to_csv(os.path.join(PROC_DIR, "analysis_d_delivery_mode.csv"),
                index=False, encoding="utf-8-sig")
    loss.to_csv(os.path.join(PROC_DIR, "analysis_d_loss.csv"),
                index=False, encoding="utf-8-sig")
    pcycle.to_csv(os.path.join(PROC_DIR, "analysis_d_purchase_cycle.csv"),
                  index=False, encoding="utf-8-sig")
    turnover.to_csv(os.path.join(PROC_DIR, "analysis_d_stock_turnover.csv"),
                    index=False, encoding="utf-8-sig")
    print("  配送模式对比：")
    for _, row in mode[mode["业务类型"] == "电商订单"].iterrows():
        print(f"    {row['配送模式']}: 时效 {row['平均履约时效_天']} 天, "
              f"损耗 {row['配送损耗率_pct']}%, 运费 {row['单位运费_元每kg']} 元/kg")

    # ---------- E 门店测算 ----------
    print("[5/5] 门店盈利测算 ...")
    df_e = run_sql_file(cur, "e_store_pnl.sql", keep="store_detail")
    df_e.to_csv(os.path.join(PROC_DIR, "analysis_e_store_pnl.csv"),
                index=False, encoding="utf-8-sig")
    # 汇总结论由明细表复算
    n_store = len(df_e)
    n_profit = int((df_e["月净利"] > 0).sum())
    n_marginal = int(df_e["月净利"].between(-1000, 0).sum())
    n_loss = int((df_e["月净利"] < -1000).sum())
    avg_net = float(df_e["月净利"].mean())
    sum_net = float(df_e["月净利"].sum())
    be_sum = float(df_e["盈亏平衡月销售额"].sum())
    cur_sum = float(df_e["月均销售额"].sum())
    gap_sum = float(df_e["月销售缺口"].sum())
    scen30 = float(df_e["情景净利_客流加30pct"].sum())
    scen60 = float(df_e["情景净利_客流加60pct"].sum())
    scen100 = float(df_e["情景净利_客流翻倍"].sum())
    df_sum = pd.DataFrame([{
        "门店总数": n_store, "盈利门店数": n_profit, "临界门店数": n_marginal,
        "亏损门店数": n_loss, "平均月净利": round(avg_net, 2),
        "合计月净利": round(sum_net, 2),
        "盈亏平衡月销售合计": round(be_sum, 2), "现状月销售合计": round(cur_sum, 2),
        "月销售缺口合计": round(gap_sum, 2),
        "情景合计净利_客流加30pct": round(scen30, 2),
        "情景合计净利_客流加60pct": round(scen60, 2),
        "情景合计净利_客流翻倍": round(scen100, 2)}])
    df_sum.to_csv(os.path.join(PROC_DIR, "analysis_e_store_summary.csv"),
                  index=False, encoding="utf-8-sig")
    cur.execute("SELECT * FROM v_store_monthly WHERE 月份 >= '2025-01'")
    sm = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])
    sm.to_csv(os.path.join(PROC_DIR, "analysis_e_store_monthly.csv"),
              index=False, encoding="utf-8-sig")
    print(f"  门店 {n_store} 家：盈利 {n_profit}，临界 {n_marginal}，亏损 {n_loss}；"
          f"合计月净利 {sum_net:,.0f} 元")
    print(f"  盈亏平衡月销售合计 {be_sum:,.0f} 元 vs 现状 {cur_sum:,.0f} 元，"
          f"缺口 {gap_sum:,.0f} 元")
    print(f"  情景（客流提升）：+30% → {scen30:,.0f} 元/月；"
          f"+60% → {scen60:,.0f} 元/月；翻倍 → {scen100:,.0f} 元/月")

    # ================= Pandas 独立复算校验 =================
    print("\n" + "=" * 62)
    print("Pandas 复算校验（SQL ↔ Pandas 一致性）")
    print("=" * 62)
    checks = []

    # 1) 电商 GMV
    o = pd.read_csv(os.path.join(PROC_DIR, "fact_orders.csv"), dtype=str)
    paid = o["order_status"].isin(["已付款", "已发货", "已完成"])
    pd_ecom_gmv = pd.to_numeric(o.loc[paid, "pay_amount"]).sum()
    cur.execute("""SELECT SUM(pay_amount) FROM fact_orders
                   WHERE order_status IN ('已付款','已发货','已完成')""")
    sql_ecom_gmv = float(cur.fetchone()[0])
    checks.append(("电商GMV", sql_ecom_gmv, pd_ecom_gmv))

    # 2) 复购率
    o2 = o[paid].copy()
    cnt = o2.groupby("user_id")["order_id"].count()
    pd_rep = (cnt >= 2).sum() / len(cnt) * 100
    sql_rep = float(rep["复购率_pct"][0])
    checks.append(("复购率%", sql_rep, pd_rep))

    # 3) 全渠道 GMV（含 B2B + 门店）
    b2b = pd.read_csv(os.path.join(PROC_DIR, "fact_b2b_orders.csv"))
    ss = pd.read_csv(os.path.join(PROC_DIR, "fact_store_sales_daily.csv"))
    pd_total = pd_ecom_gmv + b2b["amount"].sum() + ss["sales_amount"].sum()
    checks.append(("全渠道GMV", total_gmv, pd_total))

    # 4) 门店 2025 月均销售额 & 净利（复算单店模型）
    ss["sale_date"] = pd.to_datetime(ss["sale_date"])
    ss25 = ss[ss["sale_date"] >= "2025-01-01"].copy()
    ss25["margin"] = ss25["category"].map(STORE_MARGIN)
    ss25["毛利"] = ss25["sales_amount"] * ss25["margin"]
    st = pd.read_csv(os.path.join(PROC_DIR, "dim_stores.csv"))
    g = ss25.groupby("store_id").agg(销售额=("sales_amount", "sum"),
                                     订单数=("order_cnt", "sum"),
                                     毛利=("毛利", "sum"))
    n_month = ss25["sale_date"].dt.to_period("M").nunique()
    g["月均销售额"] = g["销售额"] / n_month
    g["月均毛利"] = g["毛利"] / n_month
    g = g.join(st.set_index("store_id")[
        ["rent_monthly", "staff_cnt", "staff_cost_monthly", "util_monthly",
         "amort_months", "initial_investment"]])
    g["月净利"] = g["月均毛利"] - (
        g["rent_monthly"] + g["staff_cnt"] * g["staff_cost_monthly"]
        + g["util_monthly"] + g["initial_investment"] / g["amort_months"])
    pd_store_net = g["月净利"].sum()
    # 从 SQL 汇总结果取数
    sql_store_net = sum_net
    checks.append(("门店合计月净利", sql_store_net, float(pd_store_net)))
    print(f"  （门店月数 n={n_month}，2025 年）")

    print(f"\n{'指标':<18}{'SQL':>16}{'Pandas':>16}{'差异':>10}  结果")
    all_ok = True
    for name, sv, pv in checks:
        diff = abs(sv - pv)
        # 一致性校验关注「口径是否一致」，容差取相对 1e-4（±0.01%）+
        # 绝对 0.5 元兜底：SQL 侧对中间值 ROUND(...,2) 会引入微小舍入差，
        # 这是精度差异而非口径差异，不应判为不一致。
        tol = max(abs(sv) * 1e-4, abs(pv) * 1e-4, 0.5)
        ok = diff <= tol
        all_ok &= ok
        print(f"{name:<18}{sv:>16,.2f}{pv:>16,.2f}{diff:>10.4f}  {'✔' if ok else '✗'}")
    cur.close(); conn.close()

    # ---------- 汇总核心结论 ----------
    rec = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cross_check_passed": bool(all_ok),
        "category": {
            "total_gmv": round(total_gmv, 2),
            "n_categories": int(len(df_a)),
            "top3": [{"品类": row["品类"], "GMV": float(row["品类GMV"]),
                      "占比_pct": float(row["GMV占比_pct"])}
                     for _, row in top3.iterrows()],
            "top3_share_pct": float(top3["GMV占比_pct"].sum()),
            "best_roi": [{"品类": row["品类"], "ROI": float(row["品类ROI"])}
                         for _, row in df_a.nlargest(3, "品类ROI").iterrows()
                         if pd.notna(row["品类ROI"])],
            "table": df_a[["品类", "品类GMV", "GMV占比_pct", "品类毛利",
                           "综合毛利率_pct", "内容投入成本", "品类ROI"]]
                     .round(2).to_dict("records"),
        },
        "user": {
            "segments": seg.to_dict("records"),
            "repurchase_rate_pct": float(rep["复购率_pct"][0]),
            "buyers": int(rep["购买用户数"][0]),
            "avg_freq": float(rep["人均购买频次"][0]),
        },
        "funnel": {
            "steps": funnel.to_dict("records"),
            "slots": slot.to_dict("records"),
        },
        "supply_chain": {
            "mode_compare": mode.to_dict("records"),
            "loss": loss.to_dict("records"),
        },
        "store": {
            "detail": df_e.round(2).to_dict("records"),
            "summary": df_sum.to_dict("records"),
            "monthly": sm.round(2).to_dict("records"),
        },    }
    with open(os.path.join(LOG_DIR, "analysis_results.json"), "w",
              encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n核心结论已写入 logs/analysis_results.json")
    print("✔ 分析执行完成（模拟数据，仅用于方法复现，不代表真实经营结果）")


if __name__ == "__main__":
    main()
