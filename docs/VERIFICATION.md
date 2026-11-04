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
from apps.api.app.api.v1.interviews.routes import InterviewInput, InterviewUpdate, create_interview, list_interviews, update_interview, delete_interview
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
from apps.api.app.api.v1.workspace.routes import (
    WorkspaceItemCreate, WorkspaceItemUpdate, list_items, create_item, update_item, delete_item, search_workspace,
)


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
    owner.is_verified = True
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



def test_gmail_authorization_does_not_persist_state_when_provider_config_is_invalid(db, users, monkeypatch):
    owner, _ = users
    owner.is_verified = True
    db.flush()
    monkeypatch.setattr(
        gmail_client,
        "_flow",
        lambda state: (_ for _ in ()).throw(RuntimeError("OAuth configuration unavailable")),
    )

    with pytest.raises(RuntimeError):
        gmail_client.create_authorization(db, owner.id)

    assert db.scalars(select(OAuthState).where(OAuthState.user_id == owner.id)).all() == []


def test_career_workspace_items_are_private_and_mutations_are_owner_scoped(db, users):
    owner, other = users
    own_task = CareerWorkspaceItem(
        user_id=owner.id, item_type="task", title="Follow up with recruiter",
        description="Send a follow-up after the interview", status="open", priority="high",
    )
    private_note = CareerWorkspaceItem(
        user_id=other.id, item_type="note", title="Private career note",
        description="Other user's confidential notes", status="open",
    )
    db.add_all([own_task, private_note])
    db.flush()

    records = list_items(item_type=None, status=None, user=owner, db=db)
    assert [item["title"] for item in records] == ["Follow up with recruiter"]

    with pytest.raises(HTTPException) as error:
        update_item(private_note.id, WorkspaceItemUpdate(title="Tampered"), owner, db)
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        delete_item(private_note.id, owner, db)
    assert error.value.status_code == 404
    assert private_note.title == "Private career note"

    updated = update_item(own_task.id, WorkspaceItemUpdate(status="in_progress"), owner, db)
    assert updated["status"] == "in_progress"
    assert private_note.status == "open"


def test_career_workspace_validates_item_lifecycle_and_persists_metadata(db, users):
    owner, _ = users
    created = create_item(
        WorkspaceItemCreate(
            item_type="project", title="Build a portfolio pipeline",
            description="Demonstrate ingestion, validation and analytics",
            status="in_progress", priority="high",
            metadata={"repository": "https://github.com/example/project"},
        ),
        owner, db,
    )
    assert created["item_type"] == "project"
    assert created["metadata"]["repository"].startswith("https://")
    with pytest.raises(HTTPException) as error:
        update_item(created["id"], WorkspaceItemUpdate(status="cancelled"), owner, db)
    assert error.value.status_code == 422
    deleted = delete_item(created["id"], owner, db)
    assert deleted is None
    assert list_items(item_type="project", status=None, user=owner, db=db) == []


def test_interview_update_and_delete_require_record_ownership(db, users):
    owner, other = users
    owned = Interview(user_id=owner.id, interview_type="technical", notes="Prepare SQL")
    foreign = Interview(user_id=other.id, interview_type="screening", notes="Private")
    db.add_all([owned, foreign])
    db.flush()

    updated = update_interview(owned.id, InterviewUpdate(notes="Prepare SQL and Python"), owner, db)
    assert updated["notes"] == "Prepare SQL and Python"
    with pytest.raises(HTTPException) as error:
        update_interview(foreign.id, InterviewUpdate(notes="Tampered"), owner, db)
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        delete_interview(foreign.id, owner, db)
    assert error.value.status_code == 404
    assert foreign.notes == "Private"
    assert delete_interview(owned.id, owner, db) is None


def test_global_workspace_search_only_returns_the_signed_in_users_records(db, users):
    owner, other = users
    db.add_all([
        CandidateOpportunity(user_id=owner.id, title="Data Engineer", company="Owner Labs"),
        CandidateOpportunity(user_id=other.id, title="Data Engineer", company="Private Labs"),
        Application(user_id=owner.id, role_title="Analytics Engineer", company_name="Owner Labs"),
        Application(user_id=other.id, role_title="Analytics Engineer", company_name="Private Labs"),
        CareerWorkspaceItem(user_id=owner.id, item_type="note", title="Interview preparation"),
        CareerWorkspaceItem(user_id=other.id, item_type="note", title="Interview private notes"),
    ])
    db.flush()

    results = search_workspace("Engineer", owner, db)
    assert len(results) == 2
    assert {item["subtitle"] for item in results} == {"Owner Labs"}
    assert all(item["kind"] in {"OPPORTUNITY", "APPLICATION"} for item in results)


def test_global_workspace_search_rejects_whitespace_only_queries(db, users):
    owner, _ = users
    with pytest.raises(HTTPException) as error:
        search_workspace("   ", owner, db)
    assert error.value.status_code == 422
    assert error.value.detail == "Search query must contain at least two non-whitespace characters"



## Phase 4: release audit follow-up

**Branch:** `phase-4-career-operations-workspace`  
**PR:** #9

### Source-level hardening added during release review

- Global workspace search now trims the query and rejects inputs containing fewer than two non-whitespace characters. This prevents whitespace-only input from degenerating into a broad wildcard query.
- Workspace item updates now trim titles before persistence and continue rejecting blank titles.
- Added regression coverage for whitespace-only search, title normalization and workspace create/update/delete audit records.

### Latest observed CI limitation

The latest commit-associated runs returned failed jobs with no recorded step summaries. The corresponding job-log download endpoints also returned no stored log artifacts. Consequently, no application command has been observed executing in those runs. Treat this as an unresolved Actions execution/runner or workflow-initialization issue, not as a pass or a confirmed application-code failure. Recheck repository Actions availability/permissions and obtain a run with recorded steps before using CI as release evidence.

### Remaining release gates

- The repository currently has no `pnpm-lock.yaml`; frontend installs therefore remain non-frozen in CI and the web Dockerfile. Generate and commit a lockfile from pnpm 9.15.0 in a network-enabled checkout before switching installs to frozen mode.
- Execute the targeted workspace security tests and full backend suite against this exact branch head.
- Execute Ruff, mypy, clean-database Alembic upgrade and migration drift check.
- Execute frontend TypeScript check and production build.
- Execute Compose validation and build all four service images.
- Run authenticated browser/API smoke tests, desktop/mobile review, accessibility and reduced-motion checks.
- Do not merge or deploy until the above results are recorded. No result is inferred from the presence of workflow steps or test files.


### Latest Phase 4 Actions attempts

For PR head `03e7603c243ce98fd8e63d0e064c552bd2c508e2`:

- [CI run 41802499629](https://github.com/Victor-Kipruto-Rop/jobseaker/actions/runs/41802499629): Python, Web and Docker jobs were marked failed; GitHub returned `steps: null` for all three jobs.
- [Secret scan run 41802499617](https://github.com/Victor-Kipruto-Rop/jobseaker/actions/runs/41802499617): Gitleaks job was marked failed with `steps: null`.
- The connector could not retrieve job logs; the log download endpoint returned a missing-artifact response.

No lint, type check, migration, test, dependency audit, image build or Gitleaks command result is available from these runs. This is not a source-code pass/fail signal. The release gate remains open.


## Company identity and branding import

Added source-derived company metadata to the Greenhouse/Lever opportunity import path:

- Greenhouse board names are read from the public Job Board API; Lever board pages are inspected for published site identity.
- Public board HTML metadata is parsed for company description, canonical company URL, Open Graph/Twitter image and favicon.
- Only HTTPS company asset and website URLs are persisted for dashboard rendering.
- Company metadata is stored with each imported opportunity by migration `20261104_0009`.
- Opportunity cards and linked application records render imported company imagery; the discovery result displays the resolved company profile and asset provenance.
- Re-running discovery can backfill missing company metadata on existing imported roles without overwriting non-empty company fields.
- Added mocked connector tests for official board name, metadata extraction and missing-logo fallback.

**Still unverified:** the connector tests, Alembic migration, live Greenhouse/Lever import, frontend lint/build, and browser rendering have not been executed. The feature must not be treated as release-verified until those checks pass against the current branch head.


### Final company-branding implementation notes

The company metadata contract also includes a validated public theme color and an HTML image-element logo fallback when Open Graph/Twitter images are absent. Company domain and description are returned to the opportunity and application views. Greenhouse board API names take precedence over generic page-title metadata. Re-discovery backfills missing company fields on previously imported records. Extracted company URLs are HTTPS-only and bounded to their database column sizes.

Current PR head at this documentation update: `8ff103fcc5f55310dbb0682b070e18ba941931fa`. No commit-associated workflow runs were returned for this exact head. The latest observed earlier runs (`41803320382` CI and `41803320060` Secret scan) failed with null step summaries and no retrievable logs. No test/build/migration/browser result is available for this implementation.


Final company-enrichment hardening commit: `c00154fb6c6d52d82cc54f7fef6d42d4823d8d40`. The commit-associated workflow lookup returned no runs for this exact head. No tests or builds have been executed by this environment.


## Final review follow-up (2026-11-04)

Source review found and fixed two issues before handoff:

- Application updates now re-load the linked opportunity under the current user's ownership boundary before serializing the response, so employer logo, favicon, domain, description and brand color remain present after editing notes or status.
- Removed an unused Python import and corrected literal escaped-newline characters in the opportunity page, including preserving the intended newline-delimited keyword regex.

The latest source commits include:
- `0b63e35d270ad9ab91b39553cb3761afad547498` — preserve company branding after application updates.
- `836c4a7736b0f1d74f26eaa23ef15fb6197e39c5` — normalize escaped newlines in the opportunities page.
- `3698bf952fabfd1e24c88773767f39e6fbfc4bdb` — restore the escaped newline keyword delimiter.
- `510b6e948dbd9d805faf4ac73c9a2cdc23cfce6f` — remove unused connector import.

Actions associated with commit `0b63e35d270ad9ab91b39553cb3761afad547498` returned CI run [41803989173](https://github.com/Victor-Kipruto-Rop/jobseaker/actions/runs/41803989173) and Secret scan run [41803989168](https://github.com/Victor-Kipruto-Rop/jobseaker/actions/runs/41803989168). The CI jobs (Python, Web and Docker) and Gitleaks job are marked failed, but the GitHub integration returned `steps: null` and no job-log URLs for all of them. These results do not reveal whether setup, source checks or the runner failed. No subsequent workflow run was returned for commit `510b6e948dbd9d805faf4ac73c9a2cdc23cfce6f`.

**Release decision: NOT VERIFIED.** Do not merge or deploy based on source review alone. Execute the full CI workflow and the local authenticated discovery/application flow, including migration `20261104_0009`, against the current branch head. Validate actual Greenhouse and Lever boards with and without published brand assets. Company details are intentionally limited to public metadata exposed by the two supported ATS sources; broad web-wide company enrichment and other ATS providers are not implemented.


Final provenance refinement: resolved Greenhouse employer names now retain the public board page as their source even when the board does not publish any logo, favicon, description or theme color. Latest source commit: `a448d3e5477529217528e3f9b0e04065af93a690`. No Actions run was returned for this commit. Release verification remains pending.


## Employer identity and lifecycle follow-up (2026-11-04)

The implementation now normalizes employer data into reusable user-scoped Company records and adds:
- Migration `20261104_0010`: company profile fields, opportunity relationship and a data backfill for existing imported roles.
- Migration `20261104_0011`: vacancy availability and last-seen timestamps.
- Migration `20261104_0012`: original job-description and employer-profile snapshots on applications.
- Greenhouse/Lever metadata extraction for public employer logos, favicons, websites, domains, descriptions, social links, industry, headquarters and theme color where published.
- Saved-search worker refresh, duplicate protection, removed/reappearing vacancy handling and notifications for newly imported roles.
- Best-effort company enrichment so a missing employer page does not prevent valid vacancy ingestion.
- Additional tests for metadata extraction, skill/work-mode parsing, timestamps, and employer-profile fetch failures.

**Still not runtime-verified.** This environment has updated source files through the connected GitHub repository, but it has not run the Python suite, Ruff, mypy, Alembic against a real database, frontend lint/build, Docker services, or authenticated live-board tests. CI must be inspected on the latest commit. Keep PR #9 draft and unmerged until those checks pass.


## Latest CI observation (2026-11-04)

The latest observed head commit during final review was `8e449b42dff3c0b9e28948be47941c99283ae199`. GitHub Actions created CI run `41807300362` and Secret scan run `41807299768`; all four jobs are marked failed, but GitHub returned empty step lists and no job-log artifacts. The failed jobs were retried; the rerun did not produce inspectable step logs either. This is an infrastructure/runner-level unknown, not evidence that source checks passed or that a particular code change failed.

No local test runner or checkout is connected to this session. Runtime verification remains outstanding and PR #9 remains draft and unmerged.


Latest follow-up after the previous entry: Secret scan run `41807440119` for the subsequent documentation head also reports failure with an empty step list and no downloadable job log. The CI workflow did not return a run for that exact documentation commit. No new source verification evidence is available.

## Infrastructure and career-intelligence stack follow-up (2026-11-04)

Source changes added on the Phase 4 branch:

- Local PostgreSQL image now includes pgvector; first-time database initialization enables vector and pg_trgm extensions. Migration 20261104_0013 already conditionally creates a 384-dimensional vector column and HNSW cosine index when PostgreSQL reports pgvector as available.
- Redpanda is included as the local Kafka-compatible broker. The versioned event publisher supports job, candidate activity, application lifecycle and classified-email topics.
- Candidate interaction events, application lifecycle transitions and Gmail classification summaries are sent to the event stream in background tasks after their database writes.
- MinIO is included as a local private S3-compatible object store with bucket initialization.
- Resume uploads and deletion now use a storage adapter that supports private S3-compatible storage and local filesystem fallback. Uploaded bytes remain behind authenticated, user-scoped routes.
- Optional dependency groups expose sentence-transformers, LightGBM, XGBoost, SciPy, NumPy, Pandas, PyArrow, Polars and Playwright without forcing large ML/browser packages into the default install.
- Added unit tests for private object round trips, traversal rejection, upload bounds and disabled/invalid event publishing.
- Added the versioned event envelope schema and platform infrastructure guide.

### Important limitations

- The Kafka publisher is currently a best-effort adapter, not a transactional outbox. A database commit can succeed even if event delivery subsequently fails. Production must add outbox/inbox persistence and replay-safe consumers before making the event stream authoritative.
- The event stream currently publishes candidate interactions, application lifecycle events and Gmail classifications. A complete independent consumer fleet and all downstream topic processors are not yet implemented.
- The local ML dependencies are optional. A model is not considered trained simply because LightGBM/XGBoost can be installed; labelled data, offline evaluation, model registry and drift/fairness monitoring remain required.
- Playwright is an optional browser-assistance dependency only. CAPTCHA bypass, stealth evasion, proxy rotation to defeat restrictions and unattended third-party form submission are intentionally excluded.
- Gmail is still read-only. Classified email events are signals for candidate review; they do not automatically transition applications to offer/rejection.
- The MinIO credentials in Compose are for local development only. Production must use managed private object storage and secret-managed credentials.

### Verification remains outstanding

No local checkout/runtime is connected to this session. The Compose stack, Alembic migrations, resume upload against MinIO, Kafka broker connectivity, Python tests, Ruff, mypy, frontend build, container image builds and authenticated end-to-end flows have not been executed. The latest workflow run must be inspected on the final branch head; do not infer a pass from source commits or added tests.

Run from repository root:

    python -m pytest -q tests/unit/test_platform_adapters.py
    python -m pytest -q
    ruff check .
    mypy apps packages
    alembic upgrade head
    docker compose -f infrastructure/compose/docker-compose.yml config
    docker compose -f infrastructure/compose/docker-compose.yml up --build

Then verify MinIO resume upload/list/delete, Kafka events for a recommendation interaction and application status transition, Gmail read-only sync and classification events, and a clean-database migration with pgvector enabled.