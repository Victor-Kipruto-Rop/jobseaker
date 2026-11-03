def score_job(title:str,description:str,skills:list[str])->dict:
    text=f"{title} {description}".lower()
    normalized=sorted({s.strip() for s in skills if s.strip()})
    matched=[s for s in normalized if s.lower() in text]
    missing=[s for s in normalized if s.lower() not in text]
    return {"title":title,"fit_score":round(100*len(matched)/max(len(normalized),1)),"matched_skills":matched,"skills_not_explicitly_found":missing,"method":"transparent_keyword_baseline","warning":"Baseline keyword score only. Verify requirements manually."}
