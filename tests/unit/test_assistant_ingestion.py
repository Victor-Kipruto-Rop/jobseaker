from packages.assistant.engine import semantic_chunks, extractive_summary
from packages.assistant.ingestion import parse_document

def test_plain_text_ingestion():
    value = parse_document("notes.txt", "text/plain", b"Career goals and Python data engineering.")
    assert "Python" in value

def test_python_ast_ingestion_extracts_symbols():
    source = b"class Pipeline:\n    def run(self, source):\n        return source\n"
    value = parse_document("pipeline.py", "text/x-python", source)
    assert "Pipeline" in value
    assert "run" in value

def test_semantic_chunker_flushes_on_headings():
    chunks = semantic_chunks("# Profile\n\nData engineer with Python.\n\n# Goals\n\nBuild reliable pipelines.")
    assert len(chunks) >= 2
    assert chunks[0].startswith("# Profile")
    assert any(chunk.startswith("# Goals") for chunk in chunks)

def test_extractive_summary_returns_useful_sentence():
    value = extractive_summary("Python is useful. Kafka supports streaming. Python Kafka pipelines are reliable.")
    assert value
    assert len(value) <= 500
