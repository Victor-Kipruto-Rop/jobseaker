import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from packages.database.models import Base
from packages.database.models.identity import User
from packages.database.models.career import (
    Application, AIConversation, AIMessage, Company, EmailAccount, EmailMessage,
    Interview, Recruiter, ResumeDocument,
)
from apps.api.app.api.v1.resumes.routes import list_resumes, resume_text
from apps.api.app.api.v1.recruiters.routes import RecruiterInput, create_recruiter, list_recruiters
from apps.api.app.api.v1.interviews.routes import InterviewInput, create_interview, list_interviews
from apps.api.app.api.v1.ai.routes import conversations, conversation_messages
from apps.api.app.api.v1.integrations.gmail_routes import account, messages, disconnect


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def users(db):
    owner = User(email="owner-isolation@example.com", password_hash="unused")
    other = User(email="other-isolation@example.com", password_hash="unused")
    db.add_all([owner, other])
    db.flush()
    return owner, other


def test_resume_list_and_document_access_are_owner_scoped(db, users):
    owner, other = users
    own_resume = ResumeDocument(
        user_id=owner.id, filename="own.pdf", content_type="application/pdf",
        storage_key="owner/own.pdf", extracted_text="private owner data",
    )
    other_resume = ResumeDocument(
        user_id=other.id, filename="other.pdf", content_type="application/pdf",
        storage_key="other/other.pdf", extracted_text="private other data",
    )
    db.add_all([own_resume, other_resume])
    db.flush()

    assert [item["filename"] for item in list_resumes(owner, db)] == ["own.pdf"]
    with pytest.raises(HTTPException) as error:
        resume_text(other_resume.id, owner, db)
    assert error.value.status_code == 404


def test_recruiters_and_company_relationships_are_owner_scoped(db, users):
    owner, other = users
    own_company = Company(user_id=owner.id, name="Owner Company")
    other_company = Company(user_id=other.id, name="Other Company")
    own_recruiter = Recruiter(user_id=owner.id, full_name="Owner Recruiter")
    other_recruiter = Recruiter(user_id=other.id, full_name="Other Recruiter")
    db.add_all([own_company, other_company, own_recruiter, other_recruiter])
    db.flush()

    assert [item["full_name"] for item in list_recruiters(owner, db)] == ["Owner Recruiter"]
    request = RecruiterInput(full_name="Injected Recruiter", company_id=other_company.id)
    with pytest.raises(HTTPException) as error:
        create_recruiter(request, owner, db)
    assert error.value.status_code == 404


def test_interviews_and_linked_applications_are_owner_scoped(db, users):
    owner, other = users
    own_application = Application(user_id=owner.id, role_title="Owner role")
    other_application = Application(user_id=other.id, role_title="Other role")
    own_interview = Interview(user_id=owner.id, interview_type="technical")
    other_interview = Interview(user_id=other.id, interview_type="screening")
    db.add_all([own_application, other_application, own_interview, other_interview])
    db.flush()

    assert len(list_interviews(owner, db)) == 1
    request = InterviewInput(application_id=other_application.id)
    with pytest.raises(HTTPException) as error:
        create_interview(request, owner, db)
    assert error.value.status_code == 404


def test_ai_conversations_and_messages_are_private_to_owner(db, users):
    owner, other = users
    own_conversation = AIConversation(user_id=owner.id, title="Owner chat")
    other_conversation = AIConversation(user_id=other.id, title="Private chat")
    db.add_all([own_conversation, other_conversation])
    db.flush()
    db.add(AIMessage(
        user_id=other.id, conversation_id=other_conversation.id,
        role="assistant", content="private message",
    ))
    db.flush()

    assert [item["title"] for item in conversations(owner, db)] == ["Owner chat"]
    with pytest.raises(HTTPException) as error:
        conversation_messages(other_conversation.id, owner, db)
    assert error.value.status_code == 404


def test_gmail_account_messages_and_disconnect_are_owner_scoped(db, users):
    owner, other = users
    other_account = EmailAccount(
        user_id=other.id, provider="gmail", email="other@gmail.com",
        encrypted_credentials="encrypted-test-only", scopes=["gmail.readonly"],
    )
    db.add(other_account)
    db.flush()
    db.add(EmailMessage(
        user_id=other.id, account_id=other_account.id,
        gmail_message_id="msg-1", gmail_thread_id="thread-1",
        subject="Private message",
    ))
    db.flush()

    assert account(owner, db) == {"connected": False, "read_only": True}
    assert messages(owner, db) == []
    assert disconnect(owner, db) == {"connected": False}
    assert db.scalar(select(EmailAccount).where(EmailAccount.user_id == other.id)) is not None
    assert db.scalar(select(EmailMessage).where(EmailMessage.user_id == other.id)) is not None
