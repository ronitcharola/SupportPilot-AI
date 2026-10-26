"""Upload validation and text extraction for knowledge-base documents."""
import io
import re
from pathlib import Path
from typing import Optional

from app.ai.text_utils import normalize_whitespace
from app.config import settings


class ExtractionError(ValueError):
    """Raised when an upload is unsupported, unreadable, or empty."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | PDF_EXTENSIONS

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
MIN_EXTRACTED_CHARS = 20


def validate_upload(filename: Optional[str], data: bytes) -> str:
    """Validates an upload and returns its normalized extension (e.g. '.pdf')."""
    if not filename:
        raise ExtractionError("A file name is required.", status_code=422)

    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ExtractionError(
            f"Unsupported file type '{extension or 'unknown'}'. "
            "Supported types: .txt, .md, .markdown, .pdf.",
            status_code=415,
        )

    if not data:
        raise ExtractionError("The uploaded file is empty.")
    if len(data) > settings.MAX_UPLOAD_BYTES:
        limit_mb = settings.MAX_UPLOAD_BYTES / (1024 * 1024)
        raise ExtractionError(
            f"The uploaded file exceeds the {limit_mb:.0f} MB limit.",
            status_code=413,
        )
    return extension


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ExtractionError("The file could not be decoded as text.")

    if _CONTROL_CHARS.search(text[:4096]):
        raise ExtractionError("The uploaded file does not look like a text document.")
    return text


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is pinned
        raise ExtractionError("PDF support is unavailable on this deployment.") from exc

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise ExtractionError("Password-protected PDFs cannot be indexed.") from exc
        pages = [page.extract_text() or "" for page in reader.pages]
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError("The PDF could not be read. It may be corrupted.") from exc

    return "\n\n".join(pages)


def extract_text(filename: Optional[str], data: bytes) -> str:
    """Validates and extracts plain text from a supported upload."""
    extension = validate_upload(filename, data)
    raw = _extract_pdf(data) if extension in PDF_EXTENSIONS else _decode_text(data)
    text = normalize_whitespace(raw)
    if len(text) < MIN_EXTRACTED_CHARS:
        raise ExtractionError(
            "No usable text could be extracted from this file."
            + (" Scanned PDFs need OCR before upload." if extension in PDF_EXTENSIONS else "")
        )
    return text


def clean_pasted_text(text: str) -> str:
    """Normalizes and validates text submitted directly through the API."""
    cleaned = normalize_whitespace(text or "")
    if len(cleaned) < MIN_EXTRACTED_CHARS:
        raise ExtractionError(
            f"Knowledge documents need at least {MIN_EXTRACTED_CHARS} characters of text."
        )
    if len(cleaned.encode("utf-8")) > settings.MAX_UPLOAD_BYTES:
        raise ExtractionError("The text exceeds the configured document size limit.", status_code=413)
    return cleaned
