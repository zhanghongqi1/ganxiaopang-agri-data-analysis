# -*- coding: utf-8 -*-
"""数据库连接配置模板（ganxiaopang_db）。

使用方法：
    复制本文件为同目录下的 db_config.py，按本机 MySQL 环境修改。
    db_config.py 已被 .gitignore 排除，不会被提交到 GitHub。

本项目复用本地便携版 MySQL 8.4 实例（端口 3306），
仅新建 ganxiaopang_db 数据库与 gxp_app 应用账号，不影响实例中的其他库。
"""

# 应用账号（分析脚本运行时使用，仅授予 ganxiaopang_db 权限）
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "gxp_app",
    "password": "Gxp@2026",   # 请改为本机实际设置的密码
    "database": "ganxiaopang_db",
    "charset": "utf8mb4",
}

# root 账号（仅 scripts/03_load_to_mysql.py 初始化建库建账号时使用）
ROOT_DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",           # 本机便携实例 root 默认空密码
    "charset": "utf8mb4",
}
