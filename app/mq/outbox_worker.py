import logging
import time

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import engine
from app.services.outbox import publish_next_outbox_message


logger = logging.getLogger(__name__)
OUTBOX_POLL_INTERVAL_SECONDS = 1


def run_outbox_publisher_worker() -> None:
    """持续把数据库中的待发送消息发布到 RabbitMQ。"""

    while True:
        try:
            with Session(engine) as db:
                processed = publish_next_outbox_message(db)
        except SQLAlchemyError:
            logger.exception("查询或更新 Outbox 消息失败")
            processed = False

        if not processed:
            time.sleep(OUTBOX_POLL_INTERVAL_SECONDS)
