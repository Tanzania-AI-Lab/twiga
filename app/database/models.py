from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, date
from pydantic import BaseModel, ConfigDict, field_validator
from sqlmodel import (
    Index,
    Integer,
    Field,
    SQLModel,
    UniqueConstraint,
    Column,
    DateTime,
    String,
    ARRAY,
    JSON,
    Enum,
    Relationship,
    Date,
)
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa


class ResourceType(str, Enum):
    textbook = "textbook"
    curriculum = "curriculum"
    document = "document"
    # NOTE: add more types as needed, but keep clean structure with good segregation


class Role(str, Enum):
    admin = "admin"
    teacher = "teacher"


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    tool = "tool"
    system = "system"


class GradeLevel(str, Enum):
    p1 = "p1"  # primary 1
    p2 = "p2"
    p3 = "p3"
    p4 = "p4"
    p5 = "p5"
    p6 = "p6"
    os1 = "os1"  # ordinary secondary 1 (form 1)
    os2 = "os2"
    os3 = "os3"
    os4 = "os4"
    as1 = "as1"  # advanced secondary 1 (form 5)
    as2 = "as2"


class OnboardingState(str, Enum):
    new = "new"
    personal_info_submitted = "personal_info_submitted"
    completed = "completed"


class UserState(str, Enum):
    blocked = "blocked"
    rate_limited = "rate_limited"
    new = "new"
    onboarding = "onboarding"
    active = "active"


class SubjectNames(str, Enum):
    geography = "geography"
    mathematics = "mathematics"


class ChunkType(str, Enum):
    text = "text"
    exercise = "exercise"
    image = "image"
    table = "table"
    other = "other"
    # NOTE: add more types as needed, but keep clean structure with good segregation


class ClassInfo(BaseModel):
    """Maps subjects to their grade levels for a teacher"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # NOTE: The keys are Subject and the values are lists of GradeLevel
    subjects: Dict[str, List[str]]

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        return {
            subject: [grade for grade in grades]
            for subject, grades in data["subjects"].items()
        }

    @classmethod
    def model_validate(cls, data: Dict):
        if data is None:
            return None
        return cls(
            subjects={
                Subject(subject): [GradeLevel(grade) for grade in grades]
                for subject, grades in data.items()
            }
        )


class User(SQLModel, table=True):
    __tablename__ = "users"

    # TODO: allow for arbitrary types like OnboardingState, UserState, Role
    # The id is optional because it will be generated by the database
    id: Optional[int] = Field(default=None, primary_key=True)
    name: Optional[str] = Field(max_length=50)
    wa_id: str = Field(max_length=20, unique=True, index=True)
    state: str = Field(default=UserState.new, max_length=50)
    # TODO: Update the onboarding_state
    onboarding_state: Optional[str] = Field(
        default=OnboardingState.new, max_length=50
    )  # Is this really optional?
    role: str = Field(default=Role.teacher, max_length=20)
    selected_class_ids: Optional[List[int]] = Field(
        sa_column=Column(ARRAY(Integer)), default=[]
    )
    class_info: Optional[dict] = Field(default=None, sa_type=JSON)
    school_name: Optional[str] = Field(default=None, max_length=100)
    birthday: Optional[date] = Field(default=None, sa_type=Date)
    region: Optional[str] = Field(default=None, max_length=50)
    last_message_at: Optional[datetime] = Field(
        sa_type=DateTime(timezone=True)
    )  # user.last_message_at = datetime.now(timezone.utc) (this is how to set it when updating later)
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),  # type: ignore
        sa_column_kwargs={"server_default": sa.func.now()},
        nullable=False,
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),  # type: ignore
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc),
        },
        nullable=False,
    )

    # A teacher may have entries in the teachers_classes table
    taught_classes: Optional[List["TeacherClass"]] = Relationship(
        back_populates="teacher_", cascade_delete=True  # Could rename to user_
    )

    # A teacher may have entries in the messages table
    user_messages: Optional[List["Message"]] = Relationship(
        back_populates="user_", cascade_delete=True
    )


class Subject(SQLModel, table=True):
    __tablename__ = "subjects"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, nullable=False)

    # A subject may have entries in the classes table
    subject_classes: Optional[List["Class"]] = Relationship(back_populates="subject_")


class SubjectClassStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class Class(SQLModel, table=True):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("subject_id", "grade_level", name="unique_classes"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(
        max_length=100
    )  # we use this when we show user the class names on the flow
    subject_id: int = Field(foreign_key="subjects.id", index=True)
    grade_level: str = Field(max_length=10, index=True)  # use GradeLevel enum
    status: str = Field(default="active")

    # A class may have entries in the teachers_classes table
    class_teachers: Optional[List["TeacherClass"]] = Relationship(
        back_populates="class_", cascade_delete=True
    )
    # A class may have entries in the classes_resources table
    class_resources: Optional[List["ClassResource"]] = Relationship(
        back_populates="class_", cascade_delete=True
    )
    # Relationship to the Subject table
    subject_: Subject = Relationship(back_populates="subject_classes")


class TeacherClass(SQLModel, table=True):
    __tablename__ = "teachers_classes"
    __table_args__ = (
        UniqueConstraint("teacher_id", "class_id", name="unique_teacher_class"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    teacher_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    class_id: int = Field(foreign_key="classes.id", index=True, ondelete="CASCADE")

    class_: Class = Relationship(back_populates="class_teachers")
    teacher_: User = Relationship(back_populates="taught_classes")


class Message(SQLModel, table=True):
    """
    Message model aligned with OpenAI's chat completion format.
    Supports standard messages, tool calls, and tool responses.
    """

    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    role: str = Field(max_length=20)  # system, user, assistant, tool
    content: Optional[str] = Field(default=None)  # None when tool_calls present

    # Tool call related fields
    tool_calls: Optional[List[dict]] = Field(
        default=None, sa_column=Column(JSON)
    )  # For assistant messages with tool calls
    tool_call_id: Optional[str] = Field(default=None)  # For tool response messages
    # TODO: Make tool_name actually be used (right now its always None)
    tool_name: Optional[str] = Field(
        default=None, max_length=50
    )  # Good for tracking tool usage

    # Metadata
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),  # type: ignore
        sa_column_kwargs={"server_default": sa.func.now()},
        nullable=False,
        index=True,
    )

    # Relationships
    user_: "User" = Relationship(back_populates="user_messages")

    @field_validator("tool_calls", mode="before")
    @classmethod
    def validate_tool_calls(cls, v):

        # Convert empty list to none
        if v == []:
            return None
        """Ensure tool_calls is a list of dicts with required fields"""
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("tool_calls must be a list")
            for call in v:
                if not isinstance(call, dict):
                    raise ValueError("Each tool call must be a dict")
                required_fields = {"id", "type", "function"}
                if not all(field in call for field in required_fields):
                    raise ValueError(
                        f"Tool call missing required fields: {required_fields}"
                    )
        return v

    def to_api_format(self) -> dict:
        """Convert message to OpenAI API format"""
        message = {"role": self.role}
        if self.tool_calls and len(self.tool_calls) > 0:
            message["tool_calls"] = self.tool_calls
            message["content"] = None
        if self.content is not None:
            message["content"] = self.content
        if self.tool_call_id is not None:
            message["tool_call_id"] = self.tool_call_id
        # if self.tool_name is not None:
        #     message["name"] = self.tool_name

        return message

    @classmethod
    def from_api_format(cls, data: dict, user_id: int) -> "Message":
        """Create message from OpenAI API format"""
        message_data = {
            "user_id": user_id,
            "role": data["role"],
            "content": data.get("content"),
            "tool_calls": data.get("tool_calls"),
            "tool_call_id": data.get("tool_call_id"),
            "tool_name": data.get("name"),  # NOTE: This might not be needed
        }
        return cls(**message_data)


# class Message(SQLModel, table=True):
#     __tablename__ = "messages"

#     id: Optional[int] = Field(default=None, primary_key=True)
#     user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
#     role: str = Field(max_length=20)
#     content: str

#     created_at: Optional[datetime] = Field(
#         default_factory=lambda: datetime.now(timezone.utc),
#         sa_type=DateTime(timezone=True),  # type: ignore
#         sa_column_kwargs={"server_default": sa.func.now()},
#         nullable=False,
#         index=True,
#     )

#     user_: User = Relationship(back_populates="user_messages")
#     # NOTE: add a field for message type (eg. text/image)
#     # NOTE: add a field for the content embedding for when we start doing RAG on chat history


class Resource(SQLModel, table=True):
    __tablename__ = "resources"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    type: Optional[str] = Field(max_length=30)  # use ResourceType enum
    authors: Optional[List[str]] = Field(sa_column=Column(ARRAY(String(50))))
    grade_levels: Optional[List[str]] = Field(
        sa_column=Column(ARRAY(String(10)))
    )  # Use GradeLevel enum
    subjects: Optional[List[str]] = Field(sa_column=Column(ARRAY(String(50))))
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),  # type: ignore
        sa_column_kwargs={"server_default": sa.func.now()},
        nullable=False,
    )

    resource_classes: Optional[List["ClassResource"]] = Relationship(
        back_populates="resource_", cascade_delete=True
    )
    resource_sections: Optional[List["Section"]] = Relationship(
        back_populates="resource_", cascade_delete=True
    )
    resource_chunks: Optional[List["Chunk"]] = Relationship(
        back_populates="resource_", cascade_delete=True
    )


class ClassResource(SQLModel, table=True):
    __tablename__ = "classes_resources"
    id: Optional[int] = Field(default=None, primary_key=True)
    class_id: int = Field(foreign_key="classes.id", index=True, ondelete="CASCADE")
    resource_id: int = Field(foreign_key="resources.id", index=True, ondelete="CASCADE")

    class_: Class = Relationship(back_populates="class_resources")
    resource_: Resource = Relationship(back_populates="resource_classes")


class Section(SQLModel, table=True):
    __tablename__ = "sections"
    id: Optional[int] = Field(default=None, primary_key=True)
    resource_id: int = Field(foreign_key="resources.id", index=True, ondelete="CASCADE")
    parent_section_id: Optional[int] = Field(
        default=None, foreign_key="sections.id", nullable=True
    )
    section_index: Optional[str] = Field(max_length=20, default=None)
    section_title: Optional[str] = Field(max_length=100, default=None)
    section_type: Optional[str] = Field(max_length=15, default=None)
    section_order: int
    page_range: Optional[List[int]] = Field(sa_column=Column(ARRAY(Integer)))
    summary: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),  # type: ignore
        sa_column_kwargs={"server_default": sa.func.now()},
        nullable=False,
    )

    resource_: Resource = Relationship(back_populates="resource_sections")
    parent: Optional["Section"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={
            "remote_side": "[Section.id]"  # Quote wrapped to handle forward references
        },
    )

    # Only part I'm not too sure about
    children: Optional[List["Section"]] = Relationship(
        back_populates="parent",
        cascade_delete=True,
        sa_relationship_kwargs={
            "single_parent": True,  # This ensures a child can only have one parent
        },
    )
    section_chunks: Optional[List["Chunk"]] = Relationship(
        back_populates="section_", cascade_delete=True
    )


class Chunk(SQLModel, table=True):
    __tablename__ = "chunks"
    __table_args__ = (
        Index(
            "chunk_embedding_idx",  # index name
            "embedding",  # column name
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    resource_id: int = Field(foreign_key="resources.id", index=True, ondelete="CASCADE")
    section_id: Optional[int] = Field(
        foreign_key="sections.id", index=True, ondelete="CASCADE", default=None
    )
    content: str
    page: Optional[int] = Field(default=None)  # Maybe add index in future
    content_type: Optional[str] = Field(
        max_length=30
    )  # exercise, text, image, etc. (to define later)  - maybe add index in future

    """
    XXX: FILL IN THE EMBEDDING LENGTH FOR YOUR EMBEDDINGS
    - Default is set to 1024 (for bge-large vectors)
    - Replace with 1536 for text-embedding-3-small if using OpenAI's embedder
    """
    embedding: Any = Field(sa_column=Column(Vector(1024)))

    top_level_section_index: Optional[str] = Field(max_length=10, default=None)
    top_level_section_title: Optional[str] = Field(max_length=100, default=None)
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),  # type: ignore
        sa_column_kwargs={"server_default": sa.func.now()},
        nullable=False,
    )

    resource_: Optional["Resource"] = Relationship(back_populates="resource_chunks")
    section_: Optional["Section"] = Relationship(back_populates="section_chunks")
