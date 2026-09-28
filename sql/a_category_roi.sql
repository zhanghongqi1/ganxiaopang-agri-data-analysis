-- ==================================================================
-- a_category_roi.sql — 品类 ROI / 毛利拆解（约 2100 个 SKU）
-- ⚠️ 模拟数据：仅用于分析方法复现，不代表真实经营结果
-- 口径说明（详见 docs/指标口径.md）：
--   品类 GMV = 电商(order_items×有效订单) + B2B(amount) + 门店(按 STORE_CAT_MAP 归集)
--   品类毛利 = 各渠道销售额 × 对应毛利率
--     · 电商/B2B：用 SKU 级毛利率加权
--     · 门店：用门店品类综合毛利率参数（宽粉麻辣烫 0.60 / 特色小吃 0.45 / 饮品 0.55 / 伴手礼盒 0.42）
--   品类投入成本（ROI 分母）= 内容成本 + 采购成本占用
--     · 内容成本：该品类作为主推品类的直播场次数 × 单场内容成本 1500 元
--     · 采购成本：该品类采购金额 × 资金占用系数 0.35（年化周转约 3 次）
--   品类 ROI = 品类毛利 ÷ 品类投入成本
-- 说明：MySQL 临时表在同一语句中不可重复引用，故各渠道先落成普通表，
--       计算完成后再统一 DROP，兼容任何 MySQL 版本。
-- ==================================================================
USE ganxiaopang_db;

-- ------------------------------------------------------------------
-- 步骤 1：电商渠道品类 GMV 与毛利
-- 口径：明细行按行金额占比摊销整单实付金额（pay_amount），
--       使品类 GMV 合计与「实付口径」的全渠道 GMV 严格一致（可与 Pandas 复算对齐）。
-- ------------------------------------------------------------------
DROP TABLE IF EXISTS ana_ecom_cat;
CREATE TABLE ana_ecom_cat AS
SELECT
    s.category_l1                                      AS 品类,
    COUNT(DISTINCT s.sku_id)                           AS 在售SKU数,
    ROUND(SUM(i.quantity * i.unit_price
              / o.item_amount * fo.pay_amount), 2)      AS 电商GMV,
    ROUND(SUM(i.quantity * i.unit_price
              / o.item_amount * fo.pay_amount
              * s.gross_margin_rate), 2)               AS 电商毛利,
    SUM(i.quantity)                                    AS 销量
FROM fact_order_items i
JOIN (
    -- 每单明细行金额合计，用于按行金额占比摊销实付金额
    SELECT order_id, NULLIF(SUM(quantity * unit_price), 0) AS item_amount
    FROM fact_order_items GROUP BY order_id
) o ON i.order_id = o.order_id
JOIN fact_orders fo ON i.order_id = fo.order_id
JOIN dim_sku   s  ON i.sku_id   = s.sku_id
WHERE fo.order_status IN ('已付款','已发货','已完成')
GROUP BY s.category_l1;

-- ------------------------------------------------------------------
-- 步骤 2：B2B 渠道品类 GMV 与毛利（按 SKU 毛利率）
-- ------------------------------------------------------------------
DROP TABLE IF EXISTS ana_b2b_cat;
CREATE TABLE ana_b2b_cat AS
SELECT
    s.category_l1                                      AS 品类,
    ROUND(SUM(b.amount), 2)                            AS B2B供货额,
    ROUND(SUM(b.amount * s.gross_margin_rate), 2)      AS B2B毛利
FROM fact_b2b_orders b
JOIN dim_sku s ON b.sku_id = s.sku_id
GROUP BY s.category_l1;

-- ------------------------------------------------------------------
-- 步骤 3：门店渠道品类归集（品类映射 + 门店综合毛利率）
-- ------------------------------------------------------------------
DROP TABLE IF EXISTS ana_store_cat;
CREATE TABLE ana_store_cat AS
SELECT
    CASE category
        WHEN '宽粉麻辣烫' THEN '定西宽粉及薯制品'
        WHEN '特色小吃'   THEN '高原夏菜及土豆'
        WHEN '饮品'       THEN '甘肃生鲜水果'
        WHEN '伴手礼盒'   THEN '礼盒组合'
    END                                                AS 品类,
    ROUND(SUM(sales_amount), 2)                        AS 门店销售额,
    ROUND(SUM(sales_amount * CASE category
                        WHEN '宽粉麻辣烫' THEN 0.60
                        WHEN '特色小吃'   THEN 0.45
                        WHEN '饮品'       THEN 0.55
                        WHEN '伴手礼盒'   THEN 0.42
                      END), 2)                         AS 门店毛利
FROM fact_store_sales_daily
GROUP BY category;

-- ------------------------------------------------------------------
-- 步骤 4：品类投入成本（内容成本 + 采购资金占用）
-- ------------------------------------------------------------------
DROP TABLE IF EXISTS ana_content_cost;
CREATE TABLE ana_content_cost AS
SELECT
    main_category                                      AS 品类,
    COUNT(*)                                           AS 主推场次数,
    COUNT(*) * 1500                                    AS 内容成本
FROM fact_live_sessions
GROUP BY main_category;

DROP TABLE IF EXISTS ana_purchase_cost;
CREATE TABLE ana_purchase_cost AS
SELECT
    s.category_l1                                      AS 品类,
    ROUND(SUM(pi.amount), 2)                           AS 采购金额,
    ROUND(SUM(pi.amount) * 0.35, 2)                    AS 采购资金占用
FROM fact_purchase_items pi
JOIN dim_sku s ON pi.sku_id = s.sku_id
GROUP BY s.category_l1;

-- ------------------------------------------------------------------
-- 步骤 5：品类 ROI 汇总（全品类统一以"品类全量清单"为主表左连三渠道）
-- ------------------------------------------------------------------
DROP TABLE IF EXISTS ana_category_roi;
CREATE TABLE ana_category_roi AS
SELECT
    cat.品类,
    IFNULL(c.在售SKU数, 0)                             AS 在售SKU数,
    IFNULL(c.电商GMV, 0)                               AS 电商GMV,
    IFNULL(b.B2B供货额, 0)                             AS B2B供货额,
    IFNULL(st.门店销售额, 0)                           AS 门店销售额,
    ROUND(IFNULL(c.电商GMV,0) + IFNULL(b.B2B供货额,0) + IFNULL(st.门店销售额,0), 2) AS 品类GMV,
    ROUND((IFNULL(c.电商GMV,0) + IFNULL(b.B2B供货额,0) + IFNULL(st.门店销售额,0))
          / ((SELECT IFNULL(SUM(pay_amount),0) FROM fact_orders
                WHERE order_status IN ('已付款','已发货','已完成'))
             + (SELECT IFNULL(SUM(amount),0) FROM fact_b2b_orders)
             + (SELECT IFNULL(SUM(sales_amount),0) FROM fact_store_sales_daily)) * 100, 2) AS GMV占比_pct,
    ROUND(IFNULL(c.电商毛利,0) + IFNULL(b.B2B毛利,0) + IFNULL(st.门店毛利,0), 2) AS 品类毛利,
    ROUND((IFNULL(c.电商毛利,0) + IFNULL(b.B2B毛利,0) + IFNULL(st.门店毛利,0))
          / NULLIF(IFNULL(c.电商GMV,0) + IFNULL(b.B2B供货额,0) + IFNULL(st.门店销售额,0), 0) * 100, 2) AS 综合毛利率_pct,
    IFNULL(cc.主推场次数, 0)                           AS 主推场次数,
    IFNULL(cc.内容成本, 0) + IFNULL(pc.采购资金占用, 0) AS 内容投入成本,
    IFNULL(pc.采购金额, 0)                             AS 采购金额,
    ROUND((IFNULL(c.电商毛利,0) + IFNULL(b.B2B毛利,0) + IFNULL(st.门店毛利,0))
          / NULLIF(IFNULL(cc.内容成本,0) + IFNULL(pc.采购资金占用,0), 0), 2) AS 品类ROI
FROM (
    SELECT 品类 FROM ana_ecom_cat
    UNION SELECT 品类 FROM ana_b2b_cat
    UNION SELECT 品类 FROM ana_store_cat
) cat
LEFT JOIN ana_ecom_cat     c  ON cat.品类 = c.品类
LEFT JOIN ana_b2b_cat      b  ON cat.品类 = b.品类
LEFT JOIN ana_store_cat    st ON cat.品类 = st.品类
LEFT JOIN ana_content_cost cc ON cat.品类 = cc.品类
LEFT JOIN ana_purchase_cost pc ON cat.品类 = pc.品类;

-- 结果集 1：品类 ROI 明细（按 GMV 降序）
SELECT
    品类, 在售SKU数, 电商GMV, B2B供货额, 门店销售额, 品类GMV, GMV占比_pct,
    品类毛利, 综合毛利率_pct, 主推场次数, 内容投入成本, 采购金额, 品类ROI
FROM ana_category_roi
ORDER BY 品类GMV DESC;

-- ------------------------------------------------------------------
-- 步骤 6：Top3 重点品类贡献（帕累托，呼应简历"Top3 品类贡献约 65% GMV"）
-- 结果集 2
-- ------------------------------------------------------------------
SELECT
    'Top3 品类合计' AS 指标,
    ROUND(SUM(品类GMV), 2) AS GMV,
    ROUND(SUM(GMV占比_pct), 2) AS GMV占比_pct,
    ROUND(SUM(品类毛利), 2) AS 毛利
FROM (
    SELECT 品类, 品类GMV, GMV占比_pct, 品类毛利
    FROM ana_category_roi
    ORDER BY 品类GMV DESC
    LIMIT 3
) top3;

-- 清理中间表
DROP TABLE IF EXISTS ana_ecom_cat;
DROP TABLE IF EXISTS ana_b2b_cat;
DROP TABLE IF EXISTS ana_store_cat;
DROP TABLE IF EXISTS ana_content_cost;
DROP TABLE IF EXISTS ana_purchase_cost;
DROP TABLE IF EXISTS ana_category_roi;
