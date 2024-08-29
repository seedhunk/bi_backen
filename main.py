"""
遵循REST规范
"""
import asyncio
import string
import inspect
import re
import random
import jwt
from env import *
from models import (execute_sql, StaffToRole)
import json
import os
import time
from datetime import timedelta, date as Date, datetime
import io
from models import (User, user_pydantic, Profile, Project, profile_pydantic, measurement_pydantic, Measurement,
                    measurement_pydantic_genera, Record, SPU, SKU, records_pydantic, Category, ProjectSubRelation, conn)
import uuid
from typing_extensions import TypedDict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import List
from starlette.responses import FileResponse
from starlette.requests import Request
from starlette.responses import JSONResponse
# from database import database2
from database import database
from recommend import Recommendation
from services import (TokenData, get_order_by_str_from_sort, token_generator, get_password_hash, Datetime,
                      verify_password, AuthorityConst)

from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, status, Header, Body, WebSocket
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise
from pydantic import BaseModel
import uvicorn
import pandas as pd
import numpy as np
from fastapi.staticfiles import StaticFiles

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr


class EmailSchema(BaseModel):
    email: List[EmailStr]


conf = ConnectionConfig(
    MAIL_USERNAME="brikeny213@gmail.com",
    MAIL_PASSWORD="cgik nhmu rrgg yobx",
    MAIL_FROM="CAFILAB@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

oath2_scheme = OAuth2PasswordBearer(tokenUrl='user/token')

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    data = await websocket.receive_text()
    data = json.loads(data)
    last_in = 0
    last_or = 0
    last_new = 0
    while True:
        sql = f"""select SQL_CALC_FOUND_ROWS * from inventory where branch_id={data['branch_id']} and current < threshold"""
        in_list, in_count = database.select_apart_and_count_all(sql)
        sql = f"""select SQL_CALC_FOUND_ROWS * from `order` where transfer_to = {data['branch_id']}"""
        or_list, or_count = database.select_apart_and_count_all(sql)
        sql = f"""select SQL_CALC_FOUND_ROWS * from `order` where isNew = 1"""
        orlist, orcount = database.select_apart_and_count_all(sql)
        if or_count != last_or or in_count != last_in or orcount != last_new:
            data_back = {"inventory": in_count,
                         "orders": or_count,
                         "isNew": orcount}
            await websocket.send_json(data_back)
        last_in = in_count
        last_or = or_count
        last_new = orcount
        await asyncio.sleep(5)


# 随机码
random_number: dict = {}
random_code: dict = {}
new_email: dict = {}


@app.get("/list_files/{page}/{num}")
async def list_files(page: int, num: int):
    files = os.listdir("/opt/lampp/htdocs/spu_img")
    datas = []
    for data in files:
        print(data)
        datas.append({'name': data,
                      'time': time.ctime(os.path.getmtime(f'/opt/lampp/htdocs/spu_img/{data}')),
                      'size': round(os.path.getsize(f'/opt/lampp/htdocs/spu_img/{data}') / (1024 * 1024), 2),
                      'url': f'https://info.cafilab.com/spu_img/{data}'})
    return {'len': len(datas), 'data': datas[(page - 1) * num:(page) * num]}


@app.get("/list_files_name")
async def list_files_name():
    files = os.listdir("/opt/lampp/htdocs/spu_img")
    datas = []
    for data in files:
        datas.append(data)
    return datas


@app.post("/list_files/delete")
async def list_files_delete(url: str = Body(embed=True)):
    files = os.listdir("/opt/lampp/htdocs/spu_img")
    datas = []
    os.remove("/opt/lampp/htdocs/spu_img/" + url)
    return 'Success'


''' "id": row["id"], '''


@app.post("/json2excel")
async def json2excel(json_data: list = Body()):
    df = pd.read_json(json.dumps(json_data))
    excel_file = io.BytesIO()
    df.to_excel(excel_file, index=False)
    excel_file.seek(0)
    return StreamingResponse(excel_file,
                             media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             headers={'Content-Disposition': 'attachment; filename=data.xlsx'})

    # excel_file = './data.xlsx'
    # df.to_excel(excel_file, index=False)
    # return FileResponse(excel_file, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename='data.xlsx')


# /file/tmp
@app.post("/excel2json")
async def excel2json(file: UploadFile = File(...)):
    contents = await file.read()
    df = pd.read_excel(contents)
    result = []
    for _, row in df.iterrows():
        item = {"id": '', "code": row["code"], "type": row["type"], "category_id": row["category_id"],
                "name": row["name"],
                "description": row["description"], "image_path_list": row["image_path_list"],
                "size_chart": row["size_chart"], "pattern_path": row["pattern_path"],
                "standard_price": row["standard_price"],
                "sale_price": row["sale_price"], "created_time": row["created_time"],
                "modified_time": row["modified_time"]}
        result.append(item)
    for item in result:
        for key, value in item.items():
            if isinstance(value, float) and np.isnan(value):
                item[key] = None
    return result


def get_token_data(token: str = Depends(oath2_scheme)) -> TokenData:
    token_data = TokenData(token)
    if token_data.staff_id == 0:
        user = database.select_one(f"select modified_time from user where id={token_data.user_id}")
        if user is None:
            # print(re.sub(r"\n[ \n]+", "\n    ", "\n  " + f"No staff id={payload['staff_id']}"))
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not exist")
        modified_time = user["modified_time"]
    else:
        staff = database.select_one(f"select modified_time from staff where id={token_data.staff_id}")
        if staff is None:
            # print(re.sub(r"\n[ \n]+", "\n    ", "\n  " + f"No staff id={payload['staff_id']}"))
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff not exist")
        modified_time = staff["modified_time"]
    if token_data.modified_time != modified_time:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token need update")
    return token_data


async def get_current_user(token: str = Depends(oath2_scheme)):
    try:
        payload = jwt.decode(token, config_credentials['SECRET'], algorithms=['HS256'])
        user = await User.get(id=payload.get("user_id"))
    except Exception:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await user


# Uniform API merge start

@app.get('user/profile')  # FIXME:修改了接口名称，前端需要对应修改, 返回的字典部分key变化
async def __get_profiles__(qr_quote: str = "", token_data: TokenData = Depends(get_token_data)):
    if qr_quote:
        if token_data.staff_id == 0:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
        sql = f"select * from profile join project on project.id=profile.project_id where qr_quote={repr(qr_quote)}"
    else:
        sql = f"""
            select * from profile join project on project.id=profile.project_id 
            where user_id={token_data.user_id} order by id desc
            """
    profile_list = database.select_all(sql)
    return {"status": "Success", "data": profile_list}


@app.get('/notification')
async def __get_notification__(token_data: TokenData = Depends(get_token_data)):
    if token_data is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    list = database.select_all(
        f"select * from notification where user_id={token_data.user_id} order by create_time desc limit 0,10")
    return list

@app.post("/send_mail")
async def send_mail(email: EmailSchema, token_data: TokenData = Depends(get_token_data)):
    sql = f"""select distinct * from user
                    inner join staff on user.id = staff.user_id
                    where user.email = '{email.email[0]}'
                """
    user = database.select_one(sql)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email")
    global random_number
    random_number[token_data.user_id] = random.randint(100000, 999999)
    template = f"""

        <html>

        <body>

          <p>Verification code:

        <br>{random_number[token_data.user_id]}</p>

          </body>

        </html>

        """

    message = MessageSchema(

        subject="Business Intelligence System",

        recipients=email.dict().get("email"),  # List of recipients, as many as you can pass

        body=template,

        subtype="html"

    )

    fm = FastMail(conf)

    await fm.send_message(message)

    return JSONResponse(status_code=200, content={"message": "email has been sent"})

@app.post("/send_mail2client")
async def send_mail2client(email: EmailSchema, token_data: TokenData = Depends(get_token_data)):
    sql = f"""select * from user where user.email = '{email.email[0]}'"""
    user = database.select_one(sql)
    if user is not None:
        return False

    global random_code
    global new_email
    random_code[token_data.user_id] = random.randint(100000, 999999)
    new_email[token_data.user_id] = email.email[0]
    template = f"""

        <html>

        <body>

          <p>Verification code:

        <br>{random_code[token_data.user_id]}</p>

          </body>

        </html>

        """

    message = MessageSchema(

        subject="AOB-uniform",

        recipients=email.dict().get("email"),  # List of recipients, as many as you can pass

        body=template,

        subtype="html"

    )

    fm = FastMail(conf)

    await fm.send_message(message)

    return True

@app.post("/add_email")
async def add_email(email: str = Body(embed=True), code: str = Body(embed=True), token_data: TokenData = Depends(get_token_data)):
    if int(code) == random_code[token_data.user_id] and email == new_email[token_data.user_id]:
        database.update(f"update user set email = '{email}' where id = {token_data.user_id}")
        return True
    else:
        return False


@app.post('/notification')
async def __post_notification__(project_id: int = (Body(embed=True)), token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.PROJECT_DELETE not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    name = database.select_one(f"select name from project where id = {project_id}")
    profiles = database.select_all(f"select * from profile where project_id = {project_id}")
    repeat = []
    dataList = {}
    for profile in profiles:
        if profile['user_id'] not in repeat:
            repeat.append(profile['user_id'])
            dataList[profile['user_id']] = [profile['ENGname']]
        else:
            dataList[profile['user_id']].append(profile['ENGname'])
    for user_id in repeat:
        database.insert(
            f"insert into notification (user_id, is_check, content) values ({user_id}, 0, 'Since the project {name['name']} has been discontinued, the project has been destroyed, and the corresponding profiles: {', '.join(dataList[user_id])} have also been removed. If needed, please recreate them and select a different project.')")
    return 1


@app.post('/notification/check')
async def __post_notification_check__(token_data: TokenData = Depends(get_token_data)):
    if token_data is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    database.update(f"update notification set is_check = 1 where user_id={token_data.user_id}")
    return 1


@app.get('/getprofileByQrcode')  # TODO:建议弃用
async def __get_profile_by_qrcode__(QRquote: str):
    profile = await Profile.get(qr_quote=QRquote)
    project = await Project.get(id=profile.project_id)
    return {"status": "Successfully create", "data": {"profile": profile, "project": project}}


@app.post("/avatar/{profile_id}", tags=["File"], summary="上传头像")
async def __upload_avatar_image__(file: UploadFile = File(...), profile_id: str = None):
    filename = profile_id + os.path.splitext(file.filename)[1]
    path = f"./avatar/{filename}"
    try:
        with open(path, "wb") as f:
            f.write(await file.read())
        await Profile.filter(id=profile_id).update(avatar=f"https://aob.bi.cafilab.com/avatar/{filename}")
        return {'url': f"https://aob.bi.cafilab.com/avatar/{filename}"}
    except Exception as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


@app.post('/profile')
async def __create_profile__(profile: profile_pydantic, user: user_pydantic = Depends(get_current_user)):
    user_id = user.id
    profile_info = profile.dict(exclude_unset=True)
    profile_info["user_id"] = user_id
    profile_obj = await Profile.create(**profile_info)
    profile_id = profile_obj.id
    s_uuid = str(uuid.uuid3(uuid.NAMESPACE_URL, str(profile_id)))
    qr_quote = ''.join(s_uuid.split('-')).upper()
    profile_obj.qr_quote = qr_quote
    # new_profile = await profile_pydantic.from_tortoise_orm(profile_obj)
    await Profile.filter(id=profile_id).update(qr_quote=qr_quote)
    profile_data = await Profile.get(id=profile_id)
    project = await Project.get(id=profile_info['project_id'])
    # type = await Type.get(typeEng= typeEng)
    # schooltype = await SchoolType.get(schoolID=school.schoolID ,typeID=typeID)
    return {"status": "Successfully create",
            "data":
                {
                    "profileID": profile_obj.id,
                    "project": project,
                    "profile_info": profile_data
                }

            }


@app.delete("/profile/{profile_id}", tags=["Order"], summary="用户删除购物车项")
async def __delete_shopping_cart__(
        profile_id: int,
        token_data: TokenData = Depends(get_token_data)
):
    url = database.select_one(f"select avatar from profile where id={profile_id}")
    path = f"./avatar/{url['avatar'].split('/')[-1]}"
    os.remove(path)
    sql = f"""
        delete from profile where id={profile_id} and user_id={token_data.user_id}
        """
    row_count = database.delete(sql)
    return {"row_count_update": row_count}

@app.delete("/account/delete", tags=["Account"], summary="注销客户端账户")
async def __delete_account__( token_data: TokenData = Depends(get_token_data)):
    sql = f"""
        delete from profile where user_id={token_data.user_id}"""
    database.delete(sql)
    sql = f"""
        delete from user where id={token_data.user_id}"""
    row_count = database.delete(sql)
    return {"row_count_update": row_count}

@app.post('/updateProfile')
async def __update_profile__(profile: profile_pydantic, profileID: str,
                             user: user_pydantic = Depends(get_current_user)):
    profile_id = profileID
    profile_info = profile.dict(exclude_unset=True)
    await Profile.filter(id=profile_id).update(ENGname=profile_info["ENGname"],
                                               CHIname=profile_info["CHIname"],
                                               gender=profile_info["gender"],
                                               birth=profile_info["birth"],
                                               project_id=profile_info["project_id"],
                                               avatar=profile_info["avatar"]
                                               )
    profile_data = await Profile.get(id=profile_id)
    project = await Project.get(id=profile_info["project_id"])
    return {"status": "Successfully update",
            "data":
                {
                    "profileID": profile_id,
                    "project": project,
                    "profile": profile_data
                }
            }


@app.get('/profile/detailes')
async def __get_profile__(QRquote: str, user: user_pydantic = Depends(get_current_user)):
    user_id = user.id
    profile = await Profile.get(user_id=user_id)
    # response = await profile_pydantic.from_queryset(Profile.get(user_id=user_id))
    project = await Project.get(id=profile.project_id)
    #  school = await School.get(schoolID=schooltype.schoolID)
    #  type = await Type.get(typeID= schooltype.typeID)
    return {"status": "ok",
            "data":
                {
                    "profileID": profile.id,
                    "ENGname": profile.ENGname,
                    "CHIname": profile.CHIname,
                    "gender": profile.gender,
                    "birth": profile.birth,
                    "projectID": profile.project_id,
                    "QRquote": profile.qr_quote,
                    "project": project
                }

            }


@app.post('/measurement')
async def __create_measurement__(measurement: measurement_pydantic):
    measurement_info = measurement.dict(exclude_unset=True)
    measurement_obj = await Measurement.create(**measurement_info)
    new_measurement = await measurement_pydantic.from_tortoise_orm(measurement_obj)
    return {"status": "Successfully create",

            }


@app.post('/genera_measurement')
async def __genera_measurement__(measurement: measurement_pydantic_genera):
    measurement_info = measurement.dict(exclude_unset=True)
    profile_id = measurement_info['profileID']
    profile_obj = await Profile.get(id=profile_id)
    if profile_obj:
        measurement_obj = await Measurement.create(**measurement_info)
        new_measurement = await measurement_pydantic.from_tortoise_orm(measurement_obj)
        # measurement_update = await measurement_obj.filter(profileID=profile_id).update(**measurement_info)
        # new_measurement = await measurement_pydantic_genera.from_queryset(measurement_obj)
        return {"status": "Successfully update",
                "data": new_measurement,
                "profile": profile_obj
                }


@app.get('/get_measurement')
async def __get_measurement__(profileID: int):
    profile_id = profileID
    # response = await measurement_pydantic_get.from_queryset(Measurement.filter(profileID=profile_id))
    count = await Measurement.filter(profileID=profile_id).count()
    measurement = {}
    if count > 0:
        measurement = await Measurement.filter(profileID=profile_id).order_by('-mid').first()
    profile = await Profile.get(id=profile_id)
    project = await Project.get(id=profile.project_id)
    return {"status": "ok",
            "data":
                {
                    'measurement': measurement,
                    'profile': profile,
                    'project': project
                }
            }


@app.get('/get_measurements')
async def __get_measurements__(profileID: int):
    profile_id = profileID
    # response = await measurement_pydantic_get.from_queryset(Measurement.filter(profileID=profile_id))
    measurements = await Measurement.filter(profileID=profile_id).order_by('-mid').all()
    profile = await Profile.get(id=profile_id)
    res = []
    for item in measurements:
        measurement = item.__dict__
        user = await User.get(id=profile.user_id)
        count = await Record.filter(mid=item.mid).count()
        if count > 0:
            record = await Record.get(mid=item.mid)
            user = await User.get(id=record.userID)
        measurement['user'] = user
        res.append(measurement)
    return {"status": "ok",
            # return {"status": "ok",
            "data":
                res
            }


@app.post('/record')
async def __create_record__(measurement: measurement_pydantic_genera, user: user_pydantic = Depends(get_current_user)):
    user_id = user.id
    measurement_info = measurement.dict(exclude_unset=True)
    profile_id = measurement_info['profileID']
    profile_obj = await Profile.get(id=profile_id)
    user_obj = await User.get(id=user_id)
    if profile_obj and user_obj:
        measurement_obj = await Measurement.create(**measurement_info)
        new_measurement = await measurement_pydantic.from_tortoise_orm(measurement_obj)
        add_records = await Record.create(profileID=profile_id, userID=user_id, mid=measurement_obj.mid)
    return {"status": "ok",
            "data": {}
            }


@app.get('/getRecords')
async def __get_records__():
    records = await Record.all()
    res = []
    for item in records:
        json_dic = item.__dict__
        user = await User.get(id=item.userID)
        profile = await Profile.get(id=item.profileID)
        project = await Project.get(id=profile.project_id)
        json_dic['user'] = user
        json_dic['profile'] = profile
        json_dic['project'] = project
        res.append(json_dic)
    return {"status": "ok",
            "data": res
            }


async def get_records_page(recordID: int, page: int = 1, size: int = 10) -> List[Record]:
    offset = (page - 1) * size
    limit = size
    records = await records_pydantic.from_queryset(
        Record.filter(records=recordID).all().offset(offset).limit(limit).all())

    return records


async def get_profiles_page(profileID: int, page: int = 1, size: int = 10) -> List[Profile]:
    offset = (page - 1) * size
    limit = size
    # uniforms = await uniform_pydantic.from_queryset(Uniform.all().offset(offset).limit(limit).all())

    profiles = await profile_pydantic.from_queryset(
        Profile.filter(id=profileID).all().offset(offset).limit(limit).all())
    return profiles


@app.get('/get_records')
async def __get_records__(recordID, page: int = 1, size: int = 10):
    record = await Record.get(recordID=recordID)
    records = get_records_page(page, size, recordID)
    # response = await profile_pydantic.from_queryset(Profile.get(user_id=user_id))
    # profiles = await Profile.get(id=record.profileID)
    profiles = get_profiles_page(record.profileID, page, size)
    return {"status": "ok",

            "data":
                {
                    "records": records,
                    "profiles": profiles

                }

            }


# @app.get('/get_type/')
# async def get_type():
#     type = await Type.all()
#     return {"status": "ok",

#             "data":type
#             }


# Uniform API merge end
@app.put('/user', tags=["BiSystem", "Account", ], summary="注册帐户")
async def __register_user__(request_form: OAuth2PasswordRequestForm = Depends()):
    hashed_password = get_password_hash(request_form.password)
    email = request_form.username

    try:
        sql = f"insert into user (password,email) values ('{hashed_password}','{email}')"
        last_row_id, row_count = database.insert(sql)
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"{str(e)}")
    template = f"""

        <html>

        <body>

          <p>Your BISYSTEM account is actived!
          
        <br>username is your email
        
        <br>password:{request_form.password}
        
        <br>you can sign in your account and reset your password </p>

          </body>

        </html>

        """

    message = MessageSchema(

        subject="Business Intelligence System",

        recipients=[email],  # List of recipients, as many as you can pass

        body=template,

        subtype="html"

    )

    fm = FastMail(conf)

    await fm.send_message(message)
    return last_row_id


@app.put("/user/password", tags=["BiSystem", "Account", ], summary="修改密码")
async def __change_user_password__(
        old_password: str = Form(), new_password: str = Form(),
        token_data: TokenData = Depends(get_token_data)
):
    sql = f"select id,password from user where id={token_data.user_id}"
    user = database.select_one(sql)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    if not verify_password(old_password, user["password"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "old password is wrong")
    with database.user_lock:
        sql = f"""
            update user
            set password='{get_password_hash(new_password)}'
            where id={user['id']}
            """
        row_count = database.update(sql)
    return {"row_count": row_count}


@app.put("/user/reset_password", tags=["BiSystem", "Account", ], summary="重置密码")
async def __change_user_password__(
        email: str,
        code: int,
        new_password: str = Form(),
        token_data: TokenData = Depends(get_token_data)
):
    global random_number
    if code != random_number[token_data.user_id]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "code wrong")
    with database.user_lock:
        sql = f"""
            update user
            set password='{get_password_hash(new_password)}'
            where email='{email}'
            """
        row_count = database.update(sql)
    random_number[token_data.user_id] = -1
    return {"row_count": row_count}


# 未遵循REST, 因为OAuth2PasswordRequestForm只接受urlEncodeForm
@app.post('/user/token/{time}', tags=["Token", ], summary="登录，获取token")
async def __get_token__(time: float,
                        request_form: OAuth2PasswordRequestForm = Depends()):
    if not request_form.username:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "username needed")
    (token, is_staff) = await token_generator(request_form.username, request_form.password, time)
    return {'access_token': token, 'token_type': 'bearer', 'username': request_form.username, 'is_staff': is_staff}


@app.post('/user/token', tags=["Token", ], summary="顾客登录，获取token")
async def __cus_get_token__(request_form: OAuth2PasswordRequestForm = Depends()):
    if not request_form.username:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "username needed")
    (token, is_staff) = await token_generator(request_form.username, request_form.password, -1)
    return {'access_token': token, 'token_type': 'bearer', 'username': request_form.username, 'is_staff': is_staff}


@app.get('/user/email', tags=["Token", ], summary="顾客获取email")
async def __email__(token_data: TokenData = Depends(get_token_data)):
    user = database.select_one(f"select email from user where id={token_data.user_id}")
    return user['email']


@app.get('/user/token_isexpired', tags=["Token", ], summary="登录，获取token")
async def __token_isexpired__(token_data: TokenData = Depends(get_token_data)):
    return True


@app.get('/user/re_token', tags=["Token", ], summary="登录，获取token")
async def __re_token__(token_data: TokenData = Depends(get_token_data)):
    new_token_data = {
        "user_id": token_data.user_id,
        "email": token_data.email,
        "staff_id": token_data.staff_id,
        "modified_time": token_data.modified_time,
        "authority_dict": token_data.authority_dict,
        "exp": (datetime.datetime.utcnow() + datetime.timedelta(hours=0.5)).timestamp()
    }
    try:
        token = jwt.encode(new_token_data, SECRET)
    except Exception as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Error when encode token")
    return token


# @app.get("/user/role/{role_id}/token", tags=["Token", ], summary="切换role")
# async def __change_role__(role_id: int, token: str = Depends(oath2_scheme)):
#     token = change_role(token, role_id)
#     return {'access_token': token, 'token_type': 'bearer'}


def get_branch_list_from_authority_dict(authority_dict: dict[int, list[int]]):
    branch_id_list = []
    for x_list in authority_dict.values():
        for branch_id in x_list:
            if branch_id not in branch_id_list:
                branch_id_list.append(branch_id)
    if not branch_id_list:
        branch_list = []
    else:
        branch_list = database.select_all(f"select * from branch where id in ({str(branch_id_list)[1:-1]})")
    return branch_list


''' /profile/get '''


@app.get("/staff/self", tags=["BiSystem"], summary="staff登录后获取个人信息")
async def __get_staff_info_with_token__(token_data: TokenData = Depends(get_token_data)):
    user = database.select_one(f"select * from user where id = {token_data.user_id}")
    staff = database.select_one(f"select name from staff where id={token_data.staff_id}")
    auth_list = database.select_one(
        f"SELECT r.auth_list FROM staff s JOIN staff_to_role str ON s.id = str.staff_id JOIN role r ON str.role_id = r.id WHERE s.id = {token_data.staff_id}")
    if user is None or staff is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    branch_list = get_branch_list_from_authority_dict(token_data.authority_dict)
    return {
        "staff_id": token_data.staff_id,
        "staff_name": staff["name"],
        "email": token_data.email,
        "user_id": token_data.user_id,
        "auth_list": auth_list["auth_list"],
        "branch_list": branch_list
    }


#############################################################{config_credentials['resource_file_url']}/tmp/{file_name}
# File ######################################################
app.mount("/avatar", StaticFiles(directory="avatar"), name="avatar")


@app.post("/file/tmp", tags=["File"], summary="上传文件")
async def __upload_product_image__(file: UploadFile = File(...)):
    file_name = file.filename
    # print(f"{await file.read()}")
    # exec(str(await file.read(), encoding='utf-8'))
    # file_name = f"{int(Datetime.now().timestamp() * 1000000)}.{file.filename.split('.')[-1]}"
    path = f"/opt/lampp/htdocs/spu_img/{file_name}"
    try:
        with open(path, "wb") as f:
            f.write(await file.read())
        return {
            "file_name": file_name
        }
    except Exception as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


@app.get("/file/tmp/{file_name}")
async def __get_tmp_file__(file_name: str):
    # 防止不安全的访问行为
    if '/' in file_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Don't use Path in file name!")
    file_path = f"{config_credentials['resource_file_url']}/tmp/{file_name}"
    res = FileResponse(
        file_path,
        filename=file_name,
    )
    return res


#############################################################
# Product####################################################

class SKUData(BaseModel):
    id: int | None
    code: str
    spu_id: int | None
    material: str | None
    size: str | None
    color: str | None


class SPUData(BaseModel):
    id: int | None
    code: str
    type: bool  # 0 is MTM, 1 is RTW
    category_id: int
    name: str
    description: str | None
    image_path_list: list[str] | None
    size_chart: dict | None  # {'S':{'shoulder':55},'M':{}}
    pattern_path: str | None
    standard_price: float | None
    sale_price: float | None
    created_time: Datetime | None
    modified_time: Datetime | None
    sku_list: list[SKUData]
    rule_name: str


@app.get("/product/{product_id}", tags=["BiSystem", "Product"])
async def __get_product_with_product_id__(product_id: str, token_data: TokenData = Depends(get_token_data)):
    """
    """
    if AuthorityConst.PRODUCT_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"select * from spu where id={product_id}"
    spu = database.select_one(sql)

    sql = f"select * from sku where spu_id={product_id}"
    sku_list = database.select_all(sql)

    spu["sku_list"] = sku_list
    return spu


@app.get("/productCop", tags=[])
async def __get_product_with_product_id__(token_data: TokenData = Depends(get_token_data)):
    """
    """
    ''' if AuthorityConst.PRODUCT_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN) '''
    sql = f"select * from spu"
    spu = database.select_all(sql)

    return spu


@app.get("/productCode", tags=["BiSystem", "Product"])
async def __get_productCode(token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.PRODUCT_PUT not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql1 = f"select code from spu"
    sql2 = f"select code from sku"
    spu_code = database.select_all(sql1)
    sku_code = database.select_all(sql2)
    codes = [item['code'] for item in spu_code + sku_code]
    return codes


@app.put("/productExcel", tags=["BiSystem", "Product"], summary="添加或修改Product by Excel")
async def __add_or_update_product__(productList: list[SPUData], token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.PRODUCT_PUT not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    pro = []
    for product in productList:
        print(1, product)
        product.created_time = None
        product.modified_time = None

        spu_data = product.dict(exclude_none=True)
        spu_data["image_path_list"] = json.dumps(product.image_path_list)
        spu_data["size_chart"] = json.dumps(product.size_chart)
        sku_list = spu_data.pop("sku_list")
        # todo:未清除应该删除掉的文件
        # save image
        for image_file_name in product.image_path_list:
            tmp_path = f'{config_credentials["resource_file_url"]}/tmp/{image_file_name}'
            if os.path.exists(tmp_path):
                tmp_image = open(tmp_path, "rb")
                image_path = f'{config_credentials["resource_file_url"]}/product/image/{image_file_name}'
                image = open(image_path, "wb")
                image.write(tmp_image.read())
                image.close()
                tmp_image.close()
        # save pattern
        if product.pattern_path:
            tmp_path = f'{config_credentials["resource_file_url"]}/tmp/{product.pattern_path}'
            if os.path.exists(tmp_path):
                tmp_pattern = open(tmp_path, "rb")
                pattern_path = f'{config_credentials["resource_file_url"]}/product/pattern/{product.pattern_path}'
                pattern = open(pattern_path, "wb")
                pattern.write(tmp_pattern.read())
                pattern.close()
                tmp_pattern.close()

        try:
            if not product.id:
                # create spu
                spu = await SPU.create(**spu_data)
                product.id = spu.id
                # create skus
                try:
                    for sku_data in sku_list:
                        sku_data["spu_id"] = spu.id
                        await SKU.create(**sku_data)
                except Exception as e:
                    await spu.delete()
                    raise e
            else:
                # update spu
                spu = await SPU.get(id=spu_data["id"])
                spu = await spu.update_from_dict(spu_data)
                await spu.save()
                # update skus
                await SKU.filter(spu_id=spu.id).delete()
                for sku_data in sku_list:
                    await SKU.create(**sku_data)
        except Exception as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
        pro.append({"product_id": product.id})
        print(pro)
    print(11)
    return pro


@app.put("/product", tags=["BiSystem", "Product"], summary="添加或修改Product")
async def __add_or_update_product__(product: SPUData, token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.PRODUCT_PUT not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    product.created_time = None
    product.modified_time = None

    spu_data = product.dict(exclude_none=True)
    spu_data["status"] = 'active'
    spu_data["image_path_list"] = json.dumps(product.image_path_list)
    spu_data["size_chart"] = json.dumps(product.size_chart)
    sku_list = spu_data.pop("sku_list")
    # todo:未清除应该删除掉的文件
    # save image
    for image_file_name in product.image_path_list:
        tmp_path = f'{config_credentials["resource_file_url"]}/tmp/{image_file_name}'
        if os.path.exists(tmp_path):
            tmp_image = open(tmp_path, "rb")
            image_path = f'{config_credentials["resource_file_url"]}/product/image/{image_file_name}'
            image = open(image_path, "wb")
            image.write(tmp_image.read())
            image.close()
            tmp_image.close()
    # save pattern
    if product.pattern_path:
        tmp_path = f'{config_credentials["resource_file_url"]}/tmp/{product.pattern_path}'
        if os.path.exists(tmp_path):
            tmp_pattern = open(tmp_path, "rb")
            pattern_path = f'{config_credentials["resource_file_url"]}/product/pattern/{product.pattern_path}'
            pattern = open(pattern_path, "wb")
            pattern.write(tmp_pattern.read())
            pattern.close()
            tmp_pattern.close()

    try:
        if not product.id:
            # create spu
            print(spu_data)
            spu = await SPU.create(**spu_data)
            product.id = spu.id
            # create skus
            try:
                for sku_data in sku_list:
                    sku_data["spu_id"] = spu.id
                    sku = await SKU.create(**sku_data)
                    sql1 = f"""SELECT id FROM branch"""
                    branch_id_list = database.select_all(sql1)
                    for branch_id in branch_id_list:
                        sql2 = f"""insert into inventory (branch_id, sku_id, current, threshold, status) values 
                                ({branch_id['id']},{sku.id},0,0,'active'),"""
                        database.insert(sql2[:-1])
            except Exception as e:
                await spu.delete()
                raise e
        else:
            # update spu
            spu = await SPU.get(id=spu_data["id"])
            spu = await spu.update_from_dict(spu_data)
            await spu.save()
            # update skus
            await SKU.filter(spu_id=spu.id).delete()
            for sku_data in sku_list:
                await SKU.create(**sku_data)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return {"product_id": product.id}


@app.get("/product/image/{image_file_name}", response_class=FileResponse, tags=["BiSystem", "Product", ])
async def __get_product_image_file__(image_file_name: str, token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.PRODUCT_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    # 防止不安全的访问行为
    if '/' in image_file_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Don't use Path in file name!")
    file_path = f"{config_credentials['resource_file_url']}/product/image/{image_file_name}"
    res = FileResponse(file_path, filename=image_file_name)
    return res


@app.get("/product_del_isok/{spu_id}", tags=["BiSystem", "Product", ])
async def __get_product_del_isok__(spu_id: int, token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.PRODUCT_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""SELECT o.*
                    FROM order_product op
                    JOIN `order` o ON op.order_id = o.id
                    WHERE op.spu_id = {spu_id}
                    AND o.status NOT IN ('completed', 'cancelled')"""
    orderList = database.select_all(sql)
    if len(orderList) == 0:
        return True
    else:
        return False


@app.delete("/product", tags=["BiSystem", "Product", ])
async def __delete_products_in_list__(
        product_id: int = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.PRODUCT_DELETE not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""delete from spu where id = {product_id}"""
    row_count = database.delete(sql)
    # TODO: 删除spu相关文件
    try:
        await SKU.filter(spu_id=product_id).delete()
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return {"row_count": row_count}


@app.post("/getProductByProject", tags=["BiSystem", "Product", ], summary="分页查找product")
async def __getProductByProject__(
        project_id: int = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.PRODUCT_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    ''' select spu_id from cooperation where project_id = {project_id} '''
    print(project_id)
    sql = f"""
        select a.name , b.spu_id 
        from spu a,cooperation b
        where b.project_id = {project_id} and a.id = b.spu_id ;
        """
    spu_list = database.select_all(sql)
    ''' for spu in spu_list:
        spu["image_path_list"] = json.loads(spu["image_path_list"]) if spu["image_path_list"] else [] '''
    return {
        "spu_list": spu_list
    }


@app.get("/product", tags=["BiSystem", "Product", ], summary="分页查找product")
async def __get_all_product__(
        offset: int = 0, count: int = -1,
        name: str = None,
        sale_status: str = None,
        category_id: int = None,
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.PRODUCT_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if offset < 0 or count < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    sql = f"""select SQL_CALC_FOUND_ROWS * from spu where true
        {f"and name like '%{name}%' " if name is not None else ""}
        {f"and category_id = '{category_id}' " if category_id is not None else ""}
        {f"and status = '{sale_status}' " if sale_status is not None else ""}
        {f"limit {offset},{count} " if offset >= 0 and count > 0 else ""}
        """
    spu_list, spu_count = database.select_apart_and_count_all(sql)
    for spu in spu_list:
        spu["image_path_list"] = json.loads(spu["image_path_list"]) if spu["image_path_list"] else []
    return {
        "spu_list": spu_list,
        "spu_count": spu_count
    }


@app.put("/change_spu_status", tags=["BiSystem", "Product", ])
async def __get_all_skus__(token_data: TokenData = Depends(get_token_data),
                           sale_status: str = Body(embed=True),
                           spu_id: int = Body(embed=True)):
    if AuthorityConst.PRODUCT_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql_inventory = f"""update inventory 
                        set status = '{sale_status}'
                        WHERE sku_id IN
                        (SELECT s.id
                        FROM sku s
                        JOIN spu p ON s.spu_id = p.id
                        WHERE p.id = {spu_id})"""
    database.update(sql_inventory)
    sql = f"""update spu set status = '{sale_status}' where id = {spu_id}"""
    database.update(sql)


@app.get("/sku", tags=["BiSystem", "Product", ])
async def __get_all_skus__(token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.PRODUCT_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""select * from sku"""
    sku_list = database.select_all(sql)
    return {
        "sku_list": sku_list
    }


@app.get("/category", tags=["BiSystem", "Product", ])
async def __get_category_directory__():
    data = {}
    categories = database.select_all("select * from category")
    if not categories:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Wrong with get categories")
    for category in categories:
        data[category["id"]] = category["name"]
    return data


@app.put("/category", tags=["BiSystem", "Product", ], summary="创建新的category")
async def __add_category__(category_name: str = Body(embed=True), token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.PRODUCT_PUT not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    last_row_id, row_count = database.insert(f"insert into category (name) values ({repr(category_name)})")
    return {"last_row_id": last_row_id, "row_count": row_count}


@app.delete("/category/{category_id}", tags=["BiSystem", "Product", ], summary="删除category")
async def __delete_category__(category_id: int, token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.PRODUCT_DELETE not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    row_count = database.delete(f"delete from category where id={category_id}")
    return {"row_count": row_count}


# Inventory ####################
@app.get("/branch/{branch_id}/inventory", tags=["BiSystem", "Inventory", ], summary="分页查看inventory")
async def __get_inventories__(
        branch_id: int,
        offset: int = 0, count: int = -1, sort: str = "",
        token_data: TokenData = Depends(get_token_data),
):
    """
    获取 inventories结果集,可排序字段["id", "current", "threshold", "code", "color", "material", "size", "name"]
    """
    print(AuthorityConst.INVENTORY_GET not in token_data.authority_dict)
    if AuthorityConst.INVENTORY_GET not in token_data.authority_dict \
            or branch_id not in token_data.authority_dict[AuthorityConst.INVENTORY_GET]:
        raise HTTPException(status.HTTP_403_FORBIDDEN)

    can_be_sort_col_list = ["id", "current", "threshold", "code", "color", "material", "size", "name"]
    order_by = get_order_by_str_from_sort(sort, can_be_sort_col_list)
    sql = f"""
        select 
        SQL_CALC_FOUND_ROWS
        i.id as `id`,
        i.current as `current`,
        i.threshold as `threshold`,
        k.code as `code`,
        k.color as `color`,
        k.material as `material`,
        k.size as `size`,
        p.name as `name`
        from inventory i inner join sku k on i.sku_id = k.id inner join spu p on k.spu_id = p.id
        where i.branch_id={branch_id} and i.status = 'active'
        {f"order by {order_by} " if order_by else ""}
        {f"limit {offset},{count} " if offset >= 0 and count > 0 else ""}
        """
    inventory_list, inventory_count = database.select_apart_and_count_all(sql)
    return {"inventory_list": inventory_list, "inventory_count": inventory_count}


# @app.get("/branch/{branch_id}/inventory/count", tags=["BiSystem", "Inventory", ])
# async def __get_inventories_count_of_branch__(branch_id: int, token_data: TokenData = Depends(get_token_data)):
#     if AuthorityConst.INVENTORY_GET not in token_data.authority_dict \
#             or branch_id not in token_data.authority_dict[AuthorityConst.INVENTORY_GET]:
#         raise HTTPException(status.HTTP_403_FORBIDDEN)
#     sql = f"""select count(*) as inventory_count from inventory where branch_id={branch_id}"""
#     res = database.select_one(sql)
#     return {"inventory_count": res["inventory_count"]}


@app.put("/branch/{branch_id}/inventory/{inventory_id}/threshold", tags=["BiSystem", "Inventory", ],
         summary="修改一条inventory记录的threshold")
async def __change_inventory_threshold__(
        branch_id: int, inventory_id: int, threshold: int = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.INVENTORY_PUT not in token_data.authority_dict \
            or branch_id not in token_data.authority_dict[AuthorityConst.INVENTORY_PUT]:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"update inventory set threshold={threshold} where id={inventory_id} and branch_id={branch_id}"
    rowCount = database.update(sql)
    return {"rowCount": rowCount}


@app.put("/branch/{branch_id}/inventory/{inventory_id}/rectify", tags=["BiSystem", "Inventory", ],
         summary="修改一条inventory记录的threshold")
async def __inventory_rectify__(
        branch_id: int, inventory_id: int, current: int = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.INVENTORY_PUT not in token_data.authority_dict \
            or branch_id not in token_data.authority_dict[AuthorityConst.INVENTORY_PUT]:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"update inventory set current= {current} where id={inventory_id} and branch_id={branch_id}"
    rowCount = database.update(sql)
    return {"rowCount": rowCount}


@app.put("/branch/{branch_id}/inventory/threshold", tags=["BiSystem", "Inventory", ],
         summary="修改多条inventory记录的threshold")
async def __change_inventories_threshold__(
        branch_id: int, inventory_id_list: list[int] = Body(embed=True), threshold: int = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.INVENTORY_PUT not in token_data.authority_dict \
            or branch_id not in token_data.authority_dict[AuthorityConst.INVENTORY_PUT]:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if not inventory_id_list:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "inventory_id_list can't be empty")
    sql = f"""
        update inventory 
        set threshold={threshold} 
        where id in ({str(inventory_id_list)[1:-1]}) and branch_id={branch_id}"""
    with database.inventory_lock:
        rowCount = database.update(sql)
    return {"rowCount": rowCount}


@app.put("/branch/{branch_id}/inventory", tags=["BiSystem", "Inventory", ], summary="添加inventory记录")
async def __add_inventories__(
        branch_id: int, sku_id_list: list[int] = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.INVENTORY_PUT not in token_data.authority_dict \
            or branch_id not in token_data.authority_dict[AuthorityConst.INVENTORY_PUT]:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if not sku_id_list:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "sku_id_list can't be empty")
    sql = f"""insert into inventory (branch_id, sku_id, current, threshold) values"""
    for sku_id in sku_id_list:
        sql = f"{sql} ({branch_id},{sku_id},0,0),"
    (lastRowId, rowCount) = database.insert(sql[:-1])
    return {"lastRowId": lastRowId, "rowCount": rowCount}


@app.delete("/branch/{branch_id}/inventories", tags=["BiSystem", "Inventory", ])
async def __delete_inventories__(
        branch_id: int, inventory_id_list: list[int] = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.INVENTORY_DELETE not in token_data.authority_dict \
            or branch_id not in token_data.authority_dict[AuthorityConst.INVENTORY_DELETE]:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if not inventory_id_list:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "inventory_id_list can't be empty")
    sql = f"delete from inventory where id in ({str(inventory_id_list)[1:-1]}) and branch_id={branch_id}"
    with database.inventory_lock:
        database.delete(sql)


@app.get("/branch/{branch_id}/skus/notInInventory", tags=["BiSystem", "Inventory", ])
async def __get_all_skus_not_in_branch_inventory__(
        branch_id: int,
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.INVENTORY_PUT not in token_data.authority_dict \
            or branch_id not in token_data.authority_dict[AuthorityConst.INVENTORY_PUT]:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""
        select 
            spu.name as product_name,
            sku.id as sku_id,
            sku.color as color,
            sku.material as material,
            sku.size as size,
            sku.code as code
        from sku join spu 
        where sku.spu_id=spu.id and 
            not (sku.id in (select sku_id from inventory where branch_id={branch_id}))
    """
    return database.select_all(sql)


#############################################################
# Project & Cooperation######################################
class ProjectData(BaseModel):
    id: int = None
    name: str
    parent_id: int
    partner: str
    description: str = None
    spu_amount: int = None
    encryption: str = None


@app.get("/project/{project_id}/hasSubList", tags=["BiSystem", "Project", ])
async def __has_sub_list__(project_id: int):
    hasSubProject = False
    hasSubProduct = False
    if database.select_one(f"select * from project where parent_id={project_id} limit 1"):
        hasSubProject = True
    if database.select_one(f"select * from cooperation where project_id=project_id limit 1"):
        hasSubProduct = True
    return {
        "has_sub_project": hasSubProject,
        "has_sub_product": hasSubProduct
    }


@app.get("/project/{project_id}/subList", tags=["BiSystem", "Project", ], summary="获取project的subProject或商品列表")
async def __get_project_sub_list__(
        project_id: int,
        offset: int = 0, count: int = -1,
        start_day: Date = None, end_day: Date | None = None,
        name: str = None,
        category_id: int = None,
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.PROJECT_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)

    # get all sub_projects of project
    # can_be_sort_col_list = ["name", "created_time", "modified_time", "spu_amount"]
    # order_by = get_order_by_str_from_sort(sort, can_be_sort_col_list)
    sql = f"""
        select SQL_CALC_FOUND_ROWS * from project where parent_id={project_id}
        {f"and DATE(created_time) between '{start_day}' and  '{end_day}' " if start_day is not None and end_day is not None else ""}
        {f"and name like '%{name}%' " if name is not None else ""}
        {f"limit {offset},{count} " if offset >= 0 and count > 0 else ""}
        """
    sub_project_list, sub_project_count = database.select_apart_and_count_all(sql)

    # get all product of project
    # can_be_sort_col_list = ["name", "created_time", "modified_time", "code", "standard_price", "sale_price"]
    # order_by = get_order_by_str_from_sort(sort, can_be_sort_col_list)
    sql = f"""
        select SQL_CALC_FOUND_ROWS * from spu 
        where id in (select spu_id from cooperation where project_id={project_id})
        {f"and name like '%{name}%' " if name is not None else ""}
        {f"and category_id = '{category_id}' " if category_id is not None else ""}
        {f"limit {offset},{count} " if offset >= 0 and count > 0 else ""}
        """
    spu_list, spu_count = database.select_apart_and_count_all(sql)
    # for spu in spu_list:
    #     spu["image_path_list"] = json.loads(spu["image_path_list"]) if spu["image_path_list"] else []
    #     spu["size_chart"] = json.loads(spu["size_chart"]) if spu["size_chart"] else {}
    return {
        "id": project_id,
        "sub_project_list": sub_project_list,
        "sub_project_count": sub_project_count,
        "spu_list": spu_list,
        "spu_count": spu_count
    }


@app.get("/project/{project_id}")
async def __get_pro__():
    pass


@app.put("/project")
async def __add_or_update_project__(
        project_data_obj: ProjectData,
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.PROJECT_PUT not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    project_data = project_data_obj.dict(exclude_none=True)
    if project_data_obj.id is None:
        # add new project
        try:
            await Project.create(**project_data)
        except Exception as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    else:
        # update project
        # sql = f"""update project set """
        # for (key, value) in project_data:
        #     sql = sql + f"{key}={repr(value)},"
        # database.update(sql[:-1] + f" where id={project_data_obj.id}")
        project = await Project.get(id=project_data_obj.id)
        await project.update_from_dict(project_data)
        await project.save()


@app.delete("/project")
async def __delete_project_with_project_id_list__(
        project_id: int = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.PROJECT_DELETE not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    profiles = database.select_all(f"select id from profile where project_id = {project_id}")
    for profile in profiles:
        url = f"./avatar/{profile['id']}.jpg"
        os.remove(url)
    children = database.select_all(f"""select child_id from project_sub_relation where parent_id = {project_id}""")
    if children == ():
        parent = database.select_one(f"""select parent_id from project_sub_relation where child_id = {project_id}""")
        try:
            project = await Project.get(id=project_id)
            await project.delete()
        except Exception as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
        if parent is not None:
            parent_id = parent['parent_id']
            database.update(f"""UPDATE project SET spu_amount = COALESCE((
                                SELECT total_spu_amount FROM
                                (SELECT SUM(p.spu_amount) AS total_spu_amount
                                FROM project_sub_relation psr
                                JOIN project p ON psr.child_id = p.id
                                WHERE psr.parent_id = {parent_id}) subquery),0)
                                WHERE id = {parent_id}""")
    else:
        for child in children:
            try:
                project = await Project.get(id=child['child_id'])
                await project.delete()
            except Exception as e:
                raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
        try:
            project = await Project.get(id=project_id)
            await project.delete()
        except Exception as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@app.get("/project")
async def __get_project_list__(
        offset: int = 0, count: int = -1, sort: str = "",
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.PROJECT_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    can_be_sort_col_list = ["name", "created_time", "modified_time", "spu_amount"]
    order_by = get_order_by_str_from_sort(sort, can_be_sort_col_list)
    sql = f"""
        select SQL_CALC_FOUND_ROWS * from project
        {f"order by {order_by} " if order_by else ""}
        {f"limit {offset},{count} " if offset >= 0 and count > 0 else ""}
        """
    project_list, project_count = database.select_apart_and_count_all(sql)
    return {"project_list": project_list, "project_count": project_count}


@app.put("/cooperation")  # 其中一个列表长度为1
async def __create_cooperation__(
        project_id_list: list[int] = Body(embed=True),
        product_id_list: list[int] = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.COOPERATION_PUT not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if (not project_id_list) or (not product_id_list) or (len(project_id_list) != 1 and len(product_id_list) != 1):
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    values_list = []
    for project_id in project_id_list:
        for spu_id in product_id_list:
            values_list.append((project_id, spu_id))
    sql = f"""insert into cooperation (project_id, spu_id) values {str(values_list)[1:-1]}"""
    with database.cooperation_lock:
        (last_row_id, row_count) = database.insert(sql)
    return {"last_row_id": last_row_id, "row_count": row_count}


@app.delete("/cooperation")  # 其中一个列表长度为1
async def __delete_cooperation__(
        project_id_list: list[int] = Body(embed=True), product_id_list: list[int] = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.COOPERATION_DELETE not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if (not project_id_list) or (not product_id_list) or (len(project_id_list) != 1 and len(product_id_list) != 1):
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    sql = f"""
        delete from cooperation
        where project_id in ({str(project_id_list)[1:-1]}) and spu_id in ({str(product_id_list)[1:-1]})
        """
    row_count = database.delete(sql)
    return {"row_count": row_count}


#############################################################
# Branch ####################################################
@app.post("/branch", tags=["Branch", "BiSystem"], summary="创建branch")
async def __add_branch__(
        branch_name: str = Body(embed=True), branch_address: str = Body(embed=True),
        branch_phone: str = Body(embed=True), branch_id: int = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.BRANCH_PUT not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if branch_id == -1:
        sql = f"""
            insert into branch (name,address,parent_id,phone)
            values ({repr(branch_name)},{repr(branch_address)},1,{repr(branch_phone)});
        """
        (id, row_count) = database.insert(sql)
        return {"id": id,
                "row_count": row_count
                }
    else:
        sql = f"""
            update branch set name = {repr(branch_name)}, address={repr(branch_address)}, phone={repr(branch_phone)} where id = {branch_id}
            """
        row_count = database.update(sql)
        return row_count


@app.delete("/branch/{branch_id}", tags=["Branch", "BiSystem"], summary="删除branch")
async def __remove_branch__(branch_id: int, token_data: TokenData = Depends(get_token_data)):
    """须经由 parent branch 删除"""
    if AuthorityConst.BRANCH_DELETE not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""delete from user where id in (select user_id from staff s
              JOIN staff_to_role str ON s.id = str.staff_id
              JOIN role r ON str.role_id = r.id
              WHERE r.branch_id = {branch_id}) """
    database.delete(sql)
    sql = f"""delete from staff where id in 
            (select staff_id from staff_to_role str 
            join role r on str.role_id = r.id 
            where r.branch_id = {branch_id}) """
    database.delete(sql)
    sql = f"""delete from staff_to_role where role_id in (select id from role where branch_id = {branch_id})"""
    database.delete(sql)
    sql = f"""delete from role where branch_id = {branch_id}"""
    database.delete(sql)
    sql = f"""delete from branch where id={branch_id}"""
    row_count = database.delete(sql)
    return {"row_count": row_count}


@app.get("/branch", tags=["Branch", "BiSystem"], summary="查看branch")
async def __get_branch__(token_data: TokenData = Depends(get_token_data), name: str = None,
                         offset: int = 0, count: int = -1):
    if AuthorityConst.BRANCH_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""select SQL_CALC_FOUND_ROWS * from branch where parent_id = 1
        {f"and name like '%{name}%' or address like '%{name}%' " if name is not None else ""}
        {f"limit {offset},{count} " if offset >= 0 and count > 0 else ""}
        """
    branch_list, branch_count = database.select_apart_and_count_all(sql)
    return {"branch_list": branch_list,
            "branch_count": branch_count
            }


@app.get("/branchList", tags=["Branch", "BiSystem"], summary="查看branch")
async def __get_branch_list__(token_data: TokenData = Depends(get_token_data)):
    if token_data is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""select SQL_CALC_FOUND_ROWS * from branch where parent_id = 1
        """
    branch_list, branch_count = database.select_apart_and_count_all(sql)
    return {"branch_list": branch_list,
            "branch_count": branch_count
            }


#############################################################
# Staff & Role & Authority###################################
@app.put("/staff", tags=["Staff & Role & Authority", "BiSystem"], summary="将一个user加入staff")
async def __add_staff__(
        user_id: int = Body(embed=True),
        staff_name: str = Body(embed=True), staff_id_card: str = Body(embed=True),
        role_id: int = Body(embed=True),
        staff_id: int = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.STAFF_PUT not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if staff_id == -1:
        sql = f"""
            insert into staff (user_id, name, id_card) 
            values ({user_id}, {repr(staff_name)},{repr(staff_id_card)})
            """
        (staff_id, count) = database.insert(sql)
        sql = f"insert into staff_to_role (staff_id, role_id) values ({staff_id}, {role_id})"
        database.insert(sql)
        return staff_id
    else:
        database.update(f"update staff_to_role set role_id = {repr(role_id)} where staff_id = {staff_id}")
        database.update(
            f"update staff set name = {repr(staff_name)}, id_card = {repr(staff_id_card)} where id = {staff_id}")


@app.delete("/staff/delete", tags=["Staff & Role & Authority", "BiSystem"], summary="删除指定的staff")
async def __delete_a_staff_of_branch__(staff_id: int = Body(embed=True),
                                       token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.STAFF_DELETE not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""DELETE FROM user WHERE id = (SELECT user_id FROM staff WHERE id = {staff_id})"""
    database.delete(sql)
    sql = f"""delete from staff where id={staff_id}"""
    database.delete(sql)
    sql = f"""delete from staff_to_role where staff_id={staff_id}"""
    database.delete(sql)
    return 1


@app.post("/customer/get", tags=["Staff & Role & Authority", "BiSystem"], summary="查询customer")
async def __get_the_customer__(page: int = Body(embed=True), pageCount: int = Body(embed=True),
                               token_data: TokenData = Depends(get_token_data)):
    # if AuthorityConst.CUSTOMER_GET not in token_data.authority_dict:
    # raise HTTPException(status.HTTP_403_FORBIDDEN)
    sqlstaff = f"""select user_id from staff"""
    sql = f"""select id,account,email from user"""  # limit {(page-1)*pageCount},{pageCount}
    # sql2 = f"""select id,username,email,phone from user"""
    staff_id_list = database.select_all(sqlstaff)
    user_list = database.select_all(sql)
    customer_list = []
    for user in user_list:
        for staff in staff_id_list:
            if user['id'] == staff['user_id']:
                customer_list.append(user)
                break
    sql2 = f"""SELECT id,account,email
    FROM user
    WHERE NOT EXISTS (
    SELECT * FROM staff
    WHERE staff.user_id = user.id)"""
    customer2_list = database.select_all(sql2)
    # customer_total = database.select_all(sql2)
    # customer_list = database.select_all(sql)
    return customer2_list[(page - 1) * pageCount:pageCount], len(customer_list)


@app.post("/profile/get", tags=["Staff & Role & Authority", "BiSystem"], summary="查询profile")
async def __get_the_profile__(user_id: int = Body(embed=True), token_data: TokenData = Depends(get_token_data)):
    # if AuthorityConst.CUSTOMER_GET not in token_data.authority_dict:user_id:int=Body(embed=True),
    # raise HTTPException(status.HTTP_403_FORBIDDEN)token_data.user_id
    sql = f"""select * from profile where user_id = {user_id}"""
    profile_list = database.select_all(sql)  # database2
    for profile in profile_list:
        print(profile)
        sql2 = f"""
        select partner from project where id = {profile['project_id']}
    """
        profile['company'] = database.select_all(sql2)
        print(profile['company'])
        profile['profileID'] = profile['id']
    return profile_list


@app.post("/history/get", tags=["Staff & Role & Authority", "BiSystem"], summary="查询history")
async def __get_the_history__(user_id: int = Body(embed=True), token_data: TokenData = Depends(get_token_data)):
    # if AuthorityConst.CUSTOMER_GET not in token_data.authority_dict:
    # raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""select code,payment_method,origin,created_time,total_price from `order` where user_id = {user_id}"""
    history_list = database.select_all(sql)
    return history_list


@app.get("/staff")
async def __search_staff__(account: str):
    pass


@app.get("/spu_list/{project_id}", tags=["Staff & Role & Authority", "BiSystem"], summary="获取一个spu_list列表")
async def __get_all_spu__(project_id: int, ):  # token_data: TokenData = Depends(get_token_data)
    # if AuthorityConst.ROLE_GET not in token_data.authority_dict \
    # or branch_id not in token_data.authority_dict[AuthorityConst.ROLE_GET]:
    # raise HTTPException(status.HTTP_403_FORBIDDEN)

    sql = f"""select psr.child_id, p.name from project_sub_relation psr
            join project p on psr.child_id = p.id
            where psr.parent_id = {project_id}"""
    projects = database.select_all(sql)
    spu_list = []
    for project in projects:
        sql = f"""
            select * from spu 
            where id in (select spu_id from cooperation where project_id = {project['child_id']}) 
            and status = 'active' 
            """
        spus = database.select_all(sql)
        for spu in spus:
            spu['project'] = project['name']
        spu_list.extend(spus)
    parent_name = database.select_one(f"select name from project where id = {project_id}")
    return {
        "spu_list": spu_list,
        "project_name": parent_name['name']
    }


@app.get("/branch/{branch_id}/role", tags=["Staff & Role & Authority", "BiSystem"], summary="获取一个branch的所有role")
async def __get_all_roles_of_branch__(branch_id: int, name: str = None,
                                      offset: int = 0, count: int = -1,
                                      token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.ROLE_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""select SQL_CALC_FOUND_ROWS * from role where branch_id={branch_id}
        {f"and name like '%{name}%' " if name is not None else ""}
        {f"limit {offset},{count} " if offset >= 0 and count > 0 else ""}
        """
    role_list, role_count = database.select_apart_and_count_all(sql)
    for role in role_list:
        link_list, link_count = database.select_apart_and_count_all(
            f"""select SQL_CALC_FOUND_ROWS * from staff_to_role where role_id={role['id']}""")
        role['staffs'] = link_count
    return {"role_list": role_list,
            "role_count": role_count
            }


@app.delete("/branch/role/delete", tags=["Staff & Role & Authority", "BiSystem"], summary="删除指定的role")
async def __delete_a_roles_of_branch__(role_id: int = Body(embed=True),
                                       token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.ROLE_DELETE not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""delete from role where id={role_id}"""
    database.delete(sql)
    return 1


@app.post("/branch/{branch_id}/role", tags=["Staff & Role & Authority", "BiSystem"], summary="创建role")
async def __create_a_role_for_branch__(
        branch_id: int, role_name: str = Body(embed=True), authority_list: str = Body(embed=True),
        role_id: int = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.ROLE_PUT not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if "'" in role_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Name can't contain '")
    if role_id == -1:
        (role_id, rowcount) = database.insert(
            f"insert into role (name, branch_id, auth_list) values ({repr(role_name)},{branch_id},{repr(authority_list)})")
        sql = f"insert into role_to_authority (role_id, authority_id) values"
        authority_id_list = database.select_all(f"select id from authority")
        for authority_id in authority_id_list:
            sql = f"{sql} ({role_id},{authority_id['id']}),"
        database.insert(sql[:-1])
        return {"role_id": role_id}
    else:
        database.update(
            f"update role set auth_list = {repr(authority_list)}, name = {repr(role_name)} where id = {role_id}")


@app.get("/branch/{branch_id}/staff", tags=["Staff & Role & Authority", "BiSystem"])
async def __get_staff_roles_in_branch__(
        branch_id: int, offset: int = 0, count: int = -1, name: str = None,
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.ROLE_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""SELECT SQL_CALC_FOUND_ROWS s.id,s.name,s.id_card,s.user_id,u.email,r.id as role
        FROM staff s
        JOIN staff_to_role str ON s.id = str.staff_id
        JOIN role r ON str.role_id = r.id
        JOIN user u ON u.id = s.user_id
        WHERE r.branch_id = {branch_id}
        {f"and s.name like '%{name}%' or s.id_card like '%{name}%'" if name is not None else ""}
        {f"limit {offset},{count}" if offset >= 0 and count > 0 else ""}
        """
    staff_list, staff_count = database.select_apart_and_count_all(sql)
    return {"staff_list": staff_list,
            "staff_count": staff_count
            }


@app.get("/authority", tags=["Staff & Role & Authority", "BiSystem"])
async def __get_authorities_that_can_be_allocated_to_others__(
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.ROLE_PUT not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    auth_list = database.select_all(f"select * from authority")
    return {
        "authority_list": auth_list
    }


@app.post("/staff/role/addStaffWithRole", tags=["Staff & Role & Authority", "BiSystem"])
async def __give_staff_a_role__(id: int = Body(embed=True), role_list: list[int] = Body(embed=True),
                                token_data: TokenData = Depends(get_token_data)):
    staff_id = id
    for role_id in role_list:
        role = database.select_one(f"select branch_id from role where id={role_id}")
        if role is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Role not exist")
        branch_id = role["branch_id"]
        if AuthorityConst.ROLE_PUT not in token_data.authority_dict \
                or branch_id not in token_data.authority_dict[AuthorityConst.ROLE_PUT]:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
        database.insert(f"""insert into staff_to_role (staff_id,role_id) values ({staff_id},{role_id})
                        on duplicate key update
                        staff_id = values(staff_id),
                        role_id = values(role_id)
                        """)


#############################################################
# Appointment ###############################################
@app.put("/appointment", tags=["Appointment"], summary="创建appointment,只能由顾客本人创建")
async def __make_an_appointment__(
        day: Date = Body(embed=True), period: int = Body(embed=True),
        note: str = Body(embed=True), branch_id: int = Body(embed=True),
        profile_id: int = Body(embed=True), token_data: TokenData = Depends(get_token_data)
):
    # 根据实际检查period是否在营业时间内
    if day < Date.today() or (day == Date.today() and period / 4 <= Datetime.now().hour):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请延后预约时间")
    # 检查 profile 与 user 是否匹配
    profile = database.select_one(f"select user_id from profile where id={profile_id}")
    if profile is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Profile not exist")
    if profile["user_id"] != token_data.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Profile not belongs to you")

    with database.appointment_lock:
        # 检查 branch 在指定 day & period 预约人数是否已满
        sql = f"select count(*) as num from appointment where day='{day}' and period={period} and branch_id={branch_id}"
        num = database.select_one(sql)["num"]
        if num >= MAX_APPOINTMENT_NUM_IN_ONE_PERIOD:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "该时段预约已满")
        # 添加预约
        sql = f"""
            insert into appointment (branch_id, profile_id, day, period, note)
            values ({branch_id},{profile_id},'{day}',{period}, '{note}')
            """
        (appointment_id, count) = database.insert(sql)

    return {"appointment_id": appointment_id}


@app.get("/branch/{branch_id}/appointment", tags=["Appointment", "BiSystem"], summary="获取符合条件的appointments")
async def __get_appointments__(
        branch_id: int,
        profile_id: int = None,  # 顾客查看自己的预约
        day: Date = None, start_period: int = None, end_period: int = None,  # 按日期及时间段筛选
        start_day: Date = None, end_day: Date | None = None,  # 按日期区间筛选
        appointment_status: int = None, user_account: str = None,  # 按状态/用户邮箱搜索
        offset: int = 0, count: int = -1,
        token_data: TokenData = Depends(get_token_data)
):
    """取所有条件的交集，例如同时提供start_period,end_period,start_day,end_day,则筛选结果同时满足 <=day<= 以及 <=period<= """
    # if token_data.staff_id == 0 and profile_id is not None:  # 顾客查询指定profile的预约
    #     profile = database.select_one(f"select user_id from profile where id={profile_id}")
    #     if profile is None:
    #         raise HTTPException(status.HTTP_400_BAD_REQUEST, "Profile not exist")
    #     if profile["user_id"] != token_data.user_id:
    #         raise HTTPException(status.HTTP_403_FORBIDDEN)
    #     sql = f"""
    #         select * from appointment
    #         join profile on appointment.profile_id = profile.id
    #         join branch on appointment.branch_id=branch.id
    #         where appointment.profile_id={profile_id}
    #         order by day,period
    #         """
    #     appointment_list = database.select_all(sql)
    #     appointment_num = len(appointment_list)
    # elif token_data.staff_id == 0 and profile_id is None:  # 顾客查询账号下所有预约
    #     profile_list = database.select_all(f"select id from profile where user_id={token_data.user_id}")
    #     if not profile_list:
    #         return {"appointment_list": []}
    #     profile_id_list = [profile["id"] for profile in profile_list]
    #     sql = f"""
    #         select * from appointment
    #         join profile on appointment.profile_id = profile.id
    #         join branch on appointment.branch_id=branch.id
    #         where appointment.profile_id in ({str(profile_id_list)[1:-1]})
    #         order by day,period
    #         """
    #     appointment_list = database.select_all(sql)
    #     appointment_num = len(appointment_list)
    # else:  # 员工查询 branch 下满足条件预约

    ## TODO:
    # if AuthorityConst.APPOINTMENT_GET not in token_data.authority_dict \
    #         or branch_id not in token_data.authority_dict[AuthorityConst.APPOINTMENT_GET]:
    #     raise HTTPException(status.HTTP_403_FORBIDDEN)
    with database.sql_calc_found_rows_lock:
        sql = f"""
            select SQL_CALC_FOUND_ROWS * from appointment 
            join profile on appointment.profile_id = profile.id
            join user on user.id=profile.user_id
            join branch on appointment.branch_id=branch.id
            where branch_id={branch_id}
            {f"and day>='{start_day}' " if start_day is not None else ""}
            {f"and day<='{end_day}' " if end_day is not None else ""}
            {f"and day='{day}' " if day is not None else ""}
            {f"and period>={start_period} " if start_period is not None else ""}
            {f"and period<={end_period} " if end_period is not None else ""}
            {f"and status={appointment_status} " if appointment_status is not None else ""}
            {f"and profile.ENGname like '%{user_account}%' " if user_account is not None else ""}
            order by day,period
            {f"limit {offset},{count}" if offset >= 0 and count > 0 else ""}
            """
        appointment_list, appointment_num = database.select_apart_and_count_all(sql)
    return {"appointment_list": appointment_list, "appointment_num": appointment_num}


@app.get("/branch/appointment", tags=["Appointment", "BiSystem"], summary="顾客查看appointments")
async def __get_profile_appointments__(
        token_data: TokenData = Depends(get_token_data)
):
    if token_data is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    with database.sql_calc_found_rows_lock:
        sql = f"""
            select SQL_CALC_FOUND_ROWS * from appointment 
            join profile on appointment.profile_id = profile.id
            join user on user.id=profile.user_id
            join branch on appointment.branch_id=branch.id
            where profile_id in (select id from profile where user_id = {token_data.user_id})
            ORDER BY appointment.day DESC
            limit 0,10
            """
        appointment_list, appointment_num = database.select_apart_and_count_all(sql)
    return {"appointment_list": appointment_list, "appointment_num": appointment_num}


@app.put("/appointment/{appointment_id}", tags=["Appointment", "BiSystem"],
         summary="修改指定appointment的预约时间和状态")
async def __change_status_of_appointment__(
        appointment_id: int, appointment_status: int = Body(embed=True, default=None),
        appointment_day: Date = Body(embed=True, default=None),
        appointment_period: int = Body(embed=True, default=None),
        # appointment_branch_id: int = Body(embed=True, default=None),
        token_data: TokenData = Depends(get_token_data)
):
    """0 coming, 1 completed, -1 canceled, -2 timeout"""
    # 检查 status
    # if appointment_status not in range(-2, 2):
    #     raise HTTPException(status.HTTP_400_BAD_REQUEST)
    # if token_data.branch_id == 0 and appointment_status != -1:  # 顾客，只能将status改为-1 canceled
    #     raise HTTPException(status.HTTP_403_FORBIDDEN)

    # 根据实际检查period是否在营业时间内
    # if not (appointment_period in range(MORNING_OPEN, MORNING_CLOSE)
    #         or appointment_period in range(AFTERNOON_OPEN, AFTERNOON_CLOSE)
    #         or appointment_period in range(EVENING_OPEN, EVENING_CLOSE)):
    #     raise HTTPException(status.HTTP_400_BAD_REQUEST, "所选时段不在营业时间内")
    # if appointment_day < Date.today() \
    #         or (appointment_day == Date.today() and appointment_period / 4 <= Datetime.now().hour):
    #     raise HTTPException(status.HTTP_400_BAD_REQUEST, "请延后预约时间")
    # 检查Appointment存在性及有无修改权限
    # if token_data.branch_id == 0:
    #     sql = f"""
    #         select profile.user_id as user_id, appointment.branch_id as branch_id
    #         from appointment join profile on appointment.profile_id=profile.id
    #         where appointment.id={appointment_id}
    #         """
    #     appointment = database.select_one(sql)
    #     if appointment is None:
    #         raise HTTPException(status.HTTP_400_BAD_REQUEST, "Appointment not exist")
    #     if appointment["user_id"] != token_data.user_id:
    #         raise HTTPException(status.HTTP_403_FORBIDDEN, "Appointment not belongs to you")
    #     branch_id = appointment["branch_id"]
    # else:
    #     sql = f"select branch_id from appointment where id={appointment_id}"
    #     appointment = database.select_one(sql)
    #     if appointment is None:
    #         raise HTTPException(status.HTTP_400_BAD_REQUEST, "Appointment not exist")
    #     branch_id = appointment["branch_id"]
    #     if branch_id != token_data.branch_id:
    #         raise HTTPException(status.HTTP_403_FORBIDDEN, "Appointment not belongs to your branch")
    # with database.appointment_lock:
    # 检查 branch 在指定 day & period 预约人数是否已满
    # sql = f"""
    #     select count(*) as num from appointment
    #     where day='{appointment_day}' and period={appointment_period} and branch_id={branch_id}
    #     """
    # num = database.select_one(sql)["num"]
    # if num >= MAX_APPOINTMENT_NUM_IN_ONE_PERIOD:
    #     raise HTTPException(status.HTTP_400_BAD_REQUEST, "该时段预约已满")

    sql = f"""
        update appointment set status={appointment_status}, day='{appointment_day}', period={appointment_period}
        where id={appointment_id}
        """
    row_count = database.update(sql)
    return {"rowCount": row_count}


#############################################################
# Order #####################################################
order_status_option_list = ["pending", "failed", "processing", "shipped", "completed", "cancelled"]
order_payment_method_option_list = ["alipay", "wechat", "octopus", "cash"]  # TODO: 设置付款方式
order_origin_option_list = ["business app", "client app ", "website"]  # TODO: 设置订单来源


@app.post("/user/sku-from-spu", tags=["Order"], summary="获取spu里的sku")
async def __get_user_shopping_cart__(token_data: TokenData = Depends(get_token_data), spu_id: int = Body(embed=True)):
    sql = f"""select * from sku where spu_id={spu_id}"""
    shopping_cart_list = database.select_all(sql)
    return shopping_cart_list


@app.get("/user/shopping-cart", tags=["Order"], summary="获取token用户的购物车")
async def __get_user_shopping_cart__(token_data: TokenData = Depends(get_token_data)):
    sql = f"""select shopping_cart.id, shopping_cart.profile_id, shopping_cart.num, sku.material, sku.color, sku.size, spu.name, spu.sale_price, spu.image_path_list, project.id, project.name
        from shopping_cart 
        join sku on sku.id=shopping_cart.sku_id
        join spu on spu.id=sku.spu_id
        left join cooperation on cooperation.spu_id = spu.id
        join project on project.id = cooperation.project_id
        where user_id={token_data.user_id}
        """
    shopping_cart_list = database.select_all(sql)
    for shopping_cart in shopping_cart_list:
        parent_pro = database.select_one(
            f"select name from project where id in (select parent_id from project_sub_relation where child_id = {shopping_cart['project.id']})")
        shopping_cart["parent_pro"] = parent_pro["name"]
    return shopping_cart_list


@app.put("/user/shopping-cart", tags=["Order"], summary="用户将商品加入购物车")
async def __add_product_into_shopping_cart__(
        sku_id: int = Body(embed=True), spu_id: int = Body(embed=True),
        profile_id: int = Body(embed=True), product_num: int = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    sql = f"""select project_id from profile where id={profile_id} and user_id={token_data.user_id}"""
    profile = database.select_one(sql)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"User {token_data.user_id} has no Profile {profile_id}")
    # 检查 product 是否属于profile对应的project
    sql = f"""
        select * from cooperation 
        where spu_id in (select spu_id from sku where id={sku_id} and spu_id={spu_id})
        and project_id in (select child_id from project_sub_relation where parent_id = {profile["project_id"]})
        """
    if database.select_one(sql) is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Product not in project of profile")
    cart = database.select_one(
        f"select * from shopping_cart where sku_id = {sku_id} and profile_id = {profile_id} and user_id = {token_data.user_id}")
    # 添加shopping_cart项
    if cart is None:
        sql = f"""
            insert into shopping_cart (user_id,sku_id,profile_id,num)
            values ({token_data.user_id},{sku_id},{profile_id},{product_num})
            """
        (shopping_cart_id, row_num) = database.insert(sql)
        return {"id": shopping_cart_id}
    else:
        database.update(f"update shopping_cart set num = {cart['num'] + product_num} where id = {cart['id']}")
        return 1


@app.delete("/user/shopping-cart/{shopping_cart_id}", tags=["Order"], summary="用户删除购物车项")
async def __delete_shopping_cart__(
        shopping_cart_id: int,
        token_data: TokenData = Depends(get_token_data)
):
    sql = f"""
        delete from shopping_cart where id={shopping_cart_id} and user_id={token_data.user_id}
        """
    row_count = database.delete(sql)
    return {"row_count_update": row_count}


@app.put("user/shopping-cart/{shopping_cart_id}", tags=["Order"], summary="用户修改购物车项")
async def __modify_shopping_cart__(
        shopping_cart_id: int, sku_id: int = Body(embed=True), product_num: int = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    sql = f"""
        update shopping_cart set sku_id={sku_id},num={product_num}
        where id={shopping_cart_id} and user_id={token_data.user_id}
        """
    row_count = database.update(sql)
    return {"row_count_update": row_count}


@app.get("/{branch_id}/orders", tags=["Order", "BiSystem"], summary="筛选符合条件的order并排序")
async def __filter_orders__(
        # 筛选参数
        start_day: Date = None, end_day: Date | None = None,
        unique_id: str = None, branch_id: int = None,
        status: str = None,
        # 排序参数
        offset: int = 0, count: int = -1,
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.ORDER_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""
        select SQL_CALC_FOUND_ROWS * from `order` where appoint_branch = {branch_id} and transfer_from is NULL
        {f"and DATE(created_time) between '{start_day}' and  '{end_day}' " if start_day is not None and end_day is not None else ""}
        {f"and unique_id like '%{unique_id}%' " if unique_id is not None else ""}
        {f"and status = '{status}' " if status is not None else ""}
        order by id desc
        {f"limit {offset},{count} " if offset >= 0 and count > 0 else ""}
        """
    order_list, count = database.select_apart_and_count_all(sql)
    return {
        "order_list": order_list,
        "count": count
    }

@app.get("/orders/history", tags=["Order"], summary="顾客查看order")
async def __user_orders__(
        token_data: TokenData = Depends(get_token_data)
):
    sql = f"""select code,id,status,total_price,payment_method from `order`
        where `order`.user_id = {token_data.user_id}
        order by `order`.id desc
        """
    order_list = database.select_all(sql)
    for item in order_list:
        sql = f"""select order_product.price, order_product.num, order_product.product_json, spu.image_path_list, spu.name
            from order_product
            join spu on order_product.spu_id = spu.id
            where order_product.order_id = {item['id']}
            """
        product = database.select_all(sql)
        item["products"] = product
    return {
        "order_list": order_list
    }


@app.get("/{branch_id}/transfer_orders", tags=["Order", "BiSystem"], summary="筛选符合条件的transfer_order并排序")
async def __filter_transfer_orders__(
        # 筛选参数
        branch_id: int = None,
        token_data: TokenData = Depends(get_token_data)
):
    if AuthorityConst.ORDER_GET not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""
        select * from `order` where transfer_from = {branch_id} or transfer_to = {branch_id}
        """
    order_list = database.select_all(sql)
    return order_list


@app.get("/order/{order_id}", tags=["BiSystem", "Order"], summary="获取指定order的详细信息")
async def __get_order_detail__(order_id: int, token_data: TokenData = Depends(get_token_data)):
    sql = f"""
        select 
            `order`.code as id,
            `order`.status as status,
            `order`.payment_method as payment_method,
            `order`.origin as origin,
            `order`.created_time as created_time,
            `order`.modified_time as modified_time,
            `order`.total_price as total_price,
            `order`.appoint_branch as appoint_branch,
            `order`.contact_no as phone,
            `order`.pickup_time as pickup_time,
            `order`.transfer_from as transfer_from,
            `order`.transfer_to as transfer_to,
            user.id as user_id,
            user.nickname as name,
            user.email as email
        from `order` join user on `order`.user_id=user.id
        where `order`.id={order_id}
        """
    order = database.select_one(sql)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No order that id={order_id}")
    if AuthorityConst.ORDER_GET not in token_data.authority_dict and order["user_id"] != token_data.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    # get product list of order
    sql = f"""
        select id, spu_id, profile_id, price, num, product_json
        from order_product where order_id={order_id}
        """
    order["product_list"] = database.select_all(sql)
    for product in order["product_list"]:
        x = product.pop("product_json")
        product["detail"] = json.loads(x)
    # get order history list
    sql = f"""
        select 
            order_history.id as id,
            order_history.summary as summary,
            order_history.detail as detail,
            order_history.created_time as created_time,
            user.id as user_id,
            user.nickname as user_nickname
        from order_history join user on order_history.user_id=user.id 
        where order_id={order_id}
        """
    order["history_list"] = database.select_all(sql)
    return order


@app.post("/order/{order_id}", tags=["BiSystem", "Order"], summary="更改order的isNew")
async def __update_order_detail__(order_id: int,
                                  token_data: TokenData = Depends(get_token_data)):
    sql = f"""update `order` set isNew = 0 where id = {order_id}"""
    rowCount = database.update(sql)
    return rowCount


@app.post("/order/update/{order_id}", tags=["BiSystem", "Order"], summary="更改order的详细信息")
async def __update_order_detail__(order_id: int,
                                  order_status: str = Body(embed=True), history_status: str = Body(embed=True),
                                  pickup_time: Date = Body(embed=True), history_pickup_time: Date = Body(embed=True),
                                  commentList: list = Body(embed=True),
                                  token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.ORDER_PUT not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if history_status != order_status:
        sql = f"""INSERT INTO order_history (order_id, summary, detail, created_time, user_id)
                VALUES ({order_id}, 'status', 'Status change: {history_status} => {order_status}', 
                '{Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}', {token_data.user_id});"""
        database.insert(sql)
    if history_pickup_time != pickup_time:
        sql = f"""INSERT INTO order_history (order_id, summary, detail, created_time, user_id)
                VALUES ({order_id}, 'status', 'Pickup time change: {history_pickup_time} => {pickup_time}', 
                '{Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}', {token_data.user_id});"""
        database.insert(sql)
    for comment in commentList:
        sql = f"""INSERT INTO order_history (order_id, summary, detail, created_time, user_id)
                VALUES ({order_id}, 'comment', '{comment['detail']}', 
                '{comment['created_time']}', {token_data.user_id});"""
        database.insert(sql)
    sql = f"""update `order` set status = '{order_status}', pickup_time = '{pickup_time}' where id = {order_id}"""
    rowCount = database.update(sql)
    return rowCount


@app.post("/order/transfer/{order_id}", tags=["BiSystem", "Order"], summary="转移order")
async def __transfer_order_detail__(order_id: int,
                                    branch_name: str = Body(embed=True), transfer_branch_name: str = Body(embed=True),
                                    branch_id: int = Body(embed=True), transfer_branch_id: int = Body(embed=True),
                                    token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.ORDER_PUT not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""update `order` set transfer_from = {branch_id}, transfer_to = {transfer_branch_id} where id = {order_id}"""
    rowCount = database.update(sql)
    sql1 = f"""INSERT INTO order_history (order_id, summary, detail, created_time, user_id)
            VALUES ({order_id}, 'status', 'Transferring: {branch_name} => {transfer_branch_name}', 
            '{Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}', {token_data.user_id});"""
    database.insert(sql1)
    return rowCount


@app.post("/order/transfer_done/{order_id}", tags=["BiSystem", "Order"], summary="取消或完成转移order")
async def __transfer_done_order_detail__(order_id: int,
                                         type: int = Body(embed=True), branch_id: int = Body(embed=True),
                                         token_data: TokenData = Depends(get_token_data)):
    if AuthorityConst.ORDER_PUT not in token_data.authority_dict:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""update `order` set transfer_from = NULL, transfer_to = NULL, appoint_branch = {branch_id} where id = {order_id}"""
    rowCount = database.update(sql)
    if type == 1:
        sql1 = f"""INSERT INTO order_history (order_id, summary, detail, created_time, user_id)
                    VALUES ({order_id}, 'status', 'Transfer is canceled', 
                    '{Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}', {token_data.user_id});"""
        database.insert(sql1)
    else:
        sql1 = f"""INSERT INTO order_history (order_id, summary, detail, created_time, user_id)
                    VALUES ({order_id}, 'status', 'Transfer is accepted', 
                    '{Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}', {token_data.user_id});"""
        database.insert(sql1)
    return rowCount


def generate_code():
    # 获取当前的年月日时分秒
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")

    # 生成六位随机的大写字母和数字的组合
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    # 组合成最终的随机码
    random_code = current_time + random_part
    return random_code


@app.post("/user/order", tags=["Order"], summary="用户下单")
async def __create_order__(
        order_shopping_cart_id_list: list[int] = Body(embed=True),
        payment_method: str = Body(embed=True),
        appoint_branch: int = Body(embed=True),
        contact_no: str = Body(embed=True),
        pickup_time: Date = Body(embed=True),
        token_data: TokenData = Depends(get_token_data)
):
    if not order_shopping_cart_id_list:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    code = generate_code()  # TODO: 需要一个生成 order code 的算法
    origin = "client"  # TODO: 放进token还是作为参数
    # 获取要添加到order的shopping_cart
    sql = f"""select 
        spu.id as spu_id, spu.name as name, size_chart as size_chart_json, sale_price as price,
        material, color, `size`, profile_id, num
        from shopping_cart 
        join sku on sku.id=shopping_cart.sku_id 
        join spu on spu.id=sku.spu_id 
        where shopping_cart.id in ({str(order_shopping_cart_id_list)[1:-1]}) and shopping_cart.user_id= {token_data.user_id}
        """
    shopping_cart_list = database.select_all(sql)
    if not shopping_cart_list:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    # 计算总价
    total_price = 0
    for shopping_cart in shopping_cart_list:
        total_price = total_price + shopping_cart["price"]
    # 添加 order
    sql = f"""
        insert into `order` (code, status, user_id, payment_method, origin, total_price, appoint_branch, contact_no, pickup_time, isNew) values 
        ({repr(code)}, 'pending', {token_data.user_id}, {repr(payment_method)}, {repr(origin)}, {total_price}, {appoint_branch}, {repr(contact_no)}, '{pickup_time}',1)
        """
    (order_id, row_count) = database.insert(sql)
    # 添加order_product
    sql = f"insert into order_product (order_id,spu_id,profile_id,price,num,product_json) values "
    values = []
    for x in shopping_cart_list:
        product = {
            "name": x["name"],
            "material": x["material"],
            "color": x["color"],
            "size": x["size"],
            "size_chart_json": json.loads(x["size_chart_json"])[x["size"]]
        }
        product_json = json.dumps(product)
        value = (order_id, x["spu_id"], x["profile_id"], x["price"], x["num"], product_json)
        values.append(value)
    sql = f"{sql} {str(values)[1:-1]}"
    database.insert(sql)
    # 添加order_history
    sql = f"insert into order_history (order_id,detail,summary,user_id) values ({order_id},'creat order','status',{token_data.user_id})"
    database.insert(sql)
    sql = f"""
        delete from shopping_cart where id in ({str(order_shopping_cart_id_list)[1:-1]}) and user_id= {token_data.user_id}
        """
    database.delete(sql)
    return {"order_id": order_id}
    pass


#############################################################
# Recommendation#############################################
def get_mid_and_body_data_by_profile_id(profileId: int, sizeCode2Name: dict[str, str]) -> tuple[int, dict[str, float]]:
    # 认为mid最大的measurement数据为该用户最新量体数据, 获取该量体数据
    sql = f"""select mid,sizes from measurement where profileID={profileId} order by mid desc limit 1"""
    measurement = database.select_one(sql)
    sizes = json.loads(measurement["sizes"])
    """
    example for sizes:
    {
      "sizes":[
        {
         "sizeCode": "msize00_010", 
         "sizeCmVal": 180, 
         "sizeName": "Body Height",
         "sizeDesc": "The vertical length between head-top to the floor.",
         "iconUrl": "https://www.emtailor.com/imeas_asset/icon/icon190102/msize00_010.png"
         },
         ...
       ],
       "intlSize":[
         {
          "BottomSz":"180/104A",
          "TopSz":"180/104A",
          "Country":"CN",
          "TopSzTight":"180/100A",
          "ChartVersion":"中国GT1335.1-Men 2008标准",
          "BottomSzTight":"180/100A",
          "SizeTight":"180/100A",
          "Size":"180/104A"
         },
          ...
       ]
    }"""

    bodyData = {}
    for sizeCode, bodyPartName in sizeCode2Name.items():
        sizeValue = 0
        for item in sizes["sizes"]:
            if item["sizeCode"] == sizeCode:
                sizeValue = item["sizeCmVal"]
        bodyData[bodyPartName] = sizeValue
    return measurement["mid"], bodyData


@app.get("/product/{spuId}/{profileId}/size/recommendation", tags=["Recommendation"])
def __size_recommend__(spuId: int, profileId: int, tokenData: TokenData = Depends(get_token_data)):
    """

    :param spuId: 要推荐尺码的产品spu_id
    :param profileId: 给谁推荐尺码
    :param tokenData:
    :return: 推荐结果
    """
    if tokenData.staff_id == 0:
        # 检查profile合法性
        sql = f"""select project_id from profile where id={profileId} and user_id={tokenData.user_id}"""
        profile = database.select_one(sql)
        if profile is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"User {tokenData.user_id} has no Profile {profileId}")
    # 获取尺码推荐所需参数
    sql = f"select size_chart,size_code_to_name,screen_rule from spu where id={spuId}"
    spu = database.select_one(sql)
    sizeCode2Name = json.loads(spu["size_code_to_name"])
    mid, bodyData = get_mid_and_body_data_by_profile_id(profileId, sizeCode2Name)
    sizeChart = json.loads(spu["size_chart"])
    screenRule = json.loads(spu["screen_rule"])
    recommendation = Recommendation(bodyData, sizeChart, **screenRule)
    processingDataJson = (f'{{'
                          f'"mid":{mid},'
                          f'"spuId":{spuId},'
                          f'"sizeCode2Name":{sizeCode2Name},'
                          f'"processing":{recommendation}'
                          f'}}')
    return {
        "all": recommendation.overallOder,
        "body": recommendation.bodyData,
        "item": recommendation.sizeChart,
        "fit": recommendation.easeData,
        "range": recommendation.rangeNode
    }


class AbsFitValue2FitValue(TypedDict):
    absFitValueName: str
    fitValueName: str
    easeValueName: str
    rangeNode: list[float]
    rangeWeight: list[float]


class ScreenRuleDict(TypedDict):
    idealEase: dict[str, float]
    absFitValue2FitValue: list[AbsFitValue2FitValue]
    allWeighting: dict[str, float]
    easeThreshold: dict[str, float]


def check_screen_rule(
        screenRule: ScreenRuleDict = Body(embed=True),
        sizeCodeToName: dict[str, str] = Body(embed=True)
):
    bodyPartWithSizeCodeList = [bodyPartName for bodyPartName in sizeCodeToName.values()]
    bodyPartNameInIdealEase = [bodyPartName for bodyPartName in screenRule["idealEase"].keys()]
    for bodyPartName in bodyPartNameInIdealEase:
        if bodyPartName not in bodyPartWithSizeCodeList:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"BodyPart {bodyPartName} in screenRule.idealEase is"
                                                             f" not in sizeCodeToName")
    for x in screenRule["absFitValue2FitValue"]:
        if x["absFitValueName"] not in bodyPartNameInIdealEase:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Wrong screenRule.absFitValue2FitValue obj {x}: \n"
                                                             f"obj.absFitValueName in screenRule.idealEase")
        if x["easeValueName"] not in bodyPartNameInIdealEase:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Wrong screenRule.absFitValue2FitValue obj {x}: \n"
                                                             f"obj.easeValueName in screenRule.idealEase")
        if x["fitValueName"] not in screenRule["allWeighting"].keys():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Wrong screenRule.absFitValue2FitValue obj {x}: \n"
                                                             f"obj.fitValueName in screenRule.allWeighting")
        if len(x["rangeNode"]) != len(x["rangeWeight"]) - 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Wrong screenRule.absFitValue2FitValue obj {x}: \n"
                                                             f"obj.rangeNode.len != obj.rangeWeight.len - 1")
    for bodyPartName in screenRule["easeThreshold"].keys():
        if bodyPartName not in bodyPartNameInIdealEase:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"BodyPart {bodyPartName} in screenRule.easeThreshold"
                                                             f" is not in screenRule.idealEase")


@app.put("/product/{spuId}/screen_rule", tags=["Recommendation"])
def __update_screen_rule_of_product__(
        spuId: int,
        screenRule: ScreenRuleDict = Body(embed=True),
        sizeCodeToName: dict[str, str] = Body(embed=True),  # {BodyPartCode: BodyPartName}
        tokenData: TokenData = Depends(get_token_data)
):
    # 权限检查
    if tokenData.staff_id == 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not staff")
    # if AuthorityConst.xxx not in tokenData.authority_dict:
    #     raise HTTPException(status.HTTP_403_FORBIDDEN, "no Auth")

    # 数据检查
    try:
        check_screen_rule(screenRule, sizeCodeToName)
    except Exception as e:
        raise e

    # 数据更新
    sql = (f"update spu set screen_rule={repr(json.dumps(screenRule))}, "
           f"size_code_to_name={repr(json.dumps(sizeCodeToName))} "
           f"where id={spuId}"
           )
    rowCount = database.update(sql)
    return {"rowCount": rowCount}


@app.post("/get_screen_rule", tags=["Recommendation"])
def __get_screen_rule__(
        page: int = Body(embed=True),
        pageCount: int = Body(embed=True),
        tokenData: TokenData = Depends(get_token_data)
):
    if tokenData.staff_id == 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not staff")
    # 数据查询

    sql = f"select * from screen_rule_model"
    datas = database.select_all(sql)
    return {'len': len(datas), 'data': datas[(page - 1) * pageCount:(page) * pageCount]}


@app.get("/get_screen_rule_name", tags=["Recommendation"])
def __get_screen_rule__(tokenData: TokenData = Depends(get_token_data)):
    if tokenData.staff_id == 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not staff")
    # 数据查询

    sql = f"select name from screen_rule_model"
    datas = database.select_all(sql)
    names = [item['name'] for item in datas]
    return names


# {"lastRowId": lastRowId, "rowCount": rowCount}
@app.post("/delete_screen_rule", tags=["Recommendation"])
def __delete_screen_rule__(
        id: int = Body(embed=True),
        tokenData: TokenData = Depends(get_token_data)
):
    if tokenData.staff_id == 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not staff")
    # 数据查询

    sql = f"delete  from screen_rule_model where id={id}"
    datas = database.delete(sql)
    return datas


@app.post("/screen_rule_model", tags=["Recommendation"])
def __add_screen_rule_model__(
        name: str = Body(embed=True),
        screenRule: ScreenRuleDict = Body(embed=True),
        sizeCodeToName: dict[str, str] = Body(embed=True),
        tokenData: TokenData = Depends(get_token_data)
):
    # sizeCodeToName = json.loads(s=sizeCodeToName)
    # 权限检查dict[str, str] = Body(embed=True)
    if tokenData.staff_id == 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not staff")
    # if AuthorityConst.xxx not in tokenData.authority_dict:
    #     raise HTTPException(status.HTTP_403_FORBIDDEN, "no Auth")

    # 数据检查
    try:
        check_screen_rule(screenRule, sizeCodeToName)
    except Exception as e:
        raise e

    # 数据插入
    sql = f"insert into screen_rule_model (name, screen_rule, size_code_to_name) " \
          f"values ({repr(name)}, {repr(json.dumps(screenRule))}, {repr(json.dumps(sizeCodeToName))})"
    lastRowId, rowCount = database.insert(sql)
    return {"lastRowId": lastRowId, "rowCount": rowCount}


@app.put("/screen_rule_model/{modelId}", tags=["Recommendation"])
def __update_screen_rule_model__(
        modelId: int,
        name: str = Body(embed=True),
        screenRule: ScreenRuleDict = Body(embed=True),
        sizeCodeToName: dict[str, str] = Body(embed=True),
        tokenData: TokenData = Depends(get_token_data)
):
    # 权限检查
    if tokenData.staff_id == 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not staff")
    # if AuthorityConst.xxx not in tokenData.authority_dict:
    #     raise HTTPException(status.HTTP_403_FORBIDDEN, "no Auth")

    # 数据检查
    try:
        check_screen_rule(screenRule, sizeCodeToName)
    except Exception as e:
        raise e

    # 数据更新
    sql = (f"update screen_rule_model set name={repr(name)}, screen_rule={repr(json.dumps(screenRule))}, "
           f"size_code_to_name={repr(json.dumps(sizeCodeToName))} "
           f"where id={modelId}"
           )
    rowCount = database.update(sql)
    return {"rowCount": rowCount}


# Yangping add 2024/05/17 start
@app.get('/getprofiles')
async def getprofiles(user: user_pydantic = Depends(get_current_user)):
    user_id = user.id
    data = await Profile.filter(user_id=user_id).all().order_by('id')
    res = []
    for item in data:
        jsondic = item.__dict__
        project = await Project.get(id=item.project_id)
        jsondic['project'] = project
        res.append(jsondic)
    return {"status": "Successfully create",
            "data":
                res
            }


# Step 3: Organize the data into a tree-like structure
def build_tree(projects):
    project_dict = {proj['id']: proj for proj in projects}
    tree = []

    for project in projects:
        parent_id = project['parent_id']
        if parent_id == 0:
            tree.append(project)
        else:
            parent = project_dict[parent_id]
            if 'children' not in parent:
                parent['children'] = []
            parent['children'].append(project)

    return tree


@app.get("/projects")
async def __get_project_list__():
    try:
        projects = await Project.all()
        project_list = []
        for item in projects:
            jsondic = item.__dict__
            project_list.append(jsondic)
        tree = build_tree(project_list)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    return {
        "project_list": tree
    }


# Yangping add 2024/05/17 end

#############################################################
register_tortoise(app, db_url=config_credentials["db_url"], modules={'models': ['models']}, add_exception_handlers=True)


# 定时任务
def reconnect_pymysql():
    print(f"{Datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 更新pymysql连接！")
    conn.ping(reconnect=True)


def delete_timeout_file():
    for root, ds, fs in os.walk(f'{config_credentials["resource_file_url"]}/tmp/'):
        # print(f"root: {root} \nds: {ds} \nfs:{fs}")
        for file in fs:
            print(int(file.split('.')[0]) / 1000000)
            if Datetime.now() - Datetime.fromtimestamp(int(file.split('.')[0]) / 1000000) > timedelta(days=1):
                os.remove(f"{root}{file}")


def scheduler_task():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(reconnect_pymysql, 'interval', minutes=10)
    scheduler.add_job(delete_timeout_file, 'interval', days=1)
    scheduler.start()


''' Body(embed=True) '''


@app.post('/ayjjtest', tags=['yjj'], summary='12345')
async def get_data(a: int, order_shopping_cart_id_list: list[int] = Body(embed=True), note: str = Body(embed=True),
                   token_data: TokenData = Depends(get_token_data)):
    return a


@app.on_event('startup')
async def init_scheduler():
    scheduler_task()


if __name__ == '__main__':
    from uvicorn import run

    ssl_keyfile = config_credentials["ssl_keyfile"]
    ssl_certfile = config_credentials["ssl_cert_file"]
    run('main:app', host=HOST_URL, port=HOST_PORT, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile)


# 创建branch put /branch
# 创建role(提供authority) put /branch/{branch_id}/role
# 创建user put /user
# 为user添加staff put /staff
# 为staff添加role(可选) put /staff/{staff_id}/role/{role_id}
#


# TODO: 修改添加measurement的接口，添加时检查对应profile是否
#  有未完成的且measurement_json字段为空的order_product,如果有,同步字段,并完成尺码推荐

# class DataModel:
#     x: int = Body(embed=True)
#
# @app.put("/test")
# async def func(data: DataModel = Depends()):
#     pass

# 另一个App的api:
@app.post("/anotherApp_profile_create", tags=["anotherApp_profile", "anotherApp"])
async def __create_the_anotherApp_profile__(name: str = Body(embed=True),
                                            gender: str = Body(embed=True),
                                            height: int = Body(embed=True),
                                            weight: int = Body(embed=True),
                                            token_data: TokenData = Depends(get_token_data)):
    if token_data is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""
        insert into anotherApp_profile (name, gender, height, weight, user_id) 
        values ('{name}', '{gender}', {height},{weight},{token_data.user_id})
        """
    (profile_id, count) = database.insert(sql)
    return {"profile_id": profile_id}


@app.post("/anotherApp_profile_modify", tags=["anotherApp_profile", "anotherApp"])
async def __modify_the_anotherApp_profile__(id: int = Body(embed=True),
                                            name: str = Body(embed=True),
                                            gender: str = Body(embed=True),
                                            height: int = Body(embed=True),
                                            weight: int = Body(embed=True),
                                            token_data: TokenData = Depends(get_token_data)):
    if token_data is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""
        update anotherApp_profile set name = '{name}', gender = '{gender}', 
        height = {height}, weight = {weight}
        where id = {id}
        """
    row_count = database.update(sql)
    return row_count


@app.get("/anotherApp_profile_get", tags=["anotherApp_profile", "anotherApp"])
async def __get_the_anotherApp_profile__(token_data: TokenData = Depends(get_token_data)):
    if token_data is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""
        select * from anotherApp_profile where user_id = {token_data.user_id}
        """
    profile = database.select_all(sql)
    return profile


@app.delete("/anotherApp_profile_delete/{id}", tags=["anotherApp_profile", "anotherApp"])
async def __delete_the_anotherApp_profile__(id: int,
                                            token_data: TokenData = Depends(get_token_data)):
    if token_data is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""
        delete from anotherApp_profile where id = {id}
        """
    datas = database.delete(sql)
    return datas


@app.delete("/anotherApp_account_delete", tags=["anotherApp"])
async def __delete_the_anotherApp_account__(token_data: TokenData = Depends(get_token_data)):
    if token_data is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""select * from anotherApp_profile where user_id = {token_data.user_id}"""
    profiles = database.select_all(sql)
    for profile in profiles:
        sql = f"""delete from anotherApp_measurement where profileID = {profile['id']}"""
        database.delete(sql)
    sql = f"""delete from anotherApp_profile where user_id = {token_data.user_id}"""
    database.delete(sql)
    sql = f"""delete from user where id = {token_data.user_id}"""
    database.delete(sql)
    return 1


@app.post('/anotherApp_genera_measurement', tags=["anotherApp_measurement", "anotherApp"])
async def __anotherApp_genera_measurement__(measurement: measurement_pydantic_genera,
                                            token_data: TokenData = Depends(get_token_data)):
    if token_data is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    measurement_info = measurement.dict(exclude_unset=True)
    profile_id = measurement_info['profileID']
    sql1 = f"""SELECT * FROM anotherApp_profile WHERE id = {profile_id}"""
    profile = database.select_all(sql1)
    if len(profile) == 0:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "can't find the profile_id")
    date = Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sql2 = f"""
        insert into anotherApp_measurement ( profileID, date, measureType, height, weight, frontpic, 
        sidepic, measureId, sizes, frontProfileBody, sideProfileBody) 
        values ({profile_id}, '{date}', '{measurement_info['measureType']}', {measurement_info['height']},
        {measurement_info['weight']},'{measurement_info['frontpic']}','{measurement_info['sidepic']}',
        '{measurement_info['measureId']}','{measurement_info['sizes']}','{measurement_info['frontProfileBody']}',
        '{measurement_info['sideProfileBody']}')
        """
    (mid, count) = database.insert(sql2)
    return {"measurement_id": mid}


@app.get('/anotherApp_get_measurement', tags=["anotherApp_measurement", "anotherApp"])
async def __anotherApp_get_measurement__(profileID: int, token_data: TokenData = Depends(get_token_data)):
    if token_data is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sql = f"""select * from anotherApp_measurement where profileID = {profileID}"""
    measurementList = database.select_all(sql)
    return measurementList


@app.post("/account_generate", tags=["Tools"], summary="excel生成账户")
async def __account_generate__(file: UploadFile = File(...)):
    contents = await file.read()
    df = pd.read_excel(contents)
    dupAccount = []

    # 三个函数
    async def __account_check__(accounts):
        for account in accounts:
            user = database.select_one(f"select * from user where account={repr(account)}")
            if user is not None:
                dupAccount.append(account)
        if len(dupAccount):
            return True
        return False

    async def __create_account__(account, psw):
        hashed_password = get_password_hash(psw)
        try:
            sql = f"insert into user (account, password) values ('{account}','{hashed_password}')"
            last_row_id, row_count = database.insert(sql)
        except:
            print(f"{account} is duplicate")
        return last_row_id

    async def __create_profile__(profile, user_id):
        if (profile['gender'] == 0):
            gender = 'male'
        else:
            gender = 'female'
        sql = (f"""insert into profile (ENGname, CHIname, gender, birth, project_id, avatar, user_id)
            values ('{profile['ENGname']}','','{gender}','{profile['birth']}','{profile['project_id']}','https://aob.bi.cafilab.com/avatar/6.jpg', {user_id})""")
        last_row_id, row_count = database.insert(sql)
        profile_id = last_row_id
        s_uuid = str(uuid.uuid3(uuid.NAMESPACE_URL, str(profile_id)))
        qr_quote = ''.join(s_uuid.split('-')).upper()
        database.update(f"update profile set qr_quote = '{qr_quote}' where id = {profile_id}")
        return qr_quote

    # 开始
    if await __account_check__(df['account']):
        return {"Duplicate Account": dupAccount}
    quotes = []
    for index, row in df.iterrows():
        user_id = await __create_account__(row['account'], str(row['password']))
        profileData = row.drop(['account', 'password']).to_dict()
        qr_quote = await __create_profile__(profileData, user_id)
        quotes.append(qr_quote)
    for quote in quotes:
        df['quote'] = df.apply(lambda row: f"{quote}", axis=1)
    excel_file = io.BytesIO()
    df.to_excel(excel_file, index=False)
    excel_file.seek(0)
    return StreamingResponse(excel_file,
                             media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             headers={'Content-Disposition': 'attachment; filename=data.xlsx'})
