"""Parses PDF documents to extract text, tables, and images, and organizes them into a structured JSON format."""

import pymupdf
import json
import statistics
import re
import os
import tempfile
import sys

# -----------------------------
# Parsing tables
# -----------------------------
def find_nested_table(page):
    outer = page.find_table()

    real_table = []

    for big in outer.table:
        x0, y0, x1, y1 = big.bbox
        inner = page.find_table(clip=(x0, y0, x1, y1))

        for t in inner.table:
            if t.bbox != big.bbox:
                real_table.append(t)

    return real_table


# def get_article_title(doc):
#     page = doc[0]
#     blocks = page.get_text("dict")["blocks"]

#     candidates = []
#     for b in blocks:
#         if b["type"] != 0:
#             continue
#         for line in b["lines"]:
#             for span in line["spans"]:
#                 text = span["text"].strip()
#                 if 5 < len(text) < 200:
#                     candidates.append((span["size"], text))
#     if not candidates:
#          return None

#     # return largest-font candidate
#     candidates.sort(reverse=True)  # largest font first
#     return candidates[0][1]

# def is_title(text: str) -> bool:
#     t = text.strip()
#     if len(t) > 140:
#         return False
#     if t.count(".") > 1:
#         return False
#     if re.match(r"^(figure|table)\s+\d+", t.lower()):
#         return False
#     return True

# ---------------------------------------------------------------------------------------
# Classifies the text into title,bullet, or paragraph before going to the json
# ---------------------------------------------------------------------------------------
def classify_block(text, avg_font_size, body_font):
    big_font = avg_font_size >= body_font * 1.20

    punctuation = sum(text.count(ch) for ch in [".", ",", ";", ":"])
    is_paragraphish = (
        len(text) > 180 or punctuation >= 3
    )

    if big_font and not is_paragraphish:
        return "title"
    elif "•" in text:
        return "bullet"
    return "paragraph"

# --------------------------------------------------------
# Separates bullet points so they are not saved as 1 text
# --------------------------------------------------------
def split_bullets(elements):
    out = []
    for e in elements:
        if e.get("type") == "bullet" and "•" in e.get("text", ""):
            parts = [p.strip(" ••\t-—–") for p in e["text"].split("•")]
            parts = [p for p in parts if p]
            for p in parts:
                out.append({
                    "text": p,
                    "avg_font_size": e.get("avg_font_size", 0),
                    "type": "bullet",
                })
        else:
            out.append(e)
    return out

# -----------------------------
# Builds JSON structure
# -----------------------------
def build_hierarchical_structure(parsed):
    elements = parsed["elements"]
    outline = []

    current_section = None
    current_subsection = None
    current_bullet_group = None

    i = 0
    n = len(elements)

    def ensure_section():
        nonlocal current_section, current_subsection, current_bullet_group
        if current_section is None:
            current_section = {"section": "Intro", "content": [], "subsections": []}
            current_subsection = None
            current_bullet_group = None

    def next_type(start_idx):
        j = start_idx + 1
        while j < n:
            if elements[j]["text"].strip():
                return elements[j]["type"]
            j += 1
        return None

    def collect_consecutive_table(start_idx):
        table_payload = []
        j = start_idx
        while j < n and elements[j]["type"] == "table":
            e = elements[j]
            table_obj = (
                e.get("table")
                or e.get("data")
                or {} 
            )

            payload = {
                "caption": table_obj.get("caption") or e.get("caption"),
                "headers": table_obj.get("headers") or e.get("headers"),
                "rows": table_obj.get("rows") or e.get("rows"),
                "raw": e  
            }
            table_payload.append(payload)
            j += 1
        return table_payload, j

    while i < n:
        e = elements[i]
        text = e["text"].strip()
        t = e["type"]
        font = e.get("avg_font_size", 0) 

        if t == "title" and font >= 16:
            if current_section:
                outline.append(current_section)

            current_section = {
                "section": text,
                "content": [],
                "subsections": []
            }
            current_subsection = None
            current_bullet_group = None
            i += 1
            continue

        if t == "title" and font < 16:
            nt = next_type(i)

            if nt == "title":
                if current_section:
                    outline.append(current_section)
                current_section = {
                    "section": text,
                    "content": [],
                    "subsections": []
                }
                current_subsection = None
                current_bullet_group = None
                i += 1
                continue

            ensure_section()

            if nt == "bullet":
                current_subsection = {
                    "title": text,
                    "paragraphs": [],
                    "bullets": [],
                    "table": []
                }
                current_section["subsections"].append(current_subsection)
                current_bullet_group = None
                i += 1
                continue

            if nt == "paragraph":
                current_section["content"].append(text)
                current_subsection = None
                current_bullet_group = None
                i += 1
                continue

        if t == "bullet":
            ensure_section()
            if current_subsection:
                current_subsection["bullets"].append(text)
            else:
                if not current_bullet_group:
                    current_bullet_group = {"bullets": []}
                    current_section["content"].append(current_bullet_group)
                current_bullet_group["bullets"].append(text)
            i += 1
            continue

        if t == "paragraph":
            ensure_section()
            current_bullet_group = None

            if current_subsection:
                current_subsection.setdefault("paragraphs", []).append(text)
            else:
                current_section["content"].append(text)
            i += 1
            continue

        if t == "table":
            ensure_section()
            current_bullet_group = None

            table_payload, next_idx = collect_consecutive_table(i)

            if current_subsection:
                if "table" not in current_subsection:
                    current_subsection["table"] = []
                current_subsection["table"].extend(table_payload)
            else:
                current_section["content"].append({"table": table_payload})

            i = next_idx
            continue

        i += 1

    if current_section:
        outline.append(current_section)

    return outline

# ---------------------------------------------------------------------------------
# Extracts the metadata from document to use for title author, date and year
# ---------------------------------------------------------------------------------
def extract_metadata(doc):
    meta = doc.metadata or {}
    title = (meta.get("title") or "").strip()
    author = (meta.get("author") or "").strip()
    date = (meta.get("creationDate") or "").strip()
    year = ""
    if date:
        m = re.search(r"D:(\d{4})(\d{2})?(\d{2})?", date)
        if m:
            parts = [m.group(1)]
            if m.group(2):
                parts.append(m.group(2))
            if m.group(3):
                parts.append(m.group(3))
            year = "-".join(parts)

    return {
        "title": title or None,
        "author": author or None,
        "date": year or None,
    }

# ----------------------------
# Extracts text from pdf file
# ----------------------------
def extract_text(fname):
    doc = pymupdf.open(fname)
    metadata = extract_metadata(doc)

    all_pages = []
    raw_elements = []

    for page in doc:
        pgdict = page.get_text("dict", sort=True)

        for block in pgdict["blocks"]:
            if block["type"] != 0:
                continue

            block_text = []
            font_sizes = []

            for line in block["lines"]:
                for span in line["spans"]:
                    s = span.get("text", "")
                    if s:
                        block_text.append(s)
                        font_sizes.append(span.get("size", 0))

            text = " ".join(block_text).strip()
            if not text or not font_sizes:
                continue

            raw_elements.append({
                "text": text,
                "avg_font_size": sum(font_sizes) / len(font_sizes)
            })

    body_font = statistics.median([e["avg_font_size"] for e in raw_elements])

    for e in raw_elements:
        e["type"] = classify_block(
            text=e["text"],
            avg_font_size=e["avg_font_size"],
            body_font=body_font
        )
        all_pages.append(e)

    elements = split_bullets(all_pages)
    hierarchy = build_hierarchical_structure({"elements": elements})

    output = {
        "file": fname,
        "title": metadata["title"],
        "author": metadata["author"],
        "date": metadata["date"],
        "hierarchy": hierarchy
    }

    out_json = fname + ".json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return output


# ---------------------------------------------------------------------------
# Extracts pdf images to be used later for image replacement options
# ---------------------------------------------------------------------------
def extract_images(fname):
    doc = pymupdf.open(fname)
    tmp_dir = tempfile.mkdtemp(prefix="doc_images_")
    smask_xrefs = set()
    for page in doc:
        for img in page.get_images(full=True):
            if img[1] > 0:
                smask_xrefs.add(img[1])

    images = []
    seen_xrefs = set()
    for xref in range(1, doc.xref_length()):
        if not doc.xref_is_stream(xref):
            continue
        obj_str = doc.xref_object(xref)
        if "/Subtype /Image" not in obj_str and "/Subtype/Image" not in obj_str:
            continue
        if xref in seen_xrefs or xref in smask_xrefs:
            continue
        seen_xrefs.add(xref)

        try:
            base_image = doc.extract_image(xref)
        except Exception:
            continue

        if base_image["width"] < 50 or base_image["height"] < 50:
            continue

        filename = f"img_{xref}.{base_image['ext']}"
        path = os.path.join(tmp_dir, filename)
        with open(path, "wb") as f:
            f.write(base_image["image"])
        images.append({
            "xref": xref,
            "width": base_image["width"],
            "height": base_image["height"],
            "bpc": base_image["bpc"],
            "colorspace": base_image["colorspace"],
            "ext": base_image["ext"],
            "path": path,
        })

    return {"tmp_dir": tmp_dir, "images": images}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    result = extract_text(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
