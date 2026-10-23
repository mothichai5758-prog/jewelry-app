import os
import json
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

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
                    s["received"] = min(int(s.get("qty", 0)), int(s.get("received", 0)) + qty)
                    save_data(orders_db)
                    return {"status": "success", "order": order}
    return {"status": "not found"}

@app.get("/api/orders/{product_code}/pdf", response_class=HTMLResponse)
def generate_pdf(product_code: str):
    order = next((o for o in orders_db if str(o.get("code")) == str(product_code)), None)
    if not order:
        return "<h3>ไม่พบข้อมูลใบสั่งผลิต</h3>"

    sizes_html = ""
    total_qty = 0
    total_rec = 0
    
    for s in order.get("sizes", []):
        qty = int(s.get("qty", 0) or 0)
        rec = int(s.get("received", 0) or 0)
        rem = max(0, qty - rec)
        total_qty += qty
        total_rec += rec
        sizes_html += (
            "<tr style='border-bottom: 1px solid #E5E7EB; text-align: center;'>"
            f"<td style='padding: 10px 8px; font-weight: 500;'>ไซส์ {s.get('size_th', '-')}</td>"
            f"<td style='padding: 10px 8px; color: #6B7280;'>{s.get('size_us', '-')}</td>"
            f"<td style='padding: 10px 8px; font-weight: bold;'>{qty}</td>"
            f"<td style='padding: 10px 8px; color: #059669; font-weight: 600;'>{rec}</td>"
            f"<td style='padding: 10px 8px; color: #D97706; font-weight: 600;'>{rem}</td>"
            "</tr>"
        )

    code = order.get("code", "-")
    weight = order.get("weight", "-")
    status = order.get("status", "-")
    factory = order.get("factory", "-")
    due_date = order.get("dueDate") or "-"
    pending_total = max(0, total_qty - total_rec)

    html_content = (
        "<!DOCTYPE html>"
        "<html lang='th'>"
        "<head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        f"<title>ใบสั่งผลิต - {code}</title>"
        "<link href='https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&display=swap' rel='stylesheet'>"
        "<style>"
        "body { font-family: 'Sarabun', sans-serif; padding: 24px; color: #1F2937; background-color: #F9FAFB; }"
        ".card { max-width: 700px; margin: 0 auto; background: white; border: 1px solid #E5E7EB; border-radius: 16px; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }"
        ".header { border-bottom: 2px solid #8A5A12; padding-bottom: 16px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: flex-end; }"
        ".title { font-size: 22px; font-weight: 700; color: #8A5A12; }"
        ".info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 13px; margin-bottom: 24px; background: #FDFBF7; padding: 16px; border-radius: 12px; border: 1px solid #F7F2E7; }"
        "table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; }"
        "th { background-color: #F3F4F6; padding: 10px 8px; border-bottom: 2px solid #E5E7EB; color: #4B5563; font-weight: 600; }"
        ".btn-print { background-color: #8A5A12; color: white; border: none; padding: 10px 20px; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer; }"
        ".btn-print:hover { background-color: #6D4408; }"
        "@media print {"
        "  .no-print { display: none !important; }"
        "  body { padding: 0; background: white; }"
        "  .card { border: none; box-shadow: none; padding: 0; }"
        "}"
        "</style>"
        "</head>"
        "<body>"
        "<div class='card'>"
        "<div class='no-print' style='margin-bottom: 20px; text-align: right;'>"
        "<button class='btn-print' onclick='window.print()'>🖨️ พิมพ์เอกสาร / บันทึกเป็น PDF</button>"
        "</div>"
        "<div class='header'>"
        "<div>"
        "<div class='title'>ใบสั่งผลิตชิ้นงาน (Work Order)</div>"
        "<div style='font-size: 13px; color: #6B7280; margin-top: 4px;'>โรงงานผลิตทองรูปพรรณ</div>"
        "</div>"
        f"<div style='text-align: right; font-size: 16px; font-weight: bold; color: #111827;'>รหัส: {code}</div>"
        "</div>"
        "<div class='info-grid'>"
        f"<div><strong>น้ำหนักทองเฉลี่ย:</strong> {weight}</div>"
        f"<div><strong>สถานะงาน:</strong> {status}</div>"
        f"<div><strong>โรงงาน/แผนก:</strong> {factory}</div>"
        f"<div><strong>กำหนดส่ง:</strong> {due_date}</div>"
        "</div>"
        "<table>"
        "<thead>"
        "<tr>"
        "<th>ไซส์ (TH)</th>"
        "<th>ไซส์ (US)</th>"
        "<th>จำนวนสั่ง (ชิ้น)</th>"
        "<th>รับแล้ว</th>"
        "<th>ค้างรับ</th>"
        "</tr>"
        "</thead>"
        "<tbody>"
        f"{sizes_html}"
        "<tr style='background-color: #FDFBF7; font-weight: bold; text-align: center; border-top: 2px solid #E5E7EB;'>"
        "<td colspan='2' style='padding: 12px 8px; text-align: right;'>รวมทั้งหมด:</td>"
        f"<td style='padding: 12px 8px;'>{total_qty}</td>"
        f"<td style='padding: 12px 8px; color: #059669;'>{total_rec}</td>"
        f"<td style='padding: 12px 8px; color: #D97706;'>{pending_total}</td>"
        "</tr>"
        "</tbody>"
        "</table>"
        "</div>"
        "</body>"
        "</html>"
    )
    return html_content
