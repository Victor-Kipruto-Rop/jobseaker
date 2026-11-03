import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from packages.database.models import Base
from packages.database.models.identity import User
from packages.database.models.career import (
    Application, AIConversation, AIMessage, Company, EmailAccount, EmailMessage,
    Interview, Recruiter, ResumeDocument, CandidateProfile, CandidateOpportunity,
    GeneratedArtifact, SavedSearch, Notification, OAuthState, ApplicationEvent, CandidateSkill,
    UserAIBudget,
)
from apps.api.app.api.v1.resumes.routes import list_resumes, resume_text
from apps.api.app.api.v1.recruiters.routes import RecruiterInput, create_recruiter, list_recruiters
from apps.api.app.api.v1.interviews.routes import InterviewInput, create_interview, list_interviews
from apps.api.app.api.v1.ai.routes import (
    conversations, conversation_messages, usage, get_budget, update_budget,
    BudgetUpdate, chat, ChatRequest,
)
from apps.api.app.api.v1.integrations.gmail_routes import account, messages, disconnect
from apps.api.app.api.v1.profile.routes import get_profile, ProfileUpdate, update_profile
from apps.api.app.api.v1.saved_searches.routes import (
    list_saved_searches, delete_saved_search,
)
from apps.api.app.api.v1.notifications.routes import list_notifications, mark_read
from apps.api.app.api.v1.companies.routes import list_companies
from apps.api.app.api.v1.opportunities.routes import list_opportunities
from apps.api.app.api.v1.applications.routes import (
    list_applications, application_events, create_application, ApplicationCreate,
)
from apps.api.app.api.v1.career_tools.routes import (
    list_artifacts, get_artifact, update_artifact, ArtifactUpdate,
    tailor_cv, CVTailorRequest,
)
from apps.api.app.api.v1.automations.routes import approvals, approval_decision, ApprovalDecision
from packages.automation.approvals.service import create_approval
from packages.database.models.entities import AIUsage
from packages.integrations.gmail import client as gmail_client
from packages.automation import tasks


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


def test_profile_skills_and_saved_searches_are_owner_scoped(db, users):
    owner, other = users
    own_profile = CandidateProfile(user_id=owner.id, headline="Owner profile", summary="private owner summary")
    other_profile = CandidateProfile(user_id=other.id, headline="Other profile", summary="private other summary")
    db.add_all([own_profile, other_profile])
    db.flush()

    profile = get_profile(owner, db)
    assert profile["profile"]["headline"] == "Owner profile"
    assert profile["profile"]["summary"] != "private other summary"

    update_profile(ProfileUpdate(headline="Updated owner headline"), owner, db)
    assert own_profile.headline == "Updated owner headline"
    assert other_profile.headline == "Other profile"

    own_search = SavedSearch(user_id=owner.id, name="Owner search", query={"keyword": "python"})
    other_search = SavedSearch(user_id=other.id, name="Other search", query={"keyword": "secret"})
    db.add_all([own_search, other_search])
    db.flush()
    assert [item["name"] for item in list_saved_searches(owner, db)] == ["Owner search"]
    with pytest.raises(HTTPException) as error:
        delete_saved_search(other_search.id, owner, db)
    assert error.value.status_code == 404


def test_notifications_are_owner_scoped_for_listing_and_mutation(db, users):
    owner, other = users
    own_notice = Notification(user_id=owner.id, title="Owner notice", body="owner-only")
    other_notice = Notification(user_id=other.id, title="Other notice", body="private")
    db.add_all([own_notice, other_notice])
    db.flush()

    assert [item["title"] for item in list_notifications(owner, db)] == ["Owner notice"]
    with pytest.raises(HTTPException) as error:
        mark_read(other_notice.id, owner, db)
    assert error.value.status_code == 404
    assert other_notice.read_at is None


def test_companies_opportunities_and_applications_are_owner_scoped(db, users):
    owner, other = users
    own_company = Company(user_id=owner.id, name="Owner Ltd")
    other_company = Company(user_id=other.id, name="Other Ltd")
    own_job = CandidateOpportunity(user_id=owner.id, title="Owner Engineer", source_url="https://jobs.example/owner")
    other_job = CandidateOpportunity(user_id=other.id, title="Private Engineer", source_url="https://jobs.example/private")
    own_application = Application(user_id=owner.id, role_title="Owner application")
    other_application = Application(user_id=other.id, role_title="Private application")
    db.add_all([own_company, other_company, own_job, other_job, own_application, other_application])
    db.flush()
    db.add_all([
        ApplicationEvent(user_id=owner.id, application_id=own_application.id,
                         event_type="application.created", details={}),
        ApplicationEvent(user_id=other.id, application_id=other_application.id,
                         event_type="application.created", details={"secret": True}),
    ])
    db.flush()

    assert [item["name"] for item in list_companies(owner, db)] == ["Owner Ltd"]
    assert [item["title"] for item in list_opportunities(owner, db)] == ["Owner Engineer"]
    assert [item["role_title"] for item in list_applications(owner, db)] == ["Owner application"]
    with pytest.raises(HTTPException) as error:
        application_events(other_application.id, owner, db)
    assert error.value.status_code == 404


def test_generated_artifacts_are_owner_scoped_for_read_and_update(db, users):
    owner, other = users
    own_artifact = GeneratedArtifact(
        user_id=owner.id, artifact_type="cover_letter", title="Owner draft",
        content="owner content", status="draft",
    )
    other_artifact = GeneratedArtifact(
        user_id=other.id, artifact_type="cover_letter", title="Private draft",
        content="private content", status="draft",
    )
    db.add_all([own_artifact, other_artifact])
    db.flush()

    assert [item["title"] for item in list_artifacts(owner, db)] == ["Owner draft"]
    with pytest.raises(HTTPException) as error:
        get_artifact(other_artifact.id, owner, db)
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        update_artifact(other_artifact.id, ArtifactUpdate(content="tampered"), owner, db)
    assert error.value.status_code == 404
    assert other_artifact.content == "private content"


def test_approval_requests_are_private_to_the_requesting_user(db, users):
    owner, other = users
    own_approval = create_approval(
        db, owner.id, "application_submission",
        {"application_id": 999}, "Candidate explicitly requested review",
    )
    assert [item["id"] for item in approvals(owner, db)] == [own_approval["id"]]
    assert approvals(other, db) == []
    with pytest.raises(HTTPException) as error:
        approval_decision(
            own_approval["id"],
            ApprovalDecision(decision="rejected", note="not mine"),
            other,
            db,
        )
    assert error.value.status_code == 404


def test_gmail_oauth_state_is_owner_bound_and_single_use(db, users, monkeypatch):
    owner, other = users
    raw_state = "state-for-owner-account-123456789"
    import hashlib
    from datetime import datetime, timedelta, timezone

    state_record = OAuthState(
        user_id=owner.id,
        state_hash=hashlib.sha256(raw_state.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.add(state_record)
    db.flush()

    class FakeCredentials:
        def to_json(self):
            return '{"token": "fake-token"}'

    class FakeFlow:
        credentials = FakeCredentials()
        def fetch_token(self, code):
            assert code == "authorization-code"

    class FakeProfileRequest:
        def execute(self):
            return {"emailAddress": "owner@gmail.com"}

    class FakeUsers:
        def getProfile(self, userId):
            assert userId == "me"
            return FakeProfileRequest()

    class FakeService:
        def users(self):
            return FakeUsers()

    monkeypatch.setattr(gmail_client, "_flow", lambda state: FakeFlow())
    monkeypatch.setattr(gmail_client, "build", lambda *args, **kwargs: FakeService())
    monkeypatch.setattr(gmail_client, "_encrypt", lambda value: "encrypted-test-token")

    account = gmail_client.complete_authorization(db, raw_state, "authorization-code")
    assert account.user_id == owner.id
    assert account.user_id != other.id
    assert state_record.consumed_at is not None
    with pytest.raises(ValueError):
        gmail_client.complete_authorization(db, raw_state, "authorization-code")



def test_candidate_skills_ai_usage_and_budgets_are_owner_scoped(db, users):
    owner, other = users
    db.add_all([
        CandidateSkill(user_id=owner.id, skill_name="Python", proficiency="advanced", evidence="owner evidence"),
        CandidateSkill(user_id=other.id, skill_name="Kubernetes", proficiency="expert", evidence="private evidence"),
        AIUsage(user_id=owner.id, provider="mock", model="mock-v1", input_tokens=10, output_tokens=20),
        AIUsage(user_id=other.id, provider="openai", model="private-model", input_tokens=900, output_tokens=900),
        UserAIBudget(user_id=owner.id, monthly_token_limit=1000, hard_token_limit_enabled=True),
        UserAIBudget(user_id=other.id, monthly_token_limit=999999, hard_token_limit_enabled=True),
    ])
    db.flush()

    profile = get_profile(owner, db)
    assert [item["skill_name"] for item in profile["skills"]] == ["Python"]
    usage_snapshot = usage(owner, db)
    assert usage_snapshot["scope"] == "user"
    assert sum(item["input_tokens"] for item in usage_snapshot["items"]) == 10
    budget = get_budget(owner, db)
    assert budget["monthly_token_limit"] == 1000
    updated = update_budget(
        BudgetUpdate(monthly_token_limit=1200, hard_token_limit_enabled=True),
        owner,
        db,
    )
    assert updated["monthly_token_limit"] == 1200
    other_budget = get_budget(other, db)
    assert other_budget["monthly_token_limit"] == 999999



def test_interview_reminder_worker_keeps_notifications_with_interview_owner(db, users, monkeypatch):
    owner, other = users
    from datetime import datetime, timedelta, timezone

    scheduled = datetime.now(timezone.utc) + timedelta(hours=2)
    db.add_all([
        Interview(user_id=owner.id, interview_type="technical", scheduled_at=scheduled),
        Interview(user_id=other.id, interview_type="screening", scheduled_at=scheduled),
    ])
    db.commit()
    monkeypatch.setattr(tasks, "SessionLocal", lambda: Session(bind=db.get_bind()))

    result = tasks.create_upcoming_interview_reminders()
    assert result["reminders_created"] == 2
    notices = db.scalars(select(Notification).order_by(Notification.user_id)).all()
    assert len(notices) == 2
    assert {item.user_id for item in notices} == {owner.id, other.id}
    assert all(item.body.startswith("interview:") for item in notices)



def test_saved_search_worker_persists_each_result_to_its_search_owner(db, users, monkeypatch):
    from types import SimpleNamespace

    owner, other = users
    db.add_all([
        SavedSearch(user_id=owner.id, name="Owner board", query={"source": "greenhouse", "board": "owner-board"}),
        SavedSearch(user_id=other.id, name="Other board", query={"source": "greenhouse", "board": "other-board"}),
    ])
    db.commit()

    async def fake_discover(board, limit):
        return [{
            "title": f"Role from {board}",
            "source_name": "greenhouse",
            "source_url": f"https://jobs.example/{board}",
        }]

    monkeypatch.setattr(tasks, "get_settings", lambda: SimpleNamespace(
        global_automation_paused=False,
        job_discovery_enabled=True,
    ))
    monkeypatch.setattr(tasks, "discover_greenhouse", fake_discover)
    monkeypatch.setattr(tasks, "SessionLocal", lambda: Session(bind=db.get_bind()))

    result = tasks.run_saved_search_discovery()
    assert result["saved"] == 2

    rows = db.scalars(select(CandidateOpportunity)).all()
    by_title = {row.title: row.user_id for row in rows}
    assert by_title == {
        "Role from owner-board": owner.id,
        "Role from other-board": other.id,
    }



def test_application_cannot_link_to_another_users_opportunity(db, users):
    owner, other = users
    private_opportunity = CandidateOpportunity(
        user_id=other.id,
        title="Private opportunity",
        source_url="https://jobs.example/private-opportunity",
    )
    db.add(private_opportunity)
    db.flush()

    with pytest.raises(HTTPException) as error:
        create_application(
            ApplicationCreate(
                role_title="Data Engineer",
                opportunity_id=private_opportunity.id,
            ),
            owner,
            db,
        )
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_ai_chat_and_cv_tailoring_cannot_use_another_users_sources(db, users):
    owner, other = users
    private_conversation = AIConversation(user_id=other.id, title="Private conversation")
    private_resume = ResumeDocument(
        user_id=other.id,
        filename="private.pdf",
        content_type="application/pdf",
        storage_key="other/private.pdf",
        extracted_text="private CV evidence",
    )
    db.add_all([private_conversation, private_resume])
    db.flush()

    with pytest.raises(HTTPException) as chat_error:
        await chat(
            ChatRequest(message="Continue this private conversation", conversation_id=private_conversation.id),
            owner,
            db,
        )
    assert chat_error.value.status_code == 404

    with pytest.raises(HTTPException) as cv_error:
        await tailor_cv(
            CVTailorRequest(
                resume_id=private_resume.id,
                job_description="A sufficiently long job description for a data engineer role.",
            ),
            owner,
            db,
        )
    assert cv_error.value.status_code == 404
