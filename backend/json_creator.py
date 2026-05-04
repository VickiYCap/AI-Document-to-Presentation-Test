# Fills the JSON schema for each slide using the mapping functions, 
# then checks for blanks and fills them in
import pymupdf
import fitz
import json
import statistics
import re
import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, APIRouter, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from typing import Optional, Tuple, Dict, Any, List, Optional, TypedDict
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from langchain_core.messages import SystemMessage, HumanMessage
from backend.llm_api.llm_init import LLMService, LLMConfig
import logging
from logging.handlers import WatchedFileHandler

from .pptx_parser import apply_json_to_pptx, build_presentation_mapping
from .prompts import CREATE_FILLER, CHECK_BLANKS, FILL_TABLE
from .document_parser import extract_text


#=================================
# LOGGING STUFF
#=================================
LOG_DIR = os.getenv('LOG_DIR', os.path.join(os.path.dirname(__file__), '..', 'logs'))
LOG_FILE = os.path.join(LOG_DIR, "policy_graph.log")
pg_logger = logging.getLogger('policy_graph_logger')
pg_logger.setLevel(logging.INFO)
pg_logger.propagate = False

if not any(isinstance(h, WatchedFileHandler) for h in pg_logger.handlers):
    os.makedirs(LOG_DIR, exist_ok=True)
    file_handler = WatchedFileHandler(LOG_FILE, mode="a")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    pg_logger.addHandler(file_handler)

pg_logger.info("LOGGING INITIATED for Policy Graph.")

#=================================
# INVOKE STRUCTURE
#=================================

class TableSpec(BaseModel):
    rows: List[List[str]] 
    class Config:
        extra = "forbid" 

class SlideBodyItem(BaseModel):
    text: str
    bulleted: bool

class Slide(BaseModel):
    title: str
    subtitle: List[str]
    body: List[List[SlideBodyItem]]
    table: List[TableSpec] = Field(default_factory=list)
    images: List[str]

class Filler(BaseModel):
    slides: List[Slide]

class SlideCount(TypedDict):
    slide_index: int                      
    titles: int                          
    subtitles: int                      
    body_rows: int                     
    body_items: int                     

#=================================
# COUNTING ELEMENTS FOR LLM TO BE MORE ACCURATE
#=================================
def count_schema_elements(mapping: Dict[str, Any]) -> List[SlideCount]:
    def _slide_key_to_index(k: str) -> int:
        try:
            return int(k.split("_")[-1])
        except Exception:
            return 10**9

    counts: List[SlideCount] = []
    slide_keys = sorted(mapping.keys(), key=_slide_key_to_index)

    for k in slide_keys:
        slide = mapping.get(k, {}) or {}

        titles = 1 if slide.get("title") else 0

        subs = slide.get("subtitle", [])
        subtitles = len(subs) if isinstance(subs, list) else 0

        body = slide.get("body", [])
        body_rows = 0
        body_items = 0

        if isinstance(body, list):
            for row in body:
                if not isinstance(row, dict):
                    continue
                content = row.get("content", [])
                if isinstance(content, list):
                    body_rows += 1
                    body_items += len(content)

        counts.append(SlideCount(
            slide_index=_slide_key_to_index(k),
            titles=titles,
            subtitles=subtitles,
            body_rows=body_rows,
            body_items=body_items
        ))

    counts.sort(key=lambda x: x["slide_index"])
    return counts

#=================================
# ACTUAL JSON CREATING FUNCTIONS
#=================================
import json
import re
from typing import Dict, Any

# -------------------------------------------------------------------
#  EXTRACTED UTILITY FUNCTION (formerly nested inside get_filler_json)
# -------------------------------------------------------------------
def sanitize_txt(txt: str, is_subtitle: bool = False) -> str:
    if not txt:
        return ""
    txt = re.sub(r"(https?://\S+)", "", txt)
    txt = re.sub(r"\b(?:Figure|Table)\s+\d+\b", "", txt, flags=re.I)
    txt = re.sub(r"\(\d{4}\)", "", txt)
    txt = txt.strip(" •\u2022\t-—–\"' ").strip().rstrip(".;,:")
    words = txt.split()
    limit = 4 if is_subtitle else 12
    if len(words) > limit:
        txt = " ".join(words[:limit]).rstrip(".;,:")
    return txt


# -------------------------------------------------------------------
#  ORIGINAL FUNCTION, UPDATED TO CALL sanitize_txt(...)
# -------------------------------------------------------------------
def get_filler_json(mapping: Dict[str, Any], parsed: Dict[str, Any], count_schema, user_images: Optional[List[str]] = None, style_prompt: str = "") -> Dict[str, Any]:
    schema_str = json.dumps(mapping, indent=2, ensure_ascii=False)
    parsed_data = {
        "file": parsed.get("file", ""),
        "title": parsed.get("title"),
        "author": parsed.get("author"),
        "date": parsed.get("date"),
        "hierarchy": parsed.get("hierarchy", []),
    }
    parsed_str = json.dumps(parsed_data, indent=2, ensure_ascii=False)
    count_str = json.dumps(count_schema, indent=2, ensure_ascii=False)

    # ---------------------------
    # Internal helpers (table-only)
    # ---------------------------
    def _truncate_words(s: str, max_words: int = 3) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        return " ".join(s.split()[:max_words])

    def _row_lengths_from_table_spec(t_spec: Dict[str, Any]) -> List[int]:
        rows_template = (t_spec or {}).get("rows")
        cols_template = (t_spec or {}).get("cols")
        row_lengths: List[int] = []
        if isinstance(rows_template, list):
            for r in rows_template:
                if isinstance(r, list):
                    row_lengths.append(len(r))
                else:
                    row_lengths.append(0)
        elif isinstance(rows_template, int) and isinstance(cols_template, int):
            row_lengths = [cols_template] * rows_template
        else:
            row_lengths = []
        return row_lengths

    def _extract_table_headers(table_spec: Dict[str, Any]) -> List[str]:
        rows = table_spec.get("rows")
        if isinstance(rows, list) and rows and isinstance(rows[0], list):
            headers = []
            for h in rows[0]:
                if isinstance(h, (str, int, float)):
                    headers.append(str(h))
                else:
                    headers.append("")
            return headers
        return []

    _VAGUE = {
        "innovation", "collaboration", "support", "updates", "guidelines",
        "improvements", "enhancements", "processes", "activities", "timeline",
        "development", "partnerships", "best practices"
    }

    def _looks_vague(token: str) -> bool:
        t = (token or "").strip().lower()
        return t in _VAGUE or (len(t.split()) == 1 and t.isalpha() and len(t) > 3)

    def _title_case_phrase(s: str) -> str:
        return " ".join([w.capitalize() for w in (s or "").split()])

    def _refine_cell(cand: str, header: str = "", row_topic: str = "") -> str:
        verbs_by_header = {
            "compliance": "Ensure",
            "enforcement": "Enforce",
            "penalties": "Apply",
            "risk": "Assess",
            "risks": "Assess",
            "risk assessment": "Assess",
            "scope": "Define",
            "objectives": "Achieve",
            "monitoring": "Monitor",
            "reporting": "Submit",
            "standards": "Follow",
            "governance": "Establish",
            "transparency": "Disclose",
            "data protection": "Protect",
            "privacy": "Protect",
            "accountability": "Assign",
            "training": "Train",
            "guidelines": "Follow",
            "stakeholders": "Engage",
            "timeline": "Schedule"
        }
        h = (header or "").strip()
        rt = (row_topic or "").strip()
        base = (cand or "").strip()

        verb = ""
        key = h.lower()
        if key in verbs_by_header:
            verb = verbs_by_header[key]
        else:
            for k, v in verbs_by_header.items():
                if k in key:
                    verb = v
                    break
        if not verb:
            verb = "Define" if h else "Clarify"

        if h and h.lower() not in {"", "n/a", "header"}:
            phrase = f"{verb} {h}"
        elif rt:
            phrase = f"{verb} {rt}"
        else:
            phrase = base or "Define Scope"

        return _truncate_words(_title_case_phrase(phrase), 3) or "Define Scope"

    def _make_column_semantics(headers: List[str]) -> List[str]:
        canonical = {
            "scope": "Describe coverage or applicability boundaries",
            "objectives": "State concrete goals or intended outcomes",
            "compliance": "List duties, controls, or required actions to comply",
            "enforcement": "Describe oversight or mechanisms ensuring compliance",
            "penalties": "Describe fines, sanctions, or consequences",
            "stakeholders": "Identify involved parties or roles",
            "timeline": "Indicate time windows or phases",
            "risk": "Describe risk types or evaluations",
            "risk assessment": "Specify evaluation steps or criteria",
            "accountability": "Assign responsibilities or owners",
            "standards": "List norms, frameworks, or benchmarks",
            "reporting": "Specify required reports or disclosures",
            "governance": "Describe policies, structures, or processes",
            "data protection": "Specify safeguards or controls on data",
            "transparency": "Describe disclosures or explainability",
            "training": "State learning or competency requirements",
            "guidelines": "Reference playbooks or procedural references",
        }
        hints = []
        for h in headers:
            key = (h or "").strip().lower()
            best = ""
            if key in canonical:
                best = canonical[key]
            else:
                for k, v in canonical.items():
                    if k in key:
                        best = v
                        break
            hints.append(best or f"Provide concrete details related to '{h}'")
        return hints

    # ---------------------------
    # Pydantic (for table-only calls)
    # ---------------------------
    class TableRowsOnly(BaseModel):
        rows: List[List[str]] = Field(default_factory=list)

    class TableSlideOnly(BaseModel):
        table: List[TableRowsOnly] = Field(default_factory=list)

    class RowTopics(BaseModel):
        topics: List[str] = Field(default_factory=list)

    # ---------------------------
    # Phase 1: ORIGINAL non-table behavior (unchanged)
    # ---------------------------
    system_prompt = CREATE_FILLER
    human_prompt = (
        "PPTX Schema (JSON template):\n"
        f"{schema_str}\n\n"
        "COUNT_SCHEMA (per-slide counts you MUST match exactly):\n"
        f"{count_str}\n\n"
        "Parsed document sections (use key_points and summaries as your source content):\n"
        f"{parsed_str}\n\n"
        "Return JSON ONLY. Fill the skeleton in-place.\n"
        "- Include 'table' for each slide exactly as in the schema.\n"
        "- For each table, preserve the number of tables, row count, and column count per row from the schema template.\n"
        "- Keep cell contents short (<=12 words) and avoid duplicates within the same slide."
        + (
            f"\n\nSTYLE GUIDANCE (apply to every title, subtitle, and body item):\n{style_prompt}\n"
            "Adjust the tone, vocabulary, and energy of all language to match this style. "
            "Keep facts accurate but rewrite phrasing to fit the requested register — "
            "e.g. casual/fun means shorter sentences, conversational words, active voice; "
            "corporate/formal means precise terminology, professional tone, third-person where appropriate."
            if style_prompt.strip() else ""
        )
    )

    cfg = LLMConfig(
        temperature=0.0,
        max_tokens=8000,
        provider="anthropic",
        host_provider="anthropic",
        model="claude-haiku-4-5-20251001"
    )
    llm = LLMService(cfg, logger=pg_logger)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]

    filler_obj: Filler = llm.invoke_structured(messages, Filler)
    data = json.loads(filler_obj.model_dump_json())

    # ---------------------------
    # Reservoir: key_points first, then summary sentences as fallback
    # ---------------------------
    def _extract_hierarchy_texts(hierarchy):
        texts = []
        for section in hierarchy:
            if section.get("section"):
                texts.append(section["section"])
            for item in section.get("content", []):
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, dict):
                    for bullet in item.get("bullets", []):
                        if isinstance(bullet, str):
                            texts.append(bullet)
            for subsec in section.get("subsections", []):
                if subsec.get("title"):
                    texts.append(subsec["title"])
                for para in subsec.get("paragraphs", []):
                    if isinstance(para, str):
                        texts.append(para)
                for bullet in subsec.get("bullets", []):
                    if isinstance(bullet, str):
                        texts.append(bullet)
        return texts

    reservoir = []
    seen_chunks = set()
    try:
        for text in _extract_hierarchy_texts(parsed.get("hierarchy", [])):
            t = text.strip(" •\t-—–\"' ").strip().rstrip(".;,:")
            if t and t not in seen_chunks:
                seen_chunks.add(t)
                reservoir.append(t)
    except Exception:
        pass

    reservoir_i = 0
    slides_out: List[Dict[str, Any]] = []
    non_table_context: List[Dict[str, Any]] = []   # for Phase 2
    table_schema_only: List[List[Dict[str, Any]]] = []  # for Phase 2

    slide_keys = sorted(mapping.keys(), key=lambda k: int(k.split("_")[-1]))
    llm_slides = data.get("slides", [])
    while len(llm_slides) < len(slide_keys):
        llm_slides.append({"title": "", "subtitle": [], "body": [], "table": [], "images": []})

    # ---------------------------
    # Process slides (ORIGINAL title/subtitle/body shaping)
    # ---------------------------
    for idx, slide_key in enumerate(slide_keys):
        schema_slide = mapping.get(slide_key, {}) or {}
        llm_slide = llm_slides[idx] if idx < len(llm_slides) else {}

        title_needed = bool(schema_slide.get("title"))
        sub_targets = schema_slide.get("subtitle", [])
        body_targets = schema_slide.get("body", [])
        schema_tables = schema_slide.get("table", []) or []

        # ----- Title (original) -----
        title_val = llm_slide.get("title", "") if title_needed else ""
        title_val = sanitize_txt(title_val)
        if title_needed and not title_val:
            if reservoir_i < len(reservoir):
                title_val = reservoir[reservoir_i]
                reservoir_i += 1
            else:
                title_val = ""
        try:
            if title_val and not title_val.isupper():
                title_val = " ".join(
                    [w if w.isupper() and len(w) <= 4 else w.capitalize() for w in title_val.split()]
                )
        except Exception:
            pass

        # ----- Subtitles (original) -----
        expected_subs = len(sub_targets)
        subs_llm = llm_slide.get("subtitle", []) or []
        subs_fixed = []
        for i in range(expected_subs):
            cand = subs_llm[i] if i < len(subs_llm) else ""
            cand = sanitize_txt(cand, is_subtitle=True)
            if not cand:
                if reservoir_i < len(reservoir):
                    cand = sanitize_txt(reservoir[reservoir_i], is_subtitle=True)
                    reservoir_i += 1
                else:
                    cand = ""
            subs_fixed.append(cand)

        # ----- Body (original) -----
        body_llm = llm_slide.get("body", []) or []
        body_fixed = []
        seen_in_slide = set(([title_val] if title_needed else []) + subs_fixed)

        for b_idx, body_block in enumerate(body_targets or []):
            slot_specs = body_block.get("content", []) or []
            expected_items = len(slot_specs)
            row_llm = body_llm[b_idx] if b_idx < len(body_llm) else []

            flattened = []
            for itm in row_llm:
                raw_txt = (itm.get("text", "") or "").strip()
                if not raw_txt:
                    continue
                words = raw_txt.split()
                if len(words) <= 12:
                    flattened.append(raw_txt)
                else:
                    for i in range(0, len(words), 12):
                        piece = " ".join(words[i:i+12])
                        if piece:
                            flattened.append(piece)

            if len(flattened) > expected_items:
                extras = flattened[expected_items:]
                for ex in extras:
                    s = sanitize_txt(ex)
                    if s and s not in seen_chunks:
                        seen_chunks.add(s)
                        reservoir.append(s)
                flattened = flattened[:expected_items]

            while len(flattened) < expected_items:
                if reservoir_i < len(reservoir):
                    flattened.append(reservoir[reservoir_i])
                    reservoir_i += 1
                else:
                    flattened.append("")

            row_fixed = []
            for s_idx, slot in enumerate(slot_specs):
                expect_bulleted = bool(slot.get("bullets", False))
                txt = sanitize_txt(flattened[s_idx], is_subtitle=False)

                if not txt:
                    if reservoir_i < len(reservoir):
                        txt = sanitize_txt(reservoir[reservoir_i], is_subtitle=False)
                        reservoir_i += 1
                    else:
                        txt = ""

                if txt and txt in seen_in_slide:
                    replaced = False
                    while reservoir_i < len(reservoir):
                        alt = sanitize_txt(reservoir[reservoir_i], is_subtitle=False)
                        reservoir_i += 1
                        if alt and alt not in seen_in_slide:
                            txt = alt
                            replaced = True
                            break

                seen_in_slide.add(txt)
                row_fixed.append({"text": txt, "bulleted": expect_bulleted})

            body_fixed.append(row_fixed)

        # Original debug print
        for b_idx, body_block in enumerate(body_targets or []):
            print(
                f"Row {b_idx+1}: items needed {len(body_block.get('content', []) or [])}, "
                f"LLM gave {len(body_llm[b_idx]) if b_idx < len(body_llm) else 0}"
            )

        # NOTE: We DO NOT build tables here anymore.
        # We store non-table context and schema for Phase 2.
        non_table_context.append({
            "title": title_val,
            "subtitle": subs_fixed,
            "body": body_fixed,
        })
        table_schema_only.append(schema_tables)

        # Add slide with empty tables for now; we'll fill tables after Phase 2.
        slides_out.append({
            "title": title_val,
            "subtitle": subs_fixed,
            "body": body_fixed,
            "table": [],
            "images": llm_slide.get("images", []),
        })

    # ---------------------------
    # Override slide 1 title with the document title if the parser found one
    # ---------------------------
    doc_title = (parsed.get("title") or "").strip()
    if slides_out and doc_title:
        slides_out[0]["title"] = doc_title
        non_table_context[0]["title"] = doc_title

    # ---------------------------
    # Phase 2a: Build table hints (headers + semantics + row topics)
    # ---------------------------
    topics_cfg = LLMConfig(
        temperature=0.2,
        max_tokens=2000,
        provider="anthropic",
        host_provider="anthropic",
        model="claude-3-5-haiku-20241022"
    )
    topics_llm = LLMService(topics_cfg, logger=pg_logger)

    table_hints: List[List[Dict[str, Any]]] = []
    for s_idx, slide_tables in enumerate(table_schema_only):
        hints_for_slide = []
        slide_ctx = non_table_context[s_idx]
        for t_spec in slide_tables:
            headers = _extract_table_headers(t_spec)
            semantics = _make_column_semantics(headers) if headers else []
            row_lengths = _row_lengths_from_table_spec(t_spec)
            n_rows = len(row_lengths)
            data_rows = (n_rows - 1) if (headers and n_rows > 0) else n_rows

            # Generate row topics per table
            row_topics_list: List[str] = []
            if data_rows > 0:
                try:
                    topics_payload = {
                        "slide_context": slide_ctx,
                        "headers": headers,
                        "column_semantics": semantics,
                        "row_count": data_rows,
                        "instructions": (
                            "Propose distinct, concrete row topics (2–3 words each) appropriate for the table. "
                            "Each topic should be specific enough to anchor a coherent row across all columns. "
                            "No duplicates. Use domain-appropriate phrasing. Return JSON ONLY as {\"topics\": [..]}."
                        )
                    }
                    topics_messages = [
                        SystemMessage(content="You propose compact, domain-appropriate row topics for tables."),
                        HumanMessage(content=json.dumps(topics_payload, ensure_ascii=False)),
                    ]
                    topics_obj = topics_llm.invoke_structured(topics_messages, RowTopics)
                    topics_json = json.loads(topics_obj.model_dump_json())
                    for t in topics_json.get("topics", []):
                        row_topics_list.append(_truncate_words(sanitize_txt(t or ""), 3))
                    if len(row_topics_list) < data_rows:
                        row_topics_list += ["General Topic"] * (data_rows - len(row_topics_list))
                    elif len(row_topics_list) > data_rows:
                        row_topics_list = row_topics_list[:data_rows]
                except Exception as e:
                    pg_logger.warning(f"Row topics generation error: {repr(e)}")
                    row_topics_list = ["General Topic"] * max(0, data_rows)
            hints_for_slide.append({
                "headers": headers,
                "column_semantics": semantics,
                "row_topics": row_topics_list
            })
        table_hints.append(hints_for_slide)

    # ---------------------------
    # Phase 2b: Generate tables per slide using FILL_TABLE
    # ---------------------------
    system_prompt_tables = FILL_TABLE
    slide_table_json: List[Dict[str, Any]] = []
    for idx in range(len(slides_out)):
        if not table_schema_only[idx]:
            slide_table_json.append({"table": []})
            continue
        per_slide_payload = {
            "table_schema": table_schema_only[idx],
            "table_hints": table_hints[idx],
            "filled_slide": non_table_context[idx],
            "instructions": (
                "Generate and FILL ONLY the 'table' content for this slide.\n"
                "Use 'headers', 'column_semantics', and 'row_topics' to keep rows coherent and columns faithful to semantics.\n"
                "Each row must elaborate on its single row_topic across all columns.\n"
                "Max 3 words per cell. Avoid vague single nouns. No duplicates within the slide.\n"
                "Respect EXACT row/col counts for each table.\n"
                "Return JSON shaped like: { 'table': [ { 'rows': [[cells]] } ] }.\n"
                "Return JSON ONLY."
            ),
        }
        per_messages = [
            SystemMessage(content=system_prompt_tables),
            HumanMessage(content=json.dumps(per_slide_payload, ensure_ascii=False)),
        ]
        try:
            one_obj = llm.invoke_structured(per_messages, TableSlideOnly)
            one_json = json.loads(one_obj.model_dump_json())
            if isinstance(one_json, dict) and "table" in one_json:
                slide_table_json.append(one_json)
            else:
                slide_table_json.append({"table": []})
        except Exception as e:
            pg_logger.warning(f"Table generation error (slide {idx+1}): {repr(e)}")
            slide_table_json.append({"table": []})

    # ---------------------------
    # Phase 2c: Coerce shapes + enforce ≤3 words + de-vague + de-dupe
    # ---------------------------
    for idx in range(len(slides_out)):
        schema_tables = table_schema_only[idx] or []
        returned_tables = (slide_table_json[idx] or {}).get("table", []) if idx < len(slide_table_json) else []

        print(f"\n[DEBUG] Slide {idx+1} table shapes (row lengths per row):")
        for t_idx, t_spec in enumerate(schema_tables):
            print("  Table", t_idx + 1, "->", _row_lengths_from_table_spec(t_spec))

        # Prepare a de-dup set that includes title/subtitle/body (to avoid slide-level duplicates)
        non_table_seen = set()
        if slides_out[idx].get("title"):
            non_table_seen.add(slides_out[idx]["title"].strip().lower())
        for s in slides_out[idx].get("subtitle", []):
            if s:
                non_table_seen.add(s.strip().lower())
        for row in slides_out[idx].get("body", []):
            for item in row:
                if item and isinstance(item, dict):
                    t = item.get("text", "")
                    if t:
                        non_table_seen.add(t.strip().lower())

        tables_fixed: List[Dict[str, Any]] = []
        for t_idx, t_spec in enumerate(schema_tables):
            row_lengths = _row_lengths_from_table_spec(t_spec)
            headers = _extract_table_headers(t_spec)
            hints = table_hints[idx][t_idx] if idx < len(table_hints) and t_idx < len(table_hints[idx]) else {}
            row_topics = hints.get("row_topics", []) if hints else []

            if t_idx < len(returned_tables):
                llm_rows = (returned_tables[t_idx] or {}).get("rows", []) or []
            else:
                llm_rows = []

            flat_cells: List[str] = []
            for r in llm_rows:
                if isinstance(r, list):
                    for c in r:
                        s = _truncate_words(sanitize_txt(str(c) if c is not None else ""), 3)
                        if s:
                            flat_cells.append(s)

            total_needed = sum(row_lengths) if row_lengths else 0
            print(f"[DEBUG] Slide {idx+1} Table {t_idx+1}: cells needed={total_needed}, LLM cells parsed={len(flat_cells)}")

            # Seed if absolutely nothing
            if not flat_cells:
                seed = slides_out[idx].get("title", "") or "Slide Content"
                seed = _truncate_words(sanitize_txt(seed), 2) or "Cell"
                flat_cells = [seed]

            # Build rows with final enforcement + de-vague + de-dupe (against both table cells & non-table text)
            fixed_rows: List[List[str]] = []
            seen_cells = set(non_table_seen)  # start with non-table strings to avoid slide-level duplicates
            i = 0
            for r_i, rl in enumerate(row_lengths):
                row_cells: List[str] = []
                for c_i in range(rl):
                    if i < len(flat_cells):
                        cand = flat_cells[i]; i += 1
                    else:
                        base = row_cells[-1] if row_cells else (fixed_rows[-1][-1] if fixed_rows and fixed_rows[-1] else (flat_cells[-1] if flat_cells else "Cell"))
                        cand = base

                    cand = _truncate_words(sanitize_txt(cand), 3) or "Cell"

                    header = headers[c_i] if headers and c_i < len(headers) else ""
                    topic_index = r_i - 1 if headers else r_i   # adjust if row 0 is header row
                    topic = row_topics[topic_index] if 0 <= topic_index < len(row_topics) else ""

                    if _looks_vague(cand) or cand.strip().lower() in seen_cells:
                        cand = _refine_cell(cand, header=header, row_topic=topic)

                    cand = _truncate_words(cand, 3)
                    seen_cells.add(cand.strip().lower())
                    row_cells.append(cand)
                fixed_rows.append(row_cells)

            tables_fixed.append({"rows": fixed_rows})

            # Original-like debug
            llm_row_count = len(llm_rows)
            llm_max_cols = max((len(r) for r in llm_rows if isinstance(r, list)), default=0)
            print(
                f"Table {t_idx+1}: rows needed {len(row_lengths)}, "
                f"LLM gave rows {llm_row_count}, max cols {llm_max_cols}"
            )

        slides_out[idx]["table"] = tables_fixed

    # Distribute user-provided images across slides in order of image slots
    if user_images:
        image_pool = list(user_images)
        for idx, slide_key in enumerate(slide_keys):
            n_slots = len((mapping.get(slide_key, {}) or {}).get("image", []))
            if n_slots > 0 and image_pool:
                slides_out[idx]["images"] = [image_pool.pop(0) for _ in range(min(n_slots, len(image_pool)))]

    return {"slides": slides_out}

#=================================
# CHECKS FOR BLANKS AND FILLS THEM IN
#=================================
def check_blanks(parsed: Dict[str, Any], filler_json: Dict[str, Any]) -> Dict[str, Any]:
    def extract_missing(data: Any) -> Optional[Any]:
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                if k == "table":
                    continue
                extracted = extract_missing(v)
                if extracted not in (None, {}, []):
                    result[k] = extracted
            return result

        elif isinstance(data, list):
            result = []
            for item in data:
                extracted = extract_missing(item)
                if extracted not in (None, {}, []):
                    result.append(extracted)
            return result if result else None

        else:
            if isinstance(data, str) and (data == "" or data == "FILL_THIS_TEXT"):
                return data
            return None

    missing_fields = extract_missing(filler_json)
    if not missing_fields:
        return filler_json 

    system_prompt = CHECK_BLANKS.format(
        FULL_JSON=json.dumps(filler_json, indent=2, ensure_ascii=False),
        PDF_TEXT=json.dumps(parsed, indent=2, ensure_ascii=False),
    )

    human_prompt = "Fill ONLY the fields that are empty strings or 'FILL_THIS_TEXT'. Return the full JSON object."

    cfg = LLMConfig(
        temperature=0.0,
        max_tokens=3000,
        provider="anthropic",
        host_provider="anthropic",
        model="claude-3-5-haiku-20241022"
    )
    llm = LLMService(cfg, logger=pg_logger)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]
    try:
        filled_full_obj = llm.invoke_structured(messages, Filler)
        filled_full = json.loads(filled_full_obj.model_dump_json())
    except Exception as e:
        raise RuntimeError(f"invoke_structured failed to produce a valid full JSON: {e}")

    def merge_blanks(original: Any, patch: Any) -> Any:
        if isinstance(original, dict) and isinstance(patch, dict):
            for k in original.keys():
                if k in patch:
                    original[k] = merge_blanks(original[k], patch[k])
            return original

        if isinstance(original, list) and isinstance(patch, list):
            n = min(len(original), len(patch))
            for i in range(n):
                original[i] = merge_blanks(original[i], patch[i])
            return original

        if isinstance(original, str) and original in ("", "FILL_THIS_TEXT"):
            if isinstance(patch, str):
                return patch.strip()
            else:
                return original

        return original

    updated = merge_blanks(json.loads(json.dumps(filler_json)), filled_full)
    return updated

if __name__ == "__main__":
    file = input("Enter the name of the pdf: ")
    parsed_text = extract_text(file)
    #template = input("Enter the name of the pptx")

    template = "pptx_templates/Cap_Template.pptx"
    template_path = Path(__file__).resolve().parent / template
    pptx_schema = build_presentation_mapping(template_path)
    count = count_schema_elements(pptx_schema)
    print(pptx_schema)

    images_input = input("Enter image file paths in order, comma-separated (or press Enter to skip): ").strip()
    user_images = [p.strip() for p in images_input.split(",") if p.strip()] if images_input else None

    filler_json = get_filler_json(pptx_schema, parsed_text, count, user_images=user_images)
    final_json = check_blanks(parsed_text, filler_json)
    print("filler created")

    final_json_path = Path(__file__).resolve().parent / "pptx_templates" / "Cap_Filled.json"
    with open(final_json_path, "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    apply_json_to_pptx(
        pptx_in=str(template_path),
        json_in=str(final_json_path), 
        pptx_out=str(Path(__file__).resolve().parent / "pptx_templates" / "Cap_Filled.pptx")
    )
    print("pptx created successfully")