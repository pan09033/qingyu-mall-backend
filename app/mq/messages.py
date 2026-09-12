from pydantic import BaseModel, Field


class OrderExpirationMessage(BaseModel):
    order_id: int = Field(gt=0)
