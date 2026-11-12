"""客服只读工具：固定参数与授权查询，不执行模型生成的 SQL。"""

import re
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.order import get_order_by_user
from app.repositories.support import find_budget_products
from app.schemas.support import OrderSummary, SupportAnswer, SupportSource

ORDER_LABELS = {  # ORDER_LABELS：订单状态的中文说明
    "pending": "待付款", "paid": "已付款", "shipped": "已发货",
    "completed": "已完成", "cancelled": "已取消", "refund_pending": "退款处理中", "refunded": "已退款",
}
REFUND_LABELS = {  # REFUND_LABELS：商城退款申请状态，不代表银行实际入账
    "pending": "等待审核", "waiting_return": "等待退货", "returning": "退货中",
    "approved": "已批准", "rejected": "已拒绝",
}
ORDER_ID_PATTERNS = (
    re.compile(r"订单\s*(?:编号|号|ID|id)?\s*[:：#]?\s*([1-9]\d{0,9})(?!\d)"),
    re.compile(r"(?<!\d)([1-9]\d{0,9})\s*号订单"),
)


def extract_order_ids(question: str) -> set[int]:
    # 只把明确的订单编号提取为ID，金额、日期不会被当作订单号。
    return {int(value) for pattern in ORDER_ID_PATTERNS for value in pattern.findall(question)}


def is_budget_only_question(question: str) -> bool:
    # 只有价格条件的泛商品推荐使用实时 SQL；带“耳机”等需求的仍走语义检索。
    remaining = re.sub(r"\d+(?:\.\d{1,2})?", "", question)
    for phrase in ("有没有", "有哪些", "有什么", "不超过", "以内", "以下", "推荐", "预算", "最多", "商品", "产品", "东西", "可以买", "能买", "帮我", "请", "元", "的", "我", "想买", "买", "？", "?", "，", ",", "。", " "):
        remaining = remaining.replace(phrase, "")
    return not remaining


def query_budget_products(db: Session, max_price: Decimal) -> SupportAnswer:
    products = find_budget_products(db, max_price)
    if not products:
        return SupportAnswer(answer=f"当前没有找到价格不超过{max_price}元且有库存的商品。可以调整预算或联系人工客服。",
                             kind="products", handoff_available=True)
    lines = [f"当前价格不超过{max_price}元的部分有货商品（按价格从低到高）："]
    sources = []
    for number, product in enumerate(products, 1):
        lines.append(f"{product.name}：{product.price}元，库存{product.stock}件。[资料{number}]")
        sources.append(SupportSource(citation_number=number, source_type="product",
            source_id=str(product.id), title=product.name, excerpt="商城当前商品记录"))
    lines.append("价格和库存可能变化，请以下单时的页面为准。")
    return SupportAnswer(answer="\n".join(lines), kind="products", sources=sources)


def query_owned_order(db: Session, user_id: int, order_id: int, question: str) -> SupportAnswer:
    order = get_order_by_user(db, user_id, order_id)
    if order is None:
        # 对不存在及其他用户的订单返回相同结果，避免泄露其是否存在。
        return SupportAnswer(answer="没有找到你名下的这笔订单，请核对订单编号。",
                             kind="clarification", handoff_available=True)
    refund = order.refund_request
    summary = OrderSummary(order_id=order.id, status=order.status,
        status_label=ORDER_LABELS.get(order.status, "未知状态"), total_amount=str(order.total_amount),
        refund_status=refund.status if refund else None,
        refund_status_label=REFUND_LABELS.get(refund.status, "未知状态") if refund else None)
    lines = [f"订单 #{order.id} 当前状态：{summary.status_label}。订单金额：{summary.total_amount}元。"]
    if refund:
        lines.append(f"商城退款申请状态：{summary.refund_status_label}。")
    if any(word in question for word in ("退款", "退货", "能退", "退吗", "售后")):
        if refund:
            lines.append("这笔订单已经提交过退款申请，不能重复申请。请到售后页面查看或处理原申请。")
            if refund.status == "waiting_return":
                lines.append("当前需要寄回商品，并在售后页面填写退货物流信息。")
        elif order.status == "paid":
            lines.append("当前可以在订单详情申请“仅退款”，填写原因后等待管理员审核。")
        elif order.status == "shipped":
            lines.append("当前可以申请“退货退款”，不能申请仅退款；审核同意后需要寄回商品。")
        else:
            lines.append("按照当前商城业务规则，这个订单状态不能发起新的退款申请。")
        lines.append("本次仅查询并说明申请条件，没有代你提交退款。")
    if "到账" in question:
        lines.append("商城记录不能证明支付账户的实际到账情况，请核对支付账户流水或联系人工客服。")
    if "地址" in question and any(word in question for word in ("改", "换")):
        if order.status == "pending":
            lines.append("这笔订单仍待付款，可以在订单详情修改为你地址簿中的其他收货地址。")
        else:
            lines.append("当前订单状态不能修改收货地址；商城只允许待付款订单修改。可联系人工客服协助。")
    if any(word in question for word in ("快递", "物流", "送达", "到货")):
        lines.append("商城当前没有保存发货快递公司、物流轨迹或预计送达时间，需要人工协助确认。")
    if "发货" in question and any(word in question for word in ("什么时候", "多久", "几天")):
        lines.append("商城当前没有记录承诺发货时间，需要人工协助确认。")
    return SupportAnswer(answer="\n".join(lines), kind="order", order=summary,
                         handoff_available=any(word in question for word in ("到账", "快递", "物流", "送达", "到货", "地址", "什么时候", "多久", "几天")))
