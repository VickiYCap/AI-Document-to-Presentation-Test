from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from extractor import parse_pdf_bytes 
from extractor import chunk_text

app = FastAPI()

# Allow Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#checks if the server is running
@app.get("/")
def health():
    return {"status": "ok"}

#endpoint to upload PDF and extract text
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF")

    #read uploaded file into memory
    data = await file.read()  
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    # Hand off to extractor.py
    text = parse_pdf_bytes(data)

    if not text.strip():
        raise HTTPException(status_code=422, detail="No extractable text (maybe a scanned PDF)")

    chunks = list(chunk_text(text, max_chars=2000, overlap=200))


    formatted = "\n\n--- CHUNK ---\n\n".join(chunks)

    return JSONResponse({
        "ok": True,
        "filename": file.filename,
        "length": len(chunks),
        "text": formatted
    })
