from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from typing import List, Annotated
import google.generativeai as genai
import pdfplumber
import tempfile
import os
import json
import re
import time

app = FastAPI()



from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 🔥 allow all
    allow_credentials=True,
    allow_methods=["*"],   # 🔥 allow all methods
    allow_headers=["*"],   # 🔥 allow all headers
)
# 🔑 API CONFIG
genai.configure(api_key="your api key", transport="rest")

# 🤖 MODEL (IMPORTANT: OUTSIDE LOOP)
model = genai.GenerativeModel("gemini-2.5-flash-lite")


# 📄 PDF TEXT EXTRACTION
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


# 🔁 SAFE GEMINI CALL (FIXES 429 ERROR)
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


# 🚀 MAIN API
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
            # 📌 Save temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(await file.read())
                temp_path = tmp.name

            # 📌 Extract text
            resume_text = extract_text(temp_path)

            # ❌ Skip empty PDFs
            if not resume_text.strip():
                raise Exception("Empty or unreadable PDF")

            # ✂️ REDUCE TOKEN USAGE (IMPORTANT)
            resume_text = resume_text[:4000]

            # 🧠 PROMPT
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

            # 🤖 CALL GEMINI (SAFE)
            response = safe_generate(prompt)

            text_response = response.text.strip()

            # 📌 Extract JSON safely
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

    # 🏆 SORT RESULTS
    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    return {
        "total_resumes": len(results),
        "results": results
    }