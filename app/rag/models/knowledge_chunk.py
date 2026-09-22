from pgvector.sqlalchemy import VECTOR
from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.rag.database import RagBase


class KnowledgeChunk(RagBase):
    """一段可以被向量检索的商城知识。"""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index(
            "ix_knowledge_chunks_source",
            "source_type",
            "source_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    document_key: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    source_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
    )

    embedding: Mapped[list[float]] = mapped_column(
        VECTOR(settings.rag_embedding_dimension),
        nullable=False,
    )