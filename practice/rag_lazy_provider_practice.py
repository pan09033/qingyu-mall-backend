from collections.abc import Callable


def get_demo_provider() -> str:
    """模拟获取模型。"""
    print("现在才获取模型")
    return "模拟模型"


def answer_demo(
    is_personal_query: bool,
    provider_factory: Callable[[], str],
) -> str:
    # is_personal_query：是否属于个人记录查询
    # provider_factory：获取模型的函数，尚未执行

    if is_personal_query:
        return "暂时无法查询个人记录"

    provider = provider_factory()
    # provider：调用获取函数后得到的模拟模型

    return f"使用{provider}处理公共知识问题"


def main() -> None:
    print("第一次：个人记录问题")
    print(
        answer_demo(
            is_personal_query=True,
            provider_factory=get_demo_provider,
        )
    )

    print("第二次：公共知识问题")
    print(
        answer_demo(
            is_personal_query=False,
            provider_factory=get_demo_provider,
        )
    )


if __name__ == "__main__":
    main()