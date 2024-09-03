from fastapi import FastAPI, Request, Form, status, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import sqlite3
import nest_asyncio
from typing import Dict
from pydantic import BaseModel
from contextlib import contextmanager
from typing import Optional

nest_asyncio.apply()

app = FastAPI()
templates = Jinja2Templates(directory="templates")
security = HTTPBasic()

# Database setup
DATABASE_NAME = "users.db"

def init_db():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                registered_by TEXT NOT NULL,
                self_destruct BOOLEAN NOT NULL DEFAULT 0,
                utm_link TEXT,
                device_id TEXT,
                device_name TEXT,
                total_devices INTEGER DEFAULT 0
            )
        ''')
        conn.commit()

init_db()

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    try:
        yield conn
    finally:
        conn.close()

person_tokens = {
    "person1": "person1",
    "person2": "person2",
    "person3": "person3"
}

class User(BaseModel):
    email: str
    password: str
    registered_by: str
    self_destruct: bool = False
    utm_link: str = ""

class DeviceInfo(BaseModel):
    email: str
    device_id: str
    device_name: str

@app.get("/", response_class=HTMLResponse)
def registration_form(request: Request):
    return templates.TemplateResponse("registration.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
def register_user(request: Request, email: str = Form(...), password: str = Form(...), person: str = Form(...)):
    if person not in person_tokens.values():
        return templates.TemplateResponse("registration.html", {"request": request, "error": "Invalid person"})
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            return templates.TemplateResponse("registration.html", {"request": request, "error": "Email already registered"})
        
        cursor.execute("INSERT INTO users (email, password, registered_by, self_destruct, utm_link) VALUES (?, ?, ?, ?, ?)",
                       (email, password, person, False, ""))
        conn.commit()
    
    return templates.TemplateResponse("registration.html", {"request": request, "message": "User registered successfully"})

@app.post("/login")
def authenticate_user(email: str, password: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
        user = cursor.fetchone()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    return {"login_status": True, "message": "Login successful"}

def get_current_person(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username not in person_tokens or person_tokens[credentials.username] != credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid person token",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username



@app.post("/set_self_destruct")
def set_self_destruct(email: str, device_id: Optional[str] = None, self_destruct: bool = True, person: str = Depends(get_current_person)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if device_id:
            cursor.execute("SELECT * FROM users WHERE email = ? AND device_id = ?", (email, device_id))
            device = cursor.fetchone()
            
            if not device:
                raise HTTPException(status_code=404, detail="Device not found")
            
            if device[2] != person_tokens[person]:
                raise HTTPException(status_code=403, detail="Unauthorized to set self-destruct status for this device")
            
            cursor.execute("UPDATE users SET self_destruct = ? WHERE email = ? AND device_id = ?", (self_destruct, email, device_id))
            conn.commit()
            
            return {"message": f"Self-destruct status set to {self_destruct} for device {device_id} of {email}"}
        
        else:
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()
            
            if not user:
                raise HTTPException(status_code=404, detail="Email not found")
            
            if user[2] != person_tokens[person]:
                raise HTTPException(status_code=403, detail="Unauthorized to set self-destruct status for this user")
            
            cursor.execute("UPDATE users SET self_destruct = ? WHERE email = ?", (self_destruct, email))
            conn.commit()
            
            return {"message": f"Self-destruct status set to {self_destruct} for all devices of {email}"}

@app.get("/selfdestruct")
def check_self_destruct(email: str, device_id: Optional[str] = None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if device_id:
            cursor.execute("SELECT self_destruct FROM users WHERE email = ? AND device_id = ?", (email, device_id))
        else:
            cursor.execute("SELECT self_destruct FROM users WHERE email = ?", (email,))
        result = cursor.fetchone()
    
    if not result:
        if device_id:
            raise HTTPException(status_code=404, detail="Device not found")
        else:
            raise HTTPException(status_code=404, detail="Email not found")
    
    return {"self_destruct": bool(result[0])}

@app.post("/set_utm_link")
def set_utm_link(email: str, utm_link: str, person: str = Depends(get_current_person)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET utm_link = ? WHERE email = ?", (utm_link, email))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Email not found")
        conn.commit()
    
    return {"message": f"UTM link set for {email}"}

@app.get("/get_utm_link")
def get_utm_link(email: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT utm_link FROM users WHERE email = ?", (email,))
        result = cursor.fetchone()
    
    if not result:
        raise HTTPException(status_code=404, detail="Email not found or UTM link not set")
    
    return {"utm_link": result[0]}

@app.get("/protected")
def protected_route(person: str = Depends(get_current_person)):
    return {"message": "Access granted"}

@app.get("/registered_accounts")
def get_registered_accounts(person: str = Depends(get_current_person)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT email, registered_by, self_destruct, utm_link, total_devices,
                   GROUP_CONCAT(device_id) AS device_ids
            FROM users
            WHERE registered_by = ?
            GROUP BY email
        """, (person_tokens[person],))
        accounts = [
            {
                "email": row[0],
                "registered_by": row[1],
                "self_destruct": bool(row[2]),
                "utm_link": row[3],
                "total_devices": row[4],
                "device_ids": row[5].split(",") if row[5] else []
            }
            for row in cursor.fetchall()
        ]
    
    if not accounts:
        raise HTTPException(status_code=404, detail="No accounts found for the given person")
    
    return {"accounts": accounts}

@app.post("/register_device")
def register_device(device_info: DeviceInfo):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (device_info.email,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="Email not found")
        
        cursor.execute("UPDATE users SET device_id = ?, device_name = ?, total_devices = total_devices + 1 WHERE email = ?",
                       (device_info.device_id, device_info.device_name, device_info.email))
        conn.commit()
    
    return {"message": "Device registered successfully"}

@app.post("/self_destruct_device")
def self_destruct_device(email: str, device_id: str, person: str = Depends(get_current_person)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ? AND device_id = ?", (email, device_id))
        device = cursor.fetchone()
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        cursor.execute("UPDATE users SET self_destruct = 1 WHERE email = ? AND device_id = ?", (email, device_id))
        conn.commit()
    
    return {"message": f"Self-destruct signal sent to device {device_id} for {email}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9006)
