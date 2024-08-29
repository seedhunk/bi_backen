from datetime import datetime as Datetime
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from env import *
from database import database
import re
import datetime


# Branch Const ##################################################
TOP_BRANCH = 1


#################################################################
# Authority Const ###############################################
class AuthorityConst:
    ALL = 1
    APPOINTMENT_GET = 0
    APPOINTMENT_PUT = 0
    APPOINTMENT_DELETE = 0
    AUTHORITY = 2
    AUTHORITY_GET = 3
    AUTHORITY_PUT = 4
    AUTHORITY_DELETE = 5
    BRANCH = 6
    BRANCH_GET = 7
    BRANCH_PUT = 8
    BRANCH_DELETE = 9
    CATEGORY = 10
    CATEGORY_GET = 11
    CATEGORY_PUT = 12
    CATEGORY_DELETE = 13
    COOPERATION = 14
    COOPERATION_GET = 15
    COOPERATION_PUT = 16
    COOPERATION_DELETE = 17
    INVENTORY = 18
    INVENTORY_GET = 19
    INVENTORY_PUT = 20
    INVENTORY_DELETE = 21
    PRODUCT = 22
    PRODUCT_GET = 23
    PRODUCT_PUT = 24
    PRODUCT_DELETE = 25
    PROJECT = 26
    PROJECT_GET = 27
    PROJECT_PUT = 28
    PROJECT_DELETE = 29
    ROLE = 30
    ROLE_GET = 31
    ROLE_PUT = 32
    ROLE_DELETE = 33
    STAFF = 34
    STAFF_GET = 35
    STAFF_PUT = 36
    STAFF_DELETE = 37
    ORDER = 38
    ORDER_GET = 39
    ORDER_PUT = 40
    ORDER_DELETE = 41
    ROLE_ASSIGN = 42


##################################################################
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# async def send_message_to_activate_user(user: User):
#     os.environ["AWS_ACCESS_KEY_ID"] = config_credentials['ACCESS_ID']
#     os.environ["AWS_SECRET_ACCESS_KEY"] = config_credentials['ACCESS_KEY']
#     region_name = config_credentials['AWS_REGION']
#     sender = config_credentials['EMAIL']
#
#     token_data = {
#         "id": user.id,
#         'exp': Datetime.utcnow()
#     }
#     token = jwt.encode(token_data, secret)
#     template = f"""
#             <!DOCTYPE html>
#             <html>
#             <head>
#             </head>
#             <body>
#                 <div style=" display: flex; align-items: center; justify-content: center; flex-direction: column;">
#                     <h3> Account Verification </h3>
#                     <br>
#                     <p>Thanks for choosing EasyShopas, please
#                     click on the link below to verify your account</p>
#
#                     <a style="margin-top:1rem; padding: 1rem; border-radius: 0.5rem; font-size: 1rem; text-decoration:
#                     none; background: #0275d8; color: white;" href="">
#                         Verify your email
#                     <a>
#
#                     <p style="margin-top:1rem;">If you did not register for EasyShopas,
#                     please kindly ignore this email and nothing will happen. Thanks<p>
#                 </div>
#             </body>
#             </html>
#             <script>
#                 document.querySelector("a").addEventListener("click",function(){{
#                     fetch("{host_url}/user/is_verified",{{
#                         method:"PATCH",
#                         headers:{{
#                             token: '{token}'
#                         }}
#                     }}).then(res=>res.json()).then(res=>{{
#                         console.log(res)
#                     }})
#                 }})
#             </script>
#         """
#     subject = 'Uniform AccountVerification Mail'
#     charset = 'UTF-8'
#     client = boto3.client('ses', region_name=region_name)
#     try:
#         response = client.send_email(
#             Destination={
#                 'ToAddresses': [user.email, ],
#             },
#             Message={
#                 'Body': {
#                     'Html': {
#                         'Charset': charset,
#                         'Data': template,
#                     }
#                 },
#                 'Subject': {
#                     'Charset': charset,
#                     'Data': subject,
#                 },
#             },
#             Source=sender,
#         )
#     except ClientError as e:
#         print(e.response['Error']['Message'])
#     else:
#         print("Email sent! Message ID:"),
#         print(response['MessageId'])
#

def get_password_hash(password) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def authenticate_user(account: str, password: str):
    if "'" in account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    user = database.select_one(f"select * from user where email={repr(account)}")
    if user is not None and verify_password(password, user["password"]):
        return user
    else:
        user = database.select_one(f"select * from user where account={repr(account)}")
        if user is not None and verify_password(password, user["password"]):
            return user
        return None


async def token_generator(username: str, password: str, time: float) -> (str, bool):
    """

    :param username:
    :param password:
    :return: (token: str, is_staff: bool)
    """
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    staff_id = 0
    staff = database.select_one(f"select * from staff where user_id={user['id']}")
    modified_time = user["modified_time"]
    if staff:
        staff_id = staff["id"]
        modified_time = staff["modified_time"]

    authority_dict: dict[int, list[int]] = {}
    sql = f"""
        select branch_id,authority_id
        from role join role_to_authority
        where role.id=role_to_authority.role_id
        and role.id in (select role_id from staff_to_role where staff_id={staff_id})
        """
    branch_authority = database.select_all(sql)
    for x in branch_authority:
        branch_id = x["branch_id"]
        authority_id = x["authority_id"]
        if authority_id in authority_dict:
            authority_dict[authority_id].append(branch_id)
        else:
            authority_dict[authority_id] = [branch_id, ]

    if time == -1:
        token_data = {
            "user_id": user["id"],
            "email": user["email"],
            "staff_id": staff_id,
            "modified_time": modified_time.isoformat(),
            "authority_dict": authority_dict,
        }
    else:
        token_data = {
            "user_id": user["id"],
            "email": user["email"],
            "staff_id": staff_id,
            "modified_time": modified_time.isoformat(),
            "authority_dict": authority_dict,
            "exp": (datetime.datetime.utcnow() + datetime.timedelta(days=time)).timestamp()
        }
    try:
        token = jwt.encode(token_data, SECRET)
    except Exception as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Error when encode token")
    return token, bool(staff_id)


class TokenData:
    user_id: int
    email: str
    staff_id: int
    modified_time: Datetime
    authority_dict: dict[int, list[int]]  # {auth1: [branch1, branch2,....],...}表示对branch1,2具有auth1权限

    def __init__(self, token: str):
        super().__init__()
        try:
            payload = jwt.decode(token, SECRET, algorithms=['HS256'])
            self.user_id = payload["user_id"]
            self.email = payload["email"]
            self.staff_id = payload["staff_id"]
            self.modified_time = Datetime.fromisoformat(payload["modified_time"])
            self.authority_dict = {int(authIdStr): value for authIdStr, value in payload["authority_dict"].items()}
        except Exception as e:
            print(re.sub(r"\n[ \n]+", "\n    ", "\n  " + f"TokenData(): {str(e)}"))
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


# def change_role(token: str, role_id: int) -> str:
#     try:
#         payload = jwt.decode(token, config_credentials['SECRET'], algorithms=['HS256'])
#     except Exception:
#         raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Error when decode token")
#     if role_id not in payload["role_id_list"]:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="no such role for this staff"
#         )
#     try:
#         modified_time = execute_sql(f"select modified_time from staff where id={payload['staff_id']}")[0][
#             "modified_time"]
#     except IndexError as e:
#         print(str(e))
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not exist")
#     if payload["modified_time"] != modified_time.isoformat():
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token need update")
#     branch_id = execute_sql(f"select branch_id from role where id={role_id}")[0]["branch_id"]
#     role_authorities = execute_sql(f"select authority_id from role_to_authority where role_id={role_id}")
#     authority_id_list = []
#     for authority in role_authorities:
#         authority_id_list.append(authority["authority_id"])
#
#     payload["role_id"] = role_id
#     payload["branch_id"] = branch_id
#     payload["authority_id_list"] = authority_id_list
#     try:
#         token = jwt.encode(payload, SECRET)
#     except Exception:
#         raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Error when encode token")
#     return token


def get_order_by_str_from_sort(sort: str, columns: list[str]):
    """将符合 REST 规范的排序参数 sort 转换为 sql 语句中 order by 的参数"""
    if not sort:
        return ""
    order_by_list_origin = sort.split(',')
    order_by_list = []
    for column in order_by_list_origin:
        if column[1:] in columns:
            if column[0] == '+':
                order_by_list.append(f"`{column[1:]}`")
            elif column[0] == '-':
                order_by_list.append(f"`{column[1:]}` desc")
            else:
                print(f"*******{column}")
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Wrong format of sort")
    order_by = ",".join(order_by_list)
    return order_by
