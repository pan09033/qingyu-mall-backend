from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import ResourceNotFoundError
from app.models.address import Address
from app.repositories.address import (
    add_address,
    clear_default_addresses,
    get_address_by_user,
    get_addresses_by_user,
    get_first_address_by_user,
    lock_user_for_address_change,
    remove_address,
)
from app.schemas.address import AddressCreate, AddressUpdate


def get_address_or_404(
    db: Session,
    user_id: int,
    address_id: int,
) -> Address:
    """查询当前用户的地址，不存在或不属于该用户时返回404。"""

    address = get_address_by_user(
        db,
        user_id,
        address_id,
    )
    if address is None:
        raise ResourceNotFoundError(
            "收货地址不存在"
        )

    return address


def list_user_addresses(
    db: Session,
    user_id: int,
) -> Sequence[Address]:
    """返回当前用户的全部收货地址。"""

    return get_addresses_by_user(
        db,
        user_id,
    )


def create_user_address(
    db: Session,
    user_id: int,
    address_data: AddressCreate,
) -> Address:
    """创建收货地址；第一条地址自动成为默认地址。"""

    try:
        lock_user_for_address_change(
            db,
            user_id,
        )

        existing_addresses = get_addresses_by_user(
            db,
            user_id,
        )
        should_be_default = (
            not existing_addresses
            or address_data.is_default
        )

        if should_be_default:
            clear_default_addresses(
                db,
                user_id,
            )

        new_address = Address(
            user_id=user_id,
            receiver_name=address_data.receiver_name,
            phone=address_data.phone,
            province=address_data.province,
            city=address_data.city,
            district=address_data.district,
            detail_address=address_data.detail_address,
            is_default=should_be_default,
        )
        add_address(
            db,
            new_address,
        )

        db.commit()
        db.refresh(new_address)
        return new_address

    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="收货地址创建失败",
        ) from error


def update_user_address(
    db: Session,
    user_id: int,
    address_id: int,
    address_data: AddressUpdate,
) -> Address:
    """修改当前用户的一条收货地址。"""

    address = get_address_or_404(
        db,
        user_id,
        address_id,
    )
    update_data = address_data.model_dump(
        exclude_unset=True,
    )

    for field, value in update_data.items():
        setattr(address, field, value)

    try:
        db.commit()
        db.refresh(address)
        return address

    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="收货地址修改失败",
        ) from error


def set_default_address(
    db: Session,
    user_id: int,
    address_id: int,
) -> Address:
    """把指定地址设为当前用户唯一的默认地址。"""

    try:
        lock_user_for_address_change(
            db,
            user_id,
        )
        address = get_address_or_404(
            db,
            user_id,
            address_id,
        )

        clear_default_addresses(
            db,
            user_id,
        )
        address.is_default = True

        db.commit()
        db.refresh(address)
        return address

    except ResourceNotFoundError:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="默认地址设置失败",
        ) from error


def delete_user_address(
    db: Session,
    user_id: int,
    address_id: int,
) -> None:
    """删除地址；删除默认地址后自动补充一个默认地址。"""

    try:
        lock_user_for_address_change(
            db,
            user_id,
        )
        address = get_address_or_404(
            db,
            user_id,
            address_id,
        )
        was_default = address.is_default

        remove_address(
            db,
            address,
        )
        db.flush()

        if was_default:
            next_address = get_first_address_by_user(
                db,
                user_id,
            )
            if next_address is not None:
                next_address.is_default = True

        db.commit()

    except ResourceNotFoundError:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="收货地址删除失败",
        ) from error
