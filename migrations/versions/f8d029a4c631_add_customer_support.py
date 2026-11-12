"""Add persistent support conversations, turns and human tickets."""

from alembic import op
import sqlalchemy as sa

revision = "f8d029a4c631"
down_revision = "ee6653e6cf39"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("support_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_support_conversations_user_updated", "support_conversations", ["user_id", "updated_at"])
    op.create_table("support_turns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("support_conversations.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("conversation_id", "request_id", name="uq_support_turn_request"))
    op.create_index("ix_support_turns_conversation_id", "support_turns", ["conversation_id", "id"])
    op.create_table("support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("support_conversations.id"), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reply", sa.Text(), nullable=False),
        sa.Column("assigned_admin_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'resolved')", name="ck_support_tickets_status"))
    op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"])
    op.create_index("ix_support_tickets_status_updated", "support_tickets", ["status", "updated_at"])


def downgrade():
    op.drop_table("support_tickets")
    op.drop_table("support_turns")
    op.drop_table("support_conversations")
