from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Annotated, Dict, Any
from pydantic import BaseModel
import google.generativeai as genai
import pdfplumber
import tempfile
import os
import json
import re
import time
import logging
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()



from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)
# API CONFIG
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set. Please configure it.")
genai.configure(api_key=api_key, transport="rest")

model = genai.GenerativeModel("gemini-2.5-flash-lite")

class ChatRequest(BaseModel):
    question: str
    context: List[Dict[str, Any]]
    history: List[Dict[str, Any]] = []


def extract_text(file_path: str) -> str:
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        return ""

    return text


def safe_generate(prompt, retries=3):
    for i in range(retries):
        try:
            return model.generate_content(prompt)

        except Exception as e:
            error_msg = str(e)

            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                wait = 2 ** i
                print(f"Rate limited → retrying in {wait}s")
                time.sleep(wait)
            else:
                raise e

    raise Exception("Gemini API failed after retries")


@app.get("/health")
async def health_check():
    logger.info("Health check endpoint was accessed")
    return {"status": "ok", "message": "Service is extremely healthy "}


@app.post("/analyze/")
async def analyze_resumes(
    files: Annotated[List[UploadFile], File()],
    jd: Annotated[str, Form()]
):

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    results = []

    for file in files:
        temp_path = None

        try:

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(await file.read())
                temp_path = tmp.name

        
            resume_text = extract_text(temp_path)

        
            if not resume_text.strip():
                raise Exception("Empty or unreadable PDF")

            
            resume_text = resume_text[:4000]

    
            prompt = f"""
You are an ATS system.

Return ONLY valid JSON.

Resume:
{resume_text}

Job Description:
{jd}

Format:
{{
"name": "",
"score": 0,
"strengths": [],
"gaps": [],
"summary": ""
}}
"""

        
            response = safe_generate(prompt)

            text_response = response.text.strip()

            
            match = re.search(r"\{.*\}", text_response, re.DOTALL)
            if not match:
                raise Exception("Invalid JSON from model")

            parsed = json.loads(match.group())

            parsed["score"] = int(parsed.get("score", 0))
            results.append(parsed)

        except Exception as e:
            results.append({
                "name": file.filename,
                "score": 0,
                "error": str(e)
            })

        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)


    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    return {
        "total_resumes": len(results),
        "results": results
    }


@app.post("/chat/")
async def chat_resumes(request: ChatRequest):
    if not request.context:
        raise HTTPException(status_code=400, detail="No resume context provided")

    prompt = f"""
You are an expert AI recruiting assistant. You are helping a recruiter answer questions about a batch of candidates.

Context (Analyzed Resumes):
{json.dumps(request.context, indent=2)}

Chat History:
{json.dumps(request.history, indent=2)}

Recruiter's Question:
{request.question}

Provide a clear, concise, and helpful answer to the recruiter's question based ONLY on the provided context.
"""

    def event_stream():
        try:
            response = model.generate_content(prompt, stream=True)
            for chunk in response:
                if chunk.text:
                    # SSE format
                    yield f"data: {json.dumps({'text': chunk.text})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")