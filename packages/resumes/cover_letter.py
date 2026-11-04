"""Grounded cover-letter draft assembled only from supplied candidate evidence."""
from packages.resumes.tailoring import tailor_resume

def build_cover_letter(source_text, job_description, role_title, company_name=""):
    role = (role_title or "").strip()[:250]
    company = (company_name or "").strip()[:250]
    if len(role) < 2:
        raise ValueError("A target role is required")
    proposal = tailor_resume(source_text, job_description)
    evidence = [item["text"] for item in proposal["items"][:5]]
    if not evidence:
        raise ValueError("No relevant resume evidence was found for this role")
    greeting = f"Dear Hiring Team at {company}," if company else "Dear Hiring Team,"
    paragraphs = [
        greeting,
        f"I am writing to express my interest in the {role} position.",
        "The following experience from my existing resume is most relevant to this opportunity:",
        *[f"- {item}" for item in evidence],
        "I would welcome the opportunity to discuss how this documented experience could contribute to your team.",
        "Kind regards,",
        "[Your name]",
    ]
    return {"title": f"Cover letter - {role}", "content": "\n\n".join(paragraphs),
            "evidence_sentences": evidence, "claims_invented": False,
            "requires_candidate_review": True,
            "unmatched_job_terms": proposal["unmatched_job_terms"]}
