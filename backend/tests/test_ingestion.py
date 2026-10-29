"""Scenario B — PDF / image menu ingestion, review, approval, and failure safety."""
import io
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas

from .conftest import login, menu_items

API = "/api/v1"
MENU_LINES = ["STARTERS", "Crispy Corn          Rs 180", "Golden fried sweet corn with pepper", "Paneer Tikka        320", "MAINS", "Veg Biryani   250/320", "Dal Fry   Rs. 210", "Paneer Tikka        340"]


def pdf_bytes(lines=MENU_LINES):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 780
    for l in lines:
        c.drawString(60, y, l)
        y -= 22
    c.save()
    return buf.getvalue()


def image_bytes(lines=MENU_LINES, fmt="PNG"):
    font = None
    for path in ("/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(path, 40)
            break
        except OSError:
            continue
    if font is None:
        pytest.skip("no TrueType font available to render the OCR fixture")
    img = Image.new("RGB", (1400, 120 + 80 * len(lines)), "white")
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        d.text((60, 60 + 80 * i), l, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


def upload(owner, rid, name, data, ctype="application/octet-stream"):
    return owner.post(f"{API}/restaurants/{rid}/menu-uploads", files={"file": (name, data, ctype)})


def test_pdf_text_extract_review_approve_publish(client, owner, rid):
    live_before = menu_items(client)["Paneer Tikka"]["price_minor"]
    r = upload(owner, rid, "menu.pdf", pdf_bytes())
    assert r.status_code == 201, r.text
    job = r.json()
    cands = owner.get(f"{API}/restaurants/{rid}/ingestion-jobs/{job['id']}/candidates").json()
    assert cands["job"]["status"] == "review" and cands["job"]["method"] == "pdf_text"
    by = {c["name"]: c for c in cands["candidates"]}
    assert by["Crispy Corn"]["price_minor"] == 18000 and by["Crispy Corn"]["category"] == "Starters"
    assert "Golden fried" in by["Crispy Corn"]["description"]
    assert "price_ambiguous" in by["Veg Biryani"]["flags"]
    dupes = [c for c in cands["candidates"] if c["name"] == "Paneer Tikka"]
    assert any("duplicate" in c["flags"] for c in dupes)
    # nothing live changes before approval/publish
    assert menu_items(client)["Paneer Tikka"]["price_minor"] == live_before
    assert "Crispy Corn" not in menu_items(client)
    # owner corrects + approves
    vb = by["Veg Biryani"]
    owner.patch(f"{API}/restaurants/{rid}/ingestion-candidates/{vb['id']}", json={"price_minor": 25000})
    owner.post(f"{API}/restaurants/{rid}/ingestion-jobs/{job['id']}/bulk", json={"review_state": "approved", "ids": [by["Crispy Corn"]["id"], vb["id"], dupes[-1]["id"]]})
    d = owner.post(f"{API}/restaurants/{rid}/ingestion-jobs/{job['id']}/approve").json()
    assert "Crispy Corn" not in menu_items(client)  # still a draft
    pub = owner.post(f"{API}/restaurants/{rid}/menus/{d['draft_menu_id']}/publish")
    assert pub.status_code == 200
    live = menu_items(client)
    assert live["Crispy Corn"]["price_minor"] == 18000 and live["Veg Biryani"]["price_minor"] == 25000
    assert live["Paneer Tikka"]["price_minor"] == 34000
    # imported dishes carry no invented diet/allergen claims
    assert live["Crispy Corn"]["allergens"]["verified"] is False and live["Crispy Corn"]["attributes"] == []
    # restore for other tests
    menus = owner.get(f"{API}/restaurants/{rid}/menus").json()
    old = next(m for m in menus if m["status"] == "archived")
    c2 = owner.post(f"{API}/restaurants/{rid}/menus/{old['id']}/clone").json()
    owner.post(f"{API}/restaurants/{rid}/menus/{c2['id']}/publish")


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract not installed")
def test_scanned_image_ocr(client, owner, rid):
    r = upload(owner, rid, "scan.png", image_bytes())
    assert r.status_code == 201
    cands = owner.get(f"{API}/restaurants/{rid}/ingestion-jobs/{r.json()['id']}/candidates").json()
    assert cands["job"]["status"] == "review" and cands["job"]["method"] == "ocr", cands["job"]
    names = {c["name"].lower(): c for c in cands["candidates"]}
    assert any("corn" in n for n in names)
    corn = next(c for n, c in names.items() if "corn" in n)
    assert corn["price_minor"] == 18000 and 0 < corn["confidence"] <= 1


def test_signature_not_extension(client, owner, rid):
    assert upload(owner, rid, "evil.pdf", b"MZ\x90\x00 not a pdf at all").status_code == 415
    assert upload(owner, rid, "x.png", b"").status_code == 422
    # a real PNG named .pdf is accepted as what it really is, never as a PDF
    ok = upload(owner, rid, "actually-png.pdf", image_bytes(["Tea  Rs 50"]))
    assert ok.status_code == 201 and ok.json()["content_type"] == "image/png"
    assert upload(owner, rid, "broken.pdf", b"%PDF-1.4\nnot really").status_code == 422


def test_oversized_upload_rejected(client, owner, rid, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    assert upload(owner, rid, "big.pdf", b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)).status_code == 413


def test_failed_ingestion_never_touches_live_menu(client, owner, rid):
    before = menu_items(client)
    blank = io.BytesIO()
    c = canvas.Canvas(blank); c.drawString(50, 800, "Hello"); c.save()  # too little text, no images
    r = upload(owner, rid, "blank.pdf", blank.getvalue())
    assert r.status_code == 201
    job = owner.get(f"{API}/restaurants/{rid}/ingestion-jobs").json()[0]
    assert job["status"] == "failed" and job["error"]
    assert owner.post(f"{API}/restaurants/{rid}/ingestion-jobs/{job['id']}/process").json()["attempts"] == 2  # retry works
    assert owner.post(f"{API}/restaurants/{rid}/ingestion-jobs/{job['id']}/approve").status_code == 409
    assert menu_items(client) == before


def test_uploads_are_tenant_scoped(client, owner, rid):
    job = upload(owner, rid, "m.pdf", pdf_bytes()).json()
    other = login(client, "owner@kettle.demo")
    kc = other.get(f"{API}/auth/me").json()["memberships"][0]["restaurant_id"]
    assert other.get(f"{API}/restaurants/{kc}/ingestion-jobs/{job['id']}/candidates").status_code == 404
    assert other.post(f"{API}/restaurants/{rid}/menu-uploads", files={"file": ("m.pdf", pdf_bytes())}).status_code == 404
