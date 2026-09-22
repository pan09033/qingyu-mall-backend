from app.exceptions import AppError


class RagServiceUnavailableError(AppError):
    """智能购物助手暂时无法完成问答。"""

    def __init__(
        self,
        detail: str = "智能购物助手暂时不可用，请稍后重试",
    ) -> None:
        super().__init__(
            status_code=503,
            detail=detail,
        )