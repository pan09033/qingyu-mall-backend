from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.cart import (
    CartCheckout,
    CartItemCreate,
    CartItemResponse,
    CartItemUpdate,
    CartResponse,
)
from app.schemas.order import OrderResponse
from app.services.cart import (
    add_product_to_cart,
    clear_user_cart,
    delete_user_cart_item,
    list_user_cart,
    update_cart_item_quantity,
)
from app.services.order import checkout_user_cart


router = APIRouter(
    prefix="/cart",
    tags=["购物车"],
)

Database = Annotated[
    Session,
    Depends(get_db),
]
CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]
CartItemId = Annotated[
    int,
    Path(ge=1),
]


@router.get(
    "/",
    response_model=CartResponse,
)
def get_cart(
    current_user: CurrentUser,
    db: Database,
):
    return list_user_cart(
        db,
        current_user.id,
    )


@router.post(
    "/items",
    response_model=CartItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_cart_item(
    current_user: CurrentUser,
    cart_data: CartItemCreate,
    db: Database,
):
    return add_product_to_cart(
        db,
        current_user.id,
        cart_data,
    )


@router.post(
    "/checkout",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def checkout_cart(
    current_user: CurrentUser,
    checkout_data: CartCheckout,
    db: Database,
):
    return checkout_user_cart(
        db,
        current_user.id,
        checkout_data,
    )


@router.patch(
    "/items/{cart_item_id}",
    response_model=CartItemResponse,
)
def update_cart_item(
    current_user: CurrentUser,
    cart_item_id: CartItemId,
    cart_data: CartItemUpdate,
    db: Database,
):
    return update_cart_item_quantity(
        db,
        current_user.id,
        cart_item_id,
        cart_data,
    )


@router.delete(
    "/items/{cart_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_cart_item(
    current_user: CurrentUser,
    cart_item_id: CartItemId,
    db: Database,
) -> Response:
    delete_user_cart_item(
        db,
        current_user.id,
        cart_item_id,
    )
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.delete(
    "/",
    status_code=status.HTTP_204_NO_CONTENT,
)
def clear_cart(
    current_user: CurrentUser,
    db: Database,
) -> Response:
    clear_user_cart(
        db,
        current_user.id,
    )
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
