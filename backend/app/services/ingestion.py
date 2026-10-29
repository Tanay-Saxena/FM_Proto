"""PDF / image menu ingestion: validate → extract text (PDF text layer or Tesseract OCR) → parse →
flag → owner review → approve into a DRAFT menu. A failed job never touches the live menu.

The parser is heuristic and deliberately conservative: it never invents ingredients, allergens, diets
or prices. Anything uncertain is flagged for the owner.
"""
from __future__ import annotations

import hashlib
import io
import re
import shutil
import statistics
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader
from PIL import Image
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Category, IngestionCandidate, IngestionJob, Item, Menu, MenuUpload
from ..providers.storage import get_storage
from .audit import audit
from .errors import DomainError

SIGNATURES = {
    "application/pdf": lambda b: b.startswith(b"%PDF-"),
    "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    "image/webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}
EXT = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
Image.MAX_IMAGE_PIXELS = 40_000_000  # decompression-bomb guard


def sniff(data: bytes) -> str | None:
    return next((ct for ct, check in SIGNATURES.items() if check(data)), None)


def save_upload(db: Session, restaurant_id: str, filename: str, data: bytes, actor_id: str, actor: str) -> MenuUpload:
    s = get_settings()
    if not data:
        raise DomainError("empty_file", "That file is empty.", 422)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise DomainError("file_too_large", f"Files can be up to {s.max_upload_mb} MB.", 413)
    ct = sniff(data)  # content, not extension or client-declared type
    if not ct:
        raise DomainError("unsupported_file", "Upload a PDF, JPEG, PNG or WebP menu.", 415)
    if ct == "application/pdf":
        try:
            pages = len(PdfReader(io.BytesIO(data)).pages)
        except Exception:
            raise DomainError("corrupt_pdf", "That PDF couldn't be read. Try exporting it again.", 422)
        if pages > s.max_pdf_pages:
            raise DomainError("too_many_pages", f"PDFs can have up to {s.max_pdf_pages} pages.", 422)
    else:
        try:
            Image.open(io.BytesIO(data)).verify()
        except Exception:
            raise DomainError("corrupt_image", "That image couldn't be read.", 422)
    sha = hashlib.sha256(data).hexdigest()
    upload = MenuUpload(restaurant_id=restaurant_id, filename=re.sub(r"[^\w.\- ]", "_", filename)[:200] or "menu", content_type=ct, size_bytes=len(data), storage_key="", sha256=sha, uploaded_by=actor_id)
    db.add(upload)
    db.flush()
    upload.storage_key = get_storage().save(f"uploads/{restaurant_id}/{upload.id}.{EXT[ct]}", data)
    job = IngestionJob(restaurant_id=restaurant_id, upload_id=upload.id, status="queued")
    db.add(job)
    audit(db, actor, "menu.upload", restaurant_id, "menu_upload", upload.id, {"type": ct, "size": len(data)})
    db.commit()
    return upload


# ───────────── extraction ─────────────
def ocr_image(img: Image.Image) -> list[tuple[str, float]]:
    if not shutil.which("tesseract"):
        raise DomainError("ocr_unavailable", "OCR engine (Tesseract) isn't installed on the server.", 503)
    img = img.convert("L")
    if max(img.size) < 1400:
        k = 1400 / max(img.size)
        img = img.resize((int(img.width * k), int(img.height * k)))
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "in.png"
        img.save(p)
        try:
            out = subprocess.run(["tesseract", str(p), "stdout", "--psm", "6", "tsv"], capture_output=True, text=True, timeout=60, check=True).stdout
        except (subprocess.SubprocessError, OSError) as e:
            raise DomainError("ocr_failed", f"OCR failed: {type(e).__name__}", 500)
    lines: dict[tuple, list[tuple[str, float]]] = {}
    for row in out.splitlines()[1:]:
        c = row.split("\t")
        if len(c) < 12 or not c[11].strip():
            continue
        try:
            conf = float(c[10])
        except ValueError:
            continue
        if conf < 0:
            continue
        lines.setdefault((c[2], c[3], c[4]), []).append((c[11], conf))
    return [(" ".join(w for w, _ in ws), sum(cf for _, cf in ws) / len(ws) / 100) for ws in lines.values()]


def extract_lines(path: Path, content_type: str) -> tuple[list[dict], str]:
    """Returns ([{text, page, confidence}], method)."""
    out: list[dict] = []
    if content_type == "application/pdf":
        reader = PdfReader(str(path))
        method = "pdf_text"
        for pno, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if len(text) >= 30:
                out += [{"text": l.strip(), "page": pno, "confidence": 1.0} for l in text.splitlines() if l.strip()]
                continue
            # scanned page: OCR its embedded images (no poppler dependency)
            method = "ocr"
            imgs = list(page.images)
            if not imgs:
                continue
            for im in imgs:
                for t, conf in ocr_image(Image.open(io.BytesIO(im.data))):
                    out.append({"text": t, "page": pno, "confidence": conf})
        return out, method
    for t, conf in ocr_image(Image.open(path)):
        out.append({"text": t, "page": 1, "confidence": conf})
    return out, "ocr"


# ───────────── parsing ─────────────
PRICE_RE = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d{1,5}(?:[.,]\d{1,2})?)\s*(?:/-|\*)?\s*$", re.I)
MULTI_PRICE_RE = re.compile(r"(\d{2,5})\s*(?:/|\|)\s*(\d{2,5})\s*$")
LEADER_RE = re.compile(r"[.…_\-–—·]{2,}")


def _to_minor(num: str) -> int:
    return int(round(float(num.replace(",", ".")) * 100)) if re.search(r"[.,]\d{1,2}$", num) else int(num) * 100


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", LEADER_RE.sub(" ", s)).strip(" -–—|:.,*")


def parse_menu(lines: list[dict]) -> list[dict]:
    cands, category = [], "Uncategorised"
    last: dict | None = None
    for ln in lines:
        raw = ln["text"].strip()
        if not raw or len(raw) < 2:
            continue
        text = LEADER_RE.sub(" ", raw)
        multi = MULTI_PRICE_RE.search(text)
        m = None if multi else PRICE_RE.search(text)
        # a trailing number only counts as a price if there is a name before it
        if multi and len(text[: multi.start()].strip()) >= 2:
            name = _clean(text[: multi.start()])
            cand = {"category": category, "name": name, "description": "", "price_minor": _to_minor(multi.group(1)), "flags": ["price_ambiguous"], "alt_prices": [_to_minor(multi.group(2))], "page": ln["page"], "raw": raw, "confidence": ln["confidence"]}
            cands.append(cand)
            last = cand
            continue
        if m and len(_clean(text[: m.start()])) >= 2 and re.search(r"[A-Za-z]", text[: m.start()]):
            cand = {"category": category, "name": _clean(text[: m.start()]), "description": "", "price_minor": _to_minor(m.group(1)), "flags": [], "page": ln["page"], "raw": raw, "confidence": ln["confidence"]}
            cands.append(cand)
            last = cand
            continue
        cleaned = _clean(text)
        words = cleaned.split()
        is_heading = (cleaned.isupper() or cleaned.istitle() or cleaned.endswith(":")) and 1 <= len(words) <= 4 and not any(ch.isdigit() for ch in cleaned)
        if is_heading and (last is None or last.get("description") or True):
            category = cleaned.rstrip(":").title()
            last = None
        elif last is not None and len(cleaned) > 3:
            last["description"] = (last["description"] + " " + cleaned).strip()[:600]
            last["confidence"] = min(last["confidence"], ln["confidence"])
        elif len(words) <= 6 and re.search(r"[A-Za-z]{3}", cleaned):
            # name without price
            cand = {"category": category, "name": cleaned, "description": "", "price_minor": None, "flags": ["price_missing"], "page": ln["page"], "raw": raw, "confidence": ln["confidence"]}
            cands.append(cand)
            last = cand
    return cands


def flag_candidates(cands: list[dict]) -> list[dict]:
    seen: dict[str, int] = {}
    prices = [c["price_minor"] for c in cands if c["price_minor"]]
    med = statistics.median(prices) if prices else 0
    for c in cands:
        key = re.sub(r"\W+", "", c["name"].lower())
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1 and "duplicate" not in c["flags"]:
            c["flags"].append("duplicate")
        if c["confidence"] < 0.7 and "low_confidence" not in c["flags"]:
            c["flags"].append("low_confidence")
        if c["price_minor"] is None and "price_missing" not in c["flags"]:
            c["flags"].append("price_missing")
        if c["price_minor"] and med and (c["price_minor"] > med * 8 or c["price_minor"] < med / 12):
            c["flags"].append("price_outlier")
    return cands


def process_job(db: Session, job_id: str) -> IngestionJob:
    job = db.get(IngestionJob, job_id)
    if not job:
        raise DomainError("not_found", "Import not found.", 404)
    job.status, job.attempts, job.error = "processing", job.attempts + 1, None
    db.commit()
    try:
        upload = job.upload
        lines, method = extract_lines(get_storage().path(upload.storage_key), upload.content_type)
        if not lines:
            raise DomainError("no_text", "No readable text was found. Try a sharper photo or a text-based PDF.", 422)
        cands = flag_candidates(parse_menu(lines))
        if not cands:
            raise DomainError("no_items", "Text was found but no dishes with prices could be detected.", 422)
        db.query(IngestionCandidate).filter(IngestionCandidate.job_id == job.id).delete()
        for i, c in enumerate(cands):
            db.add(IngestionCandidate(job_id=job.id, category=c["category"], name=c["name"][:160], description=c["description"], price_minor=c["price_minor"], confidence=round(c["confidence"], 3), flags=c["flags"], source={"page": c["page"], "raw": c["raw"], "alt_prices": c.get("alt_prices", [])}, sort=i))
        job.status, job.method = "review", method
    except DomainError as e:
        job.status, job.error = "failed", e.message
    except Exception as e:  # never leak internals; never touch the live menu
        job.status, job.error = "failed", f"Processing failed ({type(e).__name__}). You can retry."
    job.finished_at = datetime.now(timezone.utc)
    db.commit()
    return job


def approve_job(db: Session, job: IngestionJob, actor: str) -> Menu:
    """Create a DRAFT menu = clone of the live menu + upserted approved candidates. Live menu untouched."""
    from .menu_admin import clone_menu, published_or_none  # local import to avoid cycle

    if job.status not in ("review", "approved"):
        raise DomainError("not_reviewable", "This import isn't ready to approve.", 409)
    approved = db.query(IngestionCandidate).filter(IngestionCandidate.job_id == job.id, IngestionCandidate.review_state == "approved").order_by(IngestionCandidate.sort).all()
    if not approved:
        raise DomainError("nothing_approved", "Approve at least one dish first.", 422)
    blocking = [c for c in approved if c.price_minor is None]
    if blocking:
        raise DomainError("price_missing", f"{len(blocking)} approved dish(es) have no price. Add prices or reject them.", 422)
    base = published_or_none(db, job.restaurant_id)
    draft = clone_menu(db, base, job.restaurant_id, name=f"Import: {job.upload.filename}"[:120]) if base else Menu(restaurant_id=job.restaurant_id, name="Imported menu", version=1, status="draft")
    if not base:
        db.add(draft)
        db.flush()
    cats = {c.name.lower(): c for c in draft.categories}
    for cand in approved:
        cat = cats.get((cand.category or "Uncategorised").lower())
        if not cat:
            cat = Category(menu_id=draft.id, name=cand.category or "Uncategorised", sort=len(cats))
            db.add(cat)
            db.flush()
            cats[cat.name.lower()] = cat
        existing = next((i for i in cat.items if i.name.lower() == cand.name.lower() and not i.archived), None)
        if existing:
            existing.price_minor = cand.price_minor
            if cand.description:
                existing.description = cand.description
        else:
            db.add(Item(menu_id=draft.id, category_id=cat.id, name=cand.name, description=cand.description, price_minor=cand.price_minor, sort=len(cat.items), attributes=[], allergens={"verified": False, "list": []}, ingredients={"verified": False, "list": []}, image={"kind": "illustration", "hue": (hash(cand.name) % 360), "provenance": "Placeholder — add a photo"}))
    job.status, job.draft_menu_id = "approved", draft.id
    audit(db, actor, "menu.import_approved", job.restaurant_id, "ingestion_job", job.id, {"draft_menu": draft.id, "items": len(approved)})
    db.commit()
    return draft
