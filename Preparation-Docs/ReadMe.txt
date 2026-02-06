Running the frontend
-----------------------------------------------
- install node.js 
- cd frontend
- npm run dev


Running the Backend:
------------------------------------------------
- first run a virtual env
    1. cd backend
    2. py -3 -m venv .venv
    3. .venv\Scripts\Activate.ps1

- install pdfminer
    - pip install pdfminer.six
-install fastapi and uvicorn
    - pip install fastapi uvicorn
-install python-multipart
    - pip install python-multipart

- uvicorn main:app --reload --port 8000