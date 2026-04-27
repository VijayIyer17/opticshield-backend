from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid
import sqlite3
import json
from core_engine import generate_video_dna, compare_videos

# Initialize FastAPI App
app = FastAPI(title="SportsShield API", version="1.0.0 (Persistent Pro)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

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
                status TEXT NOT NULL
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
# 1. INGEST ENDPOINT (Removed 'async' to prevent blocking issues)
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
                    INSERT INTO alerts (id, matched_asset, confidence, status) 
                    VALUES (?, ?, ?, ?)
                ''', (alert_id, asset_id, result["confidence"], "OPEN"))
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
            "status": row['status']
        }
        
    return {"total_alerts": len(active_alerts), "active_alerts": active_alerts}

# ---------------------------------------------------------
# 5. TAKE ACTION ENDPOINT
# ---------------------------------------------------------
@app.post("/api/alerts/{alert_id}/action")
def take_action(alert_id: str):
    with get_db_connection() as conn:
        conn.execute('UPDATE alerts SET status = ? WHERE id = ?', ("RESOLVED (ACTION TAKEN)", alert_id))
        conn.commit()
        
    # --- GEMINI AI INTEGRATION ---
    try:
        genai.configure(api_key="TUMHARI_GEMINI_API_KEY_YAHAN_DALO")
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Write a very short 2-line automated DMCA takedown legal notice for threat ID {alert_id} involving stolen sports broadcasting rights."
        response = model.generate_content(prompt)
        ai_generated_notice = response.text
    except:
        ai_generated_notice = "Standard Automated DMCA Notice Dispatched."

    return {
        "status": "success", 
        "message": "Automated Action dispatched.",
        "ai_analysis": ai_generated_notice
    }