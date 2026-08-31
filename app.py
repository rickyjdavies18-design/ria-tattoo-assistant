from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from datetime import date, timedelta
import sqlite3

DB = "ria.db"
app = FastAPI(title="Ria - Tattoo Assistant")


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS customers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      full_name TEXT, phone TEXT, email TEXT, instagram TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS enquiries (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      route TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'new_enquiry',
      tattoo_type TEXT, idea TEXT, placement TEXT, rough_size TEXT,
      style_pref TEXT, reference_notes TEXT, preferred_timing TEXT,
      customer_id INTEGER, quoted_price INTEGER, session_type TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS bookings (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      enquiry_id INTEGER, customer_id INTEGER,
      appointment_date TEXT UNIQUE,
      start_time TEXT DEFAULT '10:00',
      session_type TEXT NOT NULL,
      total_price INTEGER NOT NULL,
      deposit_amount INTEGER DEFAULT 50,
      deposit_status TEXT DEFAULT 'pending',
      status TEXT DEFAULT 'provisional',
      notes TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL,
      event TEXT NOT NULL, detail TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    conn.commit()
    conn.close()

init_db()

def log(entity_type, entity_id, event, detail=""):
    conn = db()
    conn.execute("INSERT INTO history(entity_type,entity_id,event,detail) VALUES(?,?,?,?)",
                 (entity_type, entity_id, event, detail))
    conn.commit()
    conn.close()

def session_for_date(d: date):
    wd = d.weekday()
    if wd == 2:
        return ("Wednesday half-day", 300, 250)
    if wd in (0,1,3,4):
        return ("Full-day", 450, 400)
    return None

def available_dates(days=90):
    conn = db()
    booked = {r["appointment_date"] for r in conn.execute("SELECT appointment_date FROM bookings")}
    conn.close()
    out = []
    cur = date.today()
    for i in range(days):
        d = cur + timedelta(days=i)
        sess = session_for_date(d)
        if sess and d.isoformat() not in booked:
            out.append({
                "date": d.isoformat(),
                "label": d.strftime("%a %d %b"),
                "session_type": sess[0],
                "price": sess[1],
                "balance": sess[2],
            })
    return out

class EnquiryIn(BaseModel):
    route: str
    tattoo_type: Optional[str] = None
    idea: Optional[str] = None
    placement: Optional[str] = None
    rough_size: Optional[str] = None
    style_pref: Optional[str] = None
    reference_notes: Optional[str] = None
    preferred_timing: Optional[str] = None

class BookingIn(BaseModel):
    enquiry_id: int
    appointment_date: str
    full_name: str
    phone: str
    email: str
    instagram: Optional[str] = ""

@app.get("/", response_class=HTMLResponse)
def home():
    return open("index.html", encoding="utf-8").read()

@app.get("/api/dashboard")
def dashboard():
    conn = db()
    counts = {}
    for s in ["new_enquiry","waiting_reference","needs_ricky","awaiting_deposit","confirmed","completed"]:
        counts[s] = conn.execute("SELECT COUNT(*) c FROM enquiries WHERE status=?", (s,)).fetchone()["c"]
    today = date.today().isoformat()
    todays = [dict(r) for r in conn.execute('''
      SELECT b.*, c.full_name, c.instagram FROM bookings b
      LEFT JOIN customers c ON c.id=b.customer_id
      WHERE b.appointment_date=? ORDER BY b.start_time
    ''', (today,))]
    conn.close()
    return {"counts": counts, "today": todays}

@app.get("/api/enquiries")
def enquiries():
    conn = db()
    rows = [dict(r) for r in conn.execute('''
      SELECT e.*, c.full_name, c.phone, c.email, c.instagram
      FROM enquiries e LEFT JOIN customers c ON c.id=e.customer_id
      ORDER BY e.id DESC
    ''')]
    conn.close()
    return rows

@app.post("/api/enquiries")
def create_enquiry(data: EnquiryIn):
    status = "needs_ricky" if data.route in ("personal","existing") else "new_enquiry"
    conn = db()
    cur = conn.execute('''
      INSERT INTO enquiries(route,status,tattoo_type,idea,placement,rough_size,style_pref,reference_notes,preferred_timing)
      VALUES(?,?,?,?,?,?,?,?,?)
    ''', (data.route,status,data.tattoo_type,data.idea,data.placement,data.rough_size,
          data.style_pref,data.reference_notes,data.preferred_timing))
    eid = cur.lastrowid
    conn.commit()
    conn.close()
    log("enquiry", eid, "created", data.route)
    return {"id": eid, "status": status}

@app.patch("/api/enquiries/{eid}")
async def update_enquiry(eid: int, request: Request):
    body = await request.json()
    allowed = ["status","tattoo_type","idea","placement","rough_size","style_pref","reference_notes","preferred_timing"]
    sets, vals = [], []
    for k in allowed:
        if k in body:
            sets.append(f"{k}=?")
            vals.append(body[k])
    if not sets:
        return {"ok": True}
    vals.append(eid)
    conn = db()
    conn.execute(f"UPDATE enquiries SET {', '.join(sets)}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)
    conn.commit()
    conn.close()
    log("enquiry", eid, "updated", str(body))
    return {"ok": True}

@app.get("/api/availability")
def availability():
    return available_dates()

@app.post("/api/bookings")
def create_booking(data: BookingIn):
    try:
        d = date.fromisoformat(data.appointment_date)
    except Exception:
        return JSONResponse({"error":"Invalid date"}, status_code=400)
    sess = session_for_date(d)
    if not sess:
        return JSONResponse({"error":"Ria only books Monday to Friday, with Wednesday as half-day."}, status_code=400)

    conn = db()
    if conn.execute("SELECT 1 FROM bookings WHERE appointment_date=?", (data.appointment_date,)).fetchone():
        conn.close()
        return JSONResponse({"error":"That date is already booked."}, status_code=409)

    cur = conn.execute("INSERT INTO customers(full_name,phone,email,instagram) VALUES(?,?,?,?)",
                       (data.full_name,data.phone,data.email,data.instagram))
    cid = cur.lastrowid
    conn.execute("UPDATE enquiries SET customer_id=?,status='awaiting_deposit',session_type=?,quoted_price=? WHERE id=?",
                 (cid,sess[0],sess[1],data.enquiry_id))
    cur = conn.execute('''
      INSERT INTO bookings(enquiry_id,customer_id,appointment_date,session_type,total_price)
      VALUES(?,?,?,?,?)
    ''', (data.enquiry_id,cid,data.appointment_date,sess[0],sess[1]))
    bid = cur.lastrowid
    conn.commit()
    conn.close()
    log("booking", bid, "provisional_created", data.appointment_date)
    return {"booking_id":bid,"customer_id":cid,"session_type":sess[0],
            "total_price":sess[1],"deposit":50,"balance":sess[2]}

@app.post("/api/bookings/{bid}/mark-deposit-paid")
def mark_paid(bid: int):
    conn = db()
    row = conn.execute("SELECT enquiry_id FROM bookings WHERE id=?", (bid,)).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error":"Not found"}, status_code=404)
    conn.execute("UPDATE bookings SET deposit_status='paid',status='confirmed' WHERE id=?", (bid,))
    conn.execute("UPDATE enquiries SET status='confirmed' WHERE id=?", (row["enquiry_id"],))
    conn.commit()
    conn.close()
    log("booking", bid, "deposit_paid", "£50")
    return {"ok": True}

@app.get("/api/customers")
def customers(q: Optional[str] = ""):
    conn = db()
    if q:
        like = f"%{q}%"
        rows = [dict(r) for r in conn.execute('''
          SELECT * FROM customers WHERE full_name LIKE ? OR phone LIKE ? OR email LIKE ? OR instagram LIKE ?
          ORDER BY id DESC
        ''', (like,like,like,like))]
    else:
        rows = [dict(r) for r in conn.execute("SELECT * FROM customers ORDER BY id DESC")]
    conn.close()
    return rows

@app.get("/api/integrations")
def integrations():
    return {
      "instagram_meta":{"connected":False,"status":"Not connected"},
      "stripe":{"connected":False,"status":"Not connected"}
    }
