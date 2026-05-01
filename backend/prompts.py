CREATE_FILLER = """
  You generate STRICT structured JSON to fill a PowerPoint template
  FROM A STRUCTURED SOURCE (sections with key points). The output MUST be valid JSON ONLY (no commentary, no markdown).

  You are given a JSON object with this structure:
  {
    "file": string,
    "sections": [
      {
        "title": string,
        "summary": string,
        "key_points": [string, ...]
      },
      ...
    ]
  }

  You must produce the following EXACT output structure:

  OUTPUT STRUCTURE (unchanged):
  {
    "slides": [
      {
        "title": string,
        "subtitle": [string, ...],
        "body": [
          [
            { "text": string, "bulleted": boolean },
            ...
          ],
          ...
        ],
        "table": [
          {
            "rows": [
              [string, ...],
              ...
            ]
          }
        ],
        "images": [string, ...]
      }
    ]
  }

  ============================================================
  MANDATORY RULES (READ CAREFULLY — ALL MUST BE FOLLOWED)
  ============================================================

  1) MATCH COUNTS EXACTLY (FROM COUNT_SCHEMA):
  - Match the exact number of slides, titles, subtitles, body rows, body items per row (and their bulleted flags), number of tables, table rows, and columns per row.
  - COUNT_SCHEMA and/or the provided PPTX Schema define the shape. You MUST produce output that matches these shapes exactly.
  - If you do not have enough content, combine key_points or summary sentences from nearby sections, then split into ≤12-word chunks for body items.
  - NEVER leave any field empty.

  2) BODY ITEM LENGTH:
  - EVERY body item MUST be ≤ 12 words.
  - If an extract is longer than 12 words, split it into smaller coherent ≤12 word phrases.

  3) SUBTITLE LENGTH & PURPOSE:
  - Subtitles must be 1–4 words.
  - Subtitles must be meaningful standalone headers.
  - Subtitles must NOT form a sentence, must NOT be sequential fragments, and must NOT depend on each other.
  - Each subtitle must summarize a different aspect of that slide’s body content.
  - Subtitles do NOT follow the body shape coherence rule.

  4) TITLE RULES:
  - Title must summarize the whole slide.
  - It must be extractive or compressive from the hierarchy (section/subsection titles or compressive versions of them).
  - It must be unique across the entire presentation.
  - Title must NOT repeat any subtitle or body item.
  - Title must NOT repeat any other slide title in the presentation; it MUST BE UNIQUE.

  5) EXTRACTIVE ONLY (NO HALLUCINATIONS, NO PLACEHOLDERS):
  - You cannot invent or hallucinate new content.
  - All text must originate from sections (key_points, summaries, or titles — possibly shortened or combined).
  - Do NOT output placeholders or boilerplate (e.g., "Date Placeholder", "Footer Placeholder", "Slide Number", "TBD", "N/A").

  6) COHERENCE WITHIN EACH BODY SHAPE (IMPORTANT):
  - Each body shape may contain multiple paragraph lines.
  - ALL lines in the same shape MUST relate to the SAME topic or subtopic.
  - Lines must come from the same section's key_points or summary — do not mix content from unrelated sections.
  - Body lines within a shape must read as a coherent mini-section.
  - This rule applies ONLY to body items, NOT subtitles.

  7) TABLE RULES:
  - You MUST match the table schema exactly: the EXACT number of tables, rows, and columns per row as defined by COUNT_SCHEMA and/or the PPTX Schema.
  - The input schema may specify table shapes either as numeric fields (e.g., {"rows": 5, "cols": 8}) OR as explicit arrays (e.g., {"rows": [[...], ...]}). Regardless of how input is specified, you MUST OUTPUT tables in the normalized array form:
    "table": [{ "rows": [[cell, ...], ...] }]
  - Fill every cell.
  - All table content must originate from sections (key_points, summaries, or titles).
  - Keep table cells short: prefer numbers or ~3 words per cell (≤5 words max).
  - Avoid duplication within the same table and slide.

  8) SANITIZATION:
  - Remove bullet glyphs (•, -, *, o), URLs, page numbers, unprintable icons, “Figure X”, “Table X”, citations like “(2024)”.
  - Trim whitespace and trailing punctuation.
  - Normalize whitespace.

  9) NO EMPTY STRINGS:
  - All titles, subtitles, body items, and table cells must be non-empty.
  - If cleaning yields emptiness, choose a different extract from the hierarchy.

  10) UNIQUENESS WITHIN EACH SLIDE:
  - All subtitles must be unique from each other.
  - All body items must be unique within the slide.
  - Title, subtitles, body items, and table cells must all be distinct within the slide.
  - Titles must be unique across all slides.

  11) FINAL SELF-CHECK BEFORE RETURNING JSON:
  For EVERY slide, verify:
  - Output matches the EXACT skeleton shape (same number of slides, body rows/items/bulleted flags, and tables/rows/columns).
  - Body items ≤12 words. Subtitles 1–4 words and NOT sentence fragments.
  - Table cells are ≤5 words (prefer ~3 words or numbers).
  - Title summarizes the slide and is unique.
  - All values are non-empty and extractive (no hallucinations, no placeholders).
  - Body lines within each shape are coherent and from the same topic (same section content block, same bullets group, or same subsection).

  ============================================================
  INPUT DELIVERY
  ============================================================
  You will receive the parsed document as a hierarchical structure:
  {
    "file": string,
    "title": string or null,
    "author": string or null,
    "date": string or null,
    "hierarchy": [
      {
        "section": "<section heading>",
        "content": [<paragraph strings, {"bullets": [...]}, or {"table": [...]} dicts>],
        "subsections": [
          {
            "title": "<subsection heading>",
            "paragraphs": [string, ...],
            "bullets": [string, ...],
            "table": [...]
          }
        ]
      },
      ...
    ]
  }

  SECTION ORGANIZATION (apply mentally before filling slides):
  - The first section you map to slides should be an "Overview" covering the document's purpose and main conclusions
  - Cover all major topics — do not artificially cap the count; use as many slides as the template provides
  - Each slide title should be descriptive and unique, derived from a distinct section or subsection
  - All content must be faithful to the document — no hallucination
  - For each slide, draw 4-8 key points that capture the most critical information, insights, or conclusions from that section
  - Key points should be the most important takeaways: concise, specific, and coherent with each other
  - ALL body lines within a single shape must come from the SAME section or subsection — never mix content from unrelated parts of the document on the same shape

  You must return ONLY the final JSON (no commentary, no markdown) that conforms to the OUTPUT STRUCTURE and the mandatory rules above.
  """

CHECK_BLANKS = """
    You are filling ONLY EMPTY text fields in an existing PPTX JSON structure.

    Your job (VERY STRICT):
    - Fix ONLY fields that are "" or "FILL_THIS_TEXT".
    - NEVER change non-empty text.
    - NEVER alter structure, keys, list lengths, indices, or ordering.
    - You MUST return the FULL JSON object in the EXACT SAME structure as provided (not a snippet).
    - The output must validate against the provided schema (slides/title/subtitle/body/images).

    =============================
    CONTENT RULES (STRICT)
    =============================
    1) Extract text ONLY from the provided PDF text (below).
    2) You MAY shorten/split/rewrite for clarity — still extractive/compressive from PDF wording.
    3) Body items MUST be 4–12 words.
    4) Subtitles MUST be 1–4 words.
    5) Text must be clean, complete, and not cut mid‑sentence.
    6) Avoid policy jargon unless present in PDF.
    7) Avoid vague summaries; use specific phrases from PDF.
    8) NO partial, cut-off, or hanging phrases.
    9) NO hallucinations; do NOT invent content.

    =============================
    TRANSFORMATION GUIDANCE
    =============================
    - Choose a coherent sentence or bullet.
    - Extract a clean fragment (≤12 words).
    - Do NOT break inside parentheses/citations/hyphenated terms.
    - Do NOT copy lines starting mid-sentence.

    BAD:
    "AI). Most of the text addresses high-risk AI systems"

    GOOD:
    "High‑risk AI systems require safeguards"
    "Limited‑risk AI needs transparency"

    =============================
    OUTPUT REQUIREMENTS
    =============================
    - Return ONLY the FULL JSON object in the SAME structure.
    - Replace ONLY blanks ("", "FILL_THIS_TEXT"). Leave all other fields untouched.
    - No commentary, no markdown, no code fences.
        
    =============================
    INPUTS
    =============================
    FULL JSON (fill only blanks):
    {FULL_JSON}

    PDF text (extract ONLY from this):
    {PDF_TEXT}
    """

FILL_TABLE = """
You are transforming parsed PDF content into JSON that fills ONLY the 'table' fields of an existing PPTX schema.
Your goal is to produce cohesive, row-consistent, column-faithful tables that match the schema exactly.

SCHEMA & FORMATTING
- Preserve the schema structure and keys verbatim. Do NOT add, remove, or rename keys.
- Every defined table must have all cells populated. No empty strings.
- Return JSON ONLY. No markdown, comments, or explanations.
- Output per slide MUST be shaped as:
  { "table": [ { "rows": [[c11, c12, ...], [c21, c22, ...], ...] }, ... ] }

CONTENT STRATEGY
- Use the provided slide context ('filled_slides'), 'headers', 'column_semantics', and 'row_topics' for each table.
- Each ROW describes exactly one 'row_topic'. All cells in that row must describe the SAME topic from the perspective of their column.
- Each COLUMN must align with its header meaning AND the provided 'column_semantics' guidance. Do not mix concepts across columns.

LANGUAGE CONSTRAINTS
- Hard cap: MAX 3 WORDS per cell.
- Prefer concrete, action-oriented or specific noun phrases (e.g., "Assess risks", "Define criteria", "Submit reports").
- Avoid vague single nouns and generic filler, including:
  Innovation, Collaboration, Support, Updates, Guidelines, Improvements, Enhancements, Processes, Activities, Timeline.
- Avoid duplicates within the same slide (across title, subtitles, body, and table).

INSUFFICIENT CONTEXT
- If the PDF text is insufficient, synthesize concise, neutral, domain-appropriate phrases that remain faithful to the row_topic and column semantics. Never leave a cell empty.

CLEANING
- No trailing punctuation in cell values.
- Trim URLs, citations, figure/table mentions, and standalone years in parentheses (e.g., "(2024)").

INPUTS YOU MAY RECEIVE IN HUMAN MESSAGE
- table_schema: table placeholders with row/col counts or explicit row arrays
- table_hints: for each table, includes 'headers', 'column_semantics', and 'row_topics'
- filled_slides: per-slide non-table content (title/subtitle/body) for topic alignment
- instructions: caller-specific constraints (always follow them)

TASK
Strictly follow the schema shapes (number of tables, rows, and columns). Fill every cell with ≤3 words, row-coherent and column-faithful content. Return JSON ONLY.
"""