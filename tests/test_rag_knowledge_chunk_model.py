from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.config import settings
from app.database import Base
from app.rag.database import RagBase
from app.rag.models.knowledge_chunk import KnowledgeChunk


def test_knowledge_chunk_is_registered_only_with_rag_base() -> None:
    assert "knowledge_chunks" in RagBase.metadata.tables
    assert "knowledge_chunks" not in Base.metadata.tables


def test_knowledge_chunk_maps_metadata_column_name() -> None:
    column = KnowledgeChunk.__table__.c.metadata

    assert column.name == "metadata"
    assert KnowledgeChunk.metadata_json.property.columns[0] is column


def test_knowledge_chunk_uses_configured_vector_dimension() -> None:
    create_table_sql = str(
        CreateTable(KnowledgeChunk.__table__).compile(
            dialect=postgresql.dialect(),
        )
    )

    expected_type = f"VECTOR({settings.rag_embedding_dimension})"
    assert expected_type in create_table_sql
