from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.address import Address
from app.models.user import User


def lock_user_for_address_change(
    db: Session,
    user_id: int,
) -> User | None:
    """锁定用户行，让该用户的地址变更依次执行。"""

    statement = (
        select(User)
        .where(User.id == user_id)
        .with_for_update()
    )
    return db.scalar(statement)


def get_address_by_user(
    db: Session,
    user_id: int,
    address_id: int,
) -> Address | None:
    """查询属于指定用户的一条地址。"""

    statement = select(Address).where(
        Address.id == address_id,
        Address.user_id == user_id,
    )
    return db.scalar(statement)


def get_addresses_by_user(
    db: Session,
    user_id: int,
) -> Sequence[Address]:
    """查询地址；默认地址优先，其余地址按新到旧排列。"""

    statement = (
        select(Address)
        .where(Address.user_id == user_id)
        .order_by(
            Address.is_default.desc(),
            Address.id.desc(),
        )
    )
    return db.scalars(statement).all()


def get_first_address_by_user(
    db: Session,
    user_id: int,
) -> Address | None:
    """查询当前用户编号最小的一条地址。"""

    statement = (
        select(Address)
        .where(Address.user_id == user_id)
        .order_by(Address.id)
        .limit(1)
    )
    return db.scalar(statement)


def clear_default_addresses(
    db: Session,
    user_id: int,
) -> None:
    """取消当前用户已有的默认地址。"""

    statement = (
        update(Address)
        .where(
            Address.user_id == user_id,
            Address.is_default.is_(True),
        )
        .values(is_default=False)
    )
    db.execute(statement)


def add_address(
    db: Session,
    address: Address,
) -> None:
    """把地址加入当前数据库会话。"""

    db.add(address)


def remove_address(
    db: Session,
    address: Address,
) -> None:
    """把地址标记为待删除。"""

    db.delete(address)
