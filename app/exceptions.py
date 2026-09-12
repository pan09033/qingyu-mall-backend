class AppError(Exception):
    """项目中所有自定义业务异常的父类。"""

    def __init__(
        self,
        status_code: int,
        detail: str,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ResourceNotFoundError(AppError):
    """查询的业务资源不存在。"""

    def __init__(
        self,
        detail: str = "资源不存在",
    ) -> None:
        super().__init__(
            status_code=404,
            detail=detail,
        )

class PermissionDeniedError(AppError):
    def __init__(self,
                 detail:str = '没有操作权限',
                 )->None:
        super().__init__(status_code=403,detail=detail)

class ConflictError(AppError):
    def __init__(self,
        detail: str = '数据冲突')->None:
        super().__init__(status_code=409,
                         detail=detail,)


class RetryableOrderExpirationError(Exception):
    """订单过期任务遇到可以重试的数据库故障。"""
