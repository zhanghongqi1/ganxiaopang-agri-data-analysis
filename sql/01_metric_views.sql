-- ==================================================================
-- 01_metric_views.sql — 四层指标体系视图（流量-转化-复购-履约）
-- ⚠️ 模拟数据：仅用于分析方法复现，不代表真实经营结果
-- 口径来源：docs/指标口径.md（本文件是其 SQL 固化实现）
-- ==================================================================
USE ganxiaopang_db;

-- ------------------------------------------------------------------
-- L1 流量层：直播获客效率（场次级）
-- ------------------------------------------------------------------
CREATE OR REPLACE VIEW v_live_traffic AS
SELECT
    s.session_id, s.live_date, DAYOFWEEK(s.live_date) AS dow, s.start_time,
    s.theme, s.anchor, s.duration_min, s.is_festival, s.main_category,
    s.total_exposure                                   AS 曝光量,
    s.total_enter                                      AS 进入人次,
    ROUND(s.total_enter / NULLIF(s.total_exposure,0), 4) * 100  AS 进入率_pct,
    s.new_followers                                    AS 涨粉数,
    s.gmv                                              AS GMV,
    ROUND(s.gmv / NULLIF(s.total_enter,0), 2)          AS UV价值,
    ROUND(s.gmv / NULLIF(s.total_exposure,0) * 1000, 2) AS GPM,
    ROUND(s.duration_min / 60.0, 2)                    AS 时长_小时,
    ROUND(s.gmv / NULLIF(s.duration_min/60.0,0), 2)    AS 时均GMV
FROM fact_live_sessions s;

-- 分时段/分主题流量汇总
CREATE OR REPLACE VIEW v_live_traffic_slot AS
SELECT
    CASE
        WHEN start_time < '16:00' THEN '午后场(14:00-16:00)'
        WHEN start_time < '19:00' THEN '傍晚场(18:30-19:00)'
        ELSE '黄金场(19:00-20:00)'
    END                                                  AS 时段,
    COUNT(*)                                             AS 场次数,
    ROUND(AVG(total_exposure), 0)                        AS 场均曝光,
    ROUND(AVG(total_enter), 0)                           AS 场均场观,
    ROUND(AVG(total_paid), 1)                            AS 场均付款人数,
    ROUND(SUM(gmv), 2)                                   AS 累计GMV,
    ROUND(AVG(gmv / NULLIF(total_enter,0)), 2)           AS UV价值,
    ROUND(AVG(total_enter / NULLIF(total_exposure,0)), 4) AS 平均进入率
FROM fact_live_sessions
GROUP BY 时段;

-- ------------------------------------------------------------------
-- L2 转化层：六段漏斗（场次级）与整体转化
-- ------------------------------------------------------------------
CREATE OR REPLACE VIEW v_live_funnel AS
SELECT
    s.session_id, s.live_date, s.theme, s.anchor, s.start_time, s.main_category,
    s.total_exposure AS 曝光, s.total_enter AS 进入, s.total_stay AS 停留,
    s.total_interact AS 互动, s.total_order_placed AS 下单, s.total_paid AS 付款,
    ROUND(s.total_enter / NULLIF(s.total_exposure,0) * 100, 2)      AS 进入率,
    ROUND(s.total_stay / NULLIF(s.total_enter,0) * 100, 2)         AS 停留率,
    ROUND(s.total_interact / NULLIF(s.total_stay,0) * 100, 2)      AS 互动率,
    ROUND(s.total_order_placed / NULLIF(s.total_interact,0) * 100, 2) AS 下单率,
    ROUND(s.total_paid / NULLIF(s.total_order_placed,0) * 100, 2)  AS 付款率,
    ROUND(s.total_paid / NULLIF(s.total_exposure,0) * 100, 3)      AS 整体转化率,
    ROUND(s.gmv / NULLIF(s.total_paid,0), 2)                       AS 直播间客单价
FROM fact_live_sessions s;

-- 漏斗流失诊断（成交额加权）
CREATE OR REPLACE VIEW v_funnel_leak AS
SELECT '进入→停留' AS 环节, ROUND(SUM(total_enter - total_stay), 0) AS 流失人次 FROM fact_live_sessions
UNION ALL SELECT '停留→互动', ROUND(SUM(total_stay - total_interact), 0) FROM fact_live_sessions
UNION ALL SELECT '互动→下单', ROUND(SUM(total_interact - total_order_placed), 0) FROM fact_live_sessions
UNION ALL SELECT '下单→付款', ROUND(SUM(total_order_placed - total_paid), 0) FROM fact_live_sessions;

-- 全站订单转化（付款口径）
CREATE OR REPLACE VIEW v_order_metrics AS
SELECT
    channel                                              AS 渠道,
    COUNT(*)                                             AS 订单数,
    SUM(CASE WHEN order_status IN ('已付款','已发货','已完成') THEN 1 ELSE 0 END) AS 付款订单数,
    SUM(CASE WHEN order_status IN ('已付款','已发货','已完成') THEN pay_amount ELSE 0 END) AS GMV,
    ROUND(AVG(CASE WHEN order_status IN ('已付款','已发货','已完成') THEN pay_amount END), 2) AS 客单价,
    ROUND(AVG(item_cnt), 2)                              AS 平均件数,
    ROUND(SUM(CASE WHEN order_status='已取消' THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS 取消率,
    ROUND(SUM(CASE WHEN order_status='已退款' THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS 退款率
FROM fact_orders
GROUP BY channel;

-- ------------------------------------------------------------------
-- L3 复购层：RFM（观察截止日 2025-12-31）
-- ------------------------------------------------------------------
CREATE OR REPLACE VIEW v_user_rfm_base AS
SELECT
    o.user_id,
    DATEDIFF('2025-12-31', MAX(DATE(o.order_time)))      AS R_最近购买天数,
    COUNT(DISTINCT o.order_id)                           AS F_购买频次,
    ROUND(SUM(o.pay_amount), 2)                          AS M_累计金额
FROM fact_orders o
WHERE o.order_status IN ('已付款','已发货','已完成')
GROUP BY o.user_id;

-- RFM 打分与人群分层
-- 说明（真实电商数据特征）：F 分布高度右偏（约 78% 用户仅购买 1 次），
--   故 F 采用「是否复购」二分（F≥2 记 1）；R、M 按中位数二分。
--   R：越小越好（近期活跃=1）；M：越大越好（高额=1）。
CREATE OR REPLACE VIEW v_user_segment AS
WITH scored AS (
    -- NTILE(2) 返回 {1,2}，先统一归一化为 0/1 再参与分层判断，避免 0 值与规则失配
    SELECT
        b.user_id, b.R_最近购买天数, b.F_购买频次, b.M_累计金额,
        IF(NTILE(2) OVER (ORDER BY b.R_最近购买天数 ASC) = 1, 1, 0) AS r_grp,
        IF(b.F_购买频次 >= 2, 1, 0)                                 AS f_grp,
        IF(NTILE(2) OVER (ORDER BY b.M_累计金额 DESC) = 1, 1, 0)    AS m_grp
    FROM v_user_rfm_base b
)
SELECT
    user_id, R_最近购买天数, F_购买频次, M_累计金额,
    r_grp               AS R_分,
    f_grp               AS F_分,
    m_grp               AS M_分,
    CONCAT(r_grp, f_grp, m_grp) AS rfm_code,
    CASE
        WHEN r_grp=1 AND f_grp=1 AND m_grp=1 THEN '重要价值客户'
        WHEN r_grp=0 AND f_grp=1 AND m_grp=1 THEN '重要保持客户'
        WHEN r_grp=1 AND f_grp=0 AND m_grp=1 THEN '重要发展客户'
        WHEN r_grp=1 AND f_grp=1 AND m_grp=0 THEN '重要挽留客户'
        WHEN r_grp=0 AND f_grp=0 AND m_grp=1 THEN '一般价值客户'
        WHEN r_grp=1 AND f_grp=0 AND m_grp=0 THEN '一般发展客户'
        WHEN r_grp=0 AND f_grp=1 AND m_grp=0 THEN '一般保持客户'
        ELSE '一般挽留客户'
    END AS 人群分层
FROM scored;

-- 人群分层汇总
CREATE OR REPLACE VIEW v_user_segment_summary AS
SELECT
    人群分层,
    COUNT(*)                                             AS 用户数,
    ROUND(COUNT(*) / (SELECT COUNT(*) FROM v_user_segment) * 100, 2) AS 人群占比_pct,
    ROUND(AVG(R_最近购买天数), 0)                        AS 平均R天数,
    ROUND(AVG(F_购买频次), 2)                            AS 平均频次,
    ROUND(AVG(M_累计金额), 2)                            AS 平均金额,
    ROUND(SUM(M_累计金额), 2)                            AS 累计贡献金额,
    ROUND(SUM(M_累计金额) / (SELECT SUM(M_累计金额) FROM v_user_rfm_base) * 100, 2) AS 贡献占比_pct
FROM v_user_segment
GROUP BY 人群分层
ORDER BY 累计贡献金额 DESC;

-- 复购率（付款口径）
CREATE OR REPLACE VIEW v_repurchase AS
SELECT
    COUNT(*)                                             AS 购买用户数,
    SUM(CASE WHEN F_购买频次 >= 2 THEN 1 ELSE 0 END)     AS 复购用户数,
    ROUND(SUM(CASE WHEN F_购买频次 >= 2 THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS 复购率_pct,
    ROUND(AVG(F_购买频次), 2)                            AS 人均购买频次
FROM v_user_rfm_base;

-- ------------------------------------------------------------------
-- L4 履约层：供应链与门店
-- ------------------------------------------------------------------
-- 采购到货周期
CREATE OR REPLACE VIEW v_purchase_cycle AS
SELECT
    sup.supplier_type AS 供应商类型,
    COUNT(*)                                          AS 采购单数,
    ROUND(AVG(DATEDIFF(p.arrival_date, p.purchase_date)), 2) AS 平均到货周期_天,
    ROUND(AVG(p.total_amount), 2)                     AS 平均单额,
    ROUND(SUM(pi.rejected_kg) / NULLIF(SUM(pi.quantity_kg),0) * 100, 3) AS 采购损耗率_pct
FROM fact_purchases p
JOIN dim_suppliers sup ON p.supplier_id = sup.supplier_id
JOIN fact_purchase_items pi ON p.purchase_id = pi.purchase_id
GROUP BY sup.supplier_type;

-- 库存周转天数（主力 SKU）
CREATE OR REPLACE VIEW v_stock_turnover AS
SELECT
    s.category_l1                                     AS 品类,
    COUNT(DISTINCT w.sku_id)                          AS SKU数,
    ROUND(AVG(w.stock_kg), 1)                         AS 平均库存_kg,
    ROUND(AVG(w.avg_daily_outflow_kg), 1)             AS 日均出库_kg,
    ROUND(AVG(w.stock_kg / NULLIF(w.avg_daily_outflow_kg,0)), 1) AS 平均库存周转天数,
    ROUND(AVG(w.avg_days_in_stock), 1)                AS 平均库龄_天
FROM fact_warehouse_stock w
JOIN dim_sku s ON w.sku_id = s.sku_id
GROUP BY s.category_l1
ORDER BY 平均库存周转天数 DESC;

-- 配送：新旧模式对比（履约时效/损耗/运费）
CREATE OR REPLACE VIEW v_delivery_mode_compare AS
SELECT
    delivery_mode                                     AS 配送模式,
    biz_type                                          AS 业务类型,
    COUNT(*)                                          AS 单量,
    ROUND(AVG(lead_time_days), 2)                     AS 平均履约时效_天,
    ROUND(SUM(loss_kg) / NULLIF(SUM(weight_kg),0) * 100, 3) AS 配送损耗率_pct,
    ROUND(SUM(freight_cost) / NULLIF(SUM(weight_kg),0), 3)  AS 单位运费_元每kg,
    ROUND(SUM(freight_cost), 2)                       AS 累计运费
FROM fact_deliveries
GROUP BY delivery_mode, biz_type
ORDER BY delivery_mode, biz_type;

-- 整体损耗指标（采购+配送）
CREATE OR REPLACE VIEW v_supply_chain_loss AS
SELECT '采购损耗' AS 环节,
       ROUND(SUM(rejected_kg) / NULLIF(SUM(quantity_kg),0) * 100, 3) AS 损耗率_pct,
       ROUND(SUM(rejected_kg), 1) AS 损耗量_kg
FROM fact_purchase_items
UNION ALL
SELECT '配送损耗',
       ROUND(SUM(loss_kg) / NULLIF(SUM(weight_kg),0) * 100, 3),
       ROUND(SUM(loss_kg), 1)
FROM fact_deliveries;

-- 门店月度经营（坪效/人效/客单）
CREATE OR REPLACE VIEW v_store_monthly AS
SELECT
    st.store_id, st.store_name, st.city,
    DATE_FORMAT(f.sale_date, '%Y-%m')                 AS 月份,
    SUM(f.order_cnt)                                  AS 订单数,
    SUM(f.customer_cnt)                               AS 客数,
    ROUND(SUM(f.sales_amount), 2)                     AS 月销售额,
    ROUND(SUM(f.sales_amount) / NULLIF(SUM(f.order_cnt),0), 2) AS 客单价,
    ROUND(SUM(f.sales_amount) / st.area_sqm, 2)       AS 坪效_元每㎡月,
    ROUND(SUM(f.sales_amount) / st.staff_cnt, 2)      AS 人效_元每人月,
    ROUND(SUM(f.order_cnt) / NULLIF(SUM(f.foot_traffic),0) * 100, 2) AS 进店转化率_pct
FROM fact_store_sales_daily f
JOIN dim_stores st ON f.store_id = st.store_id
GROUP BY st.store_id, st.store_name, st.city, DATE_FORMAT(f.sale_date, '%Y-%m');
