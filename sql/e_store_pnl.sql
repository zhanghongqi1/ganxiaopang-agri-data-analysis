-- ==================================================================
-- e_store_pnl.sql — 单店盈利测算与盈亏平衡模型（4 家门店可行性）
-- ⚠️ 模拟数据：仅用于分析方法复现，不代表真实经营结果
-- 模型（详见 docs/指标口径.md）：
--   月度毛利 = 月销售额 × 品类加权毛利率（宽粉麻辣烫 0.60 / 特色小吃 0.45 / 饮品 0.55 / 伴手礼盒 0.42）
--   固定成本 = 月租金 + 人工成本（员工数 × 人均月成本）+ 水电杂费 + 折旧摊销(初始投入 / 摊销月数)
--   月净利 = 月度毛利 - 固定成本
--   盈亏平衡月销售额 = 固定成本 / 综合毛利率
--   盈亏平衡日均单量 = 盈亏平衡月销售额 / 客单价 / 30
--   坪效 = 月销售额 / 面积；人效 = 月销售额 / 员工数；投资回收期 = 初始投入 / 月净利
--   情景测算：假设客流分别提升 30% / 60% / 100% 时各店月净利变化
-- ==================================================================
USE ganxiaopang_db;

-- ------------------------------------------------------------------
-- 1. 门店月度经营（坪效/人效/客单）
-- ------------------------------------------------------------------
SELECT * FROM v_store_monthly ORDER BY store_name, 月份;

-- ------------------------------------------------------------------
-- 2. 门店 2025 年月均经营汇总（测算输入）
-- ------------------------------------------------------------------
DROP TEMPORARY TABLE IF EXISTS tmp_store_avg;
CREATE TEMPORARY TABLE tmp_store_avg AS
SELECT
    m.store_id, m.store_name, m.city,
    st.area_sqm, st.rent_monthly, st.staff_cnt, st.staff_cost_monthly,
    st.util_monthly, st.amort_months, st.initial_investment,
    ROUND(AVG(m.月销售额), 2)                     AS 月均销售额,
    ROUND(AVG(m.订单数), 0)                       AS 月均订单数,
    ROUND(AVG(m.客单价), 2)                       AS 平均客单价,
    ROUND(AVG(m.月销售额) / st.area_sqm, 2)       AS 月均坪效,
    ROUND(AVG(m.月销售额) / st.staff_cnt, 2)      AS 月均人效
FROM v_store_monthly m
JOIN dim_stores st ON m.store_id = st.store_id
WHERE m.月份 >= '2025-01'
GROUP BY m.store_id, m.store_name, m.city, st.area_sqm, st.rent_monthly,
         st.staff_cnt, st.staff_cost_monthly, st.util_monthly,
         st.amort_months, st.initial_investment;

-- ------------------------------------------------------------------
-- 3. 门店品类加权毛利率（依据门店品类销售结构）
-- ------------------------------------------------------------------
DROP TEMPORARY TABLE IF EXISTS tmp_store_margin;
CREATE TEMPORARY TABLE tmp_store_margin AS
SELECT
    store_id,
    ROUND(SUM(sales_amount *
        CASE category
            WHEN '宽粉麻辣烫' THEN 0.60
            WHEN '特色小吃'   THEN 0.45
            WHEN '饮品'       THEN 0.55
            WHEN '伴手礼盒'   THEN 0.42
        END) / SUM(sales_amount), 4)             AS 综合毛利率
FROM fact_store_sales_daily
WHERE sale_date >= '2025-01-01'
GROUP BY store_id;

-- ------------------------------------------------------------------
-- 4. 单店盈利测算（核心结论表）
-- ------------------------------------------------------------------
SELECT
    a.store_name                                    AS 门店,
    a.city                                          AS 城市,
    a.area_sqm                                      AS 面积㎡,
    a.月均销售额,
    ROUND(a.月均销售额 * m.综合毛利率, 2)             AS 月均毛利,
    ROUND(m.综合毛利率 * 100, 2)                     AS 综合毛利率_pct,
    a.rent_monthly                                  AS 月租金,
    a.staff_cnt * a.staff_cost_monthly              AS 人工成本,
    a.util_monthly                                  AS 水电杂费,
    ROUND(a.initial_investment / a.amort_months, 2) AS 月折旧摊销,
    ROUND(a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
          + a.initial_investment / a.amort_months, 2) AS 月固定成本合计,
    ROUND(a.月均销售额 * m.综合毛利率
          - (a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
             + a.initial_investment / a.amort_months), 2) AS 月净利,
    ROUND((a.月均销售额 * m.综合毛利率
          - (a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
             + a.initial_investment / a.amort_months))
          / a.月均销售额 * 100, 2)                   AS 净利率_pct,
    a.月均坪效,
    a.月均人效,
    -- 盈亏平衡月销售额 = 固定成本 / 综合毛利率
    ROUND((a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
           + a.initial_investment / a.amort_months) / m.综合毛利率, 2) AS 盈亏平衡月销售额,
    -- 客流缺口 = 盈亏平衡月销售额 - 现状月均销售额
    ROUND((a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
           + a.initial_investment / a.amort_months) / m.综合毛利率
          - a.月均销售额, 2)                        AS 月销售缺口,
    -- 盈亏平衡日均单量
    ROUND((a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
           + a.initial_investment / a.amort_months) / m.综合毛利率
          / NULLIF(a.平均客单价, 0) / 30, 1)         AS 盈亏平衡日均单量,
    ROUND(a.月均订单数 / 30, 1)                     AS 实际日均单量,
    -- 投资回收期（月）= 初始投入 / 月净利
    CASE WHEN (a.月均销售额 * m.综合毛利率
          - (a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
             + a.initial_investment / a.amort_months)) > 0
         THEN ROUND(a.initial_investment
              / (a.月均销售额 * m.综合毛利率
                 - (a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
                    + a.initial_investment / a.amort_months)), 1)
         ELSE NULL END                              AS 投资回收期_月,
    CASE
        WHEN (a.月均销售额 * m.综合毛利率
              - (a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
                 + a.initial_investment / a.amort_months)) > 0 THEN '可行（盈利）'
        WHEN (a.月均销售额 * m.综合毛利率
              - (a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
                 + a.initial_investment / a.amort_months)) > -1000 THEN '临界（接近盈亏平衡）'
        ELSE '不可行（亏损）'
    END                                             AS 可行性结论,
    -- 情景测算：客流 +30% / +60% / +100% 时的月净利
    ROUND(a.月均销售额 * 1.30 * m.综合毛利率
          - (a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
             + a.initial_investment / a.amort_months), 2) AS 情景净利_客流加30pct,
    ROUND(a.月均销售额 * 1.60 * m.综合毛利率
          - (a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
             + a.initial_investment / a.amort_months), 2) AS 情景净利_客流加60pct,
    ROUND(a.月均销售额 * 2.00 * m.综合毛利率
          - (a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
             + a.initial_investment / a.amort_months), 2) AS 情景净利_客流翻倍
FROM tmp_store_avg a
JOIN tmp_store_margin m ON a.store_id = m.store_id
ORDER BY 月净利 DESC;

-- ------------------------------------------------------------------
-- 5. 门店可行性汇总（4 家门店结论）
-- ------------------------------------------------------------------
SELECT
    COUNT(*)                                        AS 门店总数,
    SUM(CASE WHEN 月净利 > 0 THEN 1 ELSE 0 END)      AS 盈利门店数,
    SUM(CASE WHEN 月净利 BETWEEN -1000 AND 0 THEN 1 ELSE 0 END) AS 临界门店数,
    SUM(CASE WHEN 月净利 < -1000 THEN 1 ELSE 0 END)  AS 亏损门店数,
    ROUND(AVG(月净利), 2)                           AS 平均月净利,
    ROUND(SUM(月净利), 2)                           AS 合计月净利,
    ROUND(SUM(盈亏平衡月销售额), 2)                   AS 盈亏平衡月销售合计,
    ROUND(SUM(月均销售额), 2)                        AS 现状月销售合计,
    ROUND(SUM(月销售缺口), 2)                        AS 月销售缺口合计,
    ROUND(SUM(月均销售额 * 1.30 * 综合毛利率
              - (月租金 + 人工成本 + 水电杂费 + 月折旧摊销)), 2) AS 情景合计净利_客流加30pct,
    ROUND(SUM(月均销售额 * 2.00 * 综合毛利率
              - (月租金 + 人工成本 + 水电杂费 + 月折旧摊销)), 2) AS 情景合计净利_客流翻倍
FROM (
    SELECT
        a.月均销售额, m.综合毛利率, a.rent_monthly AS 月租金,
        a.staff_cnt * a.staff_cost_monthly AS 人工成本,
        a.util_monthly AS 水电杂费,
        a.initial_investment / a.amort_months AS 月折旧摊销,
        ROUND(a.月均销售额 * m.综合毛利率
          - (a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
             + a.initial_investment / a.amort_months), 2) AS 月净利,
        ROUND((a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
               + a.initial_investment / a.amort_months) / m.综合毛利率, 2) AS 盈亏平衡月销售额,
        ROUND((a.rent_monthly + a.staff_cnt * a.staff_cost_monthly + a.util_monthly
               + a.initial_investment / a.amort_months) / m.综合毛利率
              - a.月均销售额, 2) AS 月销售缺口
    FROM tmp_store_avg a JOIN tmp_store_margin m ON a.store_id = m.store_id
) t;
