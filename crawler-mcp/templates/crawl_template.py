"""
爬虫逻辑模板
具体的数据获取 + 数据库保存逻辑
"""

CRAWL_TEMPLATE = '''"""
{description}
数据来源: {source_url}
生成时间: {generate_time}
"""

import hashlib
import json
import re
import time
import requests
from lxml import html
from datetime import datetime
from pyxxl.ctx import g

from utils.s3_utils import upload_s3

# 请求头
HEADERS = {{
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "{referer}"
}}


def md5_encode(text: str) -> str:
    """MD5 编码"""
    md5_hash = hashlib.md5()
    md5_hash.update(text.encode('utf-8'))
    return md5_hash.hexdigest()


def get_html(url: str) -> str:
    """获取页面 HTML"""
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = 'utf-8'
    return response.text


def save_data(result: dict, db_pool):
    """保存数据到数据库"""
    conn = None
    try:
        conn = db_pool.connection()
        with conn.cursor() as cursor:
            # 检查是否存在
            check_sql = "SELECT * FROM `{table_name}` WHERE `{unique_field}` = %s"
            cursor.execute(check_sql, (result['{unique_field}'],))
            existing_data = cursor.fetchone()

            # 上传图片到 S3（如果有图片字段）
            if result.get('{image_field}'):
                image_url = upload_s3(
                    result['{image_field}'],
                    '{s3_bucket}',
                    f"{{md5_encode(result['{unique_field}'])}}.png"
                )
                result['{image_field}'] = image_url

            # 准备数据
            new_data = {{
{data_mapping}
                'created_dt': datetime.now() if not existing_data else existing_data['created_dt'],
                'updated_dt': datetime.now()
            }}

            if existing_data:
                # 比较字段是否有变化
                compare_fields = [{compare_fields}]
                all_same = all(
                    str(existing_data.get(f)) == str(new_data.get(f))
                    for f in compare_fields
                )

                if all_same:
                    # 无变化，仅更新时间
                    update_sql = "UPDATE `{table_name}` SET `updated_dt` = %s WHERE `{unique_field}` = %s"
                    cursor.execute(update_sql, (new_data['updated_dt'], new_data['{unique_field}']))
                else:
                    # 有变化，更新所有字段
                    update_sql = """
                    UPDATE `{table_name}` SET
{update_set_clause}
                        `updated_dt` = %s
                    WHERE `{unique_field}` = %s
                    """
                    cursor.execute(update_sql, (
{update_values}
                        new_data['updated_dt'],
                        new_data['{unique_field}']
                    ))
            else:
                # 插入新数据
                insert_sql = """
                INSERT INTO `{table_name}`
                ({insert_columns})
                VALUES ({insert_placeholders})
                """
                cursor.execute(insert_sql, (
{insert_values}
                ))

            conn.commit()
            g.logger.info(f"数据保存成功: {{result['{unique_field}']}}")

    except Exception as e:
        g.logger.error(f"数据保存失败: {{e}}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def get_list() -> list:
    """获取列表数据"""
    g.logger.info("📋 获取列表...")

    url = "{list_url}"
    response_text = get_html(url)
    dom = html.fromstring(response_text)

    items = []
    elements = dom.xpath('{list_xpath}')

    for el in elements:
        item = dict()
{list_parse_code}
        items.append(item)

    g.logger.info(f"   找到 {{len(items)}} 条数据")
    return items


def get_detail(item: dict) -> dict:
    """获取详情数据"""
    url = item.get('detail_url')
    if not url:
        return item

    try:
        response_text = get_html(url)
        dom = html.fromstring(response_text)

{detail_parse_code}

        return item
    except Exception as e:
        g.logger.error(f"获取详情失败: {{url}} - {{e}}")
        return item


def {crawl_func}(db_pool):
    """主爬取函数"""
    g.logger.info("🚀 开始爬取 {description}...")

    # 1. 获取列表
    items = get_list()

    # 2. 获取详情并保存
    for i, item in enumerate(items, 1):
        g.logger.info(f"   [{{i}}/{{len(items)}}] {{item.get('{unique_field}', 'unknown')}}...")

        # 获取详情
        item = get_detail(item)

        # 保存数据
        save_data(item, db_pool)

        time.sleep(0.5)  # 礼貌性延迟

    g.logger.info(f"✨ 爬取完成！共 {{len(items)}} 条数据")


if __name__ == '__main__':
    # 本地测试（需配置本地数据库）
    from dbutils.pooled_db import PooledDB
    import pymysql

    test_pool = PooledDB(
        creator=pymysql,
        host='localhost',
        user='root',
        password='',
        database='test',
        charset='utf8mb4',
    )
    {crawl_func}(test_pool)
'''

# 模板变量说明
CRAWL_VARIABLES = {
    # 基础信息
    "description": "爬虫描述",
    "source_url": "数据来源 URL",
    "generate_time": "生成时间",
    "referer": "请求头 Referer",
    "crawl_func": "主爬取函数名",

    # 数据库相关
    "table_name": "数据库表名",
    "unique_field": "唯一标识字段（用于判断更新/插入）",
    "image_field": "图片字段名",
    "s3_bucket": "S3 存储桶名",
    "data_mapping": "数据字段映射代码",
    "compare_fields": "需要比较的字段列表",
    "update_set_clause": "UPDATE SET 子句",
    "update_values": "UPDATE 值列表",
    "insert_columns": "INSERT 列名",
    "insert_placeholders": "INSERT 占位符",
    "insert_values": "INSERT 值列表",

    # 解析相关
    "list_url": "列表页 URL",
    "list_xpath": "列表元素 XPath",
    "list_parse_code": "列表解析代码",
    "detail_parse_code": "详情解析代码"
}
