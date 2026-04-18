# AI Resume Screener

This project is an AI-powered Resume Screener using FastAPI, Google Generative AI (Gemini), and `pdfplumber`. It exposes API endpoints to analyze a batch of PDF resumes against a job description, return ranked results, and query the analyzed resumes using a real-time Chat API.

## Features
- Extract text from PDF resumes.
- Evaluate resumes against a Job Description (JD) using Gemini (`gemini-2.5-flash-lite`).
- Provide scores, strengths, gaps, and summaries for each candidate.
- Real-time chatting interface (streaming responses) to query about processed candidates.

## Prerequisites
- Python 3.8+
- [Google Gemini API Key](https://aistudio.google.com/app/apikey)

## Setup Instructions

**1. Clone (https://github.com/Anushka-Singh02102002/ai_resume_screener/tree/main) or navigate to the repository:**
```bash
git clone https://github.com/Anushka-Singh02102002/ai_resume_screener.gits
cd ai_resume_screener
```

**2. Create a virtual environment (recommended):**
```bash
python3 -m venv myenv
source myenv/bin/activate  # On Windows use `myenv\Scripts\activate`
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Configure Environment Variables:**
Create a `.env` file in the root directory (or update the existing one) and add your Gemini API Key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

**5. Run the server:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
The server will start at `http://localhost:8000`.

## API Endpoints

### 1. Health Check
* **Endpoint:** `GET /health`
* **Response:** Verifies if the service is running successfully.

### 2. Analyze Resumes
* **Endpoint:** `POST /analyze/`
* **Content-Type:** `multipart/form-data`
* **Payload:** 
  - `files`: List of PDF files to be uploaded.
  - `jd`: A string containing the Job Description.
* **Returns:** JSON containing total resumes processed and their respective evaluations (Score, Strengths, Gaps, Summary), sorted by highest score.

### 3. Chat with Resumes Context
* **Endpoint:** `POST /chat/`
* **Content-Type:** `application/json`
* **Payload:**
  - `question`: A string detailing the question you want to ask.
  - `context`: List of dictionary objects containing evaluated resume data (from the `/analyze/` endpoint).
  - `history`: (Optional) List of chat history objects to maintain conversation context.
* **Returns:** Server-Sent Events (SSE) stream containing the generated answers chunk by chunk.

## API Documentation
Once the server is running, you can access the automatic interactive API documentation provided by FastAPI at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
