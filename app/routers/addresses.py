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
from app.schemas.address import (
    AddressCreate,
    AddressResponse,
    AddressUpdate,
)
from app.services.address import (
    create_user_address,
    delete_user_address,
    get_address_or_404,
    list_user_addresses,
    set_default_address,
    update_user_address,
)


router = APIRouter(
    prefix="/addresses",
    tags=["收货地址"],
)

Database = Annotated[
    Session,
    Depends(get_db),
]
CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]
AddressId = Annotated[
    int,
    Path(ge=1),
]


@router.post(
    "/",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_address(
    current_user: CurrentUser,
    address_data: AddressCreate,
    db: Database,
):
    return create_user_address(
        db,
        current_user.id,
        address_data,
    )


@router.get(
    "/",
    response_model=list[AddressResponse],
)
def get_addresses(
    current_user: CurrentUser,
    db: Database,
):
    return list_user_addresses(
        db,
        current_user.id,
    )


@router.get(
    "/{address_id}",
    response_model=AddressResponse,
)
def get_address(
    current_user: CurrentUser,
    address_id: AddressId,
    db: Database,
):
    return get_address_or_404(
        db,
        current_user.id,
        address_id,
    )


@router.patch(
    "/{address_id}",
    response_model=AddressResponse,
)
def update_address(
    current_user: CurrentUser,
    address_id: AddressId,
    address_data: AddressUpdate,
    db: Database,
):
    return update_user_address(
        db,
        current_user.id,
        address_id,
        address_data,
    )


@router.patch(
    "/{address_id}/default",
    response_model=AddressResponse,
)
def make_address_default(
    current_user: CurrentUser,
    address_id: AddressId,
    db: Database,
):
    return set_default_address(
        db,
        current_user.id,
        address_id,
    )


@router.delete(
    "/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_address(
    current_user: CurrentUser,
    address_id: AddressId,
    db: Database,
) -> Response:
    delete_user_address(
        db,
        current_user.id,
        address_id,
    )
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
