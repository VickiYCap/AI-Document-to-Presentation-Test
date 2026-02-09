from io import BytesIO
from typing import List, Iterator
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams

#pdf_byte - bytes of the PDF file
#line_margin - how close 2 lines need to be to be considered part of same paragraph
#word_margin - how close 2 words need to be to be considered part of same line
#char_margin - how close 2 characters need to be to be considered part of same word
#returns string of the extracted text
def parse_pdf_bytes(pdf_bytes: bytes,
                    line_margin: float = 0.2,
                    word_margin: float = 0.2,
                    char_margin: float = 2.0) -> str:
    
    laparams = LAParams(
        line_margin=line_margin,
        word_margin=word_margin,
        char_margin=char_margin,
    )
    text = extract_text(BytesIO(pdf_bytes), laparams=laparams)
    return text or ""

from typing import Iterator, List

# Splits text into word-safe chunks up to `max_chars`, never cutting words.
# Adds optional overlap by prepending a small tail of words from the previous
# chunk to the next one to preserve context.
def chunk_text(text: str, max_chars: int = 2000, overlap: int = 200) -> Iterator[str]:
    if not text:
        return

    words = text.split()
    if not words:
        return

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for w in words:
        next_len = current_len + (1 if current else 0) + len(w)
        if next_len <= max_chars:
            current.append(w)
            current_len = next_len
        else:
            if current:
                chunks.append(" ".join(current))
            current = [w]
            current_len = len(w)

    if current:
        chunks.append(" ".join(current))

    if overlap <= 0 or len(chunks) <= 1:
        yield from chunks
        return

    prev = chunks[0]
    yield prev

    for ch in chunks[1:]:
        tail = _tail_words_by_chars(prev.split(), overlap)
        yield " ".join(tail + ch.split()) if tail else ch
        prev = ch


# Returns the last few words from a list that fit within `budget` characters.
# Used to create word-safe overlap between chunks
def _tail_words_by_chars(words: List[str], budget: int) -> List[str]:
    tail: List[str] = []
    total = 0
    for word in reversed(words):
        add = len(word) + (1 if tail else 0)
        if total + add > budget:
            break
        tail.append(word)
        total += add
    tail.reverse()
    return tail