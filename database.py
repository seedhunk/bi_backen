import re
import threading
from typing import Any
from fastapi import HTTPException, status

import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB
from env import *


class MysqlDatabaseConnection:
    # 用于避免数据库增删改的并发冲突,保证数据一致性
    appointment_lock = threading.Lock()
    branch_lock = threading.Lock()
    category_lock = threading.Lock()
    cooperation_lock = threading.Lock()
    inventory_lock = threading.Lock()
    measurement_lock = threading.Lock()  # measurement应该是只能insert?如果是就不需要该锁
    order_lock = threading.Lock()  # 可能需要优化,因为order的增删改可能有较大并发量
    profile_lock = threading.Lock()
    project_lock = threading.Lock()
    record_lock = threading.Lock()
    role_lock = threading.Lock()
    shopping_cart_lock = threading.Lock()  # 可能需要优化,因为shoppingCart的增删改可能有较大并发量
    sku_lock = threading.Lock()
    spu_lock = threading.Lock()
    staff_lock = threading.Lock()
    user_lock = threading.Lock()  # 可能需要优化,因为user的增删改可能有较大并发量
    sql_calc_found_rows_lock = threading.Lock()  # 全局变量SQL_CALC_FOUND_ROWS

    def __init__(self, host, port, user, password, db):
        try:
            self.pool = PooledDB(
                creator=pymysql,  # 使用连接数据库的模块
                maxconnections=10,  # 连接池允许的最大连接数，0 和 None表示不限制连接数
                mincached=3,  # 初始化时，链接池中至少创建的空闲的链接，0表示不创建
                maxcached=3,  # 链接池中最多闲置的链接，0和None表示不限制
                maxshared=0,  # 链接池中最多共享的链接数量,0和None表示全部共享,注:因为pymysql和mysqldb等模块的threadsafety都为1,
                # 所以值无论设置为多少，_max cached永远为0，所有永远是所有链接都共享
                blocking=True,  # 链接池中如果没有可用连接后，是否阻塞等待，True：等待  False：不等待然后报错
                maxusage=None,  # 一个连接最多被重复使用的次数，None表示无限制
                setsession=[],  # 开始会话时执行的命令列表。如：["set date style to ...","set time zone ..."]
                ping=1,  # ping mysql服务端，检查服务是否可用
                # 0 = None = never, 1 = default = whenever it is requested,
                # 2 = when a cursor is created, 4 = when a query is executed, 7 = always
                host=host, port=port, user=user, password=password, database=db
            )
        except Exception as e:
            print(str(e))

    def acquire(self) -> tuple[pymysql.connections.Connection, DictCursor]:
        """
        获取连接和游标
        :return:
        """
        # 连接
        conn = self.pool.connection()
        # 游标
        cursor = conn.cursor(cursor=DictCursor)
        return conn, cursor

    @staticmethod
    def release(connection: pymysql.connections.Connection, cursor: DictCursor):
        """
        关闭链接
        :param connection:
        :param cursor:
        :return:
        """
        cursor.close()
        connection.close()

    def _execute_sql_(self, sql: str | list[str], rollback: bool) -> tuple[pymysql.connections.Connection, DictCursor]:
        conn, cursor = self.acquire()
        try:
            if isinstance(sql, str):
                print(re.sub(r"\n[ \n]+", "\n    ", "\n  " + sql))
                cursor.execute(sql)
            else:
                print("SQL BEGIN")
                for s in sql:
                    print(re.sub(r"\n[ \n]+", "\n    ", "    " + s.strip()))
                    cursor.execute(s)
                print("SQL END")
            conn.commit()
        except Exception as e:
            print(f"SQL ERROR: {str(e)}")
            if rollback:
                conn.rollback()
            self.release(conn, cursor)
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
        return conn, cursor

    def select_all(self, sql: str | list[str]) -> tuple[dict[str, Any], ...]:
        """
        获取复数个查询结果字典的列表
        :param sql:
        :return:
        """
        conn, cursor = self._execute_sql_(sql, rollback=False)
        data = cursor.fetchall()
        self.release(conn, cursor)
        return data

    def select_one(self, sql: str | list[str]) -> dict[str, Any] | None:
        """
        获取单个查询结果的字典
        :param sql:
        :return:
        """
        conn, cursor = self._execute_sql_(sql, rollback=False)
        data = cursor.fetchone()
        self.release(conn, cursor)
        return data

    def select_apart_and_count_all(self, sql: str | list[str]) -> tuple[tuple[dict[str, Any], ...], int]:
        """

        :param sql: 查询语句中必须包含 SQL_CALC_FOUND_ROWS
        :return:
        """
        conn, cursor = self._execute_sql_(sql, rollback=False)
        data = cursor.fetchall()
        cursor.execute("SELECT FOUND_ROWS() as num")
        conn.commit()
        num = 0
        res = cursor.fetchone()
        if res:
            num = res["num"]
        self.release(conn, cursor)
        return data, num

    def insert(self, sql: str | list[str]) -> tuple[int, int]:
        """
        执行insert语句,插入数据
        :param sql:
        :return: (last_row_id, row_count)
        """
        conn, cursor = self._execute_sql_(sql, rollback=True)
        result = (cursor.lastrowid, cursor.rowcount)
        self.release(conn, cursor)
        return result

    def update(self, sql: str | list[str]) -> int:
        """
        执行update语句,更新数据
        :param sql:
        :return: row_count
        """
        conn, cursor = self._execute_sql_(sql, rollback=True)
        result = cursor.rowcount
        self.release(conn, cursor)
        return result

    def delete(self, sql: str | list[str]) -> int:
        """
        执行delete语句,删除数据
        :param sql:
        :return: row_count
        """
        return self.update(sql)


database = MysqlDatabaseConnection(
    host=PY_DB_HOST,
    port=PY_DB_PORT,
    user=PY_DB_USER,
    password=PY_DB_PASSWORD,
    db=PY_DB_DATABASE
)

database2 = MysqlDatabaseConnection( #用到uniform的user作为customer
    host=PY_DB_HOST,
    port=PY_DB_PORT,
    user=PY_DB_USER,
    password=PY_DB_PASSWORD,
    db=PY_DB_DATABASE
)
