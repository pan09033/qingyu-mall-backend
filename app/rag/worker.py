import logging
import time

from sqlalchemy.orm import Session

from app.database import engine
from app.logging_config import setup_logging
from app.rag.database import rag_engine
from app.rag.services.product_sync_tasks import (
    process_next_product_sync_task,
)


# logger：当前模块的日志记录器
logger = logging.getLogger(__name__)

# 没有任务或本轮异常时，等待1秒再查询
POLL_INTERVAL_SECONDS = 1


def run_product_sync_worker() -> None:
    """持续处理商品知识同步任务。"""

    logger.info("商品知识同步Worker已启动")

    while True:
        try:
            # 每轮创建独立会话，退出with时自动关闭
            with (
                Session(engine) as mysql_db,
                Session(rag_engine) as rag_db,
            ):
                # processed：本轮是否处理过一条任务
                processed = process_next_product_sync_task(
                    mysql_db=mysql_db,
                    rag_db=rag_db,
                )

        except Exception as error:
            # 仅记录异常类型，避免输出原始异常中的敏感信息
            logger.error(
                "商品知识同步本轮异常：%s",
                type(error).__name__,
            )
            processed = False

        if not processed:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    setup_logging()

    try:
        run_product_sync_worker()
    except KeyboardInterrupt:
        logger.info("商品知识同步Worker已停止")