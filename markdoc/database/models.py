"""
SQLAlchemy ORM models for the document crawler system.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models"""

    pass


class Task(Base):
    """Task model for crawling jobs"""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    base_url: Mapped[str] = mapped_column(String(512))  # Starting URL for crawling
    config: Mapped[str] = mapped_column(Text, default="{}")  # JSON config object
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, running, paused, completed, failed, cancelled
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )  # When task actually started running
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )  # When task completed/failed/cancelled
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    doc_urls: Mapped[list["DocURL"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Task(id={self.id}, title='{self.title}', status='{self.status}')>"


class DocURL(Base):
    """Model for storing discovered documentation URLs"""

    __tablename__ = "doc_urls"
    __table_args__ = (UniqueConstraint("task_id", "url", name="uq_task_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    url: Mapped[str] = mapped_column(String(1024))
    link_text: Mapped[str] = mapped_column(Text)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    link_detection_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, in_progress, done, error
    content_crawl_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, in_progress, done, error

    # Relationship
    task: Mapped["Task"] = relationship(back_populates="doc_urls")

    def __repr__(self):
        return f"<DocURL(id={self.id}, task_id={self.task_id}, url='{self.url}')>"


class DocContent(Base):
    """Model for storing crawled documentation content (cached by URL)"""

    __tablename__ = "doc_contents"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    markdown_content: Mapped[str] = mapped_column(Text)
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return f"<DocContent(id={self.id}, url='{self.url}')>"


__all__ = [
    "Base",
    "Task",
    "DocURL",
    "DocContent",
]
