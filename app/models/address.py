from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Address(Base):
    """用户收货地址数据库模型。"""

    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    receiver_name: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    province: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    city: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    district: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    detail_address: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    is_default: Mapped[bool] = mapped_column(
        default=False,
        server_default="0",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        back_populates="addresses",
    )
