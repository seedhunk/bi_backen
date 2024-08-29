from tortoise import fields, Model
from typing import Any
from tortoise.contrib.pydantic import pydantic_model_creator
from fastapi import HTTPException, status
import pymysql
import re
from env import *
from pymysql.cursors import DictCursor
from services import Datetime

conn = pymysql.connect(host=PY_DB_HOST, port=PY_DB_PORT, user=PY_DB_USER, password=PY_DB_PASSWORD,
                       database="new_uniform")  # 用于执行tortoise无法实现的sql


def execute_sql(query: str):
    print(re.sub(r"\n[ \n]+", "\n    ", "\n  " + query))
    conn.ping(reconnect=True)
    cursor = conn.cursor(DictCursor)
    try:
        cursor.execute(query)  # 执行sql
        conn.commit()
        method = query.split()[0].lower()
        if method == "select":
            result = cursor.fetchall()
        elif method == "insert":
            result = (cursor.lastrowid, cursor.rowcount)
        elif method == "update" or method == "delete":
            result = cursor.rowcount
        else:
            result = None
    except Exception as e:
        conn.rollback()
        conn.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    cursor.close()
    return result


"""tortoise 无法实现复杂的数据库结构，所以仅用于简单的结构标记，不体现较复杂的结构，如复合主键，甚至外键"""


class PathField(fields.CharField):
    def __init__(self, **kwargs: Any):
        super().__init__(max_length=65535, **kwargs)


class IDField(fields.IntField):
    def __init__(self, **kwargs: Any):
        super().__init__(pk=True, index=True, generated=True, **kwargs)


class Authority(Model):
    id = IDField()
    name = fields.CharField(max_length=16, null=False)
    parent_id = fields.IntField(null=False)


class Branch(Model):
    id = IDField()
    name = fields.CharField(max_length=255, null=False, index=True)
    address = fields.CharField(max_length=255, null=True)
    parent_id = fields.IntField(null=False)


class BranchSubRelation(Model):
    parent_id = fields.IntField(pk=True, null=False)
    child_id = fields.IntField(null=False)

    class Meta:
        table = "branch_sub_relation"


class Category(Model):
    id = IDField()
    name = fields.CharField(max_length=16, null=False)


class Cooperation(Model):
    project_id = fields.IntField(null=False, pk=True)
    spu_id = fields.IntField(null=False)


class Inventory(Model):
    id = IDField()
    branch_id = fields.IntField(null=False)
    sku_id = fields.IntField(null=False)
    current = fields.IntField(null=False)
    threshold = fields.IntField(null=False)


class Project(Model):
    id = IDField()
    name = fields.CharField(max_length=255, null=False)
    parent_id = fields.IntField(null=False)
    partner = fields.CharField(max_length=255, null=True)
    created_time = fields.DatetimeField(default=Datetime.now().strftime('%Y-%m-%d %H:%M:%S'), auto_now_add=True, null=False)
    modified_time = fields.DatetimeField(auto_now=True, null=False)
    description = fields.TextField(null=True)
    spu_amount = fields.IntField(null=False, default=0)
    encryption = fields.CharField(max_length=16, null=True)


class ProjectSubRelation(Model):
    parent_id = fields.IntField(pk=True, null=False)
    child_id = fields.IntField(null=False)

    class Meta:
        table = "project_sub_relation"


class Role(Model):
    id = IDField()
    name = fields.CharField(max_length=255, null=False)
    branch_id = fields.IntField(null=False)


class RoleToAuthority(Model):
    role_id = fields.IntField(pk=True, null=False)
    authority_id = fields.IntField(null=False)

    class Meta:
        table = "role_to_authority"


class SKU(Model):
    id = IDField()
    code = fields.CharField(max_length=16, null=False)
    spu_id = fields.IntField(null=False)
    material = fields.CharField(max_length=255, null=True)
    size = fields.CharField(max_length=8, null=True)
    color = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "sku"


class SPU(Model):
    id = IDField()
    code = fields.CharField(max_length=16, null=False)
    type = fields.BooleanField(null=False, description="0 is MTM, 1 is RTW")
    category_id = fields.IntField(null=False)
    name = fields.CharField(max_length=255, null=True)
    description = fields.TextField(null=True)
    image_path_list = fields.TextField(null=True)
    size_chart = PathField(null=True)
    pattern_path = PathField(null=True)
    standard_price = fields.FloatField(null=True)
    sale_price = fields.FloatField(null=True)
    created_time = fields.DatetimeField(auto_now_add=True)
    modified_time = fields.DatetimeField(auto_now=True)
    rule_name = fields.CharField(max_length=255, null=True)
    status = fields.CharField(max_length=16, null=False)

    class Meta:
        table = "spu"


class Staff(Model):
    id = IDField()
    user_id = fields.IntField(null=False)
    name = fields.CharField(max_length=255, null=True)
    code = fields.CharField(max_length=32, null=True)
    id_card = fields.CharField(max_length=32, null=True)
    modified_time = fields.DatetimeField()


class StaffToRole(Model):
    staff_id = fields.IntField(pk=True, null=False)
    role_id = fields.IntField(null=False)

    class Meta:
        table = "staff_to_role"


class User(Model):
    id = IDField()
    password = fields.CharField(max_length=64, null=True)
    email = fields.CharField(max_length=64, null=True)
    created_time = fields.DatetimeField(auto_now_add=True)
    modified_time = fields.DatetimeField(auto_now=True)
    is_verified = fields.BooleanField(null=False, default=False)


# YP uniform merge start
class Profile(Model):
    id = fields.IntField(pk=True, index=True, unique=True)
    user_id = fields.IntField(index=True, null=False)
    ENGname = fields.CharField(max_length=20, null=False)
    CHIname = fields.CharField(max_length=20, null=True)
    gender = fields.CharField(max_length=20, null=False)
    birth = fields.DateField(unique=False, null=True)
    # schoolID should be project id
    project_id = fields.IntField(unique=False, null=False)
    # qr_quote = fields.TextField(unique=False, null=False)
    qr_quote = fields.CharField(default="s", max_length=100, unique=True)
    avatar = fields.CharField(max_length=255, null=False)


class Measurement(Model):
    mid = fields.IntField(pk=True, null=False, index=True)
    profileID = fields.IntField(null=False)
    date = fields.DatetimeField(auto_now=True)
    height = fields.FloatField(null=True)
    weight = fields.FloatField(null=True)
    frontpic = fields.TextField(null=True, unique=False)
    sidepic = fields.TextField(null=True)
    measureId = fields.CharField(max_length=200, null=False)
    sizes = fields.TextField(null=True, unique=False)
    frontProfileBody = fields.TextField(null=True, unique=False)
    sideProfileBody = fields.TextField(null=True, unique=False)
    measureType = fields.IntField(null=False)


class Record(Model):
    recordID = fields.IntField(pk=True, unique=True, null=False)
    profileID = fields.IntField(unique=False, null=False)
    date = fields.DatetimeField(auto_now=True)
    userID = fields.IntField(unique=False, null=False)
    mid = fields.IntField(unique=True, null=False)


user_pydantic = pydantic_model_creator(User)
# uniform_pydantic = pydantic_model_creator(Uniform, name="Uniform", exclude=("image",))

profile_pydantic = pydantic_model_creator(Profile, name="Profile", exclude=("id", "qr_quote", "user_id"))

measurement_pydantic = pydantic_model_creator(Measurement, name="Measurement", exclude=(
    "frontpic", "sidepic", "shoulder", "bust", "waist", "hip", "sleevelen", "clothlen", "sideseam"))
measurement_pydantic_genera = pydantic_model_creator(Measurement, name="generaMeasurement", exclude=("mid", "date"))
measurement_pydantic_get = pydantic_model_creator(Measurement, name="getMeasurement", exclude=("profileID",))

records_pydantic = pydantic_model_creator(Record, name="Records")
profiles_pydantic = pydantic_model_creator(Profile, name="Profiles")

# YP uniform merge end
# user_pydantic = pydantic_model_creator(User, include=('',))
