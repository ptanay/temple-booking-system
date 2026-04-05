from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from model import predict_wait_time
import datetime
import sqlite3
import os
import io
import random
import qrcode
import razorpay

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "bookings.db")

# ✅ Razorpay
razorpay_client = razorpay.Client(
    auth=("rzp_test_SZfmvXDeJhwzmj", "svXahpkcH63cCsBkLuD4fDHg")
)

# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id TEXT,
        name TEXT,
        religion TEXT,
        location TEXT,
        visit_date TEXT,
        from_time TEXT,
        to_time TEXT,
        visitors INTEGER,
        booking_time TEXT,
        payment_id TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT,
        password TEXT
    )
    """)

    # ✅ NEW TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS temples(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        religion TEXT,
        name TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= ADD DEFAULT TEMPLES =================

def add_default_temples():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    temples = [

    ("Hindu","Tirumala Temple"),
    ("Hindu","Tirupati Temple"),
    ("Hindu","Kashi Vishwanath"),
    ("Hindu","Kedarnath"),
    ("Hindu","Rameswaram"),

    ("Muslim","Mecca Masjid"),
    ("Muslim","Charminar Mosque"),

    ("Christian","St Joseph Cathedral"),
    ("Christian","Velankanni Church"),

    ("Sikh","Golden Temple"),

    ("Buddhist","Bodh Gaya Temple"),

    ("Jain","Palitana Temple")

    ]

    for t in temples:
        cursor.execute("SELECT * FROM temples WHERE name=?", (t[1],))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO temples(religion,name) VALUES(?,?)", t)

    conn.commit()
    conn.close()

add_default_temples()

# ================= GET TEMPLES =================

@app.route("/temples/<religion>", methods=["GET"])
def get_temples(religion):

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM temples WHERE religion=?", (religion,))
    rows = cursor.fetchall()

    conn.close()

    temples = [r[0] for r in rows]

    return jsonify(temples)

# ================= PAYMENT =================

@app.route("/create_order", methods=["POST"])
def create_order():
    data = request.json

    if not data or "amount" not in data:
        return jsonify({"error": "Invalid amount"}), 400

    amount = int(data["amount"]) * 100

    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    return jsonify({
        "order_id": order["id"],
        "amount": amount
    })

# ================= RECEIPT =================

@app.route("/receipt", methods=["POST"])
def generate_receipt():

    data = request.get_json(silent=True) or request.form

    if not data:
        return jsonify({"error": "No data received"}), 400

    name = data.get("name", "Unknown")
    religion = data.get("religion", "Unknown")
    location = data.get("location", "Unknown Temple")
    date = data.get("date", "N/A")
    from_time = data.get("fromTime", "N/A")
    to_time = data.get("toTime", "N/A")
    visitors = data.get("visitors", 0)
    payment_id = data.get("payment_id", "N/A")

    booking_id = "BK" + str(random.randint(10000,99999))
    booking_time = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO bookings
    (booking_id,name,religion,location,visit_date,from_time,to_time,visitors,booking_time,payment_id)
    VALUES(?,?,?,?,?,?,?,?,?,?)
    """,(
        booking_id,
        name,
        religion,
        location,
        date,
        from_time,
        to_time,
        visitors,
        booking_time,
        payment_id
    ))

    conn.commit()
    conn.close()

    # PDF
    qr = qrcode.make(booking_id)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(420,600))
    elements = []

    style = ParagraphStyle(
        name="Title",
        fontSize=22,
        alignment=1,
        textColor=colors.darkred
    )

    elements.append(Paragraph(location.upper(), style))
    elements.append(Spacer(1,10))

    table_data = [
        ["Booking ID", booking_id],
        ["Name", name],
        ["Temple", location],
        ["Date", date],
        ["Time", f"{from_time} - {to_time}"],
        ["Visitors", visitors],
        ["Payment ID", payment_id],
        ["Status", "CONFIRMED"]
    ]

    table = Table(table_data)
    table.setStyle([
        ("GRID",(0,0),(-1,-1),1,colors.grey)
    ])

    elements.append(table)
    elements.append(Spacer(1,20))
    elements.append(Image(qr_buffer,120,120))

    doc.build(elements)

    buffer.seek(0)

    return send_file(buffer,
        as_attachment=True,
        download_name="Temple_Receipt.pdf",
        mimetype="application/pdf"
    )

# ================= OTHER APIs =================

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO users(username,email,password) VALUES(?,?,?)",
            (data["username"],data["email"],data["password"])
        )
        conn.commit()
        return jsonify({"status":"success"})
    except:
        return jsonify({"status":"fail"})
    finally:
        conn.close()


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (data["username"],data["password"])
    )

    user = cursor.fetchone()
    conn.close()

    return jsonify({"status":"success" if user else "fail"})


@app.route("/predict", methods=["POST"])
def predict():
    data = request.json

    visitors = int(data.get("visitors", 1))
    date = data.get("date")

    day = datetime.datetime.strptime(date,"%Y-%m-%d").weekday()
    predicted_time = predict_wait_time(visitors,day)

    return jsonify({"predicted_wait_time":round(predicted_time,2)})


@app.route("/history", methods=["GET"])
def history():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT booking_id,name,location,visit_date,from_time,to_time,visitors
    FROM bookings ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    data = []
    for r in rows:
        data.append({
            "booking_id": r[0],
            "name": r[1],
            "location": r[2],
            "visit_date": r[3],
            "from_time": r[4],
            "to_time": r[5],
            "visitors": r[6]
        })

    return jsonify(data)


@app.route("/delete_booking/<booking_id>", methods=["DELETE"])
def delete_booking(booking_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM bookings WHERE booking_id=?", (booking_id,))
    conn.commit()
    conn.close()

    return jsonify({"message":"deleted"})


# ================= RUN =================

if __name__ == "__main__":
    port = int(os.environ.get("PORT" ,5000))
    app.run(host="0.0.0.0", port=port)
