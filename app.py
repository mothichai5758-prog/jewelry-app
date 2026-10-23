import os
import json
import io
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = "orders_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

orders_db = load_data()

@app.get("/")
def home():
    return FileResponse("index.html")

@app.get("/api/orders")
def get_orders():
    return orders_db

@app.post("/api/orders/create")
async def create_order(
    product_code: str = Form(...),
    target_weight: str = Form(...),
    details_json: str = Form(...),
    factory_name: str = Form("โรงงานช่างทอง 1"),
    due_date: str = Form(""),
    image: UploadFile = File(None)
):
    details = json.loads(details_json)
    order_data = {
        "code": product_code,
        "weight": target_weight,
        "factory": factory_name,
        "dueDate": due_date,
        "sizes": details,
        "status": "รออนุมัติ"
    }
    orders_db.insert(0, order_data)
    save_data(orders_db)
    return {"status": "success", "order": order_data}

@app.post("/api/orders/approve")
async def approve_order(product_code: str = Form(...)):
    for order in orders_db:
        if order.get("code") == product_code:
            order["status"] = "อนุมัติผลิต"
            save_data(orders_db)
            return {"status": "success", "order": order}
    return {"status": "not found"}

@app.post("/api/orders/delete")
async def delete_order(product_code: str = Form(...)):
    global orders_db
    orders_db = [o for o in orders_db if o.get("code") != product_code]
    save_data(orders_db)
    return {"status": "success"}

@app.post("/api/orders/update")
async def update_order(
    product_code: str = Form(...),
    target_weight: str = Form(...),
    factory_name: str = Form(...),
    due_date: str = Form(""),
    details_json: str = Form(...)
):
    details = json.loads(details_json)
    for order in orders_db:
        if order.get("code") == product_code:
            order["weight"] = target_weight
            order["factory"] = factory_name
            order["dueDate"] = due_date
            order["sizes"] = details
            save_data(orders_db)
            return {"status": "success", "order": order}
    return {"status": "not found"}

@app.post("/api/orders/receive")
async def receive_item(
    product_code: str = Form(...),
    size_th: str = Form(...),
    qty: int = Form(...)
):
    for order in orders_db:
        if order.get("code") == product_code:
            for s in order.get("sizes", []):
                if s.get("size_th") == size_th:
                    s["received"] = min(s.get("qty", 0), s.get("received", 0) + qty)
                    save_data(orders_db)
                    return {"status": "success", "order": order}
    return {"status": "not found"}

@app.get("/api/orders/{product_code}/pdf")
def generate_pdf(product_code: str):
    order = next((o for o in orders_db if str(o.get("code")) == str(product_code)), None)
    if not order:
        return {"detail": "Order not found"}
    
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        elements = []
        styles = getSampleStyleSheet()

        p_code = str(order.get("code", "-"))
        p_weight = str(order.get("weight", "-"))
        p_factory = str(order.get("factory", "-"))
        p_due = str(order.get("dueDate", "-") or "-")
        p_status = str(order.get("status", "-"))

        title_p = Paragraph("<b>JEWELRY PRODUCTION ORDER</b>", styles['Title'])
        elements.append(title_p)
        elements.append(Spacer(1, 15))

        info_data = [
            [f"Order Code: {p_code}", f"Status: {p_status}"],
            [f"Target Weight: {p_weight}", f"Due Date: {p_due}"],
            [f"Factory / Dept: {p_factory}", ""]
        ]
        info_table = Table(info_data, colwidths=[270, 270])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 20))

        table_rows = [["Size (TH)", "Size (US)", "Target Qty", "Received", "Pending"]]
        for item in order.get("sizes", []):
            qty = int(item.get("qty", 0) or 0)
            rec = int(item.get("received", 0) or 0)
            table_rows.append([
                str(item.get("size_th", "")),
                str(item.get("size_us", "")),
                str(qty),
                str(rec),
                str(max(0, qty - rec))
            ])

        size_table = Table(table_rows, colwidths=[100, 100, 110, 110, 120])
        size_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.Color(0.8, 0.8, 0.8)),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('BACKGROUND', (0,0), (-1,0), colors.Color(0.95, 0.95, 0.95)),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(size_table)

        doc.build(elements)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=work_order_{p_code}.pdf"
            }
        )
    except Exception as e:
        print("PDF Generation Error:", str(e))
        return {"error": str(e)}
