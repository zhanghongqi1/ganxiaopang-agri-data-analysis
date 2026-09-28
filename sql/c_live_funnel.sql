-- ==================================================================
-- c_live_funnel.sql — 直播转化漏斗 / 时段 / 人气 / 转化分析
-- ⚠️ 模拟数据：仅用于分析方法复现，不代表真实经营结果
-- 口径（详见 docs/指标口径.md）：六段漏斗 曝光→进入→停留(>30s)→互动→下单→付款
-- 输出：整体漏斗、时段分析、主题分析、人气分层、排期与促销节奏建议
-- ==================================================================
USE ganxiaopang_db;

-- ------------------------------------------------------------------
-- 1. 整体六段漏斗（汇总 624 场）
-- ------------------------------------------------------------------
SELECT '曝光' AS 漏斗环节, SUM(total_exposure) AS 人次, 100.00 AS 占曝光_pct, NULL AS 环节转化率_pct FROM fact_live_sessions
UNION ALL SELECT '进入', SUM(total_enter),
    ROUND(SUM(total_enter)/SUM(total_exposure)*100, 2), NULL FROM fact_live_sessions
UNION ALL SELECT '停留(>30s)', SUM(total_stay),
    ROUND(SUM(total_stay)/SUM(total_exposure)*100, 2),
    ROUND(SUM(total_stay)/SUM(total_enter)*100, 2) FROM fact_live_sessions
UNION ALL SELECT '互动', SUM(total_interact),
    ROUND(SUM(total_interact)/SUM(total_exposure)*100, 2),
    ROUND(SUM(total_interact)/SUM(total_stay)*100, 2) FROM fact_live_sessions
UNION ALL SELECT '下单', SUM(total_order_placed),
    ROUND(SUM(total_order_placed)/SUM(total_exposure)*100, 2),
    ROUND(SUM(total_order_placed)/SUM(total_interact)*100, 2) FROM fact_live_sessions
UNION ALL SELECT '付款', SUM(total_paid),
    ROUND(SUM(total_paid)/SUM(total_exposure)*100, 3),
    ROUND(SUM(total_paid)/SUM(total_order_placed)*100, 2) FROM fact_live_sessions;

-- ------------------------------------------------------------------
-- 2. 漏斗流失诊断（各环节流失人次与流失率）
-- ------------------------------------------------------------------
SELECT
    环节 AS 流失环节,
    流失人次,
    ROUND(流失人次 / SUM(流失人次) OVER () * 100, 2) AS 流失占比_pct
FROM v_funnel_leak
ORDER BY 流失人次 DESC;

-- ------------------------------------------------------------------
-- 3. 时段分析（排期依据）
-- ------------------------------------------------------------------
SELECT * FROM v_live_traffic_slot ORDER BY 累计GMV DESC;

-- ------------------------------------------------------------------
-- 4. 直播主题效果对比（脚本结构与选品建议依据）
-- ------------------------------------------------------------------
SELECT
    theme                                               AS 直播主题,
    COUNT(*)                                            AS 场次数,
    ROUND(AVG(duration_min), 0)                         AS 平均时长_分钟,
    ROUND(AVG(total_enter), 0)                          AS 场均场观,
    ROUND(AVG(total_interact / NULLIF(total_stay,0)) * 100, 2) AS 平均互动率_pct,
    ROUND(AVG(total_paid / NULLIF(total_order_placed,0)) * 100, 2) AS 平均付款率_pct,
    ROUND(AVG(gmv / NULLIF(total_enter,0)), 2)          AS UV价值,
    ROUND(SUM(gmv), 2)                                  AS 累计GMV,
    ROUND(AVG(gmv), 2)                                  AS 场均GMV
FROM fact_live_sessions
GROUP BY theme
ORDER BY 场均GMV DESC;

-- ------------------------------------------------------------------
-- 5. 场次人气分层（头部场次识别）
-- ------------------------------------------------------------------
SELECT
    CASE
        WHEN total_enter >= 15000 THEN 'S级(场观≥1.5万)'
        WHEN total_enter >= 8000  THEN 'A级(8000-1.5万)'
        WHEN total_enter >= 4000  THEN 'B级(4000-8000)'
        ELSE 'C级(<4000)'
    END                                                 AS 人气分层,
    COUNT(*)                                            AS 场次数,
    ROUND(COUNT(*) / (SELECT COUNT(*) FROM fact_live_sessions) * 100, 2) AS 场次占比_pct,
    ROUND(AVG(total_enter), 0)                          AS 场均场观,
    ROUND(AVG(gmv), 2)                                  AS 场均GMV,
    ROUND(SUM(gmv) / (SELECT SUM(gmv) FROM fact_live_sessions) * 100, 2) AS GMV贡献占比_pct
FROM fact_live_sessions
GROUP BY 人气分层
ORDER BY 场均GMV DESC;

-- ------------------------------------------------------------------
-- 6. 分时段 × 星期 排期建议矩阵
-- ------------------------------------------------------------------
SELECT
    CASE WHEN DAYOFWEEK(live_date) IN (1, 7) THEN '周末' ELSE '工作日' END AS 日期类型,
    CASE
        WHEN start_time < '16:00' THEN '午后场'
        WHEN start_time < '19:00' THEN '傍晚场'
        ELSE '黄金场'
    END                                                 AS 时段,
    COUNT(*)                                            AS 场次数,
    ROUND(AVG(gmv), 2)                                  AS 场均GMV,
    ROUND(AVG(total_paid), 1)                           AS 场均付款人数,
    ROUND(AVG(gmv / NULLIF(total_enter,0)), 2)          AS UV价值
FROM fact_live_sessions
GROUP BY 日期类型, 时段
ORDER BY 场均GMV DESC;

-- ------------------------------------------------------------------
-- 7. 分钟级流量曲线（峰值出现在开播后第几分钟 → 促销节奏）
-- ------------------------------------------------------------------
SELECT
    minute_index                                        AS 开播第几分钟,
    ROUND(AVG(viewers_online), 0)                       AS 平均在线,
    ROUND(AVG(order_cnt), 2)                            AS 平均下单量,
    ROUND(AVG(pay_user_cnt), 2)                         AS 平均付款人数,
    ROUND(SUM(order_cnt) / (SELECT SUM(order_cnt) FROM fact_live_minute_traffic) * 100, 2) AS 下单时段占比_pct
FROM fact_live_minute_traffic
GROUP BY minute_index
ORDER BY minute_index;

-- ------------------------------------------------------------------
-- 8. 节庆 vs 常态 场次效果
-- ------------------------------------------------------------------
SELECT
    IF(is_festival = 1, '节庆大促', '常态场次')          AS 场次类型,
    COUNT(*)                                            AS 场次数,
    ROUND(AVG(total_enter), 0)                          AS 场均场观,
    ROUND(AVG(total_paid), 1)                           AS 场均付款人数,
    ROUND(AVG(gmv), 2)                                  AS 场均GMV,
    ROUND(SUM(gmv), 2)                                  AS 累计GMV
FROM fact_live_sessions
GROUP BY 场次类型;
