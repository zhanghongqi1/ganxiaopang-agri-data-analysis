-- ==================================================================
-- d_supply_chain.sql — 供应链周转与损耗分析（"集中仓储+分级配送"成本对比）
-- ⚠️ 模拟数据：仅用于分析方法复现，不代表真实经营结果
-- 口径（详见 docs/指标口径.md）：
--   采购到货周期 = arrival_date - purchase_date
--   采购损耗率 = rejected_kg / quantity_kg
--   库存周转天数 = stock_kg / avg_daily_outflow_kg
--   配送损耗率 = loss_kg / weight_kg
--   履约时效 = arrive_date - ship_date
-- ==================================================================
USE ganxiaopang_db;

-- ------------------------------------------------------------------
-- 1. 采购到货周期（按供应商类型）
-- ------------------------------------------------------------------
SELECT * FROM v_purchase_cycle ORDER BY 平均到货周期_天 DESC;

-- ------------------------------------------------------------------
-- 2. 库存周转天数（按品类）
-- ------------------------------------------------------------------
SELECT * FROM v_stock_turnover;

-- ------------------------------------------------------------------
-- 3. 分环节损耗率
-- ------------------------------------------------------------------
SELECT * FROM v_supply_chain_loss;

-- ------------------------------------------------------------------
-- 4. 配送模式对比（核心结论：集中仓储+分级配送 降本增效）
-- ------------------------------------------------------------------
SELECT * FROM v_delivery_mode_compare;

-- ------------------------------------------------------------------
-- 5. 配送模式整体汇总（新模式 vs 旧模式）
-- ------------------------------------------------------------------
SELECT
    delivery_mode                                       AS 配送模式,
    COUNT(*)                                            AS 单量,
    ROUND(AVG(lead_time_days), 2)                       AS 平均履约时效_天,
    ROUND(SUM(loss_kg) / SUM(weight_kg) * 100, 3)       AS 综合损耗率_pct,
    ROUND(SUM(freight_cost) / SUM(weight_kg), 3)        AS 单位运费_元每kg,
    ROUND(SUM(freight_cost), 2)                         AS 累计运费_元
FROM fact_deliveries
GROUP BY delivery_mode;

-- ------------------------------------------------------------------
-- 6. 按时间对比（2024 旧模式为主 vs 2025 新模式试点）→ 趋势验证
-- ------------------------------------------------------------------
SELECT
    DATE_FORMAT(ship_date, '%Y')                        AS 年份,
    delivery_mode                                       AS 配送模式,
    COUNT(*)                                            AS 单量,
    ROUND(AVG(lead_time_days), 2)                       AS 平均时效_天,
    ROUND(SUM(loss_kg) / SUM(weight_kg) * 100, 3)       AS 损耗率_pct
FROM fact_deliveries
GROUP BY 年份, 配送模式
ORDER BY 年份, 配送模式;

-- ------------------------------------------------------------------
-- 7. 成本量化：新模式相对旧模式的节约测算（按等量折算）
-- ------------------------------------------------------------------
SELECT
    ROUND(SUM(CASE WHEN delivery_mode LIKE '旧模式%' THEN loss_kg ELSE 0 END), 1) AS 旧模式损耗_kg,
    ROUND(SUM(CASE WHEN delivery_mode LIKE '新模式%' THEN loss_kg ELSE 0 END), 1) AS 新模式损耗_kg,
    ROUND(SUM(CASE WHEN delivery_mode LIKE '旧模式%' THEN weight_kg ELSE 0 END), 1) AS 旧模式总重_kg,
    ROUND(SUM(CASE WHEN delivery_mode LIKE '新模式%' THEN weight_kg ELSE 0 END), 1) AS 新模式总重_kg,
    ROUND(
      (SUM(CASE WHEN delivery_mode LIKE '旧模式%' THEN loss_kg ELSE 0 END)
       / SUM(CASE WHEN delivery_mode LIKE '旧模式%' THEN weight_kg ELSE 0 END)
       - SUM(CASE WHEN delivery_mode LIKE '新模式%' THEN loss_kg ELSE 0 END)
       / SUM(CASE WHEN delivery_mode LIKE '新模式%' THEN weight_kg ELSE 0 END)) * 100, 3
    ) AS 损耗率下降_pct点,
    ROUND(
      (SUM(CASE WHEN delivery_mode LIKE '旧模式%' THEN freight_cost ELSE 0 END)
       / SUM(CASE WHEN delivery_mode LIKE '旧模式%' THEN weight_kg ELSE 0 END)
       - SUM(CASE WHEN delivery_mode LIKE '新模式%' THEN freight_cost ELSE 0 END)
       / SUM(CASE WHEN delivery_mode LIKE '新模式%' THEN weight_kg ELSE 0 END)), 3
    ) AS 单位运费下降_元每kg
FROM fact_deliveries;

-- ------------------------------------------------------------------
-- 8. 目的区域履约表现（分级配送覆盖判断）
-- ------------------------------------------------------------------
SELECT
    to_region                                           AS 目的区域,
    COUNT(*)                                            AS 单量,
    ROUND(AVG(lead_time_days), 2)                       AS 平均时效_天,
    ROUND(SUM(loss_kg) / SUM(weight_kg) * 100, 3)       AS 损耗率_pct
FROM fact_deliveries
GROUP BY to_region
ORDER BY 平均时效_天 DESC;
