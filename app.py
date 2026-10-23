import os
import json
import io
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

app = FastAPI()

# เปิดให้เชื่อมต่อได้จากทุกอุปกรณ์
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ฐานข้อมูลส่วนกลางในหน่วยความจำเซิร์ฟเวอร์
orders_db = []

@app.get("/")
def home():
    return FileResponse("index.html")

# ดึงรายการสั่งผลิตทั้งหมด
@app.get("/api/orders")
def get_orders():
    return orders_db

# สร้างคำสั่งผลิตใหม่ (ตั้งสถานะเริ่มต้นเป็น 'รออนุมัติ')
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
    return {"status": "success", "order": order_data}

# อนุมัติการผลิต
@app.post("/api/orders/approve")
async def approve_order(product_code: str = Form(...)):
    for order in orders_db:
        if order["code"] == product_code:
            order["status"] = "อนุมัติผลิต"
            return {"status": "success", "order": order}
    return {"status": "not found"}

# รับชิ้นงานเข้าคลัง (ตัดยอดค้างรับ)
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
                    return {"status": "success", "order": order}
    return {"status": "not found"}

# ออกใบสั่งผลิตเป็น PDF
@app.get("/api/orders/{product_code}/pdf")
def generate_pdf(product_code: str):
    order = next((o for o in orders_db if o["code"] == product_code), None)
    if not order:
        return {"detail": "Order not found"}
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"PRODUCTION WORK ORDER: {order['code']}", styles['Title']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Status: {order['status']} | Weight: {order['weight']} | Factory: {order['factory']} | Due: {order['dueDate'] or '-'}", styles['Normal']))
    elements.append(Spacer(1, 15))
    
    table_data = [["Size TH", "Size US", "Ordered Qty", "Received", "Pending"]]
    for item in order["sizes"]:
        rem = item["qty"] - item.get("received", 0)
        table_data.append([item["size_th"], item["size_us"], str(item["qty"]), str(item.get("received", 0)), str(rem)])
        
    t = Table(table_data, colwidths=[90, 90, 100, 100, 100])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t)
    
    doc.build(elements)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"inline; filename={product_code}.pdf"})
