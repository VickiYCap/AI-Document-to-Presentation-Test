# AI Document to Presentation

Convert any PDF document into a polished PowerPoint presentation using AI.

## How It Works

1. **Upload your PDF** — provide the source document containing the content you want in your presentation
2. **Upload your template** — choose a `.pptx` file that defines the layout and style of your slides
3. **Add an optional prompt** — customize the tone or wording style the AI uses when generating slide content
4. **Click Next** — move to the image replacement step
5. **Replace images** — swap template images with ones extracted from your PDF or uploaded from your device
6. **Generate & download** — export the finished presentation as a `.pptx` or `.pdf`

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite |
| Backend | Python (FastAPI / Flask) |
| AI | Claude (Anthropic) |
| Parsing | `python-pptx`, PDF parser |

## Project Structure

```
├── backend/
│   ├── main.py             # API entry point
│   ├── document_parser.py  # PDF parsing logic
│   ├── pptx_parser.py      # PowerPoint template analysis
│   ├── json_creator.py     # AI-driven content generation
│   └── prompts.py          # LLM prompt templates
└── frontend/
    ├── index.html
    └── src/
```

## Getting Started

### Backend

```bash
cd backend
pip install -r requirements.txt

```

### Frontend

```bash
cd frontend
npm install
npm run dev
```
