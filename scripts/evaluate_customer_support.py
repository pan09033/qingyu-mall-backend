"""客服检索回归：默认只读本地知识库；--answers 才会调用已配置的聊天API。

python -m scripts.evaluate_customer_support
python -m scripts.evaluate_customer_support --answers --output output/support-evaluation.json
"""

import argparse
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.rag.database import rag_engine
from app.rag.providers.factory import get_chat_provider, get_embedding_provider
from app.rag.services.grounded_qa import GROUNDED_PROMPT, evidence_covers_question, no_knowledge_answer, validate_grounded_answer
from app.rag.services.qa import build_user_prompt
from app.rag.services.query_analysis import infer_knowledge_scope
from app.rag.services.retrieval import retrieve_knowledge

# cases：独立的固定回归题，预期来源不依赖关键词分类的实现顺序。
CASES = [
    ("address", "付款后还能修改收货地址吗？", "shipping_policy", 3),
    ("shipped_refund", "已发货的订单如何申请退款？", "refund_policy", 2),
    ("paid_refund", "已付款未发货能申请仅退款吗？", "refund_policy", 1),
    ("payment_deadline", "超过付款期限的订单还能支付吗？", "payment_policy", 0),
    ("shipping_unknown", "发货后能查到快递公司和预计送达时间吗？", "shipping_policy", 4),
    ("invoice_missing", "商城支持开发票吗？", None, None),
]


def run(evaluate_answers: bool, prompt_preview: Path | None = None) -> dict:
    results = []
    prompts = []  # prompts：可在调用API前审阅的实际测试请求，不包含密钥
    embedding = get_embedding_provider()
    with Session(rag_engine) as db:
        for name, question, source_id, chunk_index in CASES:
            scope, topic = infer_knowledge_scope(question)
            matches = retrieve_knowledge(db, embedding, question, settings.rag_minimum_similarity,
                                         source_type=scope, topic=topic, limit=settings.rag_retrieval_limit)
            rank = next((index for index, (chunk, _) in enumerate(matches, 1)
                         if (chunk.source_id, chunk.chunk_index) == (source_id, chunk_index)), None)
            record = {"name": name, "question": question, "scope": scope, "topic": topic,
                      "expected_source": source_id, "target_rank": rank,
                      "evidence_topic_covered": evidence_covers_question(question, matches),
                      "hits": [{"source": chunk.source_id, "chunk": chunk.chunk_index, "score": round(score, 4)}
                               for chunk, score in matches]}
            if matches and record["evidence_topic_covered"]:
                prompts.append({"case": name, "system_prompt": GROUNDED_PROMPT,
                                "user_prompt": build_user_prompt(question, matches)})
            if evaluate_answers:
                if matches and record["evidence_topic_covered"]:
                    raw = get_chat_provider().generate_answer(system_prompt=GROUNDED_PROMPT,
                                                              user_prompt=build_user_prompt(question, matches))
                    answer = validate_grounded_answer(raw, matches)
                else:
                    answer = no_knowledge_answer()
                record["response"] = answer.model_dump(mode="json")
                record["answer_structure_pass"] = (
                    answer.kind == "no_knowledge" if source_id is None else
                    answer.kind == "knowledge" and any(source.source_id == source_id for source in answer.sources)
                )
            results.append(record)
            print(f"{name}: target_rank={rank}, candidates={len(matches)}", flush=True)
    if prompt_preview:
        prompt_preview.parent.mkdir(parents=True, exist_ok=True)
        prompt_preview.write_text(json.dumps(prompts, ensure_ascii=False, indent=2), encoding="utf-8")
    expected = [item for item in results if item["expected_source"] is not None]
    return {"cases": results, "retrieval_expected_cases": len(expected),
            "target_hit_count": sum(item["target_rank"] is not None for item in expected),
            "target_top1_count": sum(item["target_rank"] == 1 for item in expected),
            "answer_structure_pass_count": sum(item.get("answer_structure_pass", False) for item in results) if evaluate_answers else None,
            "limitations": "小样本固定回归。原文摘录校验不能证明答案语义正确；最终回答仍需人工审核。纯预算和订单查询由接口测试单独覆盖。"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", action="store_true", help="调用聊天API评测回答，会产生API费用")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prompt-preview", type=Path, help="保存待发送的测试问题和知识原文，便于先审阅")
    args = parser.parse_args()
    try:
        result = run(args.answers, args.prompt_preview)
    except Exception as error:
        # 不打印可能包含数据库地址、密钥或请求头的异常内容。
        print(f"Evaluation unavailable: {type(error).__name__}")
        raise SystemExit(1)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
