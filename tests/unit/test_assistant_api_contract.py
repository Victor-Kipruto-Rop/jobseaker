from apps.api.app.api.v1.ai.assistant_routes import router

def test_document_ingestion_api_contract_is_registered():
    routes = {(route.path, tuple(sorted(route.methods or []))) for route in router.routes}
    assert ("/assistant/ingest-async", ("POST",)) in routes
    assert ("/assistant/ingestions", ("GET",)) in routes
    assert ("/assistant/ingestion/{job_id}", ("GET",)) in routes
    assert ("/assistant/ingestion/{job_id}", ("DELETE",)) in routes
