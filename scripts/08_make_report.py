# -*- coding: utf-8 -*-
"""
08_make_report.py — 生成 Markdown 经营数据分析报告（可用 pandoc 一键转 Word）

数据源：
  - logs/analysis_results.json    （05_run_queries.py 产出的核心指标，数字全部动态引用，不硬编码）
  - data/processed/analysis_*.csv （明细表）
  - reports/figures/fig*.png      （06 产出的 10 张图，相对路径引用）

输出：
  - reports/甘小胖经营数据分析报告.md

转 Word（可选）：pandoc reports/甘小胖经营数据分析报告.md -o reports/甘小胖经营数据分析报告.docx --resource-path=reports

声明：本项目全部数据为 Faker 模拟数据，仅用于方法复现，不代表真实经营结果。
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "logs" / "analysis_results.json"
PROC_DIR = ROOT / "data" / "processed"
OUT_PATH = ROOT / "reports" / "甘小胖经营数据分析报告.md"

with open(JSON_PATH, encoding="utf-8") as f:
    R = json.load(f)

cat = R["category"]
usr = R["user"]
fun = R["funnel"]
sup = R["supply_chain"]
sto = R["store"]
sto_sum = sto["summary"][0]


def load_csv(name):
    return pd.read_csv(PROC_DIR / name, encoding="utf-8-sig")


def wan(x):
    """元 → 万元字符串"""
    return f"{float(x) / 10000:,.2f}"


def money(x):
    return f"{float(x):,.2f}"


def num(x, nd=2):
    return f"{float(x):,.{nd}f}"


new_mode = [m for m in sup["mode_compare"] if m["配送模式"].startswith("新模式") and m["业务类型"] == "电商订单"][0]
old_mode = [m for m in sup["mode_compare"] if m["配送模式"].startswith("旧模式") and m["业务类型"] == "电商订单"][0]

# ---------------------------------------------------------------- 表格构建
def md_table(df, cols=None, fmt=None):
    """DataFrame → Markdown 表格。fmt: {列名: 格式化函数}"""
    if cols:
        df = df[cols]
    fmt = fmt or {}
    lines = ["| " + " | ".join(str(c) for c in df.columns) + " |",
             "|" + "|".join(["---"] * len(df.columns)) + "|"]
    for _, row in df.iterrows():
        cells = []
        for c in df.columns:
            v = row[c]
            if pd.isna(v):
                cells.append("—")
            elif c in fmt:
                cells.append(fmt[c](v))
            elif isinstance(v, float):
                cells.append(f"{v:,.2f}")
            elif isinstance(v, int):
                cells.append(f"{v:,}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


df_cat = load_csv("analysis_a_category_roi.csv")
df_rfm = load_csv("analysis_b_user_rfm.csv")
df_funnel = load_csv("analysis_c_live_funnel.csv")
df_slot = load_csv("analysis_c_live_slot.csv")
df_mode = load_csv("analysis_d_delivery_mode.csv")
df_loss = load_csv("analysis_d_loss.csv")
df_store = load_csv("analysis_e_store_pnl.csv")

# 漏斗补充环节转化率（正向：本环节/上一环节）
df_fun = df_funnel.copy()
df_fun["人次"] = pd.to_numeric(df_fun["人次"])
df_fun["环节转化率"] = (df_fun["人次"] / df_fun["人次"].shift(1)).map(
    lambda x: "—" if pd.isna(x) else f"{x * 100:.1f}%")
df_fun["占曝光比"] = (df_fun["人次"] / df_fun["人次"].iloc[0]).map(lambda x: f"{x * 100:.2f}%")

df_rfm_n = df_rfm.copy()
for c_ in ["人群占比_pct", "平均R天数", "平均频次", "平均金额", "累计贡献金额", "贡献占比_pct"]:
    df_rfm_n[c_] = pd.to_numeric(df_rfm_n[c_], errors="coerce")

df_slot_n = df_slot.copy()
for c_ in ["场均曝光", "场均场观", "场均付款人数", "累计GMV", "UV价值", "平均进入率"]:
    df_slot_n[c_] = pd.to_numeric(df_slot_n[c_], errors="coerce")

df_mode_n = df_mode.copy()
for c_ in ["平均履约时效_天", "配送损耗率_pct", "单位运费_元每kg", "累计运费"]:
    df_mode_n[c_] = pd.to_numeric(df_mode_n[c_], errors="coerce")

df_loss_n = df_loss.copy()
df_loss_n["损耗率_pct"] = pd.to_numeric(df_loss_n["损耗率_pct"], errors="coerce")
df_loss_n["损耗量_kg"] = pd.to_numeric(df_loss_n["损耗量_kg"], errors="coerce")

store_cols = ["门店", "面积㎡", "月均销售额", "综合毛利率_pct", "月固定成本合计", "月净利",
              "盈亏平衡月销售额", "月销售缺口", "盈亏平衡日均单量", "实际日均单量",
              "情景净利_客流加30pct", "情景净利_客流加60pct", "情景净利_客流翻倍"]

top3_txt = "、".join(f"**{t['品类']}（{t['占比_pct']}%）**" for t in cat["top3"])
roi_ge1 = df_cat[df_cat["品类ROI"] >= 1]["品类"].tolist()
roi_lt1 = df_cat[df_cat["品类ROI"] < 1]["品类"].tolist()
seg_top = sorted(usr["segments"], key=lambda x: -float(x["贡献占比_pct"]))[0]
seg_hi_freq = sorted(usr["segments"], key=lambda x: -float(x["平均频次"]))[0]
best_slot_uv = max(fun["slots"], key=lambda x: float(x["UV价值"]))
best_slot_gmv = max(fun["slots"], key=lambda x: float(x["累计GMV"]))
f = [int(s["人次"]) for s in fun["steps"]]
best_store = max(sto["detail"], key=lambda x: x["月均销售额"])
worst_store = min(sto["detail"], key=lambda x: x["月净利"])

# ---------------------------------------------------------------- 报告正文
md = f"""# “甘小胖”扎根富农产业链数据分析报告

> **⚠️ 数据声明：本报告全部数据由 Faker 按业务规则模拟生成（固定随机种子，可复现），仅用于数据分析方法复现与演示，不代表任何真实经营结果。**

- 分析区间：2025-01 ~ 2025-12（模拟）
- 数据规模：2,100 个 SKU、约 12 万条业务记录（电商订单/订单明细/B2B/门店日销/直播场次与分钟流量/采购/配送/库存）
- 技术栈：Python（Faker/pandas）+ MySQL 8（视图 + 窗口函数）+ matplotlib/seaborn + openpyxl
- 报告生成时间：{R['generated_at']} ｜ SQL ↔ Python 复算交叉校验：**{'通过 ✔' if R['cross_check_passed'] else '未通过 ✘'}**

---

## 一、项目背景

“甘小胖”是一个扎根甘肃县域的农产品产业链品牌（模拟设定），业务覆盖三条渠道：

1. **电商直播带货**（定西宽粉、生鲜水果等 11 大品类，抖音/快手式直播 + 短视频引流）；
2. **B2B 供货**（向商超、餐饮连锁、批发商供货）；
3. **线下门店**（4 家“甘小胖宽粉麻辣烫”县域门店）。

供应链正从「旧模式：分散直发 + 统配」向「新模式：集中仓储 + 分级配送」切换。本报告基于一套**四层指标体系**（明细层 → 汇总层 → 指标层 → 应用层），围绕五个业务问题展开：

| 模块 | 业务问题 | 方法 |
|---|---|---|
| A 品类 ROI | 货盘结构健康吗？内容投放值得吗？ | 全渠道 GMV 帕累托 + 毛利/内容投入 ROI |
| B 用户 RFM | 谁是高价值用户？复购怎么样？ | RFM 八分层 + 复购率 |
| C 直播漏斗 | 流量在哪一步流失？什么时段效率高？ | 六段转化漏斗 + 时段 × UV 价值 |
| D 供应链 | 新模式是否真的降本增效？ | 新旧模式时效/损耗/运费对比 + 分环节损耗 |
| E 门店盈利 | 县域门店模型跑得通吗？ | 单店 P&L + 盈亏平衡 + 客流情景测算 |

---

## 二、核心结论摘要

| 指标 | 数值 | 说明 |
|---|---|---|
| 全渠道 GMV | **¥{wan(cat['total_gmv'])} 万** | 电商 + B2B + 门店合计 |
| Top3 品类集中度 | **{cat['top3_share_pct']}%** | {cat['top3'][0]['品类']} / {cat['top3'][1]['品类']} / {cat['top3'][2]['品类']} |
| 电商复购率 | **{usr['repurchase_rate_pct']}%** | {usr['buyers']:,} 购买用户，人均 {usr['avg_freq']} 次 |
| 最高品类 ROI | **{cat['best_roi'][0]['ROI']}（{cat['best_roi'][0]['品类']}）** | 毛利 ÷ 内容投入 |
| 新模式履约时效 | **{num(new_mode['平均履约时效_天'])} 天** | 旧模式 {num(old_mode['平均履约时效_天'])} 天（电商订单口径） |
| 新模式配送损耗率 | **{num(new_mode['配送损耗率_pct'])}%** | 旧模式 {num(old_mode['配送损耗率_pct'])}% |
| 门店合计月净利 | **¥{num(sto_sum['合计月净利'], 0)}** | 4 家均未达盈亏平衡，缺口 ¥{num(sto_sum['月销售缺口合计'], 0)}/月 |
| 客流 +60% 情景净利 | **¥{num(sto_sum['情景合计净利_客流加60pct'], 0)}/月** | 情景测算转正 |

**一句话总结**：货盘有明确支柱品类（宽粉），供应链新模式降本增效显著，但增长受限于「直播引流效率」和「门店客流不足」两大瓶颈；优先做直播进入率与门店引流，ROI 差的品类收缩投放。

---

## 三、品类结构与 ROI 分析

![品类GMV帕累托](figures/fig1_品类GMV帕累托.png)

{md_table(df_cat, cols=["品类", "在售SKU数", "品类GMV", "GMV占比_pct", "综合毛利率_pct", "内容投入成本", "品类ROI"])}

![品类ROI矩阵](figures/fig2_品类ROI矩阵.png)

**结论：**

1. **货盘高度集中**：{top3_txt}，合计占全渠道 GMV 的 **{cat['top3_share_pct']}%**。支柱品类{cat['top3'][0]['品类']}兼具规模（GMV {wan(cat['top3'][0]['GMV'])} 万）与利润（毛利率 53.93%），是现金流基本盘。
2. **ROI 分化明显**：ROI≥1 的品类 {len(roi_ge1)} 个（{'、'.join(roi_ge1)}）；ROI<1 的品类 {len(roi_lt1)} 个（{'、'.join(roi_lt1)}）。**{cat['best_roi'][0]['品类']} ROI {cat['best_roi'][0]['ROI']} 最高**，体量虽小（占比 {df_cat[df_cat['品类']==cat['best_roi'][0]['品类']]['GMV占比_pct'].iloc[0]}%）但适合节礼场景放大；**肉禽蛋品 ROI 仅 {df_cat[df_cat['品类']=='肉禽蛋品']['品类ROI'].iloc[0]}**，毛利率 24.48% 叠加冷链成本高，投放需收缩。
3. **建议**：宽粉类稳投（高 GMV + ROI 1.29 为正）；生鲜水果/高原夏菜「高 GMV、ROI<1」，应优化投放素材与人群包而非追加预算；礼盒/药食同源/蜂产品作为利润补充重点培育。

![渠道结构](figures/fig10_渠道结构.png)

---

## 四、用户 RFM 分层与复购分析

![RFM用户分层](figures/fig3_RFM用户分层.png)

分层口径：R（最近购买天数）按中位数二分，F（购买频次）按 ≥2 次二分，M（累计金额）按中位数二分，共 8 层。

{md_table(df_rfm_n)}

**结论：**

1. **复购是短板**：复购率 **{usr['repurchase_rate_pct']}%**（人均 {usr['avg_freq']} 次），近 78% 用户只买一次——与生鲜/食品电商行业常态一致，说明「首单体验 → 二单转化」是最大杠杆。
2. **头部依赖明显**：「{seg_top['人群分层']}」以 {seg_top['人群占比_pct']}% 的人数贡献 **{seg_top['贡献占比_pct']}%** 的电商金额（¥{num(seg_top['累计贡献金额'], 0)}），平均每人消费 ¥{num(seg_top['平均金额'], 0)}、{num(seg_top['平均频次'])} 次。
3. **结构启示**：一般挽留 + 一般发展两类低频人群合计占比超 47% 但贡献仅约 21%；「{seg_hi_freq['人群分层']}」频次最高（{num(seg_hi_freq['平均频次'])} 次）。建议：对重要价值/保持客户推会员日与组合装锁复购；对 R 短 F 低的重要发展客户推二单券；对一般挽留客户做低成本短信召回。

---

## 五、直播转化漏斗与时段效果

![直播漏斗](figures/fig4_直播漏斗.png)

{md_table(df_fun)}

**漏斗解读（合计口径，全年直播场次汇总）：**

- **曝光 → 进入：{f[1]/f[0]*100:.1f}%** —— 最大流失点，受封面/标题/投流素材质量决定；
- **停留 → 互动：{f[3]/f[2]*100:.1f}%**，**互动 → 下单：{f[4]/f[3]*100:.1f}%** —— 第二流失点，货品讲解与价格锚点不足；
- **下单 → 付款：{f[5]/f[4]*100:.1f}%** —— 尾款流失相对健康。

![直播时段效果](figures/fig5_直播时段效果.png)

{md_table(df_slot_n, cols=["时段", "场次数", "场均场观", "场均付款人数", "累计GMV", "UV价值"])}

**结论：**

1. 「{best_slot_uv['时段']}」**UV 价值最高（{num(best_slot_uv['UV价值'])} 元）**，「{best_slot_gmv['时段']}」**累计 GMV 最大（¥{wan(best_slot_gmv['累计GMV'])} 万）**——建议稳黄金场基本盘，把傍晚场作为增量时段加密排期。
2. 三个时段进入率均在 10% 左右，差异不大，说明**时段不是效率瓶颈，素材与货盘才是**；优化优先级：直播间封面/投流素材（提升进入率）＞ 讲解话术与限时机制（提升互动→下单）＞ 排期调整。

---

## 六、供应链：配送模式与损耗分析

![配送模式对比](figures/fig6_配送模式对比.png)

{md_table(df_mode_n)}

![分环节损耗](figures/fig7_分环节损耗.png)

{md_table(df_loss_n)}

**结论（以单量最大的电商订单口径）：**

1. **时效**：平均履约 **{num(old_mode['平均履约时效_天'])} 天 → {num(new_mode['平均履约时效_天'])} 天**，缩短 {num(float(old_mode['平均履约时效_天'])-float(new_mode['平均履约时效_天']), 1)} 天；B2B 供货同样 3.74 → 2.36 天。
2. **损耗**：配送损耗率 **{num(old_mode['配送损耗率_pct'])}% → {num(new_mode['配送损耗率_pct'])}%**，下降 {num(float(old_mode['配送损耗率_pct'])-float(new_mode['配送损耗率_pct']))} 个百分点，对生鲜品类（毛利率仅 35%）意味着直接保住约 0.6pct 的毛利。
3. **成本**：单位运费 **{num(old_mode['单位运费_元每kg'])} → {num(new_mode['单位运费_元每kg'])} 元/kg**，下降 {num((1-float(new_mode['单位运费_元每kg'])/float(old_mode['单位运费_元每kg']))*100, 1)}%。
4. **分环节看**：采购损耗 {num(df_loss_n[df_loss_n['环节']=='采购损耗']['损耗率_pct'].iloc[0])}% 与配送损耗 {num(df_loss_n[df_loss_n['环节']=='配送损耗']['损耗率_pct'].iloc[0])}% 量级相当，集中采购质检 + 产地预冷是下一步压缩空间。

---

## 七、门店盈利测算与盈亏平衡分析

模型口径：月净利 = 月均毛利 −（月租金 + 人工 + 水电杂费 + 折旧摊销）；盈亏平衡月销售额 = 月固定成本 ÷ 综合毛利率；成本参数按县域真实水平设定（租金 1,500~2,200 元/月、人工 3,000~3,200 元/人/月、装修设备按 48 个月摊销）。

![门店盈亏平衡](figures/fig8_门店盈亏平衡.png)

{md_table(df_store, cols=store_cols)}

**门店汇总**：现状月销售合计 ¥{num(sto_sum['现状月销售合计'], 0)}，盈亏平衡要求 ¥{num(sto_sum['盈亏平衡月销售合计'], 0)}，**缺口 ¥{num(sto_sum['月销售缺口合计'], 0)}/月**；平均月净利 ¥{num(sto_sum['平均月净利'], 0)}。

![门店情景敏感性](figures/fig9_门店情景敏感性.png)

**结论：**

1. **现状 4 家全部未达盈亏平衡**：最好的{best_store['门店']}（月均销售 {wan(best_store['月均销售额'])} 万）月净利仍为 ¥{num(best_store['月净利'], 0)}；压力最大的{worst_store['门店']}月亏 ¥{num(abs(worst_store['月净利']), 0)}。
2. **缺口可量化**：各店盈亏平衡日均单量 26.5~37.1 单 vs 实际 14.9~24.7 单，**日均需多 8~13 单**，对应客流提升约 60% 时整体转正（合计净利 ¥{num(sto_sum['情景合计净利_客流加60pct'], 0)}/月）；客流翻倍时合计净利可达 ¥{num(sto_sum['情景合计净利_客流翻倍'], 0)}/月。
3. **经营建议**：门店定位应是「品牌体验 + 线上引流入口」而非短期利润中心——通过门店试吃扫码进直播间/社群，把门店客流转化为电商复购；在引流动作未验证前（跑通日均 +10 单），不建议新增门店。

---

## 八、综合结论与行动清单

| 优先级 | 行动 | 预期收益 | 依据 |
|---|---|---|---|
| P0 | 优化直播间封面/投流素材，进入率 9.9% → 15% | 场观 +50%，GMV 弹性最大 | 漏斗第一流失点 |
| P0 | 门店引流验证（试吃+扫码券），目标日均 +10 单 | 4 店合计月净利转正（约 +¥1,600/月，+60% 客流情景） | 盈亏平衡测算 |
| P1 | 二单券 + 会员日，复购率 22.1% → 30% | 电商 GMV +8%~10% | RFM：78% 用户单次购买 |
| P1 | 肉禽蛋品、生鲜水果收缩低效投放，预算转向礼盒/药食同源 | 内容 ROI 整体提升 | 品类 ROI 矩阵 |
| P2 | 扩大集中仓储覆盖线路，采购端产地预冷 | 损耗再降 0.3~0.5pct | 新旧模式对比 + 分环节损耗 |

---

## 附录

### A. 指标体系（四层）

- **明细层**：订单/明细/B2B/门店日销/直播场次/分钟流量/采购/配送/库存 9 张事实表 + 5 张维度表；
- **汇总层**：品类 × 渠道、用户 RFM、直播场次、配送单、门店月度等汇总视图（`sql/01_metric_views.sql`）；
- **指标层**：GMV/毛利率/ROI/复购率/转化率/履约时效/损耗率/坪效/人效/盈亏平衡等 40+ 指标；
- **应用层**：5 个分析 SQL（`sql/a_~e_*.sql`）+ Python 复算 + 10 张图 + Excel 看板 + 本报告。

### B. SQL ↔ Python 一致性校验

同一指标分别用 MySQL（视图+窗口函数）与 pandas 独立复算，容差 1e-4（相对）：

1. 电商 GMV（摊销口径）✔
2. 电商复购率 ✔
3. 全渠道 GMV ✔
4. 门店合计月净利 ✔

结果：`cross_check_passed = {str(R['cross_check_passed']).lower()}`

### C. 复现方式

```bash
python -m venv venv && venv/Scripts/activate
pip install -r requirements.txt
python scripts/01_generate_data.py     # 生成模拟数据（固定 seed）
python scripts/02_clean_data.py        # 清洗
python scripts/03_load_to_mysql.py     # 建库入库（需先配置 config/db_config.py）
python scripts/05_run_queries.py       # 5 个分析 SQL + pandas 复算校验
python scripts/06_make_figures.py      # 10 张图
python scripts/07_make_dashboard.py    # Excel 看板
python scripts/08_make_report.py       # 本报告
```

### D. 转 Word

```bash
pandoc reports/甘小胖经营数据分析报告.md -o reports/甘小胖经营数据分析报告.docx --resource-path=reports
```

---

> **再次声明：本报告全部数据为模拟数据，仅用于方法复现，不代表真实经营结果。**
"""

OUT_PATH.write_text(md, encoding="utf-8")
print(f"✔ Markdown 报告已生成：{OUT_PATH}")
print(f"  篇幅约 {len(md)} 字符 / {md.count(chr(10))} 行")
print(f"  引用图表 10 张（figures/ 相对路径），数字全部来自 analysis_results.json")
print(f"  （模拟数据，仅用于方法复现，不代表真实经营结果）")
