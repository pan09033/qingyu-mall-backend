from pathlib import Path

from app.rag.ingestion.policy import (
    build_policy_knowledge_documents,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
# PROJECT_ROOT：项目根目录


def main() -> None:
    file_path = (
        PROJECT_ROOT
        / "knowledge"
        / "policies"
        / "shipping_policy.md"
    )
    # file_path：配送规则文档路径

    documents = build_policy_knowledge_documents(
        file_path=file_path,
        source_id="shipping_policy",
        topic="shipping",
    )
    # documents：切分后的知识文档列表

    for document in documents:
        # document：当前循环中的一个知识分段

        print(f"唯一编号：{document.document_key}")
        print(f"来源类型：{document.source_type}")
        print(f"规则主题：{document.metadata.topic}")
        print(f"章节名称：{document.metadata.section}")
        print(f"文本内容：\n{document.content}")
        print("-" * 50)


if __name__ == "__main__":
    main()