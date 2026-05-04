import base64
import json
import shutil
import tempfile
import os
import traceback
import fitz
from pptxtopdf import convert
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from fastapi import FastAPI, File, Form, Request, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Optional

from backend.json_creator import get_filler_json, check_blanks, count_schema_elements
from backend.document_parser import extract_images, extract_text
from backend.pptx_parser import apply_json_to_pptx, build_presentation_mapping

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CORS_HEADERS = {"Access-Control-Allow-Origin": "*"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers=CORS_HEADERS,
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=CORS_HEADERS,
    )


@app.post("/analyze-template")
async def analyze_template(pptx_file: UploadFile = File(...)):
    contents = await pptx_file.read()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        pptx_path = os.path.join(tmp, pptx_file.filename or "template.pptx")
        with open(pptx_path, "wb") as f:
            f.write(contents)

        mapping = build_presentation_mapping(Path(pptx_path))

        convert(tmp, tmp)
        pdf_name = os.path.splitext(os.path.basename(pptx_path))[0] + ".pdf"
        pdf_path = os.path.join(tmp, pdf_name)
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=500, detail="PDF conversion failed.")

        doc = fitz.open(pdf_path)
        slides = []
        for idx, (slide_key, slide_map) in enumerate(mapping.items()):
            if idx >= len(doc):
                break
            page = doc[idx]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            thumbnail = base64.b64encode(pix.tobytes("png")).decode()
            slides.append({
                "slide_key": slide_key,
                "slide_index": idx,
                "thumbnail": f"data:image/png;base64,{thumbnail}",
                "images": slide_map.get("image", []),
            })
        doc.close()

    return JSONResponse({"slides": slides})


@app.post("/pdf-images")
async def pdf_images(pdf_file: UploadFile = File(...)):
    contents = await pdf_file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_f:
        tmp_f.write(contents)
        tmp_pdf = tmp_f.name
    tmp_dir = None
    try:
        result = extract_images(tmp_pdf)
        tmp_dir = result["tmp_dir"]
        images = []
        for img in result["images"]:
            with open(img["path"], "rb") as f:
                data = f.read()
            images.append({
                "xref": img["xref"],
                "width": img["width"],
                "height": img["height"],
                "ext": img["ext"],
                "base64": base64.b64encode(data).decode(),
            })
        return JSONResponse({"images": images})
    finally:
        os.unlink(tmp_pdf)
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/generate")
async def generate(
    pdf_file: UploadFile = File(...),
    pptx_file: UploadFile = File(...),
    image_meta: str = Form(default="[]"),
    image_files: List[UploadFile] = File(default=[]),
    style_prompt: str = Form(default=""),
):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        pdf_path = os.path.join(tmp, pdf_file.filename or "input.pdf")
        pptx_path = os.path.join(tmp, pptx_file.filename or "template.pptx")
        json_path = os.path.join(tmp, "filled.json")
        out_path = os.path.join(tmp, "output.pptx")

        with open(pdf_path, "wb") as f:
            f.write(await pdf_file.read())
        with open(pptx_path, "wb") as f:
            f.write(await pptx_file.read())

        # Save uploaded replacement images
        meta_list = json.loads(image_meta)
        img_replacements: dict[int, list] = {}
        for i, (meta, img_file) in enumerate(zip(meta_list, image_files)):
            ext = os.path.splitext(img_file.filename or "img.png")[1] or ".png"
            img_path = os.path.join(tmp, f"replacement_{i}{ext}")
            with open(img_path, "wb") as f:
                f.write(await img_file.read())
            slide_idx = meta["slide_index"]
            img_replacements.setdefault(slide_idx, []).append({
                "shape_id": meta["shape_id"],
                "path": img_path,
            })

        parsed = extract_text(pdf_path)
        schema = build_presentation_mapping(Path(pptx_path))
        count = count_schema_elements(schema)
        filler = get_filler_json(schema, parsed, count, style_prompt=style_prompt)
        # final = check_blanks(parsed, filler)
        final = filler

        # Inject image replacements into the filled JSON before applying
        for slide_idx, replacements in img_replacements.items():
            if slide_idx < len(final.get("slides", [])):
                final["slides"][slide_idx]["images"] = {
                    "by": "id",
                    "items": replacements,
                }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(final, f, ensure_ascii=False, indent=2)

        apply_json_to_pptx(pptx_in=pptx_path, json_in=json_path, pptx_out=out_path)

        with open(out_path, "rb") as f:
            pptx_bytes = f.read()

    # Convert the generated PPTX to PDF in a clean temp dir (avoids converting the template too)
    slides = []
    pdf_bytes = None

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as conv_tmp:
        pptx_conv = os.path.join(conv_tmp, "output.pptx")
        pdf_conv = os.path.join(conv_tmp, "output.pdf")

        with open(pptx_conv, "wb") as f:
            f.write(pptx_bytes)

        convert(conv_tmp, conv_tmp)

        if os.path.exists(pdf_conv):
            doc = fitz.open(pdf_conv)
            for idx, page in enumerate(doc):
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                thumbnail = base64.b64encode(pix.tobytes("png")).decode()
                slides.append({
                    "slide_index": idx,
                    "thumbnail": f"data:image/png;base64,{thumbnail}",
                })
            doc.close()
            with open(pdf_conv, "rb") as f:
                pdf_bytes = f.read()

    return JSONResponse({
        "pptx_base64": base64.b64encode(pptx_bytes).decode(),
        "pdf_base64": base64.b64encode(pdf_bytes).decode() if pdf_bytes else None,
        "slides": slides,
    })
