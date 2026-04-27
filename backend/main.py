from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid
import sqlite3
import json
import google.generativeai as genai
from core_engine import generate_video_dna, compare_videos

# Initialize FastAPI App
app = FastAPI(title="SportsShield API", version="2.0.0 (AI Powered)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)


GEMINI_API_KEY = "AIzaSyBsmbUOOdKIdwCGUKsvhoZ3NsVIGG94Zw8"

try:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"AI Config Error: {e}")

DB_FILE = "opticshield.db"
os.makedirs("temp", exist_ok=True)

# ---------------------------------------------------------
# DATABASE INITIALIZATION
# ---------------------------------------------------------
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assets (
                id TEXT PRIMARY KEY,
                dna TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                matched_asset TEXT NOT NULL,
                confidence TEXT NOT NULL,
                status TEXT NOT NULL,
                ai_notice TEXT
            )
        ''')
        conn.commit()

init_db()

def get_db_connection():
    # 🔥 FIX: check_same_thread=False prevents FastAPI threading crashes
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    return conn

# ---------------------------------------------------------
# 1. INGEST ENDPOINT
# ---------------------------------------------------------
@app.post("/api/ingest")
def ingest_asset(asset_id: str = Query(...), file: UploadFile = File(...)):
    temp_path = f"temp/official_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    dna = generate_video_dna(temp_path)
    os.remove(temp_path)
    
    if not dna: 
        raise HTTPException(status_code=400, detail="DNA Generation Failed")
        
    try:
        with get_db_connection() as conn:
            conn.execute('INSERT OR REPLACE INTO assets (id, dna) VALUES (?, ?)', 
                         (asset_id, json.dumps(dna)))
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "success", "asset_id": asset_id, "message": "Asset secured in SQLite DB."}

# ---------------------------------------------------------
# 2. GET ASSETS ENDPOINT
# ---------------------------------------------------------
@app.get("/api/assets")
def get_assets():
    with get_db_connection() as conn:
        rows = conn.execute('SELECT id, dna FROM assets').fetchall()
    
    safe_data = {}
    for row in rows:
        dna_list = json.loads(row['dna'])
        safe_data[row['id']] = f"Protected ({len(dna_list)} frames)"
        
    return {"total_assets": len(safe_data), "assets": safe_data}

# ---------------------------------------------------------
# 3. SCAN ENDPOINT
# ---------------------------------------------------------
@app.post("/api/scan")
def scan_youtube(file: UploadFile = File(...)):
    temp_path = f"temp/scan_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    with get_db_connection() as conn:
        assets = conn.execute('SELECT id, dna FROM assets').fetchall()
        
    for asset in assets:
        asset_id = asset['id']
        official_dna = json.loads(asset['dna'])
        
        result = compare_videos(official_dna, temp_path)
        
        if result.get("is_pirated"):
            alert_id = f"ALT-{uuid.uuid4().hex[:6].upper()}"
            
            with get_db_connection() as conn:
                conn.execute('''
                    INSERT INTO alerts (id, matched_asset, confidence, status, ai_notice) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (alert_id, asset_id, result["confidence"], "OPEN", "Pending AI Analysis"))
                conn.commit()
                
            os.remove(temp_path)
            return {"status": "🚨 ALERT", "message": "Infringement Detected!", "details": result}
            
    os.remove(temp_path)
    return {"status": "✅ SAFE", "message": "No match found."}

# ---------------------------------------------------------
# 4. GET ALERTS ENDPOINT
# ---------------------------------------------------------
@app.get("/api/alerts")
def get_alerts():
    with get_db_connection() as conn:
        rows = conn.execute('SELECT * FROM alerts').fetchall()
        
    active_alerts = {}
    for row in rows:
        active_alerts[row['id']] = {
            "matched_asset": row['matched_asset'],
            "confidence": row['confidence'],
            "status": row['status'],
            "ai_notice": row.get('ai_notice', '')
        }
        
    return {"total_alerts": len(active_alerts), "active_alerts": active_alerts}

# ---------------------------------------------------------
# 5. TAKE ACTION ENDPOINT (POWERED BY GEMINI AI)
# ---------------------------------------------------------
@app.post("/api/alerts/{alert_id}/action")
def take_action(alert_id: str):
    # Fetch Alert details to give context to AI
    with get_db_connection() as conn:
        alert = conn.execute('SELECT * FROM alerts WHERE id = ?', (alert_id,)).fetchone()
        
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Generate Dynamic Legal Notice using Gemini AI
    ai_generated_notice = "Standard Automated Action Dispatched."
    try:
        prompt = f"""
        You are an AI legal assistant for a sports broadcasting network. 
        Write a strict, professional 2-line DMCA takedown notice for a copyright violation.
        Details:
        - Stolen Asset ID: {alert['matched_asset']}
        - System Alert ID: {alert_id}
        - Match Confidence: {alert['confidence']}
        State clearly that the unauthorized broadcast must be removed immediately.
        """
        response = ai_model.generate_content(prompt)
        ai_generated_notice = response.text.strip()
    except Exception as e:
        print(f"Gemini AI Error: {e}")

    # Update DB with new status and AI Notice
    with get_db_connection() as conn:
        conn.execute('UPDATE alerts SET status = ?, ai_notice = ? WHERE id = ?', 
                     ("RESOLVED (ACTION TAKEN)", ai_generated_notice, alert_id))
        conn.commit()
        
    return {
        "status": "success", 
        "message": "Automated Action dispatched and logged in Database.",
        "ai_notice": ai_generated_notice
    }