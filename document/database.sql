create table authority
(
    id          int unsigned auto_increment
        primary key,
    name        char(20)     not null,
    parent_id   int unsigned not null,
    description varchar(255) null,
    constraint system_parent_name
        unique (name, parent_id)
)
    comment '可用于分配的权限' collate = utf8mb4_unicode_ci;

create definer = root@`%` trigger after_add_authority
    after insert
    on authority
    for each row
begin
    if (new.parent_id!=0) then
        insert into authority_sub_relation values (new.parent_id,new.id);
        insert into authority_sub_relation (parent_id, child_id)  select authority_sub_relation.parent_id,new.id from authority_sub_relation where child_id=new.parent_id;
    end if;
end;

create table authority_sub_relation
(
    parent_id int unsigned not null,
    child_id  int unsigned not null,
    primary key (parent_id, child_id),
    constraint authority_sub_relation_authority_id_fk
        foreign key (parent_id) references authority (id)
            on update cascade on delete cascade,
    constraint authority_sub_relation_authority_id_fk2
        foreign key (child_id) references authority (id)
            on update cascade on delete cascade
)
    collate = utf8mb4_unicode_ci;

create table branch
(
    id        int unsigned auto_increment
        primary key,
    name      varchar(255) not null,
    address   varchar(255) null,
    parent_id int unsigned not null
)
    comment '公司架构，树状结构，控制数据访问' collate = utf8mb4_unicode_ci;

create index branch_name_index
    on branch (name);

create definer = root@`%` trigger check_branch_add
    before insert
    on branch
    for each row
    if new.parent_id > 0 and not exists(select * from branch where branch.id = NEW.parent_id)
       then signal sqlstate '45000' set message_text = 'parent path not exist';
    end if;

create table branch_sub_relation
(
    parent_id int unsigned not null,
    child_id  int unsigned not null,
    primary key (parent_id, child_id),
    constraint branch_sub_relation_branch_child_id_fk
        foreign key (child_id) references branch (id)
            on update cascade,
    constraint branch_sub_relation_branch_parent_id_fk
        foreign key (parent_id) references branch (id)
            on update cascade
)
    comment '将一个结点和它所有的祖先节点关联 ' collate = utf8mb4_unicode_ci;

create index branch_sub_relation_child_id_index
    on branch_sub_relation (child_id);

create index branch_sub_relation_parent_id_index
    on branch_sub_relation (parent_id);

create table category
(
    id   int unsigned auto_increment
        primary key,
    name char(16) not null,
    constraint category_pk2
        unique (name)
)
    collate = utf8mb4_unicode_ci;

create table measurement
(
    mid              int      null,
    profileID        int      null,
    date             datetime null,
    height           float    null,
    weight           float    null,
    frontpic         longtext null,
    sidepic          longtext null,
    measureId        tinytext null,
    sizes            longtext null,
    frontProfileBody longtext null,
    sideProfileBody  longtext null
)
    collate = utf8mb4_unicode_ci;

create table project
(
    id            int unsigned auto_increment
        primary key,
    name          varchar(255)                           not null,
    parent_id     int unsigned                           not null comment '父节点id,为0时为顶层，建议此时name=合作公司名',
    partner       varchar(255)                           null comment '合作方名称',
    created_time  datetime     default CURRENT_TIMESTAMP not null,
    modified_time datetime     default CURRENT_TIMESTAMP not null comment '任何子孙节点被修改都将影响该字段',
    description   text                                   null,
    spu_amount    int unsigned default 0                 not null comment 'project及其subproject中包含的spu总数',
    constraint project_pk2
        unique (name, parent_id)
)
    comment '树状结构' collate = utf8mb4_unicode_ci;

create definer = root@`%` trigger after_add_project
    after insert
    on project
    for each row
begin
    if (new.parent_id!=0) then
        insert into project_sub_relation values (new.parent_id,new.id);
        insert into project_sub_relation (parent_id, child_id)  select project_sub_relation.parent_id,new.id from project_sub_relation where child_id=new.parent_id;
    end if;
end;

create definer = root@`%` trigger prevent_delete_if_sub_project_exist
    before delete
    on project
    for each row
begin
    if exists(select * from project_sub_relation where project_sub_relation.parent_id=OLD.id)
        then signal sqlstate '45000' set message_text = 'You should delete all subprojects first';
    end if;
end;

create table project_sub_relation
(
    parent_id int unsigned not null,
    child_id  int unsigned not null,
    primary key (child_id, parent_id),
    constraint project_sub_relation_project_child_id_fk
        foreign key (child_id) references project (id)
            on update cascade on delete cascade,
    constraint project_sub_relation_project_parent_id_fk
        foreign key (parent_id) references project (id)
            on update cascade on delete cascade
)
    comment '将一个结点和它所有的祖先节点关联 ' collate = utf8mb4_unicode_ci;

create table record
(
    recordID  int      null,
    userID    int      null,
    profileID int      null,
    mid       int      null,
    date      datetime null
)
    collate = utf8mb4_unicode_ci;

create table role
(
    id        int unsigned auto_increment
        primary key,
    name      varchar(255) not null,
    branch_id int unsigned not null,
    constraint role_pk2
        unique (name, branch_id),
    constraint role_branch_id_fk
        foreign key (branch_id) references branch (id)
            on update cascade on delete cascade
)
    comment '用于权限管理的角色' collate = utf8mb4_unicode_ci;

create index role_branch_id_index
    on role (branch_id);

create table role_to_authority
(
    role_id      int unsigned not null,
    authority_id int unsigned not null,
    primary key (authority_id, role_id),
    constraint role_to_authority_authority_id_fk
        foreign key (authority_id) references authority (id)
            on update cascade on delete cascade,
    constraint role_to_authority_role_id_fk
        foreign key (role_id) references role (id)
            on update cascade on delete cascade
)
    comment 'middle table for role and authority' collate = utf8mb4_unicode_ci;

create index role_to_authority_authority_id_index
    on role_to_authority (authority_id);

create index role_to_authority_role_id_index
    on role_to_authority (role_id);

create table spu
(
    id              int unsigned auto_increment
        primary key,
    code            char(16)                           not null,
    type            tinyint(1)                         not null comment '0 is MTM, 1 is RTW',
    category_id     int unsigned                       not null,
    name            varchar(255)                       null,
    description     text                               null,
    image_path_list text                               null comment 'json list',
    size_chart      text                               null comment 'json object',
    pattern_path    varchar(255)                       null,
    standard_price  float                              null,
    sale_price      float                              null,
    created_time    datetime default CURRENT_TIMESTAMP not null,
    modified_time   datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP,
    constraint spu_code
        unique (code),
    constraint spu_category_id_fk
        foreign key (category_id) references category (id)
)
    comment 'standard product unit' collate = utf8mb4_unicode_ci;

create table cooperation
(
    project_id int unsigned not null,
    spu_id     int unsigned not null,
    primary key (project_id, spu_id),
    constraint cooperation_project_id_fk
        foreign key (project_id) references project (id)
            on update cascade on delete cascade,
    constraint cooperation_spu_id_fk
        foreign key (spu_id) references spu (id)
            on update cascade on delete cascade
)
    comment 'add a spu into a project' collate = utf8mb4_unicode_ci;

create definer = root@`%` trigger add_project_spu_amount
    after insert
    on cooperation
    for each row
begin
    update project set spu_amount = spu_amount+1
        where
            (id in (select parent_id from project_sub_relation where child_id = new.project_id))
           or id=NEW.project_id;
end;

create definer = root@`%` trigger after_delete_cooperation
    after delete
    on cooperation
    for each row
begin
    update project set spu_amount = spu_amount-1
        where
            (id in(select parent_id from project_sub_relation where child_id = OLD.project_id))
            or id = OLD.project_id;
end;

create table sku
(
    id       int unsigned auto_increment
        primary key,
    code     char(16)     not null,
    spu_id   int unsigned not null,
    material varchar(255) null,
    size     varchar(8)   null,
    color    varchar(255) null,
    constraint sku_pk
        unique (material, spu_id, size, color),
    constraint sku_spu_id_fk
        foreign key (spu_id) references spu (id)
            on update cascade on delete cascade
)
    collate = utf8mb4_unicode_ci;

create table inventory
(
    branch_id int unsigned not null,
    sku_id    int unsigned not null,
    current   int unsigned not null comment '当前库存',
    threshold int          not null comment '警戒阈值 -1表示不提醒',
    id        int unsigned auto_increment
        primary key,
    constraint sku_id
        unique (sku_id, branch_id),
    constraint inventory_branch_id_fk
        foreign key (branch_id) references branch (id)
            on update cascade on delete cascade,
    constraint inventory_sku_id_fk
        foreign key (sku_id) references sku (id)
            on update cascade on delete cascade
)
    comment 'sku inventory for branch' collate = utf8mb4_unicode_ci;

create index inventory_sku_id_index
    on inventory (sku_id);

create table user
(
    id            int unsigned auto_increment
        primary key,
    password      char(64)                             not null,
    email         char(64)                             null,
    phone         char(16)                             null,
    created_time  datetime   default CURRENT_TIMESTAMP not null,
    is_verified   tinyint(1) default 0                 not null comment '需通过邮箱或手机验证',
    modified_time datetime   default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP
)
    collate = utf8mb4_unicode_ci;

create table `order`
(
    id             int unsigned auto_increment
        primary key,
    code           char(32)                           not null,
    status         char(16)                           not null comment 'pending, failed, processing?, shipped, completed, cancelled',
    user_id        int unsigned                       not null,
    payment_method varchar(64)                        null,
    origin         char(16)                           not null comment '通过哪种途径创建的订单Avaialbe option: business app / client app / website  (but dont know how to detect this)',
    created_time   datetime default CURRENT_TIMESTAMP not null,
    modified_time  datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP,
    total_price    float                              not null,
    note           text                               null,
    constraint oder_pk2
        unique (code),
    constraint oder_user_id_fk
        foreign key (user_id) references user (id)
)
    collate = utf8mb4_unicode_ci;

create table order_history
(
    id           int unsigned auto_increment
        primary key,
    order_id     int unsigned                       not null,
    summary      varchar(255)                       not null,
    detail       text                               null,
    created_time datetime default CURRENT_TIMESTAMP not null,
    constraint order_history_order_id_fk
        foreign key (order_id) references `order` (id)
)
    collate = utf8mb4_unicode_ci;

create table profile
(
    id         int unsigned auto_increment
        primary key,
    project_id int unsigned not null,
    user_id    int unsigned null,
    ENGname    tinytext     null,
    CHIname    tinytext     null,
    gender     char(20)     null,
    birth      date         null,
    qr_quote   tinytext     null,
    code       varchar(32)  null comment '学号，员工号等',
    constraint profile_project_id_fk
        foreign key (project_id) references project (id)
            on update cascade on delete cascade,
    constraint profile_user_id_fk
        foreign key (user_id) references user (id)
)
    collate = utf8mb4_unicode_ci;

create table appointment
(
    id         int auto_increment
        primary key,
    branch_id  int unsigned  not null,
    profile_id int unsigned  not null,
    day        date          not null,
    `period`   int           not null comment '将24h按15min划分',
    status     int default 0 not null comment '0coming, 1completed, -1canceled, -2timeout',
    note       varchar(255)  null,
    constraint appointment_branch_id_fk
        foreign key (branch_id) references branch (id)
            on update cascade on delete cascade,
    constraint appointment_profile_id_fk
        foreign key (profile_id) references profile (id)
            on update cascade on delete cascade
)
    collate = utf8mb4_unicode_ci;

create table order_product
(
    id           int unsigned auto_increment
        primary key,
    order_id     int unsigned not null,
    spu_id       int unsigned not null,
    profile_id   int unsigned not null,
    price        float        not null,
    num          int unsigned not null,
    product_json text         null,
    constraint order_product_order_id_fk
        foreign key (order_id) references `order` (id),
    constraint order_product_profile_id_fk
        foreign key (profile_id) references profile (id),
    constraint order_product_spu_id_fk
        foreign key (spu_id) references spu (id)
)
    collate = utf8mb4_unicode_ci;

create table shopping_cart
(
    id         int unsigned auto_increment
        primary key,
    user_id    int unsigned not null,
    sku_id     int unsigned not null,
    profile_id int unsigned not null,
    num        int unsigned not null,
    constraint shopping_cart_pk
        unique (profile_id, sku_id, user_id),
    constraint shopping_cart_profile_id_fk
        foreign key (profile_id) references profile (id)
            on update cascade on delete cascade,
    constraint shopping_cart_sku_id_fk
        foreign key (sku_id) references sku (id),
    constraint shopping_cart_user_id_fk
        foreign key (user_id) references user (id)
            on update cascade on delete cascade
)
    collate = utf8mb4_unicode_ci;

create table staff
(
    id            int unsigned auto_increment
        primary key,
    user_id       int unsigned                       not null comment '员工账号',
    name          varchar(255)                       null comment '员工姓名',
    code          varchar(32)                        null comment 'for example:内部员工号',
    modified_time datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '当token需要更新时改变',
    id_card       char(32)                           null comment '身份证号之类的',
    constraint staff_user_id_fk
        foreign key (user_id) references user (id)
            on update cascade on delete cascade
)
    collate = utf8mb4_unicode_ci;

create table staff_to_role
(
    staff_id int unsigned not null,
    role_id  int unsigned not null,
    primary key (staff_id, role_id),
    constraint staff_to_role_role_id_fk
        foreign key (role_id) references role (id)
            on update cascade on delete cascade,
    constraint staff_to_role_staff_id_fk
        foreign key (staff_id) references staff (id)
            on update cascade on delete cascade
)
    comment 'assign a role to a staff' collate = utf8mb4_unicode_ci;

create definer = root@`%` trigger after_add_staff_role
    after insert
    on staff_to_role
    for each row
begin
    update staff set modified_time=current_timestamp where id=new.staff_id;
end;

create definer = root@`%` trigger after_delete_staff_role
    after delete
    on staff_to_role
    for each row
begin
    update staff set modified_time=current_timestamp where id=old.staff_id;
end;

create index user_email_index
    on user (email);

create index user_phone_index
    on user (phone);

create definer = root@`%` trigger after_user_update
    after update
    on user
    for each row
begin
    update staff set modified_time=current_timestamp where user_id=new.id;
end;

create definer = root@`%` trigger check_user_add
    before insert
    on user
    for each row
begin
    if new.email='' and new.phone=''
        then signal sqlstate '45000' set message_text = 'email or phone needed';
    end if;
    if exists(select * from user where user.is_verified=TRUE and user.phone=new.phone)
        then signal sqlstate '45000' set message_text = 'phone number has been registered';
    end if;
    if exists(select * from user where user.is_verified=TRUE and user.email=new.email)
        then signal sqlstate '45000' set message_text = 'email has been registered';
    end if;
    if exists(select * from user where user.is_verified=FALSE and user.phone=new.phone)
        then signal sqlstate '45000' set message_text = 'phone number has been registered,but has been not verified';
    end if;
    if exists(select * from user where user.is_verified=FALSE and user.email=new.email)
        then signal sqlstate '45000' set message_text = 'email has been registered,but has been not verified';
    end if;
end;

create definer = root@`%` trigger check_user_update
    before update
    on user
    for each row
begin
    if new.email!=old.email
        then if exists(select * from user where user.email=new.email and user.id !=new.id)
            then signal sqlstate '45000' set message_text = 'email has been registered';
        end if;
    end if;
    if new.phone!=old.phone
        then if exists(select * from user where user.phone=new.phone and user.id !=new.id)
            then signal sqlstate '45000' set message_text = 'phone has been registered';
        end if;
    end if;
end;

