from pathlib import Path

from app.schemas.rag import (
    PolicyKnowledgeDocument,
    PolicyKnowledgeMetadata,
)


def build_policy_knowledge_documents(
    file_path: Path,
    source_id: str,
    topic: str,
) -> list[PolicyKnowledgeDocument]:
    """读取规则Markdown，并按二级标题生成知识分段。"""

    markdown_text = file_path.read_text(
        encoding="utf-8"
    )
    lines = markdown_text.splitlines()

    document_name = ""

    for line in lines:
        if line.startswith("# "):
            document_name = line[2:].strip()
            break

    if not document_name:
        raise ValueError("规则文档缺少一级标题")

    sections: list[tuple[str, list[str]]] = []
    current_section: str | None = None
    current_content_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_section is not None:
                sections.append(
                    (
                        current_section,
                        current_content_lines,
                    )
                )

            current_section = line[3:].strip()
            current_content_lines = []
            continue

        if current_section is not None:
            current_content_lines.append(line)

    if current_section is not None:
        sections.append(
            (
                current_section,
                current_content_lines,
            )
        )

    if not sections:
        raise ValueError("规则文档缺少二级标题")

    documents = []

    for chunk_index, (
        section,
        content_lines,
    ) in enumerate(sections):
        section_content = "\n".join(
            content_lines
        ).strip()

        if not section:
            raise ValueError("规则文档存在空章节标题")

        if not section_content:
            raise ValueError(
                f"规则文档章节没有正文：{section}"
            )

        content = (
            f"文档名称：{document_name}。\n"
            f"章节：{section}。\n"
            f"{section_content}"
        )

        documents.append(
            PolicyKnowledgeDocument(
                source_id=source_id,
                title=(
                    f"{document_name} - {section}"
                ),
                content=content,
                chunk_index=chunk_index,
                metadata=PolicyKnowledgeMetadata(
                    document_name=document_name,
                    section=section,
                    topic=topic,
                    source_file=file_path.name,
                ),
            )
        )

    return documents