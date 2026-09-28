-- ==================================================================
-- 00_create_database.sql — ganxiaopang_db 建库建表（MySQL 8.x）
-- ⚠️ 模拟数据：仅用于分析方法复现，不代表真实经营结果
-- 说明：本文件由 scripts/03_load_to_mysql.py 自动执行；
--       手动执行前请确认连接的是本机便携实例（端口 3306），
--       且不影响实例中的其他数据库。
-- ==================================================================

CREATE DATABASE IF NOT EXISTS ganxiaopang_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE ganxiaopang_db;

-- ------------------------------------------------------------------
-- 维度表
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_sku (
    sku_id             INT          NOT NULL COMMENT 'SKU主键',
    sku_code           VARCHAR(20)  NOT NULL COMMENT 'SKU编码',
    sku_name           VARCHAR(100) NOT NULL COMMENT '商品名',
    category_l1        VARCHAR(20)  NOT NULL COMMENT '一级大类(11个)',
    category_l2        VARCHAR(50)  NOT NULL COMMENT '二级类目(68个)',
    brand_series       VARCHAR(30)  NULL,
    spec               VARCHAR(50)  NULL,
    unit               VARCHAR(10)  NULL,
    cost_price         DECIMAL(10,2) NOT NULL COMMENT '成本价',
    retail_price       DECIMAL(10,2) NOT NULL COMMENT '零售价',
    gross_margin_rate  DECIMAL(6,4)  NOT NULL COMMENT '毛利率',
    supplier_id        INT          NULL,
    origin             VARCHAR(30)  NULL COMMENT '产地县域',
    is_self_operated   TINYINT      NOT NULL DEFAULT 0 COMMENT '1=自营工厂产品',
    shelf_date         DATE         NULL,
    status             VARCHAR(10)  NULL COMMENT '在售/清仓/下架',
    PRIMARY KEY (sku_id),
    KEY idx_sku_cat (category_l1, category_l2),
    KEY idx_sku_supplier (supplier_id)
) ENGINE=InnoDB COMMENT='商品SKU维表(2100)';

CREATE TABLE IF NOT EXISTS dim_users (
    user_id        INT         NOT NULL,
    nickname       VARCHAR(50) NULL,
    gender         VARCHAR(4)  NULL,
    age            INT         NULL,
    province       VARCHAR(20) NULL,
    city_tier      TINYINT     NULL COMMENT '城市线级1-5',
    register_date  DATE        NULL,
    source         VARCHAR(20) NULL COMMENT '直播间/短视频橱窗/商城搜索/老客推荐',
    is_fan         TINYINT     NULL COMMENT '是否粉丝',
    member_level   VARCHAR(10) NULL,
    PRIMARY KEY (user_id),
    KEY idx_users_province (province)
) ENGINE=InnoDB COMMENT='电商用户维表(10000)';

CREATE TABLE IF NOT EXISTS dim_suppliers (
    supplier_id          INT          NOT NULL,
    supplier_name        VARCHAR(100) NULL,
    supplier_type        VARCHAR(10)  NULL COMMENT '农户/合作社/工厂',
    region               VARCHAR(30)  NULL,
    coop_years           INT          NULL COMMENT '合作年限',
    annual_supply_tons   DECIMAL(10,1) NULL COMMENT '年供货量(吨)',
    PRIMARY KEY (supplier_id)
) ENGINE=InnoDB COMMENT='供应商维表(60)';

CREATE TABLE IF NOT EXISTS dim_stores (
    store_id             INT         NOT NULL,
    store_name           VARCHAR(60) NULL,
    city                 VARCHAR(10) NULL COMMENT '陇西/通渭/平凉/静宁',
    open_date            DATE        NULL,
    area_sqm             INT         NULL COMMENT '营业面积(㎡)',
    rent_monthly         DECIMAL(10,2) NULL COMMENT '月租金(元)',
    staff_cnt            INT         NULL,
    staff_cost_monthly   DECIMAL(10,2) NULL COMMENT '人均月人工成本(元)',
    util_monthly         DECIMAL(10,2) NULL COMMENT '月水电杂费(元)',
    amort_months         INT         NULL COMMENT '初始投入摊销月数',
    seats                INT         NULL,
    initial_investment   DECIMAL(12,2) NULL COMMENT '初始投入(元)',
    PRIMARY KEY (store_id)
) ENGINE=InnoDB COMMENT='线下门店维表(4)';

CREATE TABLE IF NOT EXISTS dim_warehouses (
    warehouse_id    INT         NOT NULL,
    warehouse_name  VARCHAR(60) NULL,
    area_sqm        INT         NULL,
    location        VARCHAR(20) NULL,
    PRIMARY KEY (warehouse_id)
) ENGINE=InnoDB COMMENT='仓库维表(2): 2400㎡主仓+1000㎡中转仓';

-- ------------------------------------------------------------------
-- 事实表
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_live_sessions (
    session_id         INT          NOT NULL,
    live_date          DATE         NOT NULL,
    start_time         VARCHAR(5)   NULL,
    duration_min       INT          NULL COMMENT '时长(分钟)',
    anchor             VARCHAR(20)  NULL,
    theme              VARCHAR(20)  NULL COMMENT '助农专场/宽粉工厂专场/常态化带货/节庆大促',
    is_festival        TINYINT      NULL,
    total_exposure     INT          NULL COMMENT '曝光量',
    total_enter        INT          NULL COMMENT '进入人次',
    total_stay         INT          NULL COMMENT '停留>30s人次',
    total_interact     INT          NULL COMMENT '互动人次',
    total_order_placed INT          NULL COMMENT '下单人数',
    total_paid         INT          NULL COMMENT '付款人数',
    gmv                DECIMAL(12,2) NULL COMMENT '场次GMV(元)',
    new_followers      INT          NULL,
    sku_cnt            INT          NULL,
    main_category      VARCHAR(20)  NULL COMMENT '主推品类L1(内容成本归集用)',
    PRIMARY KEY (session_id),
    KEY idx_sess_date (live_date),
    KEY idx_sess_theme (theme)
) ENGINE=InnoDB COMMENT='直播场次事实表(624)';

CREATE TABLE IF NOT EXISTS fact_live_minute_traffic (
    id              BIGINT      NOT NULL,
    session_id      INT         NOT NULL,
    minute_index    INT         NULL COMMENT '开播起第几分钟(每2分钟采样)',
    viewers_online  INT         NULL COMMENT '在线人数',
    exposure_delta  INT         NULL,
    enter_delta     INT         NULL,
    comment_cnt     INT         NULL,
    like_cnt        INT         NULL,
    follow_delta    INT         NULL,
    order_cnt       INT         NULL,
    pay_user_cnt    INT         NULL,
    PRIMARY KEY (id),
    KEY idx_min_session (session_id)
) ENGINE=InnoDB COMMENT='直播分钟级流量(22000+)';

CREATE TABLE IF NOT EXISTS fact_orders (
    order_id         VARCHAR(24) NOT NULL,
    user_id          INT         NOT NULL,
    order_time       DATETIME    NOT NULL,
    channel          VARCHAR(20) NULL COMMENT '直播间/短视频橱窗/商城搜索',
    session_id       INT         NULL COMMENT '关联直播场次(直播间渠道)',
    order_status     VARCHAR(10) NOT NULL COMMENT '已付款/已发货/已完成/已取消/已退款',
    item_cnt         INT         NULL,
    pay_amount       DECIMAL(10,2) NOT NULL COMMENT '支付金额',
    discount_amount  DECIMAL(10,2) NULL,
    freight          DECIMAL(10,2) NULL,
    province         VARCHAR(20) NULL,
    PRIMARY KEY (order_id),
    KEY idx_orders_user (user_id),
    KEY idx_orders_time (order_time),
    KEY idx_orders_session (session_id),
    KEY idx_orders_status (order_status)
) ENGINE=InnoDB COMMENT='电商订单(29000)';

-- 注意：本表 id 由自增主键生成（源数据不含业务id）
CREATE TABLE IF NOT EXISTS fact_order_items (
    id              BIGINT      NOT NULL AUTO_INCREMENT,
    order_id        VARCHAR(24) NOT NULL,
    sku_id          INT         NOT NULL,
    quantity        INT         NOT NULL,
    unit_price      DECIMAL(10,2) NULL,
    cost_price      DECIMAL(10,2) NULL,
    promotion_type  VARCHAR(20) NULL,
    PRIMARY KEY (id),
    KEY idx_items_order (order_id),
    KEY idx_items_sku (sku_id)
) ENGINE=InnoDB COMMENT='订单明细(42000+)';

CREATE TABLE IF NOT EXISTS fact_b2b_orders (
    b2b_id         INT          NOT NULL,
    customer_name  VARCHAR(100) NULL,
    customer_type  VARCHAR(20)  NULL COMMENT '火锅餐饮/商超/特产店/食品加工',
    order_date     DATE         NULL,
    sku_id         INT          NULL,
    quantity_kg    DECIMAL(10,1) NULL,
    unit_price     DECIMAL(10,2) NULL COMMENT '批发价(元/kg)',
    amount         DECIMAL(12,2) NULL,
    PRIMARY KEY (b2b_id),
    KEY idx_b2b_type (customer_type)
) ENGINE=InnoDB COMMENT='B2B供货订单(600)';

CREATE TABLE IF NOT EXISTS fact_purchases (
    purchase_id    INT          NOT NULL,
    supplier_id    INT          NULL,
    purchase_date  DATE         NULL,
    arrival_date   DATE         NULL,
    total_amount   DECIMAL(12,2) NULL,
    quality_grade  VARCHAR(4)   NULL COMMENT 'A1/A2/A3 感官分级',
    status         VARCHAR(10)  NULL,
    PRIMARY KEY (purchase_id),
    KEY idx_purch_supplier (supplier_id),
    KEY idx_purch_date (purchase_date)
) ENGINE=InnoDB COMMENT='采购单(750)';

CREATE TABLE IF NOT EXISTS fact_purchase_items (
    id             BIGINT       NOT NULL,
    purchase_id    INT          NOT NULL,
    sku_id         INT          NOT NULL,
    quantity_kg    DECIMAL(10,1) NULL,
    unit_cost      DECIMAL(10,2) NULL,
    amount         DECIMAL(12,2) NULL,
    quality_grade  VARCHAR(4)   NULL,
    rejected_kg    DECIMAL(10,1) NULL COMMENT '验收不合格量(采购损耗)',
    PRIMARY KEY (id),
    KEY idx_pi_purchase (purchase_id),
    KEY idx_pi_sku (sku_id)
) ENGINE=InnoDB COMMENT='采购明细(1200)';

CREATE TABLE IF NOT EXISTS fact_warehouse_stock (
    id                     BIGINT       NOT NULL,
    snapshot_date          DATE         NULL COMMENT '双周快照',
    warehouse_id           INT          NULL,
    sku_id                 INT          NULL,
    stock_kg               DECIMAL(10,1) NULL,
    in_transit_kg          DECIMAL(10,1) NULL,
    avg_daily_outflow_kg   DECIMAL(10,1) NULL COMMENT '日均出库量',
    avg_days_in_stock      DECIMAL(10,1) NULL COMMENT '库龄(天)',
    PRIMARY KEY (id),
    KEY idx_stock_sku_wh (sku_id, warehouse_id),
    KEY idx_stock_date (snapshot_date)
) ENGINE=InnoDB COMMENT='库存双周快照(1840, 20核心SKU×2仓)';

CREATE TABLE IF NOT EXISTS fact_deliveries (
    delivery_id    BIGINT       NOT NULL,
    biz_type       VARCHAR(10)  NULL COMMENT '电商订单/门店补货/B2B供货',
    ref_id         VARCHAR(32)  NULL COMMENT '关联业务单号',
    from_warehouse INT          NULL,
    to_region      VARCHAR(10)  NULL,
    ship_date      DATE         NULL,
    arrive_date    DATE         NULL,
    lead_time_days INT          NULL COMMENT '履约时效(天)',
    box_cnt        INT          NULL,
    weight_kg      DECIMAL(10,2) NULL,
    loss_kg        DECIMAL(10,2) NULL COMMENT '配送损耗',
    freight_cost   DECIMAL(10,2) NULL,
    delivery_mode  VARCHAR(30)  NULL COMMENT '旧模式(分散直发+统配)/新模式(集中仓储+分级配送)',
    PRIMARY KEY (delivery_id),
    KEY idx_deliv_mode (delivery_mode),
    KEY idx_deliv_biz (biz_type)
) ENGINE=InnoDB COMMENT='配送单(3600, 2025-04起新模式试点)';

CREATE TABLE IF NOT EXISTS fact_store_sales_daily (
    id               BIGINT       NOT NULL,
    store_id         INT          NOT NULL,
    sale_date        DATE         NOT NULL,
    category         VARCHAR(10)  NULL COMMENT '宽粉麻辣烫/特色小吃/饮品/伴手礼盒',
    order_cnt        INT          NULL,
    customer_cnt     INT          NULL,
    foot_traffic     INT          NULL COMMENT '进店人次',
    sales_amount     DECIMAL(10,2) NULL,
    discount_amount  DECIMAL(10,2) NULL,
    PRIMARY KEY (id),
    KEY idx_store_store_date (store_id, sale_date),
    KEY idx_store_cat (category)
) ENGINE=InnoDB COMMENT='门店日销售(11000+, 店×日×品类)';
