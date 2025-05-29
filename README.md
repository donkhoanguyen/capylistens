# CAPY Listen 🎧

## Prototype App
This project is a simple prototype consisting of a FastAPI backend and a static HTML frontend. Follow the steps below to set up and run the application locally.

## 🚀 Project Structure

```
project-root/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── ... (other backend files)
├── web_frontend/
│   ├── app2.html
│   └── ... (other frontend files)
```

## 🔧 Backend Setup (FastAPI)

### Create a virtual environment
You can use pyenv or venv. Example with venv:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Start the FastAPI server
Make sure uvicorn is installed (included in requirements.txt), then run:

```bash
uvicorn main:app --reload --port 8000
```

Server will start at: http://127.0.0.1:8000

## 🌐 Frontend Setup (Static HTML)

Open a new terminal window and navigate to the web_frontend directory:

```bash
cd web_frontend
```

Start a simple HTTP server (Python 3):

```bash
python -m http.server 8080
```

Frontend will be available at: http://localhost:8080/app2.html

## 📝 Notes
- Ensure both backend and frontend are running simultaneously.
- The frontend communicates with the backend on port 8000, so CORS should be handled appropriately if needed.

## 📦 Requirements
- Python 3.7+
- FastAPI
- Uvicorn
- Any additional packages listed in requirements.txt
