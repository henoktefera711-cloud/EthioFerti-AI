from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "ethioferti.db"
DB_PATH.parent.mkdir(exist_ok=True)

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

with connect_db() as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity_kg REAL NOT NULL,
            batch_code TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'registered'
        )
    """)

app = FastAPI(
    title="EthioFerti AI",
    description="Organic Fertilizer Production and Management Platform",
    version="0.2.0"
)

class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    category: str = Field(min_length=2, max_length=100)
    quantity_kg: float = Field(gt=0)
    batch_code: str = Field(min_length=2, max_length=100)

@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(BASE_DIR / "app" / "static" / "index.html")

@app.get("/api/v1/health")
def health():
    return {"status": "healthy", "database": "connected"}

@app.post("/api/v1/products")
def create_product(item: ProductCreate):
    try:
        with connect_db() as conn:
            cursor = conn.execute(
                """INSERT INTO products
                (name, category, quantity_kg, batch_code)
                VALUES (?, ?, ?, ?)""",
                (item.name, item.category, item.quantity_kg, item.batch_code)
            )
            product_id = cursor.lastrowid

        return {
            "message": "Product registered successfully",
            "id": product_id,
            "batch_code": item.batch_code
        }
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Batch code already exists")

@app.get("/api/v1/products")
def list_products():
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM products ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]

@app.get("/api/v1/products/{product_id}")
def get_product(product_id: int):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return dict(row)


# ETHIOFERTI_FARMER_API

class FarmerCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    region: str = Field(min_length=2, max_length=100)
    zone: str = Field(min_length=2, max_length=100)
    woreda: str = Field(min_length=2, max_length=100)
    kebele: str = Field(min_length=1, max_length=100)
    production_type: str = Field(min_length=2, max_length=150)


# Safely add new columns without deleting existing farmer data.
with connect_db() as conn:
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(farmers)").fetchall()
    }

    new_columns = {
        "region": "TEXT",
        "zone": "TEXT",
        "woreda": "TEXT",
        "kebele": "TEXT",
        "production_type": "TEXT"
    }

    for column, sql_type in new_columns.items():
        if column not in existing:
            conn.execute(
                f"ALTER TABLE farmers ADD COLUMN {column} {sql_type}"
            )


@app.post("/api/v1/farmers")
def create_farmer(item: FarmerCreate):
    with connect_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO farmers
            (full_name, phone, location, region, zone, woreda,
             kebele, production_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.full_name.strip(),
                item.phone,
                item.kebele,
                item.region.strip(),
                item.zone.strip(),
                item.woreda.strip(),
                item.kebele.strip(),
                item.production_type.strip()
            )
        )

        farmer_id = cursor.lastrowid

    return {
        "message": "Farmer registered successfully",
        "id": farmer_id
    }


@app.get("/api/v1/farmers")
def list_farmers():
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM farmers ORDER BY id DESC"
        ).fetchall()

    return [dict(row) for row in rows]


@app.get("/api/v1/farmers/{farmer_id}")
def get_farmer(farmer_id: int):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT * FROM farmers WHERE id = ?",
            (farmer_id,)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Farmer not found")

    return dict(row)


# ETHIOFERTI_QUALITY_API

class QualityRecordCreate(BaseModel):
    batch_code: str = Field(min_length=2, max_length=100)
    test_type: str = Field(min_length=2, max_length=100)
    measured_value: float | None = None
    unit: str | None = Field(default=None, max_length=30)
    method: str | None = Field(default=None, max_length=150)
    tester: str | None = Field(default=None, max_length=150)
    result_status: str = Field(default="pending", max_length=30)
    notes: str | None = Field(default=None, max_length=1000)


@app.post("/api/v1/quality-records")
def create_quality_record(item: QualityRecordCreate):
    allowed = {"pending", "passed", "failed", "needs_review"}

    if item.result_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Invalid quality status"
        )

    with connect_db() as conn:
        product = conn.execute(
            "SELECT id FROM products WHERE batch_code = ?",
            (item.batch_code,)
        ).fetchone()

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Product batch not found"
            )

        cursor = conn.execute(
            """
            INSERT INTO quality_records
            (product_id, batch_code, test_type, measured_value,
             unit, method, tester, result_status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product["id"],
                item.batch_code,
                item.test_type,
                item.measured_value,
                item.unit,
                item.method,
                item.tester,
                item.result_status,
                item.notes
            )
        )

        record_id = cursor.lastrowid

    return {
        "message": "Quality record saved",
        "id": record_id,
        "batch_code": item.batch_code
    }


@app.get("/api/v1/quality-records")
def list_quality_records():
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM quality_records ORDER BY id DESC"
        ).fetchall()

    return [dict(row) for row in rows]


@app.get("/api/v1/quality-records/{batch_code}")
def get_quality_by_batch(batch_code: str):
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM quality_records
            WHERE batch_code = ?
            ORDER BY id DESC
            """,
            (batch_code,)
        ).fetchall()

    return [dict(row) for row in rows]

# ===== ETHIOFERTI MOBILE CAMERA API =====
import base64
import binascii
import uuid
from datetime import datetime, timezone
from fastapi import Body
from fastapi.responses import FileResponse

CAMERA_DIR = BASE_DIR / "data" / "uploads" / "camera"
CAMERA_DIR.mkdir(parents=True, exist_ok=True)

class CameraPhotoCreate(BaseModel):
    batch_code: str = Field(min_length=2, max_length=100)
    image_data: str = Field(min_length=20)

@app.post("/api/v1/camera/capture")
def save_camera_photo(item: CameraPhotoCreate):
    with connect_db() as conn:
        product = conn.execute(
            "SELECT id FROM products WHERE batch_code = ?",
            (item.batch_code,)
        ).fetchone()

    if product is None:
        raise HTTPException(status_code=404, detail="Batch code not found")

    try:
        header, encoded = item.image_data.split(",", 1)
        allowed = {
            "data:image/jpeg;base64": ".jpg",
            "data:image/png;base64": ".png",
            "data:image/webp;base64": ".webp"
        }
        extension = allowed.get(header)

        if extension is None:
            raise HTTPException(status_code=400, detail="Unsupported image type")

        image_bytes = base64.b64decode(encoded, validate=True)

        if len(image_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image must be under 5 MB")

    except (ValueError, binascii.Error):
        raise HTTPException(status_code=400, detail="Invalid image data")

    filename = f"{uuid.uuid4().hex}{extension}"
    image_path = CAMERA_DIR / filename
    image_path.write_bytes(image_bytes)

    try:
        with connect_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO camera_records
                (batch_code, camera_type, image_path,
                 visual_observation, review_status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item.batch_code,
                    "mobile",
                    str(image_path.relative_to(BASE_DIR)),
                    "Visual review pending",
                    "pending"
                )
            )
            record_id = cursor.lastrowid
    except Exception:
        image_path.unlink(missing_ok=True)
        raise

    return {
        "message": "Photo saved successfully",
        "id": record_id,
        "batch_code": item.batch_code,
        "image_url": f"/api/v1/camera/photos/{record_id}"
    }

@app.get("/api/v1/camera/photos")
def list_camera_photos():
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM camera_records ORDER BY id DESC"
        ).fetchall()

    return [
        {
            "id": row["id"],
            "batch_code": row["batch_code"],
            "camera_type": row["camera_type"],
            "review_status": row["review_status"],
            "captured_at": row["captured_at"],
            "image_url": f"/api/v1/camera/photos/{row['id']}"
        }
        for row in rows
    ]

@app.get("/api/v1/camera/photos/{photo_id}")
def get_camera_photo(photo_id: int):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT image_path FROM camera_records WHERE id = ?",
            (photo_id,)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    path = (BASE_DIR / row["image_path"]).resolve()

    if not path.is_relative_to(CAMERA_DIR.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found")

    return FileResponse(path)
# ===== END ETHIOFERTI MOBILE CAMERA API =====

# ===== ETHIOFERTI_QR_API_V1 =====

import io
import secrets
import qrcode
from fastapi.responses import Response


@app.post("/api/v1/qr/generate/{batch_code}")
def generate_qr_code(batch_code: str):

    with connect_db() as conn:
        product = conn.execute(
            "SELECT * FROM products WHERE batch_code = ?",
            (batch_code,)
        ).fetchone()

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Fertilizer batch not found"
            )

        existing = conn.execute(
            "SELECT token FROM qr_codes WHERE batch_code = ?",
            (batch_code,)
        ).fetchone()

        if existing:
            token = existing["token"]
            created = False
        else:
            token = secrets.token_urlsafe(32)

            conn.execute(
                """
                INSERT INTO qr_codes
                (product_id, batch_code, token)
                VALUES (?, ?, ?)
                """,
                (product["id"], batch_code, token)
            )
            created = True

    return {
        "message": "QR code generated" if created else "Existing QR code retrieved",
        "batch_code": batch_code,
        "token": token,
        "qr_payload": f"ETHIOFERTI:{token}",
        "image_url": f"/api/v1/qr/image/{token}",
        "verification_url": f"/api/v1/qr/verify/{token}"
    }


@app.get("/api/v1/qr/image/{token}")
def get_qr_image(token: str):

    with connect_db() as conn:
        record = conn.execute(
            "SELECT id FROM qr_codes WHERE token = ?",
            (token,)
        ).fetchone()

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="QR code not found"
        )

    payload = f"ETHIOFERTI:{token}"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4
    )

    qr.add_data(payload)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    output = io.BytesIO()
    image.save(output, format="PNG")

    return Response(
        content=output.getvalue(),
        media_type="image/png",
        headers={
            "Content-Disposition": 'inline; filename="ethioferti-qr.png"'
        }
    )


@app.get("/api/v1/qr/verify/{token}")
def verify_qr_code(token: str):

    with connect_db() as conn:

        product = conn.execute(
            """
            SELECT
                p.id,
                p.name,
                p.category,
                p.quantity_kg,
                p.batch_code,
                p.status,
                q.created_at
            FROM qr_codes q
            JOIN products p ON p.id = q.product_id
            WHERE q.token = ?
            """,
            (token,)
        ).fetchone()

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Invalid or unregistered QR code"
            )

        quality_rows = conn.execute(
            """
            SELECT test_type, measured_value, unit,
                   tester, result_status, tested_at, notes
            FROM quality_records
            WHERE batch_code = ?
            ORDER BY id DESC
            """,
            (product["batch_code"],)
        ).fetchall()

    quality = [dict(row) for row in quality_rows]

    statuses = [row["result_status"] for row in quality]

    if "failed" in statuses:
        verification = "failed"
    elif statuses and all(s == "passed" for s in statuses):
        verification = "passed"
    else:
        verification = "pending"

    return {
        "valid_qr": True,
        "verification_status": verification,
        "message": {
            "passed": "Quality records show all recorded tests passed.",
            "failed": "At least one recorded quality test failed.",
            "pending": "Quality testing is incomplete or awaiting review."
        }[verification],
        "product": dict(product),
        "quality_records": quality,
        "quality_tests_count": len(quality),
        "important_notice": (
            "QR verification retrieves registered records. "
            "It does not independently certify physical fertilizer quality."
        )
    }

# ===== END ETHIOFERTI_QR_API_V1 =====

