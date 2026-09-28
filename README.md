# 「甘小胖」扎根富农产业链数据分析

> **⚠️ 模拟数据声明（重要）**
>
> 本仓库中的全部数据均为 **模拟数据**（Python Faker + 自定义业务规则生成，固定随机种子，可完全复现），
> 仅用于**数据分析方法与工程链路的复现展示**，**不代表任何真实经营结果**。
> 原始业务数据归项目方所有，本项目未使用、未包含任何真实业务数据。

对应简历项目：「"甘小胖"扎根富农产业链数据分析」——对直播电商、供应链、线下门店全链路数据的多源数据工程与商业分析。

## 项目背景

「甘小胖」是以甘肃定西宽粉为核心、覆盖甘肃名特优新农产品的直播电商 + 供应链 + 线下餐饮（宽粉麻辣烫连锁）全产业链项目。本项目围绕其业务链路，完成：

- **数据工程**：直播、电商交易、供应链、线下门店多源数据（约 12 万条，模拟）→ Python 清洗标准化 → MySQL 多表关联建模 → 「流量-转化-复购-履约」四层指标体系
- **分析建模**：约 2100 个 SKU 的品类 ROI/毛利拆解（Top3 重点品类贡献约 65% GMV）、RFM 用户分层、直播转化漏斗与排期建议、供应链周转与损耗分析（"集中仓储+分级配送"对比）、单店盈利测算（4 家门店可行性）
- **可视化交付**：matplotlib/seaborn 分析图表、openpyxl 多 sheet Excel 经营看板、完整分析报告

## 技术栈

Python 3.13（Pandas / NumPy / Faker / SQLAlchemy / PyMySQL / Matplotlib / Seaborn / openpyxl / python-docx）、MySQL 8.x、SQL、Excel。

## 目录结构

```
├── README.md                 # 本文件
├── requirements.txt          # Python 依赖
├── .gitignore
├── config/                   # 数据库配置模板（db_config.example.py）
├── data/
│   ├── raw/                  # 生成的模拟原始数据（约12万条，不入库，可重新生成）
│   ├── processed/            # 清洗后数据与分析结果（不入库）
│   └── sample/               # 每表 ≤1000 行样例（入库，便于直接查看数据结构）
├── scripts/                  # 全流程脚本（01 生成 → 08 报告，run_all.py 一键执行）
├── sql/                      # 建库建表 / 指标视图 / 5 个分析 SQL
├── reports/                  # 分析报告（md/docx）与图表 figures/
├── dashboard/                # Excel 经营分析看板
├── docs/                     # 指标口径、数据字典
└── logs/                     # 全流程验证日志
```

## 环境安装

要求：Python 3.10+、本地 MySQL 8.x（已有实例即可，仅新建 `ganxiaopang_db` 库）。

```bash
# 1) 创建虚拟环境并安装依赖
python -m venv venv
venv\Scripts\pip install -r requirements.txt

# 2) 配置数据库连接
#    将 config\db_config.example.py 复制为 config\db_config.py，按本机 MySQL 修改账号密码
#    （初始化脚本会自动创建 ganxiaopang_db 库与 gxp_app 应用账号，不影响实例中其他库）
```

## 模拟数据生成方法

```bash
# 生成全部模拟数据（固定随机种子 SEED=20240101，结果完全可复现，约 1-2 分钟）
venv\Scripts\python scripts\01_generate_data.py
```

生成规模（时间窗 2024-01-01 ~ 2025-12-31）：

| 表 | 行数（约） | 说明 |
|---|---|---|
| dim_sku | 2,100 | 11 个一级大类 / 68 个二级类目 |
| dim_users | 20,000 | 电商注册用户（复购率约 25%） |
| dim_suppliers / dim_stores / dim_warehouses | 60 / 4 / 2 | 供应商 / 门店（陇西、通渭、平凉、静宁）/ 仓库（2400㎡ 主仓 + 1000㎡ 中转仓） |
| fact_live_sessions | 624 | 直播场次（2024-2025，每周约 6 场） |
| fact_live_minute_traffic | 22,000+ | 直播分钟级流量（每 2 分钟采样） |
| fact_orders / fact_order_items | 26,349 / 38,857 | 电商订单及明细 |
| fact_b2b_orders | 600 | 火锅餐饮/商超/特产店 B2B 供货 |
| fact_purchases / fact_purchase_items | 750 / 1,200 | 采购单及明细 |
| fact_warehouse_stock | 1,840 | 20 个核心 SKU 双周库存快照 × 2 仓 |
| fact_deliveries | 3,600 | 电商/门店/B2B 配送（含损耗、新旧模式对比） |
| fact_store_sales_daily | 11,700+ | 4 家门店店×日×品类销售汇总 |
| **合计** | **约 13 万条** | |

原始层故意注入约 2%（1,035 处）脏数据（重复、缺失、异常值、格式不一致），用于完整展示清洗能力，由 `scripts/02_clean_data.py` 处理并全程留痕。

## 完整复现命令

```bash
# 步骤 1：生成模拟数据
venv\Scripts\python scripts\01_generate_data.py

# 步骤 2：清洗与标准化
venv\Scripts\python scripts\02_clean_data.py

# 步骤 3：建库建表并导入 MySQL（自动创建 ganxiaopang_db）
venv\Scripts\python scripts\03_load_to_mysql.py

# 步骤 4：导出每表1000行样例到 data/sample
venv\Scripts\python scripts\04_export_samples.py

# 步骤 5：执行 5 个分析 SQL 并导出结果（Python 复算校验一致性）
venv\Scripts\python scripts\05_run_queries.py

# 步骤 6：生成分析图表（SimHei 中文）
venv\Scripts\python scripts\06_make_figures.py

# 步骤 7：生成 Excel 经营看板
venv\Scripts\python scripts\07_make_dashboard.py

# 步骤 8：生成分析报告（Markdown，可用 pandoc 转 Word）
venv\Scripts\python scripts\08_make_report.py

# 或者一键执行步骤 1-8（MySQL 需已启动）
venv\Scripts\python scripts\run_all.py
```

分析 SQL 单独存放在 `sql/` 目录，可在 MySQL 客户端直接执行。

## 指标口径

「流量-转化-复购-履约」四层指标体系的完整口径见 **[docs/指标口径.md](docs/指标口径.md)**（并以 `sql/01_metric_views.sql` 中的视图固化）；表结构说明见 **[docs/数据字典.md](docs/数据字典.md)**。

## 与简历真实项目的区别

| 维度 | 简历真实项目 | 本复现仓库 |
|---|---|---|
| 数据 | 真实业务数据（约 12 万条，项目方所有） | **模拟数据**（Faker + 业务规则生成，种子固定） |
| 结论数字 | 真实经营结果 | 由模拟数据经同一套代码链路真实计算得出，量级与结构经参数校准贴近合理区间（如 Top3 品类 GMV 占比 ≈65%），**数值本身不代表真实经营** |
| 环境 | 企业内部环境 | 本地 MySQL 8 + Python venv，任何人都可一键复现 |
| 价值 | 支撑真实业务决策 | 完整展示数据工程 → 建模 → 分析 → 可视化的方法论与工程能力 |

## 主要产出

- `dashboard/甘小胖经营分析看板.xlsx`：核心指标 / 品类 ROI / 用户分层 / 直播漏斗 / 供应链 / 门店测算 6 个 sheet（嵌入图表、含目录超链接）
- `reports/甘小胖经营数据分析报告.md`：含背景、数据与口径、方法、图表、结论与可落地建议（可用 pandoc 一键转 Word）
- `reports/figures/`：10 张全部分析图表（SimHei 中文）
- `logs/`：analysis_results.json（核心指标与交叉校验结果）、全流程验证日志

## License

本项目代码以 [MIT License](LICENSE) 开源。再次提醒：仓库内全部数据为 **模拟数据**，仅用于方法复现，不代表真实经营结果。
