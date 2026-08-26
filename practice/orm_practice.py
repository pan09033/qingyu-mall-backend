from decimal import Decimal

from sqlalchemy import URL, Numeric, String, create_engine, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
)

from app.config import settings


# MySQL 数据库连接地址
DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=settings.db_user,
    password=settings.db_password,
    host=settings.db_host,
    port=settings.db_port,
    database=settings.db_name,
    query={
        "charset": "utf8mb4",
    },
)

# engine 负责管理数据库连接
# echo=True 会在终端显示实际执行的 SQL
engine = create_engine(
    DATABASE_URL,
    echo=True,
)


# 所有数据库模型的父类
class Base(DeclarativeBase):
    pass


# Product 类对应 products 表
class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    stock: Mapped[int] = mapped_column(
        nullable=False,
    )


# 创建尚不存在的表
# 已存在的 products 表不会被删除
Base.metadata.create_all(engine)


# Session 表示一次数据库操作会话
with Session(engine) as session:
    # 先检查商品是否已经存在，避免每次运行都重复插入
    existing_product = session.scalar(
        select(Product).where(Product.name == "显示器")
    )
    statement = select(Product).where(Product.name == "显示器")
    product = session.scalar(statement)
    if product is None:
        print("商品不存在")
    else:
        product.id = product.id
        product.name = product.name
        session.delete(product)
        session.commit()
    if product is None:
        print("商品不存在，开始添加商品...")
    else:
        product.price = Decimal("899.00")
        product.stock = 10
        session.commit()
        session.refresh(product)
        print(
            f"修改成功：{product.name}，"
            f"价格：{product.price}，"
            f"库存：{product.stock}"
        )
    statement = select(Product).where(Product.name == "显示器")

    if existing_product is None:
        new_product = Product(
            name="显示器",
            price=Decimal("899.00"),
            stock=10,
        )

        # 添加、提交，再刷新对象以获取数据库自动生成的 id
        session.add(new_product)
        session.commit()
        session.refresh(new_product)

        print(
            f"添加成功：商品ID为{new_product.id}，"
            f"名称为{new_product.name}"
        )
    else:
        print(f"商品已存在：ID为{existing_product.id}")

    # 查询并显示数据库中的全部商品
    products = session.scalars(select(Product)).all()

    print("当前全部商品：")
    for product in products:
        print(
            f"ID：{product.id}，名称：{product.name}，"
            f"价格：{product.price}，库存：{product.stock}"
        )
