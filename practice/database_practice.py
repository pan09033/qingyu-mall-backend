import pymysql

from app.config import settings


# 连接本机 MySQL
connection = pymysql.connect(
    host=settings.db_host,
    port=settings.db_port,
    user=settings.db_user,
    password=settings.db_password,
    database=settings.db_name,
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

try:
    # 自动关闭游标
    with connection.cursor() as cursor:
        # 创建商品表
        cursor.execute(
            """
create table if not exists products(
    id int primary key auto_increment,
    name varchar(30) not null ,
    price decimal(10,2) not null ,
    stock int not null
    );
            """
        )
        product_data = [
            ("机械键盘", 299.00, 20),
            ("无线鼠标", 99.00, 30),
        ]
        # 添加多个商品
        cursor.executemany(
            """
            INSERT INTO products (name, price, stock)
            VALUES (%s, %s, %s)
            """,
            product_data,
        )

        # 提交添加操作
        connection.commit()

        # 查询所有商品
        cursor.execute("SELECT * FROM products")

        products = cursor.fetchall()

        print("修改前所有商品：")
        for product in products:
            print(product)
        cursor.execute(
            """
            UPDATE products
            SET stock = %s
            WHERE name = %s
            """,
            (25, "无线鼠标"),
        )

        cursor.execute(
            """
            DELETE FROM products
            WHERE name = %s
            """,
            ("机械键盘",),
        )

        connection.commit()

        # 6. 再次查询
        cursor.execute("SELECT * FROM products")

        products = cursor.fetchall()
        print("修改后所有商品：")
        for product in products:
            print(product)

finally:
    # 无论是否发生错误，都关闭数据库连接
    connection.close()
