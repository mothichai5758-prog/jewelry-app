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
        if order["code"] == product_code:
            order["status"] = "อนุมัติผลิต"
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
        if order["code"] == product_code:
            for s in order["sizes"]:
                if s["size_th"] == size_th:
                    s["received"] = min(s["qty"], s.get("received", 0) + qty)
                    save_data(orders_db)
                    return {"status": "success", "order": order}
    return {"status": "not found"}

@app.get("/api/orders/{product_code}/pdf")
def generate_pdf(product_code: str):
    order = next((o for o in orders_db if o["code"] == product_code), None)
    if not order:
        return {"detail": "Order not found"}
    
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter, 
            rightMargin=30, 
            leftMargin=30, 
            topMargin=30, 
            bottomMargin=30
        )
        elements = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Title'],
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            alignment=1
        )
        elements.append(Paragraph(f"PRODUCTION WORK ORDER: {order['code']}", title_style))
        elements.append(Spacer(1, 12))
        
        info_text = f"Status: {order.get('status', '-')} | Target Weight: {order.get('weight', '-')} | Factory: {order.get('factory', '-')} | Due Date: {order.get('dueDate') or '-'}"
        elements.append(Paragraph(info_text, styles['Normal']))
        elements.append(Spacer(1, 15))
        
        table_data = [["Size (TH)", "Size (US)", "Target Qty", "Received", "Pending"]]
        for item in order.get("sizes", []):
            rem = item.get("qty", 0) - item.get("received", 0)
            table_data.append([
                str(item.get("size_th", "")),
                str(item.get("size_us", "")),
                str(item.get("qty", 0)),
                str(item.get("received", 0)),
                str(rem)
            ])
            
        t = Table(table_data, colwidths=[90, 90, 100, 100, 100])
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t)
        
        doc.build(elements)
        buffer.seek(0)
        
        return StreamingResponse(
            buffer, 
            media_type="application/pdf", 
            headers={
                "Content-Disposition": f"inline; filename=work_order_{product_code}.pdf"
            }
        )
    except Exception as e:
        return {"error": str(e)}
