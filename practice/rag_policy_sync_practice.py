from pathlib import Path

from sqlalchemy.orm import Session

from app.rag.database import rag_engine
from app.rag.providers.factory import get_embedding_provider
from app.rag.services.policy_sync import sync_policy_knowledge


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    file_path = (
        PROJECT_ROOT
        / "knowledge"
        / "policies"
        / "shipping_policy.md"
    )

    with Session(rag_engine) as rag_db:
        count = sync_policy_knowledge(
            rag_db=rag_db,
            embedding_provider=get_embedding_provider(),
            file_path=file_path,
            source_id="shipping_policy",
            topic="shipping",
        )

    print(f"配送规则同步完成，共同步 {count} 个知识分段。")


if __name__ == "__main__":
    main()
