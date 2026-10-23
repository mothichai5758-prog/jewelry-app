import os
import shutil
import json
from io import BytesIO
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Spacer
from reportlab.lib import colors

app = FastAPI(title="Jewelry Order System")

# เปิดสิทธิ์ CORS ให้หน้าเว็บเรียกใช้งานได้
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploaded_drawings"
os.makedirs(UPLOAD_DIR, exist_ok=True)
orders_db = {}

@app.post("/api/orders/create")
async def create_order(
    product_code: str = Form(...),
    weight_desc: str = Form(...),
    order_date: str = Form(...),
    items_json: str = Form(...),
    image_file: Optional[UploadFile] = File(None)
):
    saved_image_path = None
    if image_file:
        ext = image_file.filename.split(".")[-1]
        saved_image_path = os.path.join(UPLOAD_DIR, f"{product_code}.{ext}")
        with open(saved_image_path, "wb") as buffer:
            shutil.copyfileobj(image_file.file, buffer)
            
    items = json.loads(items_json)
    for item in items:
        item["received"] = 0
        
    orders_db[product_code] = {
        "product_code": product_code,
        "weight_desc": weight_desc,
        "order_date": order_date,
        "image_path": saved_image_path,
        "items": items
    }
    return {"status": "success", "product_code": product_code}

@app.get("/api/orders/{product_code}/pdf")
def export_pdf(product_code: str):
    if product_code not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order = orders_db[product_code]
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    
    if order["image_path"] and os.path.exists(order["image_path"]):
        img = Image(order["image_path"], width=180, height=180)
        elements.append(img)
        elements.append(Spacer(1, 15))
        
    table_data = [["Product", "Weight", "Size\n(TH)", "Size (US)", "QTY", "Total"]]
    total_qty = sum(int(item["qty"]) for item in order["items"])
    num_rows = len(order["items"])
    
    for idx, item in enumerate(order["items"]):
        row = [
            order["product_code"] if idx == 0 else "",
            order["weight_desc"] if idx == 0 else "",
            str(item.get("size_th", "")),
            str(item.get("size_us", "")),
            str(item.get("qty", "")),
            str(total_qty) if idx == 0 else ""
        ]
        table_data.append(row)
        
    t = Table(table_data, colWidths=[90, 80, 85, 85, 80, 90])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.8, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('SPAN', (0, 1), (0, num_rows)),
        ('SPAN', (1, 1), (1, num_rows)),
        ('SPAN', (5, 1), (5, num_rows)),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))
    
    date_table = Table([[f"Date: {order['order_date']}"]], colWidths=[510])
    elements.append(date_table)
    
    doc.build(elements)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"inline; filename={product_code}.pdf"})