from datetime import datetime, timezone
from enum import Enum
from typing import List, NotRequired, Optional, TypedDict

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field as SQLModelField
from sqlmodel import SQLModel

from models.db import get_session


class ChatMessageAttachmentType(str, Enum):
    """Type of chat message attachment."""

    LINK = "link"
    IMAGE = "image"
    FILE = "file"


class AuthorType(str, Enum):
    """Type of message author."""

    AGENT = "agent"
    TRIGGER = "trigger"
    SKILL = "skill"
    TELEGRAM = "telegram"
    TWITTER = "twitter"
    WEB = "web"
    SYSTEM = "system"


class ChatMessageAttachment(TypedDict):
    """Chat message attachment model.

    An attachment can be a link, image, or file that is associated with a chat message.
    """

    type: ChatMessageAttachmentType = Field(
        ...,
        description="Type of the attachment (link, image, or file)",
        examples=["link"],
    )
    url: str = Field(
        ...,
        description="URL of the attachment",
        examples=["https://example.com/image.jpg"],
    )


class ChatMessageSkillCall(TypedDict):
    """TypedDict for skill call details."""

    name: str
    parameters: dict
    success: bool
    response: NotRequired[
        str
    ]  # Optional response from the skill call, trimmed to 100 characters
    error_message: NotRequired[str]  # Optional error message from the skill call


class ChatMessageRequest(BaseModel):
    """Request model for chat messages.

    This model represents the request body for creating a new chat message.
    It contains the necessary fields to identify the chat context, user,
    and message content, along with optional attachments.
    """

    chat_id: str = Field(
        ...,
        description="Unique identifier for the chat thread",
        examples=["chat-123"],
        min_length=1,
    )
    user_id: str = Field(
        ...,
        description="Unique identifier of the user sending the message",
        examples=["user-456"],
        min_length=1,
    )
    message: str = Field(
        ...,
        description="Content of the message",
        examples=["Hello, how can you help me today?"],
        min_length=1,
    )
    attachments: Optional[List[ChatMessageAttachment]] = Field(
        None,
        description="Optional list of attachments (links, images, or files)",
        examples=[[{"type": "link", "url": "https://example.com"}]],
    )

    class Config:
        """Pydantic model configuration."""

        use_enum_values = True
        json_schema_extra = {
            "example": {
                "chat_id": "chat-123",
                "user_id": "user-456",
                "message": "Hello, how can you help me today?",
                "attachments": [
                    {
                        "type": "link",
                        "url": "https://example.com",
                    }
                ],
            }
        }


class ChatMessage(SQLModel, table=True):
    """Chat message model."""

    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_chat_id", "chat_id"),)

    id: str = SQLModelField(
        primary_key=True,
        description="Unique identifier for the chat message",
    )
    agent_id: str = SQLModelField(
        description="ID of the agent this message belongs to",
    )
    chat_id: str = SQLModelField(
        description="ID of the chat this message belongs to",
    )
    author_id: str = SQLModelField(
        description="ID of the message author",
    )
    author_type: AuthorType = SQLModelField(
        sa_column=Column(String, nullable=False),
        description="Type of the message author",
    )
    message: str = SQLModelField(
        description="Content of the message",
    )
    attachments: Optional[List[ChatMessageAttachment]] = SQLModelField(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="List of attachments in the message",
    )
    skill_calls: Optional[List[ChatMessageSkillCall]] = SQLModelField(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Skill call details",
    )
    input_tokens: int = SQLModelField(
        default=0,
        description="Number of tokens in the input message",
    )
    output_tokens: int = SQLModelField(
        default=0,
        description="Number of tokens in the output message",
    )
    time_cost: float = SQLModelField(
        default=0.0,
        description="Time cost for the message in seconds",
    )
    cold_start_cost: float = SQLModelField(
        default=0.0,
        description="Cost for the cold start of the message in seconds",
    )
    created_at: datetime = SQLModelField(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now()},
        nullable=False,
        description="Timestamp when this message was created",
    )

    class Config:
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat(timespec="milliseconds")}

    def __str__(self):
        resp = ""
        if self.skill_calls:
            for call in self.skill_calls:
                resp += f"{call['name']} {call['parameters']}: {call['response'] if call['success'] else call['error_message']}\n"
            resp += "\n"
        resp += self.message
        return resp

    async def save(self):
        async with get_session() as db:
            db.add(self)
            await db.commit()
            await db.refresh(self)
