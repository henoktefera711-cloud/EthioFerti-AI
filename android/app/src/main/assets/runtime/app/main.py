from fastapi import FastAPI, HTTPException, Request
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


# ===== ETHIOFERTI COMPLETE DATABASE INITIALIZATION =====
def init_database():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS farmers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                phone TEXT,
                location TEXT,
                region TEXT,
                zone TEXT,
                woreda TEXT,
                kebele TEXT,
                production_type TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quality_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                batch_code TEXT NOT NULL,
                test_type TEXT NOT NULL,
                measured_value REAL,
                unit TEXT,
                method TEXT,
                tester TEXT,
                result_status TEXT DEFAULT 'pending',
                notes TEXT,
                tested_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS camera_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_code TEXT NOT NULL,
                camera_type TEXT DEFAULT 'mobile',
                image_path TEXT NOT NULL,
                visual_observation TEXT,
                review_status TEXT DEFAULT 'pending',
                captured_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS qr_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                batch_code TEXT NOT NULL UNIQUE,
                token TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        columns = {
            "manufacturer": "TEXT",
            "origin": "TEXT",
            "description": "TEXT",
            "ingredients": "TEXT",
            "nutrient_composition": "TEXT",
            "benefits": "TEXT",
            "suitable_crops": "TEXT",
            "application_instructions": "TEXT",
            "safety_instructions": "TEXT",
            "storage_instructions": "TEXT",
            "production_date": "TEXT",
            "expiry_date": "TEXT",
            "registration_number": "TEXT"
        }

        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(products)")
        }

        for column, sql_type in columns.items():
            if column not in existing:
                conn.execute(
                    f"ALTER TABLE products ADD COLUMN {column} {sql_type}"
                )

init_database()
# ===== END DATABASE INITIALIZATION =====

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


class ProductProfileUpdate(BaseModel):
    manufacturer: str | None = None
    origin: str | None = None
    description: str | None = None
    ingredients: str | None = None
    nutrient_composition: str | None = None
    benefits: str | None = None
    suitable_crops: str | None = None
    application_instructions: str | None = None
    safety_instructions: str | None = None
    storage_instructions: str | None = None
    production_date: str | None = None
    expiry_date: str | None = None
    registration_number: str | None = None


@app.patch("/api/v1/products/{product_id}/profile")
def update_product_profile(product_id: int, item: ProductProfileUpdate):
    values = item.dict(exclude_unset=True)

    if not values:
        raise HTTPException(status_code=400, detail="No profile fields supplied")

    allowed = {
        "manufacturer", "origin", "description", "ingredients",
        "nutrient_composition", "benefits", "suitable_crops",
        "application_instructions", "safety_instructions",
        "storage_instructions", "production_date", "expiry_date",
        "registration_number"
    }

    values = {key: value for key, value in values.items() if key in allowed}
    assignments = ", ".join(f"{key} = ?" for key in values)

    with connect_db() as conn:
        exists = conn.execute(
            "SELECT id FROM products WHERE id = ?", (product_id,)
        ).fetchone()

        if exists is None:
            raise HTTPException(status_code=404, detail="Product not found")

        conn.execute(
            f"UPDATE products SET {assignments} WHERE id = ?",
            (*values.values(), product_id)
        )

        product = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()

    return {"message": "Fertilizer profile updated", "product": dict(product)}


@app.get("/api/v1/products/batch/{batch_code}")
def get_product_by_batch(batch_code: str):
    with connect_db() as conn:
        product = conn.execute(
            "SELECT * FROM products WHERE batch_code = ?", (batch_code,)
        ).fetchone()

    if product is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    return dict(product)

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


# ===== INDEPENDENT FERTILIZER CAMERA ANALYSIS =====
class CameraAnalyzeRequest(BaseModel):
    image_data: str = Field(min_length=20)


@app.post("/api/v1/camera/analyze")
def analyze_camera_image(item: CameraAnalyzeRequest):
    import base64
    import binascii
    import uuid

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

        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty image")

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
                    "UNMATCHED",
                    "mobile-independent",
                    str(image_path.relative_to(BASE_DIR)),
                    "Image stored; OCR and visual review not yet verified",
                    "pending"
                )
            )
            record_id = cursor.lastrowid
    except Exception:
        image_path.unlink(missing_ok=True)
        raise

    return {
        "message": "Image received for analysis",
        "id": record_id,
        "image_url": f"/api/v1/camera/photos/{record_id}",
        "ocr_status": "performed_in_browser",
        "visual_ai_status": "not_configured",
        "review_status": "pending",
        "notice": "OCR text is not proof of product authenticity or chemical composition."
    }

# ===== END INDEPENDENT FERTILIZER CAMERA ANALYSIS =====



# ===== GEMINI FERTILIZER VISUAL RECOGNITION =====
import os
import json
import base64
import binascii
import uuid
import httpx


@app.post("/api/v1/camera/recognize")
def recognize_fertilizer_material(item: CameraAnalyzeRequest):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Gemini API key is not configured.")

    try:
        header, encoded = item.image_data.split(",", 1)
        allowed = {
            "data:image/jpeg;base64": ("jpg", "image/jpeg"),
            "data:image/png;base64": ("png", "image/png"),
            "data:image/webp;base64": ("webp", "image/webp")
        }
        image_type = allowed.get(header)
        if not image_type:
            raise HTTPException(status_code=400, detail="Unsupported image type.")

        image_bytes = base64.b64decode(encoded, validate=True)
        if not image_bytes or len(image_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image must be under 5 MB.")

    except (ValueError, binascii.Error):
        raise HTTPException(status_code=400, detail="Invalid image data.")

    extension, mime_type = image_type
    image_path = CAMERA_DIR / f"{uuid.uuid4().hex}.{extension}"
    image_path.write_bytes(image_bytes)

    prompt = """
You are EthioFerti AI, an agricultural material visual inspection assistant.

Analyze the actual loose material in the image, not packaging or labels.
It may be fertilizer granules, powder, pellets, compost, manure or another
material. Do not assume it is fertilizer.

Return only valid JSON with:
{
 "is_fertilizer_candidate": true,
 "category_en": "Likely category or unknown",
 "category_am": "የሚገመተው ዓይነት",
 "identification_en": "Careful identification",
 "identification_am": "ጥንቃቄ የተሞላበት መለያ",
 "visual_description_en": "Color, texture, shape and visible condition",
 "visual_description_am": "የቀለምና የገጽታ መግለጫ",
 "visible_clues_en": ["Visible clue"],
 "visible_clues_am": ["የሚታይ ምልክት"],
 "confidence_band": "low",
 "confidence_explanation_en": "Explain uncertainty",
 "confidence_explanation_am": "የእርግጠኝነት ማብራሪያ",
 "possible_uses_en": ["Possible use if justified"],
 "possible_uses_am": ["ሊኖር የሚችል አጠቃቀም"],
 "cannot_determine_en": ["NPK", "Chemical composition", "Contamination"],
 "cannot_determine_am": ["NPK", "የኬሚካል ይዘት", "ብክለት"],
 "recommended_tests_en": ["Laboratory test"],
 "recommended_tests_am": ["የላቦራቶሪ ምርመራ"],
 "farmer_guidance_en": "Cautious practical guidance",
 "farmer_guidance_am": "ጥንቃቄ የተሞላበት ምክር"
}

Rules:
- Never invent NPK, nutrients, ingredients, brand, origin or dosage.
- Appearance cannot prove chemical composition, identity or safety.
- Never recommend applying unidentified material.
- Recommend laboratory tests where appropriate.
- If unclear, say so and request a clearer image.
- Confidence must be low, medium or high.
- Distinguish observations from hypotheses.
- If it does not look like fertilizer, say so.
- Give useful English and natural Amharic answers.
"""

    try:
        response = httpx.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
                "Api-Revision": "2026-05-20"
            },
            json={
                "model": "gemini-3.8-flash",
                "input": [
                    {"type": "text", "text": prompt},
                    {"type": "image", "data": encoded, "mime_type": mime_type}
                ],
                "generation_config": {"max_output_tokens": 1800}
            },
            timeout=120.0
        )
        response.raise_for_status()
        payload = response.json()

        text_parts = []
        for step in payload.get("steps", []):
            if step.get("type") == "model_output":
                for part in step.get("content", []):
                    if part.get("type") == "text" and part.get("text"):
                        text_parts.append(part["text"])

        if not text_parts:
            raise ValueError("Gemini returned no text analysis.")

        content = "\n".join(text_parts).strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            if content.endswith("```"):
                content = content[:-3].strip()

        analysis = json.loads(content)

        required = [
            "is_fertilizer_candidate", "category_en", "category_am",
            "identification_en", "identification_am",
            "visual_description_en", "visual_description_am",
            "confidence_band", "farmer_guidance_en", "farmer_guidance_am"
        ]
        if not all(key in analysis for key in required):
            raise ValueError("Gemini returned incomplete analysis.")
        if analysis["confidence_band"] not in ("low", "medium", "high"):
            analysis["confidence_band"] = "low"

    except httpx.HTTPStatusError as exc:
        image_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=502,
            detail=f"Gemini API HTTP {exc.response.status_code}: {exc.response.text[:500]}"
        )
    except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError, StopIteration) as exc:
        image_path.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail=f"Gemini analysis failed: {str(exc)[:300]}")

    try:
        with connect_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO camera_records
                (batch_code, camera_type, image_path, visual_observation, review_status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "UNMATCHED",
                    "gemini-vision",
                    str(image_path.relative_to(BASE_DIR)),
                    json.dumps(analysis, ensure_ascii=False),
                    "ai_analyzed"
                )
            )
            record_id = cursor.lastrowid
    except Exception:
        image_path.unlink(missing_ok=True)
        raise

    return {
        "message": "Gemini fertilizer material analysis completed.",
        "record_id": record_id,
        "analysis_source": "Google Gemini 3.8 Flash",
        "analysis": analysis,
        "important_notice": (
            "Visual analysis is not laboratory verification. "
            "It cannot establish NPK, chemical composition or safety."
        )
    }

# ===== END GEMINI FERTILIZER VISUAL RECOGNITION =====


# ===== ETHIOFERTI_QR_API_V1 =====

import io
import secrets
import qrcode
from fastapi.responses import Response


@app.post("/api/v1/qr/generate/{batch_code}")
def generate_qr_code(batch_code: str, request: Request):

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
        "qr_payload": str(request.base_url).rstrip("/") + f"/scan/{token}",
        "scan_url": str(request.base_url).rstrip("/") + f"/scan/{token}",
        "image_url": f"/api/v1/qr/image/{token}",
        "verification_url": f"/api/v1/qr/verify/{token}"
    }


@app.get("/api/v1/qr/image/{token}")
def get_qr_image(token: str, request: Request):

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

    payload = str(request.base_url).rstrip("/") + f"/scan/{token}"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4
    )

    qr.add_data(payload)
    qr.make(fit=True)

    from qrcode.image.svg import SvgPathImage

    image = qr.make_image(
        image_factory=SvgPathImage
    )

    output = io.BytesIO()
    image.save(output)

    return Response(
        content=output.getvalue(),
        media_type="image/svg+xml",
        headers={
            "Content-Disposition": 'inline; filename="ethioferti-qr.svg"'
        }
    )


@app.get("/api/v1/qr/verify/{token}")
def verify_qr_code(token: str):

    with connect_db() as conn:

        product = conn.execute(
            """
            SELECT
                p.*,
                q.created_at AS qr_created_at
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




@app.get("/manifest.webmanifest", include_in_schema=False)
def pwa_manifest():
    return FileResponse(
        BASE_DIR / "app" / "static" / "manifest.webmanifest",
        media_type="application/manifest+json"
    )


@app.get("/service-worker.js", include_in_schema=False)
def pwa_service_worker():
    return FileResponse(
        BASE_DIR / "app" / "static" / "service-worker.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"}
    )



@app.get("/local-db.js", include_in_schema=False)
def local_database_script():
    return FileResponse(BASE_DIR / "app" / "static" / "local-db.js", media_type="application/javascript")

@app.get("/vendor/jsQR.js", include_in_schema=False)
def local_qr_decoder():
    return FileResponse(BASE_DIR / "app" / "static" / "vendor" / "jsQR.js", media_type="application/javascript")

@app.get("/icons/icon.svg", include_in_schema=False)
def pwa_icon():
    return FileResponse(BASE_DIR / "app" / "static" / "icons" / "icon.svg", media_type="image/svg+xml")

@app.get("/scan", include_in_schema=False)
def portable_product_scan():
    return FileResponse(BASE_DIR / "app" / "static" / "scan.html")


@app.get("/scanner")
def qr_scanner_page():
    return FileResponse(BASE_DIR / "app" / "static" / "scanner.html")


@app.get("/scan/{token}")
def public_product_scan(token: str):
    if token.startswith("EF1:"):
        return FileResponse(BASE_DIR / "app" / "static" / "scan.html")

    with connect_db() as conn:
        record = conn.execute(
            "SELECT id FROM qr_codes WHERE token = ?",
            (token,)
        ).fetchone()

    if record is None:
        raise HTTPException(status_code=404, detail="Invalid QR code")

    return FileResponse(BASE_DIR / "app" / "static" / "scan.html")


# ===== END ETHIOFERTI_QR_API_V1 =====



@app.get("/qr-scanner")
def qr_scanner_page():
    return FileResponse(BASE_DIR / "app" / "static" / "qr-scanner.html")
