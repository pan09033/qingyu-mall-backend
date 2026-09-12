from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.order import Order
from app.models.user import User


def build_user_filters(
    keyname: str | None,
) -> list:
    """构建管理员用户列表的动态筛选条件。"""

    conditions = []
    if keyname is not None:
        conditions.append(
            User.name.contains(keyname)
        )
    return conditions


def get_users(
    db: Session,
    keyname: str | None,
    skip: int,
    limit: int,
) -> Sequence[User]:
    """根据姓名关键词分页查询用户。"""

    conditions = build_user_filters(keyname)
    statement = (
        select(User)
        .where(*conditions)
        .order_by(User.id)
        .offset(skip)
        .limit(limit)
    )
    return db.scalars(statement).all()


def count_users(
    db: Session,
    keyname: str | None,
) -> int:
    """统计符合姓名筛选条件的用户数量。"""

    conditions = build_user_filters(keyname)
    statement = select(
        func.count(User.id)
    ).where(*conditions)
    return db.scalar(statement) or 0


def count_orders_by_user(
    db: Session,
    user_id: int,
) -> int:
    """统计必须保留的用户订单记录。"""

    statement = select(func.count(Order.id)).where(
        Order.user_id == user_id,
    )
    return db.scalar(statement) or 0

def get_user_by_id(
    db: Session,
    user_id: int,
) -> User | None:
    """根据主键查询用户。"""

    return db.get(
        User,
        user_id,
    )


def get_user_with_orders_by_id(
    db: Session,
    user_id: int,
) -> User | None:
    """查询用户并预加载其订单。"""

    statement = (
        select(User)
        .options(selectinload(User.orders))
        .where(User.id == user_id)
    )
    return db.scalar(statement)


def get_user_by_username(
    db: Session,
    username: str,
) -> User | None:
    """根据登录账号查询用户。"""

    statement = select(User).where(
        User.username == username,
    )

    return db.scalar(statement)


def add_user(
    db: Session,
    user: User,
) -> None:
    """把新用户加入数据库会话。"""

    db.add(user)
