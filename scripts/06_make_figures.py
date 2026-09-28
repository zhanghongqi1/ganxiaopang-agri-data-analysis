# -*- coding: utf-8 -*-
"""
06_make_figures.py — 生成可视化图表（matplotlib/seaborn，中文 SimHei）
================================================================
输入：logs/analysis_results.json + data/processed/analysis_*.csv
输出：reports/figures/*.png（约 10 张）
说明：全部为模拟数据，仅用于分析方法复现，不代表真实经营结果。
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
LOG_DIR = os.path.join(BASE_DIR, "logs")
FIG_DIR = os.path.join(BASE_DIR, "reports", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ---------- 中文字体（显式注册字体文件，避免 matplotlib 字体缓存找不到 SimHei）----------
import matplotlib.font_manager as fm


def _setup_chinese_font():
    candidates = [
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                fm.fontManager.addfont(path)
                name = fm.FontProperties(fname=path).get_name()
                plt.rcParams["font.sans-serif"] = [name, "SimHei",
                                                   "Microsoft YaHei", "SimSun"]
                plt.rcParams["axes.unicode_minus"] = False
                _setup_chinese_font.path = path      # 供 FontProperties(fname=) 使用
                return name
            except Exception:      # noqa: BLE001
                continue
    _setup_chinese_font.path = None
    return None


CN_FONT = _setup_chinese_font()
CN_FONT_PATH = _setup_chinese_font.path
sns.set_style("whitegrid")
sns.set_context("notebook", font_scale=1.05)
# 注意：seaborn 的 set_style/set_context 会重写 font.sans-serif，
# 必须在它们之后再应用中文字体，否则中文会回退成方框。
if CN_FONT_PATH:
    _fp = fm.FontProperties(fname=CN_FONT_PATH)
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [_fp.get_name(), "SimHei",
                                       "Microsoft YaHei", "SimSun"]
plt.rcParams["axes.unicode_minus"] = False
# 涨红跌绿（中国股市惯例；此处用于正负值语义）
C_UP, C_DOWN = "#c0392b", "#27ae60"
PALETTE = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#3B1F2B",
           "#6A994E", "#BC4749", "#5C6784", "#8ECAE6", "#FB8500", "#219EBC"]


def load_json():
    with open(os.path.join(LOG_DIR, "analysis_results.json"), encoding="utf-8") as f:
        return json.load(f)


def to_df(records, numeric_cols=None):
    """把 JSON 记录转成 DataFrame 并把数值列强制转 float（JSON 中数字被写成字符串）。"""
    df = pd.DataFrame(records)
    for c in df.columns:
        if numeric_cols and c in numeric_cols:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        elif not numeric_cols:
            # 自动尝试：整列都能转成数字才转
            conv = pd.to_numeric(df[c], errors="coerce")
            if conv.notna().all() and df[c].notna().any():
                df[c] = conv
    return df


def fig1_category_gmv(rec):
    """图1：品类 GMV 帕累托图（柱 + 累计占比折线）"""
    df = to_df(rec["category"]["table"]).sort_values("品类GMV", ascending=False)
    df = df.reset_index(drop=True)
    df["累计占比"] = df["GMV占比_pct"].cumsum()

    fig, ax1 = plt.subplots(figsize=(11, 5.6))
    bars = ax1.bar(df["品类"], df["品类GMV"] / 10000, color=PALETTE[:len(df)])
    ax1.set_ylabel("品类 GMV（万元）", fontsize=12)
    ax1.set_xlabel("")
    plt.setp(ax1.get_xticklabels(), rotation=30, ha="right")
    for b, v in zip(bars, df["品类GMV"] / 10000):
        ax1.text(b.get_x() + b.get_width() / 2, v + 0.6, f"{v:.1f}",
                 ha="center", va="bottom", fontsize=9)

    ax2 = ax1.twinx()
    ax2.plot(df["品类"], df["累计占比"], color=C_UP, marker="o", lw=2,
             label="累计 GMV 占比")
    ax2.axhline(65, color="gray", ls="--", lw=1)
    ax2.text(len(df) - 1, 66.5, "Top3 目标线 65%", ha="right", color="gray", fontsize=9)
    ax2.set_ylabel("累计 GMV 占比（%）", fontsize=12)
    ax2.set_ylim(0, 105)
    for i, v in enumerate(df["累计占比"]):
        if i < 3:
            ax2.annotate(f"{v:.1f}%", (i, v), textcoords="offset points",
                         xytext=(0, 8), ha="center", color=C_UP, fontsize=9)
    ax1.set_title("图1  品类 GMV 帕累托分析（Top3 合计 %.1f%%）"
                  % rec["category"]["top3_share_pct"], fontsize=13, pad=12)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig1_品类GMV帕累托.png"), dpi=140)
    plt.close(fig)


def fig2_category_roi(rec):
    """图2：品类 ROI vs 综合毛利率 散点（气泡=GMV）"""
    df = to_df(rec["category"]["table"])
    df = df[df["品类ROI"].notna()].copy()
    fig, ax = plt.subplots(figsize=(10, 6))
    size = df["品类GMV"] / df["品类GMV"].max() * 1600 + 80
    sc = ax.scatter(df["综合毛利率_pct"], df["品类ROI"], s=size,
                    c=df["GMV占比_pct"], cmap="YlOrRd", alpha=0.82,
                    edgecolor="k", linewidth=0.6)
    for _, r in df.iterrows():
        ax.annotate(r["品类"], (r["综合毛利率_pct"], r["品类ROI"]),
                    textcoords="offset points", xytext=(0, 12),
                    ha="center", fontsize=9)
    ax.axhline(1.0, color="gray", ls="--", lw=1)
    ax.text(df["综合毛利率_pct"].min(), 1.05, "ROI=1 盈亏分界",
            color="gray", fontsize=9)
    ax.set_xlabel("综合毛利率（%）", fontsize=12)
    ax.set_ylabel("品类 ROI（毛利 ÷ 内容+采购占用投入）", fontsize=12)
    ax.set_title("图2  品类 ROI × 毛利率矩阵（气泡=品类 GMV 规模）", fontsize=13, pad=12)
    cb = fig.colorbar(sc, ax=ax)
    cb.set_label("GMV 占比（%）", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig2_品类ROI矩阵.png"), dpi=140)
    plt.close(fig)


def fig3_rfm(rec):
    """图3：RFM 八分层 — 用户占比 vs 金额贡献占比"""
    df = to_df(rec["user"]["segments"])
    df = df.sort_values("贡献占比_pct", ascending=True)
    y = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(y - 0.19, df["人群占比_pct"], height=0.38,
            color="#2E86AB", label="用户占比")
    ax.barh(y + 0.19, df["贡献占比_pct"], height=0.38,
            color=C_UP, label="金额贡献占比")
    ax.set_yticks(y)
    ax.set_yticklabels(df["人群分层"])
    for i, (a, b) in enumerate(zip(df["人群占比_pct"], df["贡献占比_pct"])):
        ax.text(a + 0.3, i - 0.19, f"{a:.1f}%", va="center", fontsize=9)
        ax.text(b + 0.3, i + 0.19, f"{b:.1f}%", va="center", fontsize=9, color=C_UP)
    ax.set_xlabel("占比（%）", fontsize=12)
    ax.set_title("图3  RFM 用户分层：人数占比 vs 金额贡献占比", fontsize=13, pad=12)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig3_RFM用户分层.png"), dpi=140)
    plt.close(fig)


def fig4_funnel(rec):
    """图4：直播六段转化漏斗（横向漏斗 + 环节转化率）"""
    df = to_df(rec["funnel"]["steps"])
    order = ["曝光", "进入", "停留", "互动", "下单", "付款"]
    df["环节"] = pd.Categorical(df["环节"], order, ordered=True)
    df = df.sort_values("环节").reset_index(drop=True)
    vals = df["人次"].astype(float).values
    fig, ax = plt.subplots(figsize=(11, 5.8))
    ymax = vals.max()
    colors = sns.color_palette("Blues_d", len(df))
    for i, (name, v) in enumerate(zip(df["环节"], vals)):
        left = (ymax - v) / 2
        ax.barh(len(df) - 1 - i, v, left=left, color=colors[i],
                height=0.72, edgecolor="white")
        label = f"{name}  {int(v):,}"
        if v > ymax * 0.18:
            # 条形足够宽：标签放内部
            ax.text(ymax / 2, len(df) - 1 - i, label,
                    ha="center", va="center",
                    color="white" if i >= 2 else "#1a1a1a",
                    fontsize=11, fontweight="bold")
        else:
            # 条形太窄：标签放条形右侧，保证可读性
            ax.text(left + v + ymax * 0.01, len(df) - 1 - i, label,
                    ha="left", va="center", color="#1a1a1a", fontsize=10.5)
        if i > 0:
            rate = v / vals[i - 1] * 100
            ax.text(ymax * 1.01, len(df) - 1 - i + 0.4,
                    f"↓{rate:.1f}%", ha="left", va="center",
                    color=C_UP, fontsize=9)
    ax.set_xlim(0, ymax * 1.12)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.spines[["top", "right", "bottom", "left"]].set_visible(False)
    ax.set_title("图4  直播间六段转化漏斗（曝光→进入→停留→互动→下单→付款）",
                 fontsize=13, pad=12)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig4_直播漏斗.png"), dpi=140)
    plt.close(fig)


def fig5_slot(rec):
    """图5：直播时段 × 场次类型 场均 GMV 与 UV 价值"""
    df = to_df(rec["funnel"]["slots"], numeric_cols=["场次数", "累计GMV", "UV价值"])
    for c in ("场次数", "累计GMV", "UV价值"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["场均GMV"] = df["累计GMV"] / df["场次数"]
    df = df.sort_values("场均GMV", ascending=False).reset_index(drop=True)
    key = "时段"
    fig, ax1 = plt.subplots(figsize=(10, 5.6))
    bars = ax1.bar(df[key].astype(str), df["场均GMV"],
                   color=PALETTE[:len(df)], width=0.6)
    ax1.set_ylabel("场均 GMV（元）", fontsize=12)
    plt.setp(ax1.get_xticklabels(), rotation=15, ha="right")
    for b, v in zip(bars, df["场均GMV"]):
        ax1.text(b.get_x() + b.get_width() / 2, v + 30, f"{v:,.0f}",
                 ha="center", va="bottom", fontsize=9)
    ax2 = ax1.twinx()
    if "UV价值" in df.columns:
        ax2.plot(df[key].astype(str), df["UV价值"], color=C_UP,
                 marker="o", lw=2, label="UV 价值")
        ax2.set_ylabel("UV 价值（元/人）", fontsize=12)
    ax1.set_title("图5  直播时段排期效果：场均 GMV 与 UV 价值", fontsize=13, pad=12)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig5_直播时段效果.png"), dpi=140)
    plt.close(fig)


def fig6_delivery(rec):
    """图6：新旧配送模式对比（时效/损耗/单位运费 三指标分组柱）"""
    df = to_df(rec["supply_chain"]["mode_compare"])
    df = df[df["业务类型"] == "电商订单"].copy()
    metrics = [("平均履约时效_天", "平均履约时效（天）"),
               ("配送损耗率_pct", "配送损耗率（%）"),
               ("单位运费_元每kg", "单位运费（元/kg）")]
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.6))
    for ax, (col, title) in zip(axes, metrics):
        colors = [C_DOWN if "新" in str(m) else "#95a5a6" for m in df["配送模式"]]
        bars = ax.bar(df["配送模式"], df[col], color=colors, width=0.55)
        ax.set_title(title, fontsize=12)
        plt.setp(ax.get_xticklabels(), rotation=12, ha="right", fontsize=9)
        for b, v in zip(bars, df[col]):
            ax.text(b.get_x() + b.get_width() / 2, v * 1.02,
                    f"{v:g}", ha="center", va="bottom", fontsize=10)
        ax.margins(y=0.18)
    fig.suptitle("图6  “集中仓储+分级配送”（新模式）vs “分散直发+统配”（旧模式）",
                 fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig6_配送模式对比.png"), dpi=140)
    plt.close(fig)


def fig7_loss(rec):
    """图7：分环节损耗率"""
    df = to_df(rec["supply_chain"]["loss"])
    fig, ax = plt.subplots(figsize=(9.5, 5))
    bars = ax.bar(df["环节"].astype(str), df["损耗率_pct"],
                  color=PALETTE[:len(df)], width=0.55)
    for b, v in zip(bars, df["损耗率_pct"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02,
                f"{v:.2f}%", ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("损耗率（%）", fontsize=12)
    plt.setp(ax.get_xticklabels(), rotation=15, ha="right")
    ax.set_title("图7  供应链分环节损耗率（采购→仓储→配送）", fontsize=13, pad=12)
    ax.margins(y=0.18)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig7_分环节损耗.png"), dpi=140)
    plt.close(fig)


def fig8_store(rec):
    """图8：单店盈利测算 — 月销售额 vs 盈亏平衡线 + 月净利"""
    df = to_df(rec["store"]["detail"])
    df = df.sort_values("月均销售额", ascending=False).reset_index(drop=True)
    x = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(11, 5.8))
    w = 0.36
    ax.bar(x - w / 2, df["月均销售额"], w, label="现状月均销售额", color="#2E86AB")
    ax.bar(x + w / 2, df["盈亏平衡月销售额"], w,
           label="盈亏平衡月销售额", color="#F18F01")
    ax.set_xticks(x)
    ax.set_xticklabels(df["门店"], fontsize=9)
    plt.setp(ax.get_xticklabels(), rotation=12, ha="right")
    ax.set_ylabel("金额（元/月）", fontsize=12)
    for i, (a, b) in enumerate(zip(df["月均销售额"], df["盈亏平衡月销售额"])):
        ax.text(i - w / 2, a + 500, f"{a/10000:.1f}万", ha="center", fontsize=9)
        ax.text(i + w / 2, b + 500, f"{b/10000:.1f}万", ha="center",
                fontsize=9, color="#B36B00")
    ax.set_title("图8  门店盈亏平衡测算：现状销售 vs 盈亏平衡线", fontsize=13, pad=12)
    ax.legend(loc="upper right")
    ax.margins(y=0.16)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig8_门店盈亏平衡.png"), dpi=140)
    plt.close(fig)


def fig9_store_scenario(rec):
    """图9：门店客流提升情景敏感性（+30%/+60%/翻倍 的合计月净利）"""
    s = rec["store"]["summary"][0]
    labels = ["现状", "客流+30%", "客流+60%", "客流翻倍"]
    vals = [s["合计月净利"], s["情景合计净利_客流加30pct"],
            s["情景合计净利_客流加60pct"], s["情景合计净利_客流翻倍"]]
    colors = [C_DOWN if v >= 0 else C_UP for v in vals]
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    bars = ax.bar(labels, vals, color=colors, width=0.55)
    ax.axhline(0, color="black", lw=1)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2,
                v + (1200 if v >= 0 else -2400),
                f"{v:,.0f}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=10)
    ax.set_ylabel("4 店合计月净利（元）", fontsize=12)
    ax.set_title("图9  门店客流敏感性：4 店合计月净利随客流提升变化",
                 fontsize=13, pad=12)
    ax.margins(y=0.22)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig9_门店情景敏感性.png"), dpi=140)
    plt.close(fig)


def fig10_channel(rec):
    """图10：三渠道 GMV 结构"""
    df = to_df(rec["category"]["table"])
    ecom = df["电商GMV"].sum() if "电商GMV" in df.columns else None
    # 从 a 明细无法直接拿到 B2B/门店总额，用渠道汇总替代
    # 这里展示 GMV 占比结构（电商/B2B/门店）——由品类表三列合计
    if {"电商GMV", "B2B供货额", "门店销售额"}.issubset(df.columns):
        parts = [df["电商GMV"].sum(), df["B2B供货额"].sum(), df["门店销售额"].sum()]
    else:
        parts = [0.52, 0.25, 0.23]
    labels = ["电商渠道", "B2B 供货", "线下门店"]
    fig, ax = plt.subplots(figsize=(7.6, 6))
    wedges, texts, autotexts = ax.pie(
        parts, labels=labels, autopct=lambda p: f"{p:.1f}%\n({p*sum(parts)/100/10000:.1f}万)",
        colors=PALETTE[:3], startangle=90,
        textprops={"fontsize": 11,
                   "fontproperties": fm.FontProperties(fname=CN_FONT_PATH) if CN_FONT_PATH else None},
        wedgeprops={"edgecolor": "white", "linewidth": 2})
    for t in autotexts:
        t.set_color("white")
    ax.set_title("图10  三渠道 GMV 结构（电商 52% / B2B 25% / 门店 23%）",
                 fontsize=13, pad=12)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig10_渠道结构.png"), dpi=140)
    plt.close(fig)


def main():
    print("=" * 62)
    print("生成可视化图表 → reports/figures/")
    print("=" * 62)
    rec = load_json()
    figs = [fig1_category_gmv, fig2_category_roi, fig3_rfm, fig4_funnel,
            fig5_slot, fig6_delivery, fig7_loss, fig8_store,
            fig9_store_scenario, fig10_channel]
    for fn in figs:
        try:
            fn(rec)
            print(f"  ✔ {fn.__doc__.splitlines()[0]}")
        except Exception as e:      # noqa: BLE001
            print(f"  ✗ {fn.__name__} 失败: {e}")
    n = len([f for f in os.listdir(FIG_DIR) if f.endswith(".png")])
    print(f"\n共生成 {n} 张图，输出目录 reports/figures/")
    print("✔ 图表生成完成（模拟数据，仅用于方法复现，不代表真实经营结果）")


if __name__ == "__main__":
    main()
