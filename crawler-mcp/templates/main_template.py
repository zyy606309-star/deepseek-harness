"""
main.py 入口文件模板
用于 XXL-JOB 任务注册和启动
"""

MAIN_TEMPLATE = '''import pymysql
from pyxxl import ExecutorConfig, PyxxlRunner
from datetime import datetime
from pyxxl.ctx import g
from dbutils.pooled_db import PooledDB

from {module_name} import {crawl_func}

# XXL-JOB 执行器配置
config = ExecutorConfig(
    xxl_admin_baseurl="https://udata-xxl-job.nie.netease.com/xxl-job-admin/api/",
    executor_app_name="{app_name}-executor",
    access_token="default_token",
    executor_listen_host="0.0.0.0",
    executor_listen_port=9999,
    executor_url="http://7.60.97.31:9999"
)

app = PyxxlRunner(config)

# 数据库连接池
SRC_DB_POOL = PooledDB(
    creator=pymysql,
    host='udata-rank-dumbo.nie.netease.com',
    user='us_gdas_rank',
    password='VqeioEKpr9ZTwbAv',
    database='us_gdas_rank',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor,
    maxconnections=10,
    ping=1,
)


@app.register(name="{job_name}")
def {task_func_name}():
    {crawl_func}(SRC_DB_POOL)


if __name__ == '__main__':
    app.run_executor()
'''

# 模板变量说明
MAIN_VARIABLES = {
    "module_name": "爬虫模块文件名（不含.py）",
    "crawl_func": "爬虫主函数名",
    "app_name": "应用名称（用于executor_app_name）",
    "job_name": "XXL-JOB 任务名",
    "task_func_name": "注册的任务函数名"
}
