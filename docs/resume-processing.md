# Resume processing and storage

## Accepted input

The local resume endpoint accepts PDF and DOCX files only. The uploaded byte stream is capped at 10 MiB before parsing. The API does not trust the browser-supplied MIME type; it checks the extension and validates the document structure.

## Parser limits

- PDF files must have a PDF signature, must not be encrypted, and may contain at most 100 pages.
- DOCX files must be valid ZIP packages containing the expected Office package entries.
- DOCX archives are limited to 1,000 entries, 50 MiB expanded size, and a maximum 100:1 per-entry compression ratio.
- Extracted text is capped at 500,000 characters.
- Parsing errors are returned as controlled client errors rather than exposing parser internals.

These are resource-abuse controls, not malware detection. Do not upload untrusted documents to a production environment until private object storage, malware scanning, retention controls, and operational monitoring are configured.

## Storage behavior

Local development stores files under the configured STORAGE_PATH, partitioned by user ID. The generated storage filename is random and does not use the uploaded filename. Writes use a temporary file followed by an atomic rename. If the database write fails, the temporary and final files are removed.

Only the owning account can list, read, or delete its resume records. Deletion removes the database record and then removes the stored file. Production uploads deliberately return HTTP 503 until a private object-storage implementation is available.

## Verification

Run `python -m pytest tests/unit/test_resume_parser_safety.py -q`. The tests cover valid DOCX extraction, unsupported and empty uploads, invalid PDF signatures, excessive PDF page counts, DOCX compression abuse, and incomplete DOCX packages.
