"""init db

Revision ID: c560649293d7
Revises:
Create Date: 2024-12-15 18:01:02.458425

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import pgvector


# revision identifiers, used by Alembic.
revision: str = "c560649293d7"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(length=30), nullable=True),
        sa.Column("authors", sa.ARRAY(sa.String(length=50)), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column("wa_id", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("state", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column(
            "onboarding_state",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=True,
        ),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("class_info", sa.JSON(), nullable=True),
        sa.Column(
            "school_name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("region", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_wa_id"), "users", ["wa_id"], unique=True)
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column(
            "chunk_type", sqlmodel.sql.sqltypes.AutoString(length=30), nullable=True
        ),
        sa.Column(
            "embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True
        ),
        sa.Column(
            "top_level_section_index",
            sqlmodel.sql.sqltypes.AutoString(length=10),
            nullable=True,
        ),
        sa.Column(
            "top_level_section_title",
            sqlmodel.sql.sqltypes.AutoString(length=100),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "chunk_embedding_idx",
        "chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        op.f("ix_chunks_resource_id"), "chunks", ["resource_id"], unique=False
    )
    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column(
            "grade_level", sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False
        ),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_id", "grade_level", name="unique_classes"),
    )
    op.create_index(
        op.f("ix_classes_grade_level"), "classes", ["grade_level"], unique=False
    )
    op.create_index(
        op.f("ix_classes_subject_id"), "classes", ["subject_id"], unique=False
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("tool_calls", sa.JSON(), nullable=True),
        sa.Column("tool_call_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "tool_name", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_messages_created_at"), "messages", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_messages_user_id"), "messages", ["user_id"], unique=False)
    op.create_table(
        "classes_resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_classes_resources_class_id"),
        "classes_resources",
        ["class_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_classes_resources_resource_id"),
        "classes_resources",
        ["resource_id"],
        unique=False,
    )
    op.create_table(
        "teachers_classes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teacher_id", "class_id", name="unique_teacher_class"),
    )
    op.create_index(
        op.f("ix_teachers_classes_class_id"),
        "teachers_classes",
        ["class_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_teachers_classes_teacher_id"),
        "teachers_classes",
        ["teacher_id"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_teachers_classes_teacher_id"), table_name="teachers_classes")
    op.drop_index(op.f("ix_teachers_classes_class_id"), table_name="teachers_classes")
    op.drop_table("teachers_classes")
    op.drop_index(
        op.f("ix_classes_resources_resource_id"), table_name="classes_resources"
    )
    op.drop_index(op.f("ix_classes_resources_class_id"), table_name="classes_resources")
    op.drop_table("classes_resources")
    op.drop_index(op.f("ix_messages_user_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_created_at"), table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_classes_subject_id"), table_name="classes")
    op.drop_index(op.f("ix_classes_grade_level"), table_name="classes")
    op.drop_table("classes")
    op.drop_index(op.f("ix_chunks_resource_id"), table_name="chunks")
    op.drop_index(
        "chunk_embedding_idx",
        table_name="chunks",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_table("chunks")
    op.drop_index(op.f("ix_users_wa_id"), table_name="users")
    op.drop_table("users")
    op.drop_table("subjects")
    op.drop_table("resources")
    # ### end Alembic commands ###
