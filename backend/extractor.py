from io import BytesIO
from typing import Optional
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
