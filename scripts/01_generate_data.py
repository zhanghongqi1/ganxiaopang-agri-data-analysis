# -*- coding: utf-8 -*-
"""
01_generate_data.py — 「甘小胖」扎根富农产业链 模拟数据生成器
================================================================
⚠️ 本脚本生成的是【模拟数据】：Faker(zh_CN) + 自定义业务规则，
   固定随机种子，完全可复现。仅用于数据分析方法复现，不代表真实经营。

校准目标（依据简历与项目计划书）：
  - 总数据量 ≈ 12 万条（15 张表）
  - dim_sku = 2100 个 SKU，11 个一级大类 / 68 个二级类目
  - Top3 品类 GMV 占比 ≈ 65%（63%~67% 断言）
  - 三渠道 GMV 占比：电商 52% / B2B 供货 25% / 门店 23%（±3pct 断言）
  - 直播场次 624 场（2024-2025）+ 分钟级流量
  - 4 家门店（陇西/通渭/平凉/静宁），供应链采购/仓储/配送
  - 原始层注入约 2% 脏数据（重复/缺失/异常/格式不一致），供 02 清洗脚本处理

输出：data/raw/*.csv（UTF-8-SIG）+ logs/generation_stats.json
"""
import json
import os
import sys
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker

# ------------------------------------------------------------------
# 全局配置
# ------------------------------------------------------------------
SEED = 20240101
DATE_START = date(2024, 1, 1)
DATE_END = date(2025, 12, 31)
OBSERVE_DATE = date(2025, 12, 31)          # RFM 观察截止日
ALL_DAYS = [DATE_START + timedelta(days=i)
            for i in range((DATE_END - DATE_START).days + 1)]  # 731 天

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

rng = np.random.default_rng(SEED)
Faker.seed(SEED)
fake = Faker("zh_CN")

N_ORDERS = 26_500          # 电商订单总数（含取消/退款），约 2.24 万有效单
N_USERS = 20_000           # 用户池：约 2 万注册用户（复购率约 30%）
N_SUPPLIERS = 60
N_SESSIONS = 624
N_B2B = 600
N_PURCHASES = 750
N_DELIVERY_ECOM = 2_400    # 电商配送抽样单
FESTIVALS = {              # 节庆大促日（含助农丰收节/年货节/618/双11）
    date(2024, 1, 18): "年货节", date(2024, 6, 18): "618大促",
    date(2024, 9, 23): "丰收节助农专场", date(2024, 11, 11): "双11大促",
    date(2024, 12, 21): "冬至年货专场", date(2025, 1, 10): "年货节",
    date(2025, 6, 18): "618大促", date(2025, 9, 20): "丰收节助农专场",
    date(2025, 11, 11): "双11大促", date(2025, 12, 12): "双12年货专场",
}

# 渠道 GMV 目标占比（电商/B2B/门店）→ B2B 与门店金额由电商实际 GMV 反推
SHARE_ECOM, SHARE_B2B, SHARE_STORE = 0.52, 0.25, 0.23

# ------------------------------------------------------------------
# 品类体系：11 个一级大类 / 68 个二级类目 / 2100 SKU
# ------------------------------------------------------------------
# L1 名称: (L2 列表, SKU 数, 零售价区间, 毛利率区间, 自营比例, 主要产地)
CATEGORIES = {
    "定西宽粉及薯制品": (
        ["干宽粉", "流汁湿宽粉", "火锅宽粉", "马铃薯粉丝", "水晶粉丝",
         "粉皮", "马铃薯淀粉", "薯脆片"],
        500, (29, 128), (0.42, 0.58), 0.70, ["定西", "陇西"]),
    "甘肃生鲜水果": (
        ["静宁苹果", "花牛苹果", "天水大樱桃", "秦安蜜桃", "敦煌李广杏",
         "瓜州蜜瓜", "兰州白兰瓜", "河西葡萄", "软儿梨", "籽瓜"],
        440, (39, 168), (0.25, 0.40), 0.05, ["静宁", "天水", "秦安", "敦煌", "瓜州", "兰州"]),
    "高原夏菜及土豆": (
        ["定西黄心土豆", "荷兰土豆", "陇椒螺丝椒", "高原西兰花", "娃娃菜",
         "芹菜", "黄皮洋葱", "胡萝卜"],
        286, (19, 59), (0.18, 0.32), 0.05, ["定西", "榆中", "兰州周边", "张掖"]),
    "小杂粮粮油": (
        ["苦荞米", "陇中小米", "燕麦米", "藜麦", "定西扁豆",
         "胡麻油", "菜籽油", "亚麻籽"],
        228, (25, 88), (0.25, 0.38), 0.10, ["定西", "会宁", "通渭"]),
    "干货山珍": (
        ["地达菜", "陇上黑木耳", "黄花菜", "香菇干", "蕨菜干",
         "花椒叶", "临泽红枣"],
        174, (35, 158), (0.35, 0.52), 0.05, ["陇南", "康县", "临泽", "定西"]),
    "香辛调料": (
        ["大红袍花椒", "秦安花椒", "甘谷辣椒面", "油泼辣子", "胡麻盐", "十三香"],
        108, (15, 68), (0.32, 0.48), 0.10, ["秦安", "甘谷", "武都"]),
    "药食同源": (
        ["陇西黄芪", "渭源党参", "岷县当归", "兰州百合", "枸杞",
         "苦水玫瑰酱", "甘草片"],
        126, (45, 198), (0.40, 0.58), 0.05, ["陇西", "渭源", "岷县", "兰州", "靖远"]),
    "蜂产品": (
        ["洋槐蜜", "枣花蜜", "枸杞蜜", "蜂王浆", "油菜花粉"],
        80, (39, 128), (0.38, 0.52), 0.05, ["天水", "陇南", "靖远"]),
    "肉禽蛋品": (
        ["靖远滩羊肉", "散养土鸡蛋", "陇西驴肉", "农家腊肉", "乌鸡"],
        70, (59, 268), (0.18, 0.30), 0.05, ["靖远", "陇西", "通渭"]),
    "预包装速食": (
        ["自热麻辣烫", "速食流汁宽粉"],
        44, (19, 49), (0.28, 0.42), 0.85, ["定西"]),
    "礼盒组合": (
        ["助农年货礼盒", "甘肃特产组合装"],
        44, (99, 298), (0.45, 0.62), 0.60, ["定西", "兰州"]),
}
L1_NAMES = list(CATEGORIES.keys())

# 各渠道品类 GMV 权重（电商/B2B；门店见 STORE_CAT_MAP）
W_ECOM = {
    "定西宽粉及薯制品": 0.06, "甘肃生鲜水果": 0.33, "高原夏菜及土豆": 0.12,
    "小杂粮粮油": 0.10, "干货山珍": 0.13, "香辛调料": 0.07,
    "药食同源": 0.09, "蜂产品": 0.05, "肉禽蛋品": 0.03,
    "预包装速食": 0.015, "礼盒组合": 0.005,
}
W_B2B = {
    "定西宽粉及薯制品": 0.48, "甘肃生鲜水果": 0.10, "高原夏菜及土豆": 0.18,
    "小杂粮粮油": 0.05, "干货山珍": 0.13, "香辛调料": 0.02,
    "药食同源": 0.01, "肉禽蛋品": 0.03,
}
# 门店销售品类 → 归集 L1（口径见 docs/指标口径.md）
STORE_CATS = ["宽粉麻辣烫", "特色小吃", "饮品", "伴手礼盒"]
STORE_CAT_MAP = {
    "宽粉麻辣烫": ("定西宽粉及薯制品", 0.50),
    "特色小吃": ("高原夏菜及土豆", 0.22),
    "饮品": ("甘肃生鲜水果", 0.13),
    "伴手礼盒": ("礼盒组合", 0.15),
}
# 门店品类综合毛利率（与 sql/a_category_roi.sql 步骤3 保持一致）
STORE_CAT_MARGIN = {
    "宽粉麻辣烫": 0.60, "特色小吃": 0.45, "饮品": 0.55, "伴手礼盒": 0.42,
}
# B2B 批发成本率（批发毛利率约 15%，用于采购校准目标）
B2B_COST_RATIO = 0.85
# 采购备货系数：采购金额 ≈ 品类销售成本 × 1.15（安全库存）
PURCH_STOCKUP = 1.15

B2B_WHOLESALE_PRICE = {   # B2B 批发价区间（元/kg）
    "定西宽粉及薯制品": (16, 22), "甘肃生鲜水果": (5.5, 8.0),
    "高原夏菜及土豆": (2.2, 3.2), "小杂粮粮油": (6, 12),
    "干货山珍": (28, 55), "香辛调料": (18, 40), "药食同源": (35, 70),
    "肉禽蛋品": (28, 55),
}

# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------
def wchoice(items, weights, size=None):
    """按权重采样（返回数组或标量）。"""
    weights = np.asarray(weights, dtype=float)
    weights = weights / weights.sum()
    if size is None:
        return items[int(rng.choice(len(items), p=weights))]
    return [items[i] for i in rng.choice(len(items), size=size, p=weights)]


def lognorm(mean, sigma, size=None, clip=(None, None)):
    """均值为 mean 的对数正态采样。"""
    mu = np.log(mean / np.sqrt(1 + sigma ** 2))
    s = np.sqrt(np.log(1 + sigma ** 2))
    out = rng.lognormal(mu, s, size)
    lo, hi = clip
    if lo is not None:
        out = np.maximum(out, lo)
    if hi is not None:
        out = np.minimum(out, hi)
    return out


def rand_date(weights=None):
    """时间窗内随机日期（可选按天权重）。"""
    if weights is None:
        idx = int(rng.integers(0, len(ALL_DAYS)))
    else:
        idx = int(rng.choice(len(ALL_DAYS), p=weights / weights.sum()))
    return ALL_DAYS[idx]


def date_weights_growth():
    """2025 年业务增长 → 日权重随时间线性上升 + 节庆尖峰。"""
    w = np.array([1.0 + 0.6 * i / len(ALL_DAYS) for i in range(len(ALL_DAYS))])
    for i, d in enumerate(ALL_DAYS):
        if d in FESTIVALS:
            w[i] *= 2.2
        elif d.month in (11, 12, 1):
            w[i] *= 1.25
    return w


DAY_W = date_weights_growth()


# ------------------------------------------------------------------
# 1. 维表
# ------------------------------------------------------------------
def gen_suppliers():
    rows = []
    types = (["农户"] * 25) + (["合作社"] * 20) + (["工厂"] * 15)
    regions = ["定西", "陇西", "通渭", "静宁", "天水", "秦安", "民勤", "瓜州",
               "敦煌", "榆中", "靖远", "临泽", "陇南", "渭源", "岷县", "会宁"]
    # 宽粉工厂优先（计划书：自建干湿粉加工厂）
    factory_regions = ["定西", "陇西", "定西", "渭源", "通渭", "定西", "岷县",
                       "陇西", "定西", "天水", "榆中", "静宁", "会宁", "临泽", "民勤"]
    for sid in range(1, N_SUPPLIERS + 1):
        stype = types[sid - 1]
        region = (factory_regions[sid - 46] if stype == "工厂"
                  else str(rng.choice(regions)))
        coop = int(rng.integers(1, 7)) if stype != "农户" else int(rng.integers(1, 4))
        tons = float(lognorm(35 if stype == "农户" else 120 if stype == "合作社" else 600,
                             0.8, clip=(3, 3000)))
        rows.append({
            "supplier_id": sid,
            "supplier_name": f"{region}{fake.company() if stype != '农户' else fake.last_name() + '家' + rng.choice(['果园', '土豆田', '养蜂场', '牧场', '菜地'])}",
            "supplier_type": stype,
            "region": region,
            "coop_years": coop,
            "annual_supply_tons": round(tons, 1),
        })
    return pd.DataFrame(rows)


def gen_sku(suppliers):
    rows = []
    sku_id = 1
    sku_prefix = {"定西宽粉及薯制品": "DF", "甘肃生鲜水果": "SG", "高原夏菜及土豆": "XC",
                  "小杂粮粮油": "ZL", "干货山珍": "GH", "香辛调料": "TL", "药食同源": "YS",
                  "蜂产品": "FP", "肉禽蛋品": "RQ", "预包装速食": "SS", "礼盒组合": "LH"}
    spec_units = {"kg": ["500g", "1kg", "2kg", "5kg"], "袋": ["1袋装", "3连袋", "5连袋"],
                  "箱": ["5斤装", "10斤装", "整箱"], "盒": ["礼盒装", "2盒装"],
                  "瓶": ["500ml", "750ml"]}
    # 供应商按主营品类池分配
    supplier_ids = suppliers["supplier_id"].tolist()
    for l1, (l2_list, n_sku, price_rng, margin_rng, self_ratio, origins) in CATEGORIES.items():
        n_l2 = len(l2_list)
        per_l2 = [n_sku // n_l2] * n_l2
        for k in range(n_sku - sum(per_l2)):
            per_l2[k % n_l2] += 1
        assert sum(per_l2) == n_sku
        for l2_idx, l2 in enumerate(l2_list):
            for _ in range(per_l2[l2_idx]):
                p_lo, p_hi = price_rng
                price = float(np.round(rng.uniform(p_lo, p_hi), 1))
                margin = float(np.round(rng.uniform(*margin_rng), 4))
                unit = str(rng.choice(list(spec_units.keys())))
                spec = str(rng.choice(spec_units[unit]))
                is_self = 1 if rng.random() < self_ratio else 0
                origin = str(rng.choice(origins))
                # 自营 SKU 优先绑定工厂类供应商
                pool = [s for s, t in zip(supplier_ids, suppliers["supplier_type"])
                        if (t == "工厂" and is_self) or (t != "工厂" and not is_self)] or supplier_ids
                rows.append({
                    "sku_id": sku_id,
                    "sku_code": f"GXP-{sku_prefix[l1]}-{sku_id:04d}",
                    "sku_name": f"{origin}{l2}{spec}",
                    "category_l1": l1,
                    "category_l2": l2,
                    "brand_series": str(rng.choice(["甘小胖", "胖娃优选", "陇原农特",
                                                    "甘肃胖娃娃", "小胖甄选", "合作甄选"])),
                    "spec": spec,
                    "unit": unit,
                    "cost_price": round(price * (1 - margin), 2),
                    "retail_price": price,
                    "gross_margin_rate": margin,
                    "supplier_id": int(rng.choice(pool)),
                    "origin": origin,
                    "is_self_operated": is_self,
                    "shelf_date": str(DATE_START - timedelta(days=int(rng.integers(30, 700)))),
                    "status": str(rng.choice(["在售"] * 92 + ["清仓"] * 5 + ["下架"] * 3)),
                })
                sku_id += 1
    df = pd.DataFrame(rows)
    assert len(df) == 2100, f"SKU 数量应为 2100，实际 {len(df)}"
    return df


def gen_users():
    provinces = ["甘肃", "广东", "江苏", "浙江", "北京", "上海", "四川", "陕西",
                 "河南", "山东", "湖北", "福建", "重庆", "新疆", "青海"]
    prob_w = np.array([30, 8, 7, 6, 5, 5, 6, 6, 5, 5, 4, 4, 3, 3, 3], dtype=float)
    rows = []
    for uid in range(1, N_USERS + 1):
        rows.append({
            "user_id": uid,
            "nickname": fake.user_name() + str(rng.integers(10, 99)),
            "gender": str(rng.choice(["男", "女"], p=[0.38, 0.62])),
            "age": int(np.clip(rng.normal(38, 11), 18, 65)),
            "province": str(rng.choice(provinces, p=prob_w / prob_w.sum())),
            "city_tier": int(rng.choice([1, 2, 3, 4, 5], p=[0.10, 0.18, 0.27, 0.28, 0.17])),
            "register_date": str(DATE_START - timedelta(days=int(rng.integers(1, 570)))),
            "source": str(rng.choice(["直播间", "短视频橱窗", "商城搜索", "老客推荐"],
                                      p=[0.48, 0.22, 0.18, 0.12])),
            "is_fan": int(rng.random() < 0.55),
            "member_level": str(rng.choice(["普通", "银卡", "金卡", "黑卡"],
                                           p=[0.62, 0.22, 0.12, 0.04])),
        })
    return pd.DataFrame(rows)


def gen_stores_warehouses():
    # 成本参数取「甘肃县域小型麻辣烫店」真实水平：
    #   县/县级市门店租金显著低于省会；员工以本地 2-3 人计，人均月成本约 3200 元
    #   （含社保的简餐店用工）；初始投入为轻资产简餐店口径，按 48 个月摊销。
    #   说明：这些参数仅用于可行性测算模型，属模拟假设，不代表真实门店财务。
    stores = pd.DataFrame([
        {"store_id": 1, "store_name": "甘小胖宽粉麻辣烫(陇西总店)", "city": "陇西",
         "open_date": "2023-02-10", "area_sqm": 45, "rent_monthly": 2200,
         "staff_cnt": 3, "staff_cost_monthly": 3200, "util_monthly": 900,
         "amort_months": 48, "seats": 26, "initial_investment": 180000,
         "daily_base": 1.00},
        {"store_id": 2, "store_name": "甘小胖宽粉麻辣烫(通渭店)", "city": "通渭",
         "open_date": "2023-03-15", "area_sqm": 38, "rent_monthly": 1800,
         "staff_cnt": 2, "staff_cost_monthly": 3100, "util_monthly": 800,
         "amort_months": 48, "seats": 20, "initial_investment": 150000,
         "daily_base": 0.78},
        {"store_id": 3, "store_name": "甘小胖宽粉麻辣烫(平凉店)", "city": "平凉",
         "open_date": "2023-04-20", "area_sqm": 32, "rent_monthly": 1600,
         "staff_cnt": 2, "staff_cost_monthly": 3000, "util_monthly": 750,
         "amort_months": 48, "seats": 18, "initial_investment": 130000,
         "daily_base": 0.62},
        {"store_id": 4, "store_name": "甘小胖宽粉麻辣烫(静宁店)", "city": "静宁",
         "open_date": "2023-06-01", "area_sqm": 30, "rent_monthly": 1500,
         "staff_cnt": 2, "staff_cost_monthly": 3000, "util_monthly": 700,
         "amort_months": 48, "seats": 16, "initial_investment": 120000,
         "daily_base": 0.53},
    ])
    warehouses = pd.DataFrame([
        {"warehouse_id": 1, "warehouse_name": "甘小胖主仓(定西加工厂)",
         "area_sqm": 2400, "location": "定西"},
        {"warehouse_id": 2, "warehouse_name": "兰州中转仓",
         "area_sqm": 1000, "location": "兰州"},
    ])
    return stores, warehouses


# ------------------------------------------------------------------
# 2. 直播场次与分钟级流量
# ------------------------------------------------------------------
def gen_live_sessions():
    """624 场：2024 年约 5 场/周、2025 年约 7 场/周（业务成长）。"""
    rows = []
    n_2024, n_2025 = 260, 364
    year_counts = {2024: n_2024, 2025: n_2025}
    sid = 1
    for year, n in year_counts.items():
        year_day_idx = np.array([i for i, x in enumerate(ALL_DAYS) if x.year == year])
        year_w = DAY_W[year_day_idx]
        for _ in range(n):
            d = ALL_DAYS[int(rng.choice(year_day_idx, p=year_w / year_w.sum()))]
            is_fest = d in FESTIVALS
            if is_fest:
                theme = "节庆大促"
            else:
                theme = str(rng.choice(["助农专场", "宽粉工厂专场", "常态化带货"],
                                       p=[0.30, 0.25, 0.45]))
            if theme == "节庆大促":
                duration = int(rng.integers(80, 121))
                enter = float(lognorm(18000, 0.45, clip=(8000, 45000)))
                pay_rate = rng.uniform(0.005, 0.008)
            elif theme == "助农专场":
                duration = int(rng.integers(60, 95))
                enter = float(lognorm(9000, 0.5, clip=(3500, 26000)))
                pay_rate = rng.uniform(0.003, 0.0055)
            elif theme == "宽粉工厂专场":
                duration = int(rng.integers(60, 90))
                enter = float(lognorm(6500, 0.5, clip=(2500, 18000)))
                pay_rate = rng.uniform(0.004, 0.007)
            else:
                duration = int(rng.integers(55, 76))
                enter = float(lognorm(4200, 0.5, clip=(1500, 12000)))
                pay_rate = rng.uniform(0.003, 0.006)
            rows.append({
                "session_id": sid, "live_date": str(d),
                "start_time": str(rng.choice(["14:00", "15:30", "18:30", "19:00", "19:30", "20:00"],
                                             p=[0.10, 0.12, 0.22, 0.28, 0.18, 0.10])),
                "duration_min": duration, "theme": theme, "is_festival": int(is_fest),
                "_enter": enter, "_pay_rate": pay_rate,   # 中间量，最后删除
            })
            sid += 1
    df = pd.DataFrame(rows).sort_values("live_date").reset_index(drop=True)
    df["session_id"] = range(1, len(df) + 1)

    # 直播间有效订单总数目标（有效订单 24,650 中 64.7%）
    target_paid_orders = 15_950
    # 每场付款人数 ~ lognormal，精确缩放到目标
    raw = lognorm(1.0, 0.55, size=len(df))
    scale = target_paid_orders / raw.sum()
    payers = np.maximum(np.round(raw * scale).astype(int), 3)
    # 修正取整误差
    diff = target_paid_orders - payers.sum()
    order_idx = np.argsort(-payers)
    i = 0
    while diff != 0:
        j = order_idx[i % len(df)]
        if diff > 0:
            payers[j] += 1
            diff -= 1
        elif payers[j] > 4:
            payers[j] -= 1
            diff += 1
        i += 1
    df["_payers"] = payers
    return df


def fill_session_funnel(df):
    """六段漏斗正向生成（行业合理区间）：
    进入→停留>30s: 25%~45%；停留→互动: 15%~35%；互动→下单: 由付款人数反推；
    下单→付款: 86%~93%。GMV = 付款人数 × 客单（与订单表强一致）。"""
    enter = df["_enter"].values
    payers = df["_payers"].values.astype(float)
    stay = enter * rng.uniform(0.25, 0.45, size=len(df))
    interact = stay * rng.uniform(0.15, 0.35, size=len(df))
    placed = payers / rng.uniform(0.86, 0.93, size=len(df))
    # 约束：付款 ≤ 下单 ≤ 互动 ≤ 停留 ≤ 进入
    interact = np.maximum(interact, placed * 2.0)
    interact = np.minimum(interact, stay * 0.95)
    stay = np.minimum(stay, enter * 0.85)
    exposure = enter / rng.uniform(0.08, 0.12, size=len(df))
    gmv = payers * lognorm(170, 0.35, size=len(df))           # 客单 ~170
    followers = exposure * rng.uniform(0.001, 0.004, size=len(df))
    df["total_exposure"] = np.round(exposure).astype(int)
    df["total_enter"] = np.round(enter).astype(int)
    df["total_stay"] = np.round(stay).astype(int)
    df["total_interact"] = np.round(interact).astype(int)
    df["total_order_placed"] = np.round(placed).astype(int)
    df["total_paid"] = payers.astype(int)
    df["gmv"] = np.round(gmv, 2)
    df["new_followers"] = np.round(followers).astype(int)
    df["sku_cnt"] = np.round(lognorm(45, 0.3, size=len(df), clip=(12, 120))).astype(int)
    df["anchor"] = rng.choice(
        ["主播小胖(负责人)", "主播小陇", "主播阿甘", "主播小花"],
        size=len(df), p=[0.45, 0.25, 0.18, 0.12])
    # 主推品类：宽粉专场→宽粉；助农专场→应季水果/夏菜；节庆/常态→按电商权重
    mains = []
    for _, r in df.iterrows():
        if r["theme"] == "宽粉工厂专场":
            mains.append("定西宽粉及薯制品")
        elif r["theme"] == "助农专场":
            mains.append(str(rng.choice(["甘肃生鲜水果", "高原夏菜及土豆", "干货山珍", "肉禽蛋品"],
                                        p=[0.45, 0.30, 0.15, 0.10])))
        else:
            mains.append(wchoice(L1_NAMES, [W_ECOM.get(k, 0.01) for k in L1_NAMES]))
    df["main_category"] = mains
    return df


def gen_minute_traffic(sessions):
    """分钟级流量（每 2 分钟采样一个点）：在线人数曲线 + 曝光/互动/下单增量。
    场次级汇总 = 分钟级累加，保证跨表一致。"""
    rows = []
    rid = 1
    for _, s in sessions.iterrows():
        n_pts = int(s["duration_min"] // 2)
        peak = max(s["total_enter"] / rng.uniform(7, 10), 30)   # 峰值在线 ≈ 场观/8
        total_orders = s["total_order_placed"]
        # 在线曲线：10 分钟内爬峰 → 平台期缓降 → 尾部掉量
        curve = np.zeros(n_pts)
        for i in range(n_pts):
            t = (i + 1) * 2
            if t <= 10:
                f = t / 10.0
            elif t <= s["duration_min"] * 0.6:
                f = 1.0
            else:
                f = 1.0 - 0.5 * (t - s["duration_min"] * 0.6) / (s["duration_min"] * 0.4)
            curve[i] = max(peak * f * rng.uniform(0.92, 1.08), 15)
        # 曝光增量：基线 + 第 15/30/45 分钟流量尖峰
        exp_delta = s["total_exposure"] / n_pts
        order_w = np.ones(n_pts)
        for spike_min in (15, 30, 45, 60):
            idx = spike_min // 2
            if idx < n_pts:
                order_w[idx] = 6.0
        order_w = order_w / order_w.sum()
        orders_alloc = np.maximum(np.round(rng.multinomial(total_orders, order_w)), 0)
        enter_alloc = np.maximum(
            np.round(rng.multinomial(s["total_enter"], np.ones(n_pts) / n_pts)), 0)
        interact_w = np.ones(n_pts) / n_pts * (1 + 0.5 * (curve / curve.max()))
        interact_w = interact_w / interact_w.sum()
        interact_alloc = np.maximum(
            np.round(rng.multinomial(s["total_interact"], interact_w)), 0)
        for i in range(n_pts):
            rows.append({
                "id": rid, "session_id": int(s["session_id"]),
                "minute_index": (i + 1) * 2,
                "viewers_online": int(round(curve[i])),
                "exposure_delta": int(round(exp_delta * rng.uniform(0.5, 1.5))),
                "enter_delta": int(enter_alloc[i]),
                "comment_cnt": int(round(curve[i] * rng.uniform(0.03, 0.10))),
                "like_cnt": int(round(curve[i] * rng.uniform(0.6, 1.8))),
                "follow_delta": int(round(s["new_followers"] / n_pts * rng.uniform(0.3, 1.7))),
                "order_cnt": int(orders_alloc[i]),
                "pay_user_cnt": int(round(orders_alloc[i] * rng.uniform(0.86, 0.93))),
            })
            rid += 1
    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# 3. 电商订单与明细
# ------------------------------------------------------------------
def build_sku_pools(sku_df):
    """按 L1 建 SKU 池，池内热度 Zipf：popular[rank] ∝ 1/rank^0.85。"""
    pools = {}
    for l1 in L1_NAMES:
        sub = sku_df[sku_df["category_l1"] == l1].reset_index(drop=True)
        ranks = np.arange(1, len(sub) + 1)
        heat = 1.0 / np.power(ranks, 0.85)
        pools[l1] = (sub["sku_id"].tolist(),
                     sub["retail_price"].tolist(),
                     sub["gross_margin_rate"].tolist(),
                     (heat / heat.sum()).tolist())
    return pools


def sample_item_price(pools, l1):
    ids, prices, _, heat = pools[l1]
    k = int(rng.choice(len(ids), p=heat))
    return ids[k], prices[k]


def gen_orders_items(sessions, users, sku_df, pools):
    """生成 29,000 单（含 15% 取消/退款）+ 明细。
    用户结构：约 70% 单次购买者 + 30% 复购族（复购次数服从几何分布，平均 2 单），
    使复购率约 27%、RFM 的 F/M 有真实区分度（8 层均可分）。
    直播间有效单数 = 场次 total_paid 之和（跨表一致）。"""
    user_ids = users["user_id"].values
    sess_ids = sessions["session_id"].values
    sess_payers = sessions["total_paid"].values
    sess_date = sessions["live_date"].values
    sess_start = sessions["start_time"].values
    sess_dur = sessions["duration_min"].values

    # 有效单渠道目标
    paid_live = int(sess_payers.sum())          # 由场次付款人数决定（强一致）
    paid_showcase = 5_400
    paid_mall = 3_300
    paid_total = paid_live + paid_showcase + paid_mall
    n_cancel = N_ORDERS - paid_total            # 取消/退款单数

    # ---- 用户订单数建模（核心口径）----
    # 思路：为每个潜在买家抽订单数 k~Geometric(p)，P(k≥2)=1-p 即目标复购率。
    # 逐个累积直到凑满目标订单数 → 买家数自然由分布决定（不需要事后缩放或校正）
    total_orders_target = paid_total + n_cancel
    geom_p = 0.78                                     # 复购率目标 ≈ 22%
    max_buyers = min(N_USERS, total_orders_target)     # 买家数上限=用户池/订单数
    freq = rng.geometric(geom_p, size=max_buyers)
    freq = np.minimum(freq, 12)
    # 逐个累积，找到刚够覆盖目标订单数的买家数
    cum = np.cumsum(freq)
    n_buyers = int(np.searchsorted(cum, total_orders_target) + 1)
    n_buyers = max(1, min(n_buyers, max_buyers))
    freq = freq[:n_buyers].copy()
    # 若累积不足以覆盖目标（截断尾部导致），用更高频买家补齐
    while int(freq.sum()) < total_orders_target:
        freq[int(rng.integers(0, n_buyers))] += 1
    # 最后一个买家截断，使坑位总数恰好 = 目标订单数
    surplus = int(freq.sum()) - total_orders_target
    idx = 0
    while surplus > 0 and idx < n_buyers:
        if freq[-1 - (idx % n_buyers)] > 1:
            freq[-1 - (idx % n_buyers)] -= 1
            surplus -= 1
        idx += 1
    n_showcase = paid_showcase
    n_mall = paid_mall

    promo_types = ["无", "限时秒杀", "满减", "助农补贴", "组合装"]
    promo_p = [0.55, 0.10, 0.15, 0.12, 0.08]
    promo_disc = {"无": 1.0, "限时秒杀": 0.85, "满减": 0.92,
                  "助农补贴": 0.90, "组合装": 0.88}
    sku_cost = dict(zip(sku_df["sku_id"], sku_df["cost_price"]))
    buyer_user_ids = np.linspace(1, N_USERS, n_buyers).astype(int)

    # 展开订单坑位（每单一个坑位），再打散
    user_slots = np.repeat(buyer_user_ids, freq)
    rng.shuffle(user_slots)

    # ---- 渠道分配：按目标占比切分坑位（同一用户可跨渠道，符合真实行为）----
    # 直播间坑位指向具体场次（保证场次付款人数一致）；橱窗/商城仅需渠道与日期
    order_pool = []                       # (user_id, channel, session_id|None)
    ptr = 0
    for sid, payers in zip(sess_ids, sess_payers):
        n_take = int(payers)
        for u in user_slots[ptr:ptr + n_take]:
            order_pool.append((int(u), "直播间", int(sid)))
        ptr += n_take
    for u in user_slots[ptr:ptr + n_showcase]:
        order_pool.append((int(u), "短视频橱窗", None))
    ptr += n_showcase
    for u in user_slots[ptr:ptr + n_mall]:
        order_pool.append((int(u), "商城搜索", None))
    ptr += n_mall
    # ② 取消/退款单：直播间 55% / 橱窗 30% / 商城 15%
    n_c_live = int(n_cancel * 0.55)
    n_c_show = int(n_cancel * 0.30)
    n_c_mall = n_cancel - n_c_live - n_c_show
    bad_users = user_slots[ptr:ptr + n_cancel]
    if len(bad_users) < n_cancel:
        pad = rng.choice(buyer_user_ids, size=n_cancel - len(bad_users), replace=True)
        bad_users = np.concatenate([bad_users, pad])
    bi = 0
    for _ in range(n_c_live):
        sid = int(rng.choice(sess_ids))
        order_pool.append((int(bad_users[bi]), "直播间", sid)); bi += 1
    for _ in range(n_c_show):
        order_pool.append((int(bad_users[bi]), "短视频橱窗", None)); bi += 1
    for _ in range(n_c_mall):
        order_pool.append((int(bad_users[bi]), "商城搜索", None)); bi += 1

    orders = []
    sess_map = {}      # session_id -> (date, start, dur)
    for sid, d, st, dur in zip(sess_ids, sess_date, sess_start, sess_dur):
        sess_map[int(sid)] = (d, st, dur)

    for u_id, channel, sid in order_pool:
        if channel == "直播间" and sid is not None:
            d, st, dur = sess_map[sid]
            sh, sm = int(st[:2]), int(st[3:])
            minutes_in = int(rng.integers(5, dur + (120 if rng.random() < 0.15 else 0)))
            hh = sh + (sm + minutes_in) // 60
            mm = (sm + minutes_in) % 60
        else:
            d = rand_date(DAY_W)
            hh, mm = int(rng.integers(8, 23)), int(rng.integers(0, 60))
        if rng.random() < 0.15:      # 15% 非付款状态
            status = str(rng.choice(["已取消", "已退款"], p=[0.53, 0.47]))
        else:
            status = str(rng.choice(["已完成", "已发货", "已付款"],
                                    p=[0.85, 0.08, 0.07]))
        orders.append({"_channel": channel, "_uid": int(u_id),
                       "_date": d, "_hh": hh, "_mm": mm,
                       "_status": status, "_sid": sid})

    rng.shuffle(orders)
    print(f"  订单构造完成: {len(orders)} 单")

    # ---- 明细生成 ----
    provinces = ["甘肃", "广东", "江苏", "浙江", "北京", "上海", "四川", "陕西",
                 "河南", "山东", "湖北", "福建", "重庆", "新疆", "青海"]
    prob_w = np.array([30, 8, 7, 6, 5, 5, 6, 6, 5, 5, 4, 4, 3, 3, 3], dtype=float)
    # 电商品类条目数权重 = GMV 权重 / 品类中位价 → 归一
    l1_median_price = {l1: np.median(
        sku_df.loc[sku_df["category_l1"] == l1, "retail_price"]) for l1 in L1_NAMES}
    item_w = np.array([W_ECOM[l1] / l1_median_price[l1] for l1 in L1_NAMES])
    item_w = item_w / item_w.sum()
    l1_prob = item_w / item_w.sum()

    item_rows = []
    order_rows = []
    oid = 0
    for o in orders:
        oid += 1
        dt_str = f"{o['_date']} {o['_hh']:02d}:{o['_mm']:02d}:00"
        order_id = f"GXP{str(o['_date']).replace('-', '')}{oid:06d}"
        n_items = int(rng.choice([1, 2, 3], p=[0.60, 0.32, 0.08]))
        amount = 0.0
        discount = 0.0
        for _ in range(n_items):
            l1 = L1_NAMES[int(rng.choice(len(L1_NAMES), p=l1_prob))]
            sku_id_v, unit_price = sample_item_price(pools, l1)
            qty = int(rng.choice([1, 2, 3], p=[0.72, 0.22, 0.06]))
            promo = str(rng.choice(promo_types, p=promo_p))
            eff = unit_price * qty * promo_disc[promo]
            discount += unit_price * qty - eff
            amount += eff
            item_rows.append({
                "order_id": order_id, "sku_id": sku_id_v, "quantity": qty,
                "unit_price": round(unit_price, 2),
                "cost_price": round(float(sku_cost[sku_id_v]), 2),
                "promotion_type": promo,
            })
        freight = 0.0 if amount >= 99 else round(float(rng.uniform(6, 12)), 1)
        province = str(rng.choice(provinces, p=prob_w / prob_w.sum()))
        order_rows.append({
            "order_id": order_id, "user_id": o["_uid"], "order_time": dt_str,
            "channel": o["_channel"], "session_id": o["_sid"],
            "order_status": o["_status"], "item_cnt": n_items,
            "pay_amount": round(amount + freight, 2),
            "discount_amount": round(discount, 2), "freight": freight,
            "province": province,
        })
    orders_df = pd.DataFrame(order_rows)
    items_df = pd.DataFrame(item_rows)
    return orders_df, items_df


# ------------------------------------------------------------------
# 4. B2B 供货
# ------------------------------------------------------------------
def gen_b2b(sku_df, ecom_gmv):
    """600 单 B2B 供货；总额与各品类金额均确定性校准（电商GMV × 25/52，品类按 W_B2B）。"""
    target_total = ecom_gmv * SHARE_B2B / SHARE_ECOM
    customers = []
    cust_types = (["火锅餐饮"] * 8) + (["商超"] * 7) + (["特产店"] * 8) + (["食品加工"] * 2)
    for i, ct in enumerate(cust_types, 1):
        customers.append({
            "customer_name": f"{fake.company_prefix()}{ {'火锅餐饮': '火锅', '商超': '生活超市', '特产店': '特产行', '食品加工': '食品'}[ct] }",
            "customer_type": ct,
        })
    rows = []
    # 客户活跃度：头部客户复购高
    freq_w = lognorm(1.0, 1.0, size=len(customers))
    cust_choices = rng.choice(len(customers), size=N_B2B,
                              p=freq_w / freq_w.sum())
    # B2B 品类【笔数】权重 = GMV 权重 / 品类批发均价（均价高的品类笔数更少）
    b2b_l1 = list(W_B2B.keys())
    avg_price = {l1: float(np.mean(B2B_WHOLESALE_PRICE[l1])) for l1 in b2b_l1}
    count_w = np.array([W_B2B[k] / avg_price[k] for k in b2b_l1])
    count_w = count_w / count_w.sum()
    for i in range(N_B2B):
        c = customers[cust_choices[i]]
        l1 = b2b_l1[int(rng.choice(len(b2b_l1), p=count_w))]
        sub = sku_df[sku_df["category_l1"] == l1]
        sku = sub.iloc[int(rng.integers(0, len(sub)))]
        p_lo, p_hi = B2B_WHOLESALE_PRICE[l1]
        price = float(np.round(rng.uniform(p_lo, p_hi), 2))
        qty = float(lognorm(150, 0.75, clip=(30, 900)))
        rows.append({
            "b2b_id": 10000 + i, "customer_name": c["customer_name"],
            "customer_type": c["customer_type"],
            "order_date": str(rand_date(DAY_W)), "sku_id": int(sku["sku_id"]),
            "quantity_kg": round(qty, 1), "unit_price": price,
            "amount": 0.0,   # 稍后逐品类校准填写
            "_l1": l1,
        })
    df = pd.DataFrame(rows)
    # 逐品类确定性校准：该品类金额 = 目标总额 × W_B2B[l1]
    for l1 in b2b_l1:
        mask = df["_l1"] == l1
        if mask.sum() == 0:
            continue
        raw = (df.loc[mask, "quantity_kg"] * df.loc[mask, "unit_price"]).sum()
        if raw <= 0:
            continue
        scale = (target_total * W_B2B[l1]) / raw
        df.loc[mask, "quantity_kg"] = (df.loc[mask, "quantity_kg"] * scale).round(1)
        df.loc[mask, "amount"] = (df.loc[mask, "quantity_kg"] * df.loc[mask, "unit_price"]).round(2)
    df = df.drop(columns=["_l1"])
    return df


# ------------------------------------------------------------------
# 5. 采购 / 仓储 / 配送
# ------------------------------------------------------------------
def gen_purchases(sku_df, suppliers, cogs_targets):
    """采购单及明细（750 单）。
    校准：各品类采购金额 ≈ 该品类销售成本（电商明细成本 + B2B 批发成本
    + 门店原料成本）× PURCH_STOCKUP 备货系数，逐品类确定性缩放数量，
    保证品类 ROI 分析（毛利/投入）落在业务合理区间。"""
    rows, item_rows = [], []
    # 采购品类权重 ≈ 销售规模（宽粉原料/水果/夏菜为主）
    purch_w = {l1: W_ECOM[l1] * 0.35 + W_B2B.get(l1, 0) * 0.65 for l1 in L1_NAMES}
    p_l1 = [k for k in purch_w if purch_w[k] > 0]
    p_w = np.array([purch_w[k] for k in p_l1]); p_w /= p_w.sum()
    iid = 1
    for pid in range(1, N_PURCHASES + 1):
        d = rand_date(DAY_W)
        arrival = d + timedelta(days=int(rng.integers(1, 8)))
        n_items = int(rng.choice([1, 2, 3], p=[0.55, 0.30, 0.15]))
        total = 0.0
        items = []
        for _ in range(n_items):
            l1 = p_l1[int(rng.choice(len(p_l1), p=p_w))]
            sub = sku_df[sku_df["category_l1"] == l1]
            sku = sub.iloc[int(rng.integers(0, len(sub)))]
            qty_kg = float(lognorm(420, 0.8, clip=(50, 4000)))
            unit_cost = round(float(sku["cost_price"]) * rng.uniform(0.85, 1.0), 2)
            amt = qty_kg * unit_cost
            grade = str(rng.choice(["A1", "A2", "A3"], p=[0.55, 0.38, 0.07]))
            items.append((int(sku["sku_id"]), qty_kg, unit_cost, amt, grade))
            total += amt
        sup = suppliers.iloc[int(rng.integers(0, len(suppliers)))]
        rows.append({
            "purchase_id": pid, "supplier_id": int(sup["supplier_id"]),
            "purchase_date": str(d), "arrival_date": str(arrival),
            "total_amount": round(total, 2),
            "quality_grade": items[0][4],
            "status": str(rng.choice(["已入库", "到货", "在途"], p=[0.72, 0.18, 0.10])),
        })
        for sku_id_v, qty, cost, amt, grade in items:
            item_rows.append({
                "id": iid, "purchase_id": pid, "sku_id": sku_id_v,
                "quantity_kg": round(qty, 1), "unit_cost": cost,
                "amount": round(amt, 2),
                "quality_grade": grade,
                "rejected_kg": round(qty * (rng.uniform(0.01, 0.06) if grade == "A3"
                                            else rng.uniform(0.0, 0.025)), 1),
            })
            iid += 1
    # ---------- 逐品类确定性校准 ----------
    df_items = pd.DataFrame(item_rows)
    sku_l1_map = dict(zip(sku_df["sku_id"], sku_df["category_l1"]))
    df_items["_l1"] = df_items["sku_id"].map(sku_l1_map)
    for l1, target in cogs_targets.items():
        mask = df_items["_l1"] == l1
        if mask.sum() == 0 or target <= 0:
            continue
        raw = float((df_items.loc[mask, "quantity_kg"] *
                     df_items.loc[mask, "unit_cost"]).sum())
        if raw <= 0:
            continue
        scale = (target * PURCH_STOCKUP) / raw
        df_items.loc[mask, "quantity_kg"] = (
            df_items.loc[mask, "quantity_kg"] * scale).round(1)
        df_items.loc[mask, "rejected_kg"] = (
            df_items.loc[mask, "rejected_kg"] * scale).round(1)
    df_items["amount"] = (df_items["quantity_kg"] * df_items["unit_cost"]).round(2)
    df_items = df_items.drop(columns=["_l1"])
    # 重算采购单总额
    rows_df = pd.DataFrame(rows)
    totals = df_items.groupby("purchase_id")["amount"].sum()
    rows_df["total_amount"] = (rows_df["purchase_id"].map(totals)).round(2)
    return rows_df, df_items


def gen_warehouse_stock(sku_df):
    """20 个核心 SKU × 2 仓 × 双周快照（46 期）。"""
    # 核心款：宽粉系 + 爆款水果/土豆/百合/蜂蜜等
    core = []
    for l1, want in [("定西宽粉及薯制品", 8), ("甘肃生鲜水果", 4), ("高原夏菜及土豆", 3),
                     ("药食同源", 2), ("蜂产品", 1), ("小杂粮粮油", 1), ("干货山珍", 1)]:
        sub = sku_df[(sku_df["category_l1"] == l1) & (sku_df["status"] == "在售")]
        core += sub.sample(n=want, random_state=SEED)["sku_id"].tolist()
    snapshot_dates = [DATE_START + timedelta(days=14 * k) for k in range(46)]
    rows = []
    rid = 1
    for sku_id_v in core:
        l1 = sku_df.loc[sku_df["sku_id"] == sku_id_v, "category_l1"].iloc[0]
        base_stock = {"定西宽粉及薯制品": 9000, "甘肃生鲜水果": 5200,
                      "高原夏菜及土豆": 12000, "药食同源": 900,
                      "蜂产品": 600, "小杂粮粮油": 1500, "干货山珍": 800}[l1]
        outflow = base_stock / rng.uniform(12, 28)     # 日均出库 kg
        for wh in (1, 2):
            for sd in snapshot_dates:
                seasonal = 1.0
                if l1 in ("甘肃生鲜水果", "高原夏菜及土豆") and sd.month in (9, 10, 11):
                    seasonal = 2.2      # 秋收季囤货
                if l1 == "定西宽粉及薯制品" and sd.month in (11, 12, 1):
                    seasonal = 1.5      # 年货备货
                stock = base_stock * seasonal * rng.uniform(0.55, 1.45) / (1.4 if wh == 2 else 1.0)
                rows.append({
                    "id": rid, "snapshot_date": str(sd), "warehouse_id": wh,
                    "sku_id": int(sku_id_v),
                    "stock_kg": round(stock, 1),
                    "in_transit_kg": round(stock * rng.uniform(0.05, 0.25), 1),
                    "avg_daily_outflow_kg": round(outflow * rng.uniform(0.8, 1.2) * seasonal * 0.6, 1),
                    "avg_days_in_stock": round(stock / max(outflow, 1) * rng.uniform(0.8, 1.2), 1),
                })
                rid += 1
    return pd.DataFrame(rows)


def gen_deliveries(orders_df, stores, b2b_df, sku_df):
    """3,600 单：电商抽样 2,400 + 门店补货 600 + B2B 600。
    2025-04 起试点"集中仓储+分级配送"新模式 → 时效/损耗/运费改善。"""
    regions = [("甘肃", 0.18, (1, 2)), ("西北", 0.10, (2, 3)), ("华北", 0.15, (3, 5)),
               ("华东", 0.22, (3, 5)), ("华南", 0.13, (4, 6)), ("西南", 0.12, (4, 6)),
               ("东北", 0.10, (4, 7))]
    reg_names = [r[0] for r in regions]
    reg_p = np.array([r[1] for r in regions])
    reg_lead = {r[0]: r[2] for r in regions}      # 区域 → 时效区间
    fresh_l1 = {"甘肃生鲜水果", "高原夏菜及土豆", "肉禽蛋品"}
    rows = []
    did = 50000
    # 电商：已发货/已完成订单抽样
    shipped = orders_df[orders_df["order_status"].isin(["已发货", "已完成"])]
    sampled = shipped.sample(n=N_DELIVERY_ECOM, random_state=SEED)
    for _, r in sampled.iterrows():
        region = reg_names[int(rng.choice(len(reg_names), p=reg_p / reg_p.sum()))]
        d = datetime.strptime(r["order_time"], "%Y-%m-%d %H:%M:%S").date() + \
            timedelta(days=int(rng.integers(0, 2)))
        is_new_mode = d >= date(2025, 4, 1) and rng.random() < 0.75
        lo, hi = reg_lead[region]
        lead = int(rng.integers(lo, hi + 1))
        if is_new_mode:
            lead = max(1, int(round(lead * rng.uniform(0.55, 0.75))))
        weight = float(lognorm(3.2, 0.7, clip=(0.5, 30)))
        is_fresh = bool(rng.random() < 0.32)
        if is_new_mode:
            loss_rate = rng.uniform(0.012, 0.025) if is_fresh else rng.uniform(0.002, 0.005)
            freight_unit = rng.uniform(1.5, 2.1)
        else:
            loss_rate = rng.uniform(0.025, 0.045) if is_fresh else rng.uniform(0.003, 0.008)
            freight_unit = rng.uniform(1.8, 2.6)
        rows.append({
            "delivery_id": did, "biz_type": "电商订单", "ref_id": r["order_id"],
            "from_warehouse": int(rng.choice([1, 2], p=[0.7, 0.3]) if not is_new_mode else 1),
            "to_region": region, "ship_date": str(d),
            "arrive_date": str(d + timedelta(days=lead)),
            "lead_time_days": lead,
            "box_cnt": max(1, int(round(weight / rng.uniform(3, 8)))),
            "weight_kg": round(weight, 2),
            "loss_kg": round(weight * loss_rate, 2),
            "freight_cost": round(weight * freight_unit + (0 if is_new_mode else 3), 1),
            "delivery_mode": "新模式(集中仓储+分级配送)" if is_new_mode else "旧模式(分散直发+统配)",
        })
        did += 1
    # 门店补货：每店 ~150 单（2-5 天一配）
    for _, st in stores.iterrows():
        n = 150
        for _ in range(n):
            d = rand_date(DAY_W)
            is_new_mode = d >= date(2025, 4, 1) and rng.random() < 0.75
            lead = int(rng.integers(1, 2)) if not is_new_mode else 1
            weight = float(lognorm(60, 0.5, clip=(15, 220)))
            loss_rate = (rng.uniform(0.008, 0.015) if is_new_mode
                         else rng.uniform(0.018, 0.03))
            rows.append({
                "delivery_id": did, "biz_type": "门店补货",
                "ref_id": f"STORE{st['store_id']:02d}",
                "from_warehouse": 1, "to_region": "甘肃",
                "ship_date": str(d), "arrive_date": str(d + timedelta(days=lead)),
                "lead_time_days": lead,
                "box_cnt": max(1, int(round(weight / 12))),
                "weight_kg": round(weight, 2),
                "loss_kg": round(weight * loss_rate, 2),
                "freight_cost": round(weight * rng.uniform(0.9, 1.3), 1),
                "delivery_mode": "新模式(集中仓储+分级配送)" if is_new_mode else "旧模式(分散直发+统配)",
            })
            did += 1
    # B2B 供货配送
    for _, b in b2b_df.iterrows():
        d = datetime.strptime(b["order_date"], "%Y-%m-%d").date()
        is_new_mode = d >= date(2025, 4, 1) and rng.random() < 0.75
        region = reg_names[int(rng.choice(len(reg_names), p=reg_p / reg_p.sum()))]
        lo, hi = reg_lead[region]
        lead = int(rng.integers(lo, hi + 1))
        if is_new_mode:
            lead = max(1, int(round(lead * rng.uniform(0.55, 0.75))))
        weight = float(b["quantity_kg"])
        loss_rate = rng.uniform(0.004, 0.010) if is_new_mode else rng.uniform(0.010, 0.022)
        rows.append({
            "delivery_id": did, "biz_type": "B2B供货", "ref_id": str(b["b2b_id"]),
            "from_warehouse": 1, "to_region": region,
            "ship_date": str(d), "arrive_date": str(d + timedelta(days=lead)),
            "lead_time_days": lead,
            "box_cnt": max(1, int(round(weight / 15))),
            "weight_kg": round(weight, 1),
            "loss_kg": round(weight * loss_rate, 2),
            "freight_cost": round(weight * rng.uniform(1.1, 1.6), 1),
            "delivery_mode": "新模式(集中仓储+分级配送)" if is_new_mode else "旧模式(分散直发+统配)",
        })
        did += 1
    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# 6. 门店日销售
# ------------------------------------------------------------------
def gen_store_sales(stores, ecom_gmv):
    """4 店 × 731 天 × 4 品类；总额校准至 电商GMV × 23/52。"""
    target_total = ecom_gmv * SHARE_STORE / SHARE_ECOM
    # 每店每日总销售 = base × 周末系数 × 季节系数 × 增长系数 × 噪声
    store_ticket = {1: 28.0, 2: 27.0, 3: 26.0, 4: 25.0}
    # 先按系数矩阵生成原始日销，再整体缩放到目标
    raw_days = []
    for d in ALL_DAYS:
        dow = d.weekday()
        dow_f = 1.16 if dow >= 5 else (0.94 if dow == 0 else 1.0)
        season_f = 1.12 if d.month in (11, 12, 1) else (0.93 if d.month in (6, 7, 8) else 1.0)
        growth = 1.0 + 0.15 * (d - DATE_START).days / 731
        for _, st in stores.iterrows():
            v = st["daily_base"] * dow_f * season_f * growth * rng.uniform(0.88, 1.12)
            raw_days.append((st["store_id"], d, v))
    raw_total = sum(x[2] for x in raw_days)
    scale = target_total / raw_total
    rows = []
    rid = 1
    for store_id, d, v in raw_days:
        day_total = v * scale
        # 品类拆分（伴手礼盒占比旗舰店更高）
        if store_id == 1:
            cat_p = [0.48, 0.22, 0.13, 0.17]
        else:
            cat_p = [0.51, 0.23, 0.14, 0.12]
        cat_sales = rng.multinomial(int(round(day_total * 100)), cat_p) / 100.0
        # 修正取整误差
        cat_sales[-1] = round(day_total - cat_sales[:-1].sum(), 2)
        for cat, sales in zip(STORE_CATS, cat_sales):
            if sales <= 0:
                continue
            ticket = store_ticket[store_id] * rng.uniform(0.92, 1.08)
            order_cnt = max(1, int(round(sales / ticket)))
            rows.append({
                "id": rid, "store_id": store_id, "sale_date": str(d),
                "category": cat, "order_cnt": order_cnt,
                "customer_cnt": max(1, int(round(order_cnt * rng.uniform(0.92, 1.0)))),
                "foot_traffic": int(round(order_cnt * rng.uniform(1.8, 2.6))),
                "sales_amount": round(sales, 2),
                "discount_amount": round(sales * rng.uniform(0.02, 0.06), 2),
            })
            rid += 1
    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# 7. 脏数据注入（约 2%）
# ------------------------------------------------------------------
def inject_dirty(orders, items, users, deliveries, store_sales):
    """向原始层注入重复/缺失/异常/格式问题，返回注入统计。"""
    stats = {}

    def dirty_idx(n, k):
        return rng.choice(n, size=k, replace=False)

    # orders：重复 130 / 省份缺失 150 / 金额异常 90 / 状态非法 80 / 时间格式错 120
    k = 130
    dup = orders.iloc[dirty_idx(len(orders), k)].copy()
    orders = pd.concat([orders, dup], ignore_index=True)
    stats["orders_重复行"] = k
    idx = dirty_idx(len(orders), 150)
    orders.loc[idx, "province"] = ""
    stats["orders_省份缺失"] = 150
    idx = dirty_idx(len(orders), 90)
    even_idx, odd_idx = idx[idx % 2 == 0], idx[idx % 2 == 1]
    orders.loc[even_idx, "pay_amount"] = -1
    orders.loc[odd_idx, "pay_amount"] = 99999
    stats["orders_金额异常"] = 90
    idx = dirty_idx(len(orders), 80)
    orders.loc[idx, "order_status"] = rng.choice(["待付款?", "PAID", "已完成 ", "已 完成"],
                                                 size=80)
    stats["orders_状态非法"] = 80
    idx = dirty_idx(len(orders), 120)
    bad_times = ["2024/3/5 14:30:00", "2025-6-18 8:5:00", "2024.12.21 20:00:00"]
    orders.loc[idx, "order_time"] = [str(rng.choice(bad_times)) for _ in range(120)]
    stats["orders_时间格式错误"] = 120

    # users：年龄异常 70 / 性别异常 50 / 省份格式不一 80
    idx = dirty_idx(len(users), 70)
    even_idx, odd_idx = idx[idx % 2 == 0], idx[idx % 2 == 1]
    users.loc[even_idx, "age"] = rng.choice([200, 150, 260], size=len(even_idx))
    users.loc[odd_idx, "age"] = rng.choice([-5, 0, 3], size=len(odd_idx))
    stats["users_年龄异常"] = 70
    idx = dirty_idx(len(users), 50)
    users.loc[idx, "gender"] = rng.choice(["", "1", "未知"], size=50)
    stats["users_性别异常"] = 50
    idx = dirty_idx(len(users), 80)
    users.loc[idx, "province"] = rng.choice(["甘肃省", " GANSU", "甘肃 ", "gansu"], size=80)
    stats["users_省份格式不一"] = 80

    # items：数量异常 100 / 价格异常 60
    idx = dirty_idx(len(items), 100)
    even_idx, odd_idx = idx[idx % 2 == 0], idx[idx % 2 == 1]
    items.loc[even_idx, "quantity"] = 0
    items.loc[odd_idx, "quantity"] = -2
    stats["items_数量异常"] = 100
    idx = dirty_idx(len(items), 60)
    items.loc[idx, "unit_price"] = 0.01
    stats["items_价格异常"] = 60

    # deliveries：损耗超重 30 / 时效为负 20
    idx = dirty_idx(len(deliveries), 30)
    deliveries.loc[idx, "loss_kg"] = deliveries.loc[idx, "weight_kg"] * 3
    stats["deliveries_损耗超重"] = 30
    idx = dirty_idx(len(deliveries), 20)
    deliveries.loc[idx, "lead_time_days"] = -1
    stats["deliveries_时效为负"] = 20

    # store_sales：负销售额 25 / 重复行 30
    idx = dirty_idx(len(store_sales), 25)
    store_sales.loc[idx, "sales_amount"] *= -1
    stats["store_sales_负销售额"] = 25
    dup = store_sales.iloc[dirty_idx(len(store_sales), 30)].copy()
    store_sales = pd.concat([store_sales, dup], ignore_index=True)
    stats["store_sales_重复行"] = 30

    return orders, items, users, deliveries, store_sales, stats


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------
def main():
    print("=" * 62)
    print("「甘小胖」模拟数据生成器  SEED =", SEED)
    print("=" * 62)

    print("[1/9] 生成维表 ...")
    suppliers = gen_suppliers()
    sku = gen_sku(suppliers)
    users = gen_users()
    stores, warehouses = gen_stores_warehouses()
    print(f"  SKU={len(sku)} 供应商={len(suppliers)} 用户={len(users)}")

    print("[2/9] 生成直播场次 ...")
    sessions = gen_live_sessions()
    sessions = fill_session_funnel(sessions)

    print("[3/9] 生成分钟级流量 ...")
    minutes = gen_minute_traffic(sessions)
    print(f"  场次={len(sessions)} 分钟流量={len(minutes)}")

    print("[4/9] 生成电商订单与明细 ...")
    pools = build_sku_pools(sku)
    orders, items = gen_orders_items(sessions, users, sku, pools)
    # 电商有效 GMV（付款口径）
    valid = orders[orders["order_status"].isin(["已付款", "已发货", "已完成"])]
    ecom_gmv = float(valid["pay_amount"].sum())
    print(f"  订单={len(orders)} 明细={len(items)} 电商GMV={ecom_gmv:,.0f} 元")

    print("[5/9] 生成 B2B 供货 ...")
    b2b = gen_b2b(sku, ecom_gmv)
    b2b_gmv = float(b2b["amount"].sum())

    print("[6/9] 生成门店日销售 ...")
    store_sales = gen_store_sales(stores, ecom_gmv)
    store_gmv = float(store_sales["sales_amount"].sum())
    print(f"  门店GMV={store_gmv:,.0f} 元")

    print("[7/9] 生成采购/仓储/配送（按品类销售成本校准）...")
    # 品类销售成本 = 电商明细成本 + B2B 批发成本 + 门店原料成本（采购校准目标）
    sku_l1_pre = dict(zip(sku["sku_id"], sku["category_l1"]))
    valid_ids_pre = set(valid["order_id"])
    ecom_cogs = (items[items["order_id"].isin(valid_ids_pre)]
                 .assign(c=lambda x: x["quantity"] * x["cost_price"])
                 .assign(l1=lambda x: x["sku_id"].map(sku_l1_pre))
                 .groupby("l1")["c"].sum())
    b2b_cogs = (b2b.assign(l1=lambda x: x["sku_id"].map(sku_l1_pre))
                .assign(c=lambda x: x["amount"] * B2B_COST_RATIO)
                .groupby("l1")["c"].sum())
    store_cogs = {}
    for cat, (l1, _) in STORE_CAT_MAP.items():
        v = float(store_sales.loc[store_sales["category"] == cat, "sales_amount"].sum())
        store_cogs[l1] = store_cogs.get(l1, 0) + v * (1 - STORE_CAT_MARGIN[cat])
    cogs_targets = {}
    for l1 in L1_NAMES:
        cogs_targets[l1] = (float(ecom_cogs.get(l1, 0)) + float(b2b_cogs.get(l1, 0))
                            + store_cogs.get(l1, 0))
    purchases, purchase_items = gen_purchases(sku, suppliers, cogs_targets)
    stock = gen_warehouse_stock(sku)
    deliveries = gen_deliveries(orders, stores, b2b, sku)
    print(f"  采购单={len(purchases)} 采购总额={float(purchases['total_amount'].sum()):,.0f} 元 "
          f"库存快照={len(stock)} 配送={len(deliveries)}")

    # ---------- 校准统计（基于注入脏数据前的干净数据）----------
    total_gmv = ecom_gmv + b2b_gmv + store_gmv
    shares = (ecom_gmv / total_gmv, b2b_gmv / total_gmv, store_gmv / total_gmv)
    sku_l1 = dict(zip(sku["sku_id"], sku["category_l1"]))
    valid_order_ids = set(valid["order_id"])
    ecom_cat = (items[items["order_id"].isin(valid_order_ids)]
                .assign(amount=lambda x: x["quantity"] * x["unit_price"])
                .assign(l1=lambda x: x["sku_id"].map(sku_l1))
                .groupby("l1")["amount"].sum())
    b2b_cat = (b2b.assign(l1=lambda x: x["sku_id"].map(sku_l1))
               .groupby("l1")["amount"].sum())
    store_cat = {}
    for cat, (l1, share) in STORE_CAT_MAP.items():
        v = float(store_sales.loc[store_sales["category"] == cat, "sales_amount"].sum())
        store_cat[l1] = store_cat.get(l1, 0) + v
    cat_gmv = {}
    for l1 in L1_NAMES:
        cat_gmv[l1] = float(ecom_cat.get(l1, 0)) + float(b2b_cat.get(l1, 0)) + store_cat.get(l1, 0)
    cat_gmv = {k: v for k, v in cat_gmv.items() if v > 0}
    top3 = sorted(cat_gmv.items(), key=lambda x: -x[1])[:3]
    top3_share = sum(v for _, v in top3) / total_gmv

    print("[8/9] 注入脏数据 ...")
    orders, items, users, deliveries, store_sales, dirty_stats = inject_dirty(
        orders, items, users, deliveries, store_sales)
    print(f"  注入 {sum(dirty_stats.values())} 处脏数据: {dirty_stats}")

    # ---------- 校准断言 ----------
    print("[9/9] 校准校验 ...")
    rows_count = {
        "dim_sku": len(sku), "dim_users": len(users), "dim_suppliers": len(suppliers),
        "dim_stores": len(stores), "dim_warehouses": len(warehouses),
        "fact_live_sessions": len(sessions),
        "fact_live_minute_traffic": len(minutes),
        "fact_orders": len(orders), "fact_order_items": len(items),
        "fact_b2b_orders": len(b2b),
        "fact_purchases": len(purchases), "fact_purchase_items": len(purchase_items),
        "fact_warehouse_stock": len(stock), "fact_deliveries": len(deliveries),
        "fact_store_sales_daily": len(store_sales),
    }
    total_rows = sum(rows_count.values())

    print(f"\n  总行数        : {total_rows:,}（目标 11.5~13 万）")
    print(f"  电商 GMV      : {ecom_gmv:>12,.0f} 元  占比 {shares[0]:.1%}")
    print(f"  B2B  GMV      : {b2b_gmv:>12,.0f} 元  占比 {shares[1]:.1%}")
    print(f"  门店 GMV      : {store_gmv:>12,.0f} 元  占比 {shares[2]:.1%}")
    print(f"  全渠道 GMV    : {total_gmv:>12,.0f} 元")
    print(f"  Top3 品类     : " + " / ".join(f"{k}({v/total_gmv:.1%})" for k, v in top3))
    print(f"  Top3 合计占比 : {top3_share:.1%}（目标 63%~67%）")

    assert 110_000 <= total_rows <= 136_000, f"总行数超界: {total_rows}"
    assert abs(shares[0] - SHARE_ECOM) <= 0.03, f"电商占比超界: {shares[0]:.3f}"
    assert abs(shares[1] - SHARE_B2B) <= 0.03, f"B2B占比超界: {shares[1]:.3f}"
    assert abs(shares[2] - SHARE_STORE) <= 0.03, f"门店占比超界: {shares[2]:.3f}"
    assert 0.63 <= top3_share <= 0.67, f"Top3 品类占比超界: {top3_share:.3f}"
    print("  ✔ 全部校准断言通过")

    # ---------- 落盘 ----------
    sessions_out = sessions.drop(columns=[c for c in sessions.columns
                                          if c.startswith("_")])
    tables = {
        "dim_sku": sku, "dim_users": users, "dim_suppliers": suppliers,
        "dim_stores": stores, "dim_warehouses": warehouses,
        "fact_live_sessions": sessions_out, "fact_live_minute_traffic": minutes,
        "fact_orders": orders, "fact_order_items": items, "fact_b2b_orders": b2b,
        "fact_purchases": purchases, "fact_purchase_items": purchase_items,
        "fact_warehouse_stock": stock, "fact_deliveries": deliveries,
        "fact_store_sales_daily": store_sales,
    }
    for name, df in tables.items():
        path = os.path.join(RAW_DIR, f"{name}.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"  写出 {name}.csv  {len(df):>7,} 行")

    stats = {
        "seed": SEED, "total_rows": total_rows, "rows": rows_count,
        "gmv": {"ecom": round(ecom_gmv, 2), "b2b": round(b2b_gmv, 2),
                "store": round(store_gmv, 2), "total": round(total_gmv, 2),
                "shares": [round(s, 4) for s in shares]},
        "top3_category": {k: round(v, 2) for k, v in top3},
        "top3_share": round(top3_share, 4),
        "dirty_injected": dirty_stats,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(LOG_DIR, "generation_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"\n校准统计已写入 logs/generation_stats.json")
    print("✔ 模拟数据生成完成（模拟数据，仅用于方法复现，不代表真实经营结果）")


if __name__ == "__main__":
    main()
