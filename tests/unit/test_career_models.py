from packages.database.models import Base

def test_identity_and_career_tables_are_registered():
    expected = {"users", "user_sessions", "candidate_profiles", "applications",
                "ai_conversations", "ai_messages", "candidate_opportunities", "audit_logs",
                "email_accounts", "email_messages", "oauth_states", "account_tokens",
                "generated_artifacts", "notifications", "interviews", "saved_searches"}
    assert expected.issubset(set(Base.metadata.tables))
