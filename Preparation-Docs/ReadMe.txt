Running the frontend
-----------------------------------------------
- install node.js 
- install react-router-dom
- npm install pdfjs-dist
- cd frontend
- npm run dev


Running the Backend:
------------------------------------------------
- first run a virtual env
    1. cd backend
    2. py -3 -m venv .venv
    3. .venv\Scripts\Activate.ps1

- install pdfminer
    - pip install pdfminer.six fastapi uvicorn python-multipart python-pptx comtypes

- uvicorn main:app --reload --port 8000