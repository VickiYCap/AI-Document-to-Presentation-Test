"""After the schema for the powerpoint template is creates, this file creates and fills in the JSON according to the mapping and the parsed document. 
It also counts the number of elements in each slide to give the LLM a better sense of how much content to generate, and to enforce that it fills in
 all required fields. """

import json
import re
import os

from pathlib import Path
from pydantic import BaseModel, Field

from langchain_core.messages import SystemMessage, HumanMessage
from backend.llm_api.llm_init import LLMService, LLMConfig
import logging
from logging.handlers import WatchedFileHandler

from .pptx_parser import apply_json_to_pptx, build_presentation_mapping
from .prompts import CREATE_FILLER, CHECK_BLANKS, FILL_TABLE, TEMPLATE_GENERATE
from .document_parser import extract_text

from typing import Optional, Dict, Any, List, Optional, TypedDict
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


#=================================
# LOGGING Information
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

# Models for llm_slide_generation structural template
class BodyShapeTemplate(BaseModel):
    item_count: int
    bulleted: bool = True

class TableTemplate(BaseModel):
    rows: int
    cols: int

class SlideTemplateItem(BaseModel):
    slide_type: str
    subtitle_count: int = 0
    body_shapes: List[BodyShapeTemplate] = Field(default_factory=list)
    tables: List[TableTemplate] = Field(default_factory=list)

class PresentationTemplate(BaseModel):
    slides: List[SlideTemplateItem]

#==============================================================================
# COUNTING ELEMENTS THAT THE LLM MAPS TO CHECK DEGRADATION (just for checking)
#===============================================================================
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
# TEXT SANITIZATION
#=================================
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

#=================================================================
# IF NO PPTX TEMPLATE GIVEN, LLM SHOULD GENERATE ITS OWN TEMPLATE
#=================================================================
def llm_slide_generation(parsed: Dict[str, Any], style_prompt: str = "") -> tuple:
    parsed_data = {
        "file": parsed.get("file", ""),
        "title": parsed.get("title"),
        "author": parsed.get("author"),
        "date": parsed.get("date"),
        "hierarchy": parsed.get("hierarchy", []),
    }
    parsed_str = json.dumps(parsed_data, indent=2, ensure_ascii=False)

    human_prompt = parsed_str
    if style_prompt.strip():
        human_prompt = f"User instructions: {style_prompt}\n\nParsed document:\n{parsed_str}"

    cfg = LLMConfig(
        temperature=0.3,
        max_tokens=4000,
        provider="anthropic",
        host_provider="anthropic",
        model="claude-haiku-4-5-20251001"
    )
    llm = LLMService(cfg, logger=pg_logger)

    messages = [
        SystemMessage(content=TEMPLATE_GENERATE),
        HumanMessage(content=human_prompt),
    ]

    template_obj: PresentationTemplate = llm.invoke_structured(messages, PresentationTemplate)
    template = json.loads(template_obj.model_dump_json())

    # Convert structural template to the mapping format expected by get_filler_json
    mapping: Dict[str, Any] = {}
    shape_counter = 1

    for idx, slide in enumerate(template.get("slides", []), start=1):
        slide_key = f"slide_{idx}"

        title_entry = [{"shape_id": shape_counter, "name": "Title"}]
        shape_counter += 1

        subtitle_entries = []
        for s in range(slide.get("subtitle_count", 0)):
            subtitle_entries.append({"shape_id": shape_counter, "name": f"Subtitle {s + 1}"})
            shape_counter += 1

        body_entries = []
        for b_idx, body_spec in enumerate(slide.get("body_shapes", [])):
            content = [{"bullets": body_spec.get("bulleted", True)}
                       for _ in range(max(1, body_spec.get("item_count", 3)))]
            body_entries.append({
                "shape_id": shape_counter,
                "name": f"Body {b_idx + 1}",
                "content": content,
            })
            shape_counter += 1

        table_entries = []
        for t_idx, table_spec in enumerate(slide.get("tables", [])):
            n_rows = max(2, table_spec.get("rows", 3))
            n_cols = max(2, table_spec.get("cols", 3))
            table_entries.append({
                "shape_id": shape_counter,
                "name": f"Table {t_idx + 1}",
                "rows": n_rows,
                "cols": n_cols,
                "total_cells": n_rows * n_cols,
            })
            shape_counter += 1

        mapping[slide_key] = {
            "title": title_entry,
            "subtitle": subtitle_entries,
            "body": body_entries,
            "table": table_entries,
            "image": [],
        }

    count_schema = count_schema_elements(mapping)
    return mapping, count_schema

#=================================
# JSON GENERATION
#=================================
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
    # Table helper utilities
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
    # Pydantic schemas for table LLM calls
    # ---------------------------
    class TableRowsOnly(BaseModel):
        rows: List[List[str]] = Field(default_factory=list)

    class TableSlideOnly(BaseModel):
        table: List[TableRowsOnly] = Field(default_factory=list)

    class RowTopics(BaseModel):
        topics: List[str] = Field(default_factory=list)

    # ---------------------------
    # Phase 1: Fill title, subtitle, and body for all slides in one batch call.
    # Tables are included in the schema so the LLM understands the full structure,
    # but the table output is discarded — Phase 2 handles tables with better context.
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
    # Build a reservoir of text chunks from the parsed document hierarchy.
    # Used as a fallback when the LLM leaves a field empty or produces too little content.
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
    non_table_context: List[Dict[str, Any]] = []  
    table_schema_only: List[List[Dict[str, Any]]] = [] 

    slide_keys = sorted(mapping.keys(), key=lambda k: int(k.split("_")[-1]))
    llm_slides = data.get("slides", [])
    while len(llm_slides) < len(slide_keys):
        llm_slides.append({"title": "", "subtitle": [], "body": [], "table": [], "images": []})

    # ---------------------------------------------------------------------
    # Shape Phase 1 output: enforce word limits, title-case titles,
    # and fill any gaps from the reservoir.
    # ---------------------------------------------------------------------
    for idx, slide_key in enumerate(slide_keys):
        schema_slide = mapping.get(slide_key, {}) or {}
        llm_slide = llm_slides[idx] if idx < len(llm_slides) else {}

        title_needed = bool(schema_slide.get("title"))
        sub_targets = schema_slide.get("subtitle", [])
        body_targets = schema_slide.get("body", [])
        schema_tables = schema_slide.get("table", []) or []

        # ----- Title -----
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

        # ----- Subtitles -----
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

        # ----- Body -----
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

        for b_idx, body_block in enumerate(body_targets or []):
            print(
                f"Row {b_idx+1}: items needed {len(body_block.get('content', []) or [])}, "
                f"LLM gave {len(body_llm[b_idx]) if b_idx < len(body_llm) else 0}"
            )

        # Save finalized non-table content and the raw table schema separately.
        # Tables are filled in Phase 2 using the finalized slide content for deduplication.
        non_table_context.append({
            "title": title_val,
            "subtitle": subs_fixed,
            "body": body_fixed,
        })
        table_schema_only.append(schema_tables)

        slides_out.append({
            "title": title_val,
            "subtitle": subs_fixed,
            "body": body_fixed,
            "table": [],
            "images": llm_slide.get("images", []),
        })

    # ---------------------------------------------------------------------
    # Pin slide 1 title to the document's parsed title when available,
    # overriding whatever the LLM generated.
    # ---------------------------------------------------------------------
    doc_title = (parsed.get("title") or "").strip()
    if slides_out and doc_title:
        slides_out[0]["title"] = doc_title
        non_table_context[0]["title"] = doc_title

    # ---------------------------------------------------------------------
    # Phase 2a: Build table hints (headers + semantics + row topics)
    # ---------------------------------------------------------------------
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

            # Ask the LLM for 2-3 word topics — one per data row — to anchor
            # cell content across columns in Phase 2b.
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

    # -------------------------------------------------------------
    # Phase 2b: Generate tables per slide using FILL_TABLE
    # -------------------------------------------------------------
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

    # Write Phase 2b output directly into slides
    for idx in range(len(slides_out)):
        raw = (slide_table_json[idx] or {}).get("table", []) if idx < len(slide_table_json) else []
        slides_out[idx]["table"] = [{"rows": t.get("rows", [])} for t in raw]

    # Distribute user-provided images across slides in order of image slots
    if user_images:
        image_pool = list(user_images)
        for idx, slide_key in enumerate(slide_keys):
            n_slots = len((mapping.get(slide_key, {}) or {}).get("image", []))
            if n_slots > 0 and image_pool:
                slides_out[idx]["images"] = [image_pool.pop(0) for _ in range(min(n_slots, len(image_pool)))]

    return {"slides": slides_out}

#===========================================
# BLANK FIELD REPAIR (currently unused)
#===========================================
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