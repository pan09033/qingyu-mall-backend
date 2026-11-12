import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .exceptions import AppError
from .logging_config import setup_logging
from .routers import (
    addresses,
    admin_orders,
    admin_rag,
    admin_refunds,
    admin_support,
    auth,
    cart,
    categories,
    media,
    orders,
    payments,
    products,
    rag,
    refunds,
    users,
    support,
)


setup_logging(
    settings.log_level,
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="用户和商品管理系统",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Vite 在默认端口被占用时会自动换端口。
    # 开发环境允许本机任意端口，生产环境仍只使用上面的明确白名单。
    allow_origin_regex=(
        r"^http://(?:localhost|127\.0\.0\.1):\d+$"
        if settings.app_env == "development"
        else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(
    _request: Request,
    error: AppError,
) -> JSONResponse:
    """把项目业务异常统一转换成 JSON 响应。"""

    return JSONResponse(
        status_code=error.status_code,
        content={
            "detail": error.detail,
        },
    )


app.include_router(users.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(addresses.router)
app.include_router(cart.router)
app.include_router(payments.router)
app.include_router(admin_orders.router)
app.include_router(admin_rag.router)
app.include_router(refunds.router)
app.include_router(admin_refunds.router)
app.include_router(media.router)
app.include_router(rag.router)
app.include_router(support.router)
app.include_router(admin_support.router)


@app.get("/", tags=["系统"])
def root() -> dict[str, str]:
    """返回系统运行状态。"""

    logger.info("用户访问系统首页")

    return {
        "message": "用户和商品管理系统运行成功",
    }
