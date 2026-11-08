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

@app.get("/language.js", include_in_schema=False)
def language_script():
    return FileResponse(
        BASE_DIR / "app" / "static" / "language.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"}
    )


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
    features: dict = Field(default_factory=dict)


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



# ===== LOCAL OFFLINE FERTILIZER MATERIAL INSPECTION =====
import base64
import binascii
import uuid
import json


@app.post("/api/v1/camera/recognize")
def recognize_fertilizer_material(item: CameraAnalyzeRequest):
    allowed = {
        "data:image/jpeg;base64": "jpg",
        "data:image/png;base64": "png",
        "data:image/webp;base64": "webp"
    }

    try:
        header, encoded = item.image_data.split(",", 1)
        extension = allowed.get(header)
        if not extension:
            raise HTTPException(status_code=400, detail="Unsupported image type.")

        image_bytes = base64.b64decode(encoded, validate=True)
        if not image_bytes or len(image_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image must be under 5 MB.")
    except (ValueError, binascii.Error):
        raise HTTPException(status_code=400, detail="Invalid image data.")

    features = item.features or {}
    try:
        brightness = float(features.get("brightness", 0))
        saturation = float(features.get("saturation", 0))
        texture = float(features.get("texture", 0))
        uniformity = float(features.get("uniformity", 0))
        edge_density = float(features.get("edge_density", 0))
        color_name = str(features.get("color_name", "unclear"))[:40]
    except (TypeError, ValueError):
        brightness = saturation = texture = uniformity = edge_density = 0
        color_name = "unclear"

    valid_features = (
        0 <= brightness <= 255
        and 0 <= saturation <= 255
        and 0 <= texture <= 255
        and 0 <= uniformity <= 1
        and 0 <= edge_density <= 1
    )

    if not valid_features:
        raise HTTPException(status_code=400, detail="Invalid image features.")

    # These are appearance groups, not chemical or product identification.
    if brightness < 1 and texture < 1:
        appearance_en = "The photograph does not provide enough usable visual detail."
        appearance_am = "ፎቶው በቂ የሆነ የእይታ መረጃ አያቀርብም።"
        category_en = "Unclear material"
        category_am = "ያልተለየ ቁሳቁስ"
    elif brightness < 105 and texture > 18:
        appearance_en = "The image has a relatively dark and varied surface appearance. This may resemble some organic materials, but appearance alone cannot establish that."
        appearance_am = "ምስሉ በአንጻራዊነት ጠቆር ያለና የተለያየ ገጽታ ያሳያል። አንዳንድ ኦርጋኒክ ቁሳቁሶችን ሊመስል ይችላል፤ ይህ ግን ማረጋገጫ አይደለም።"
        category_en = "Dark, varied material appearance"
        category_am = "ጠቆር ያለና የተለያየ ገጽታ ያለው ቁሳቁስ"
    elif saturation > 65:
        appearance_en = "The image contains noticeably saturated or coloured areas. Fertilizer products can have many colours, so colour cannot identify a product."
        appearance_am = "ምስሉ ግልጽ የሆኑ ቀለማትን ያሳያል። የማዳበሪያ ምርቶች የተለያዩ ቀለሞች ሊኖራቸው ስለሚችል ቀለም ብቻ ምርቱን አይለይም።"
        category_en = "Coloured material appearance"
        category_am = "ቀለም ያለው ቁሳቁስ"
    elif texture < 12 and edge_density < 0.12:
        appearance_en = "The visible surface appears relatively smooth or fine in this photograph. The image cannot reliably distinguish powder from very small particles."
        appearance_am = "በፎቶው የሚታየው ገጽታ በአንጻራዊነት ለስላሳ ወይም ጥቃቅን ይመስላል። ዱቄትን ከበጣም ትንንሽ ቅንጣቶች በእርግጠኝነት መለየት አይቻልም።"
        category_en = "Fine or smooth-looking material"
        category_am = "ጥቃቅን ወይም ለስላሳ የሚመስል ቁሳቁስ"
    else:
        appearance_en = "The photograph shows a visible granular or uneven surface. This appearance is shared by many unrelated materials and fertilizer products."
        appearance_am = "ፎቶው ቅንጣታማ ወይም ያልተመጣጠነ ገጽታ ያሳያል። ይህ ገጽታ በብዙ የተለያዩ ቁሳቁሶችና ማዳበሪያዎች ላይ ሊታይ ይችላል።"
        category_en = "Granular or uneven material appearance"
        category_am = "ቅንጣታማ ወይም ያልተመጣጠነ ገጽታ ያለው ቁሳቁስ"

    clues_en = [
        "Estimated dominant image colour: " + color_name,
        "Average image brightness: " + str(round(brightness, 1)) + " on a 0–255 scale",
        "Image texture variation: " + str(round(texture, 1)),
        "Image uniformity estimate: " + str(round(uniformity * 100)) + "%"
    ]
    clues_am = [
        "በምስሉ የተገመተው ዋና ቀለም፦ " + color_name,
        "የምስሉ አማካይ ብሩህነት፦ " + str(round(brightness, 1)),
        "የምስሉ የገጽታ ልዩነት፦ " + str(round(texture, 1))
    ]

    analysis = {
        "is_fertilizer_candidate": True,
        "category_en": category_en,
        "category_am": category_am,
        "identification_en": "This is a local visual screening result, not an identification of a fertilizer product. " + appearance_en,
        "identification_am": "ይህ የአካባቢያዊ የእይታ ግምገማ ነው፤ የማዳበሪያ ምርትን በትክክል የሚለይ ውጤት አይደለም። " + appearance_am,
        "visual_description_en": appearance_en + " Estimated colour: " + color_name + ". Image measurements are affected by lighting, camera quality and background.",
        "visual_description_am": appearance_am + " የተገመተው ቀለም፦ " + color_name + "። የብርሃን፣ የካሜራና የጀርባ ሁኔታ የምስል ግምቱን ሊቀይር ይችላል።",
        "visible_clues_en": clues_en,
        "visible_clues_am": clues_am,
        "confidence_band": "low",
        "confidence_explanation_en": "Low confidence. Image features describe appearance only. Different materials, including urea, DAP, NPS and NPK blends, can look similar.",
        "confidence_explanation_am": "ዝቅተኛ እርግጠኝነት። የምስል መረጃው ገጽታን ብቻ ይገልጻል። ዩሪያ፣ DAP፣ NPS እና NPK የሚመስሉ የተለያዩ ምርቶች ተመሳሳይ ሊመስሉ ይችላሉ።",
        "possible_uses_en": ["No agricultural use can be recommended until the material and its label or laboratory result are verified."],
        "possible_uses_am": ["ቁሳቁሱና መለያው ወይም የላቦራቶሪ ውጤቱ እስኪረጋገጥ ድረስ የእርሻ አጠቃቀም ምክር አይሰጥም።"],
        "cannot_determine_en": ["Exact fertilizer identity", "NPK content", "Chemical composition", "Nutrient concentration", "Authenticity", "Contamination", "Safety"],
        "cannot_determine_am": ["ትክክለኛ የማዳበሪያ ዓይነት", "የNPK ይዘት", "የኬሚካል ይዘት", "የንጥረ ነገር መጠን", "እውነተኛነት", "ብክለት", "ደህንነት"],
        "recommended_tests_en": ["Check the original product label and batch number.", "Ask an agricultural extension officer.", "Use an accredited laboratory for nutrient and composition testing."],
        "recommended_tests_am": ["የምርቱን የመጀመሪያ መለያና የባች ቁጥር ያረጋግጡ።", "የግብርና ባለሙያን ያማክሩ።", "የንጥረ ነገርና የኬሚካል ይዘትን በታወቀ ላቦራቶሪ ያስመርምሩ።"],
        "farmer_guidance_en": "Do not apply an unidentified material based on its appearance. Keep it in its original labelled container, avoid inhaling dust or touching it with bare hands, and verify its identity with a qualified agricultural professional or laboratory.",
        "farmer_guidance_am": "ያልታወቀ ቁሳቁስን በገጽታው ብቻ ተመስርተው አይጠቀሙ። በመጀመሪያው መለያ ባለው እቃ ውስጥ ያቆዩት፤ አቧራውን ከመተንፈስና በባዶ እጅ ከመንካት ይቆጠቡ። ከመጠቀምዎ በፊት የግብርና ባለሙያ ወይም ላቦራቶሪ ያረጋግጥልዎ።"
    }

    image_path = CAMERA_DIR / f"{uuid.uuid4().hex}.{extension}"
    image_path.write_bytes(image_bytes)

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
                    "offline-visual-screening",
                    str(image_path.relative_to(BASE_DIR)),
                    json.dumps(analysis, ensure_ascii=False),
                    "review_required"
                )
            )
            record_id = cursor.lastrowid
    except Exception:
        image_path.unlink(missing_ok=True)
        raise

    return {
        "message": "Offline visual screening completed.",
        "record_id": record_id,
        "analysis_source": "Local visual feature rules and reference guidance",
        "analysis": analysis,
        "important_notice": "This is not chemical identification or laboratory verification."
    }

# ===== END LOCAL OFFLINE FERTILIZER MATERIAL INSPECTION =====


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


# ETHIOFERTI_DYNAMIC_FERTILIZER_KNOWLEDGE_V1
from pathlib import Path as _KnowledgePath

_FERTILIZER_KNOWLEDGE_FILE = BASE_DIR / "data" / "knowledge" / "fertilizers.json"

def _load_fertilizer_knowledge():
    try:
        with _FERTILIZER_KNOWLEDGE_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        raise HTTPException(status_code=503, detail="Fertilizer knowledge database is unavailable.")

@app.get("/api/v1/fertilizers")
def list_fertilizer_knowledge():
    database = _load_fertilizer_knowledge()
    return {
        "database": database["database_name"],
        "version": database["schema_version"],
        "count": len(database["profiles"]),
        "fertilizers": [
            {
                "id": item["id"],
                "name": item["name"],
                "aliases": item["aliases"],
                "grade": item["grade"],
                "classification": item["classification"]
            }
            for item in database["profiles"]
        ]
    }

@app.get("/api/v1/fertilizers/{fertilizer_id}")
def get_fertilizer_knowledge(fertilizer_id: str):
    database = _load_fertilizer_knowledge()
    for profile in database["profiles"]:
        if profile["id"] == fertilizer_id:
            return profile
    raise HTTPException(status_code=404, detail="Fertilizer profile not found.")

@app.post("/api/v1/fertilizers/advice")
def get_contextual_fertilizer_advice(payload: dict):
    database = _load_fertilizer_knowledge()
    crop = str(payload.get("crop", "")).strip().lower()
    region = str(payload.get("region", "Ethiopia")).strip()
    soil_type = str(payload.get("soil_type", "")).strip()
    soil_ph = payload.get("soil_ph")
    soil_test = payload.get("soil_test", {})
    identified_id = str(payload.get("fertilizer_id", "")).strip()

    if not crop:
        raise HTTPException(status_code=422, detail="Crop is required for contextual advice.")

    matches = []
    for profile in database["profiles"]:
        if identified_id and profile["id"] != identified_id:
            continue
        crop_list = [value.lower() for value in profile.get("crop_suitability", [])]
        if any(crop in value or value in crop for value in crop_list):
            matches.append(profile)

    if identified_id and not matches:
        raise HTTPException(status_code=404, detail="No matching fertilizer profile supports this crop query.")

    results = []
    for profile in matches:
        results.append({
            "fertilizer_id": profile["id"],
            "fertilizer_name": profile["name"],
            "grade": profile["grade"],
            "crop_relevance": "Listed for this crop or crop group in the knowledge database.",
            "nutrient_functions": profile["nutrient_functions"],
            "soil_considerations": profile["soil_considerations"],
            "application_guidance": profile["application_guidance"],
            "risks": profile["excess_and_risks"],
            "verification": profile["verification"]
        })

    return {
        "crop": crop,
        "region": region,
        "soil_type": soil_type or None,
        "soil_ph": soil_ph,
        "soil_test_received": bool(soil_test),
        "results": results,
        "rate_status": (
            "A numerical application rate was not generated. Use a current local crop recommendation and soil-test interpretation."
        ),
        "context_note": (
            "Crop relevance is not proof that this fertilizer is required. Final selection and rate depend on soil analysis, "
            "crop variety, yield target, season, previous nutrient inputs and locally validated recommendations."
        )
    }




# ============================================================
# ETHIOFERTI PHYSICAL-CHARACTER INTELLIGENCE ENGINE
# ============================================================

import json as _ef_json
from pathlib import Path as _ef_Path

_EF_KB_PATH = BASE_DIR / "data" / "knowledge" / "fertilizers.json"

def _ef_load_profiles():
    try:
        raw = _ef_json.loads(_EF_KB_PATH.read_text(encoding="utf-8"))
        return {
            str(p.get("id", "")).lower(): p
            for p in raw.get("profiles", [])
            if p.get("id")
        }
    except Exception:
        return {}

_EF_PROFILES = _ef_load_profiles()

def _ef_num(features, key, default=None):
    try:
        value = float(features.get(key))
        return value if value == value else default
    except (TypeError, ValueError):
        return default



def _ef_analyse_physical_character(features):
    brightness = _ef_num(features, "brightness")
    texture = _ef_num(features, "texture")
    uniformity = _ef_num(features, "uniformity")
    edges = _ef_num(features, "edge_density")
    saturation = _ef_num(features, "saturation")
    color = str(features.get("color_name", "unknown")).lower()

    def result(status, message, quality="usable", family="unknown",
               observations=None, matches=None, candidate=None):
        data = {
            "status": status,
            "message": message,
            "quality": quality,
            "family": family,
            "observations": observations or [],
            "matches": matches or []
        }
        if candidate:
            data["candidate_profile_id"] = candidate
        return data

    if brightness is None or texture is None or uniformity is None:
        return result(
            "uncertain",
            "The photograph could not be assessed. Take another clear photograph.",
            "insufficient"
        )

    isolation = str(features.get("isolation_quality", "")).lower()
    foreground_fraction = _ef_num(features, "foreground_fraction")
    white_fraction = _ef_num(features, "white_fraction") or 0.0
    black_fraction = _ef_num(features, "black_fraction") or 0.0

    if white_fraction > 0.30:
        return result(
            "candidate",
            "White-dominant fertilizer material category. Review the mineral fertilizer information and confirm the product grade.",
            family="white_fertilizer",
            candidate="__family_white__"
        )

    if black_fraction > 0.30:
        return result(
            "candidate",
            "Black or dark fertilizer material category. Review the organic and mineral soil-amendment information.",
            family="black_fertilizer",
            candidate="__family_black__"
        )


    # Accept complex backgrounds when usable image features are available.
    if foreground_fraction is not None and (
        foreground_fraction < 0.015 or foreground_fraction > 0.985
    ):
        return result(
            "rejected",
            "The visible material area is too small or unclear. Adjust the camera distance and try again.",
            "invalid_material_region"
        )

    if brightness < 22:
        return result(
            "rejected",
            "The photograph is too dark. Improve the lighting and try again.",
            "dark"
        )

    if texture < 1.5 and uniformity > 0.997:
        return result(
            "rejected",
            "No recognizable material detail is visible. Move closer to the material.",
            "blank"
        )

    if uniformity > 0.997 and (edges is None or edges < 0.003):
        return result(
            "rejected",
            "The material is unclear or out of focus. Retake the photograph.",
            "unclear"
        )

    observations = []
    observations.append(
        "strongly varied particles" if texture >= 24 else
        "visible granular texture" if texture >= 9 else
        "fine or moderately textured material" if texture >= 4 else
        "smooth or very fine surface"
    )
    observations.append(
        "relatively consistent surface" if uniformity >= 0.85
        else "heterogeneous surface"
    )
    if edges is not None:
        observations.append(
            "distinct particle boundaries" if edges >= 0.06
            else "subtle particle boundaries"
        )
    if color != "unknown":
        observations.append("observed colour: " + color)

    def words(value):
        import re
        return set(re.findall(r"[a-z]+", str(value).lower()))

    def colour_tokens(value):
        tokens = words(value)
        aliases = {
            "grey": {"gray"}, "gray": {"grey"},
            "cream": {"pale", "off", "white"},
            "off-white": {"white", "cream", "pale"},
            "slightly": set(),
            "reddish": {"red", "brown"},
            "tan": {"brown"},
            "black": {"dark"},
            "pink": {"red"},
        }
        for token in list(tokens):
            tokens.update(aliases.get(token, set()))
        return tokens

    observed_colours = colour_tokens(color)

    def colour_score(fp, sig):
        expected = []
        expected.extend(fp.get("typical_colours", []) or [])
        expected.extend(sig.get("colors", []) or [])
        if not expected or not observed_colours:
            return None
        for item in expected:
            candidate_words = colour_tokens(item)
            if candidate_words and (
                observed_colours.intersection(candidate_words)
                or ({"grey", "gray"} & observed_colours and
                    {"grey", "gray"} & candidate_words)
            ):
                return 1.0
        return 0.0

    ranked = []

    for pid, profile in _EF_PROFILES.items():
        sig = profile.get("physical_characteristics", {}) or {}
        intelligence = profile.get("intelligence", {}) or {}
        fp = intelligence.get("physical_fingerprint", {}) or {}

        if not sig and not fp:
            continue

        family = str(sig.get("family", "unknown")).lower()
        score = 0.0
        weight = 0.0
        evidence = 0
        dimensions = {}

        # 1. Colour: compare the camera colour with the expanded fingerprint.
        cm = colour_score(fp, sig)
        if cm is not None:
            dimensions["colour"] = cm
            weight += 0.28
            score += 0.28 * cm
            evidence += int(cm > 0)

        # 2. Particle form: compare known physical forms with measurable
        # granular, crystalline or organic surface characteristics.
        forms = " ".join(
            str(x).lower()
            for x in (fp.get("particle_forms", []) or [])
        )
        shapes = " ".join(
            str(x).lower()
            for x in (fp.get("particle_shapes", []) or [])
        )
        texture_text = " ".join(
            str(x).lower()
            for x in (fp.get("surface", []) or [])
        ) + " " + str(fp.get("texture", "")).lower()

        is_organic = family.startswith("organic")
        is_granular = any(x in forms for x in (
            "granule", "prill", "crystal", "compound"
        ))
        is_crystalline = "crystal" in forms or "crystalline" in texture_text
        is_fibrous = any(x in (forms + " " + shapes + " " + texture_text)
                         for x in ("fibre", "fiber", "fragment", "crumb"))

        form_fit = 0.0
        if is_organic:
            if texture >= 5 and uniformity < 0.97:
                form_fit = 1.0
            elif texture >= 3 and uniformity < 0.985:
                form_fit = 0.65
        elif is_granular:
            if texture >= 6 and edges is not None and edges >= 0.008:
                form_fit = 1.0
            elif texture >= 4:
                form_fit = 0.55
        if is_crystalline and edges is not None and edges >= 0.012:
            form_fit = max(form_fit, 0.85)

        if forms or shapes:
            dimensions["particle_form"] = form_fit
            weight += 0.25
            score += 0.25 * form_fit
            evidence += int(form_fit >= 0.65)

        # 3. Surface consistency: manufactured mineral granules tend to be
        # more consistent than compost and manure.
        consistency = 0.0
        if is_organic:
            consistency = (
                1.0 if uniformity < 0.90 and texture >= 5 else
                0.55 if uniformity < 0.96 else 0.0
            )
        elif family.startswith("mineral") or family == "compound_nps":
            consistency = (
                1.0 if uniformity >= 0.65 else
                0.55 if uniformity >= 0.45 else 0.0
            )
        dimensions["consistency"] = consistency
        weight += 0.18
        score += 0.18 * consistency
        evidence += int(consistency >= 0.65)

        # 4. Particle boundaries.
        edge_fit = 0.0
        if edges is not None:
            if is_organic:
                edge_fit = 1.0 if edges < 0.13 else 0.35
            elif is_granular:
                edge_fit = 1.0 if edges >= 0.008 else 0.0
            dimensions["particle_boundaries"] = edge_fit
            weight += 0.14
            score += 0.14 * edge_fit
            evidence += int(edge_fit >= 0.65)

        # 5. Surface texture clues from the expanded physical fingerprint.
        surface_fit = 0.0
        if is_organic and is_fibrous:
            surface_fit = 1.0 if texture >= 8 and uniformity < 0.96 else 0.4
        elif is_granular:
            surface_fit = 1.0 if texture >= 6 else 0.45 if texture >= 3 else 0.0
        if texture_text:
            dimensions["surface_texture"] = surface_fit
            weight += 0.10
            score += 0.10 * surface_fit
            evidence += int(surface_fit >= 0.65)

        # 6. Saturation is supporting evidence only.
        if saturation is not None:
            sat_fit = 0.5
            if family == "mineral_potassium":
                sat_fit = 1.0 if saturation >= 12 else 0.25
            elif is_organic:
                sat_fit = 1.0 if saturation < 75 else 0.25
            elif family.startswith("mineral") or family == "compound_nps":
                sat_fit = 1.0 if saturation < 65 else 0.35
            dimensions["saturation"] = sat_fit
            weight += 0.05
            score += 0.05 * sat_fit
            evidence += int(sat_fit >= 0.8)

        final_score = score / weight if weight else 0.0
        ranked.append({
            "profile_id": pid,
            "score": final_score,
            "evidence": evidence,
            "family": family,
            "dimensions": dimensions
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    matches = [
        {
            "profile_id": item["profile_id"],
            "score": round(item["score"], 3),
            "evidence_count": item["evidence"],
            "matched_dimensions": item["dimensions"]
        }
        for item in ranked[:5]
    ]

    if not ranked:
        return result(
            "uncertain",
            "No matching fertilizer profile is available in the knowledge base.",
            observations=observations
        )

    best = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    margin = best["score"] - second["score"] if second else best["score"]
    family = best["family"]
    best_score = best["score"]
    best_evidence = best["evidence"]

    # Organic materials overlap physically; return their shared family
    # rather than guessing compost, manure or vermicompost.
    organic_matches = [x for x in ranked if x["family"].startswith("organic")]
    if (
        family.startswith("organic")
        and best_score >= 0.53
        and best_evidence >= 2
    ):
        return result(
            "candidate",
            "The material has physical characteristics consistent with an organic soil amendment. Its exact type needs further identification.",
            family="organic_amendment",
            observations=observations,
            matches=matches,
            candidate="__family_organic__"
        )

    # NPS grades share visible properties. Never infer B or Zn from a photo.
    if family == "compound_nps" and best_score >= 0.53 and best_evidence >= 2:
        return result(
            "candidate",
            "The material is visually consistent with an NPS-family compound fertilizer. The exact grade and micronutrient composition are not visually distinguishable.",
            family="compound_nps",
            observations=observations,
            matches=matches,
            candidate="__family_nps__"
        )

    # DAP and NPS can look alike. Avoid a false exact DAP identification.
    if family == "mineral_compound" and second:
        nps_close = any(
            x["family"] == "compound_nps"
            and best_score - x["score"] < 0.14
            for x in ranked
        )
        if nps_close:
            return result(
                "uncertain",
                "The material resembles a granular compound fertilizer, but its appearance cannot reliably distinguish DAP from NPS.",
                family="mineral_compound",
                observations=observations,
                matches=matches
            )

    # Exact profile candidate only when several independent visual
    # dimensions agree and competing profiles are sufficiently weaker.
    if best_score >= 0.76 and best_evidence >= 3 and margin >= 0.14:
        profile = _EF_PROFILES.get(best["profile_id"])
        name = profile.get("name", "fertilizer") if profile else "fertilizer"
        return result(
            "candidate",
            "The material has several physical characteristics consistent with " + name + ". Review its product-specific information.",
            family=family,
            observations=observations,
            matches=matches,
            candidate=best["profile_id"]
        )

    if best_score >= 0.48 and best_evidence >= 2:
        return result(
            "uncertain",
            "The material has some fertilizer-like characteristics, but the photograph does not support a reliable identification.",
            family=family,
            observations=observations,
            matches=matches
        )

    return result(
        "candidate",
        "General fertilizer material category. Review the available organic and mineral fertilizer information.",
        family="fertilizer_material",
        observations=observations,
        matches=matches,
        candidate="__family_general__"
    )

def _ef_profile_details(profile):
    preferred = [
        "id", "name", "aliases",
        "chemical_name", "formula", "grade", "classification",
        "nutrients", "nutrient_functions", "description",
        "physical_forms", "physical_characteristics",
        "crop_suitability", "agricultural_uses",
        "soil_considerations", "application_guidance",
        "compatibility", "deficiency_indicators",
        "excess_and_risks", "storage", "verification",
        "sources", "source_urls", "identification_method",
        "intelligence", "knowledge_dimensions"
    ]
    return {
        key: profile[key]
        for key in preferred
        if key in profile and profile[key] not in (None, "", [], {})
    }


def _ef_family_summary(family):
    if family == "compound_nps":
        return {
            "id": "nps_family",
            "name": "NPS-family compound fertilizer",
            "classification": "Mineral / inorganic compound fertilizer",
            "chemical_name": "Nitrogen-phosphorus-sulfur compound fertilizer",
            "formula": "Varies by NPS grade",
            "grade": "Varies by product; exact grade is not visually identifiable",
            "nutrients": {
                "Nitrogen (N)": "Supports leafy growth, chlorophyll and protein formation.",
                "Phosphorus (P)": "Supports root development, energy transfer, flowering and establishment.",
                "Sulfur (S)": "Supports protein formation and efficient nitrogen use.",
                "Micronutrients": "Boron and/or zinc may be included in some NPS variants; presence depends on the verified product grade."
            },
            "nutrient_functions": [
                "Nitrogen supports vegetative growth.",
                "Phosphorus supports root growth and early crop establishment.",
                "Sulfur supports protein synthesis.",
                "Additional micronutrient functions depend on the specific formulation."
            ],
            "description": "NPS fertilizers are granular compound fertilizers supplying nitrogen, phosphorus and sulfur. Some formulations also include micronutrients.",
            "physical_forms": ["Granular compound fertilizer"],
            "crop_suitability": "Used in crop nutrition programs for cereals, pulses, oilseeds, vegetables and other crops where soil testing and local recommendations indicate a need for N, P and S.",
            "agricultural_uses": "Basal or planting-time nutrient supply, especially where phosphorus and sulfur are required alongside nitrogen.",
            "soil_considerations": "Select the formulation and rate according to soil testing, crop requirements and local agricultural recommendations.",
            "application": "Apply the confirmed product grade at the locally recommended rate. Do not select a rate from visual appearance.",
            "compatibility": "Compatibility depends on the exact formulation and other products being mixed.",
            "storage": "Keep dry, sealed and protected from moisture.",
            "verification": "This is a family-level visual match. The exact NPS grade and any boron or zinc content require product-label or laboratory confirmation."
        }

    if family == "organic_amendment":
        return {
            "id": "organic_family",
            "name": "Organic fertilizer / soil amendment",
            "classification": "Organic soil amendment",
            "chemical_name": "Variable decomposed organic material",
            "formula": "No fixed chemical formula",
            "grade": "Variable; depends on feedstock, processing and analysis",
            "nutrients": {
                "Organic matter": "Contributes to soil organic matter and soil structure.",
                "Nitrogen (N)": "May contribute nitrogen as the material decomposes.",
                "Phosphorus (P) and potassium (K)": "Amounts vary with source material and processing.",
                "Secondary nutrients and micronutrients": "Content varies and should be established by analysis."
            },
            "nutrient_functions": [
                "Adds organic matter to soil.",
                "Can improve soil structure, aggregation and water retention.",
                "May release nutrients gradually as it decomposes.",
                "Supports soil biological activity."
            ],
            "description": "Organic amendments include compost, animal manure and vermicompost. Their nutrient content and maturity vary according to source materials and processing.",
            "physical_forms": ["Crumbly material", "Fibrous or irregular organic particles", "Pellets or aggregates"],
            "crop_suitability": "Can be used in soil improvement and crop production for vegetables, cereals, fruit crops and other plants according to material quality and local recommendations.",
            "agricultural_uses": "Soil conditioning, organic matter addition and nutrient contribution.",
            "soil_considerations": "Use mature, appropriately processed material. Nutrient content, salinity and maturity vary; analysis is useful when available.",
            "application": "Application rates depend on the material's analysis, maturity, crop and soil. Follow local agricultural recommendations.",
            "compatibility": "Depends on maturity, moisture, salinity and the other materials being applied.",
            "storage": "Store in a protected place and manage moisture to avoid contamination or nutrient loss.",
            "verification": "This is an organic-material family match. Appearance alone cannot distinguish compost, farmyard manure and vermicompost or establish nutrient content."
        }

    if family == "white_fertilizer":
        return {
            "id": "white_fertilizer_family",
            "name": "White / pale fertilizer material",
            "classification": "Commonly mineral / inorganic; exact composition requires product identification",
            "chemical_name": "Not established by colour",
            "formula": "Depends on the fertilizer product",
            "grade": "Not established by visual colour",
            "nutrients": {
                "Nitrogen (N)": "May support leaf and stem growth, depending on the product.",
                "Phosphorus (P)": "May support root development and crop establishment.",
                "Potassium (K)": "May support water regulation and plant resilience.",
                "Other nutrients": "Sulfur and micronutrients depend on the actual formulation."
            },
            "nutrient_functions": [
                "Nutrients support plant growth according to the product composition.",
                "Different white fertilizers have different nutrient functions."
            ],
            "description": "The camera detected a white-dominant material. Many mineral fertilizers are white or pale, but colour alone cannot determine the product or its nutrient grade.",
            "physical_forms": ["White or pale granules", "Crystals", "Powder"],
            "crop_suitability": "Depends on the confirmed nutrient composition and the crop's requirements.",
            "agricultural_uses": "Use only after identifying the product and checking its nutrient composition.",
            "soil_considerations": "Choose a product and application rate based on crop needs and soil conditions.",
            "application_guidance": "Follow the confirmed product instructions and local agricultural recommendations.",
            "verification": "Colour-based family result. Exact product, organic/mineral composition and nutrient grade are not confirmed by colour."
        }

    if family == "black_fertilizer":
        return {
            "id": "black_fertilizer_family",
            "name": "Dark organic soil amendment",
            "classification": "Organic-matter soil amendment",
            "chemical_name": "Complex organic matter and naturally occurring plant nutrients",
            "formula": "Variable natural organic composition",
            "grade": "Organic matter-based; nutrient content varies by material",
            "nutrients": {
                "Organic matter": "Builds soil structure, supports beneficial soil organisms and improves water retention.",
                "Nitrogen (N)": "Supports leaf development, chlorophyll formation and vegetative growth.",
                "Phosphorus (P)": "Supports root establishment, flowering and energy transfer.",
                "Potassium (K)": "Supports water regulation, crop strength and stress tolerance.",
                "Secondary nutrients and micronutrients": "Contribute to balanced plant nutrition according to the material's composition."
            },
            "nutrient_functions": [
                "Adds organic matter and supports healthy soil structure.",
                "Contributes nutrients that support root, leaf and crop development.",
                "Supports soil moisture retention and biological activity."
            ],
            "description": "A dark, organic-style soil amendment used to enrich soil, support beneficial soil activity and improve growing conditions.",
            "physical_forms": ["Dark granules", "Crumbly material", "Fine powder", "Organic fragments"],
            "crop_suitability": "Commonly used in cereal crops, vegetables, legumes, root crops, fruit trees and nursery plants.",
            "agricultural_uses": "Soil enrichment, organic matter addition, soil conditioning and supplementary nutrient supply.",
            "soil_considerations": "Well-decomposed material supports soil structure and moisture retention. Incorporate it evenly into the root-zone soil.",
            "application_guidance": "Apply mature, well-decomposed material and mix it into the soil before planting or around established crops. Adjust the amount to the crop, soil condition and product analysis.",
            "verification": "Visual category: dark organic-style soil amendment. Exact nutrient percentages and product grade are not represented by colour."
        }

    if family == "fertilizer_material":
        return {
            "id": "general_fertilizer_family",
            "name": "Fertilizer material",
            "classification": "Organic or mineral fertilizer family; exact type not established",
            "chemical_name": "Varies by material",
            "formula": "Varies by product",
            "grade": "Not visually established",
            "nutrients": {
                "Nitrogen (N)": "Supports vegetative growth.",
                "Phosphorus (P)": "Supports root development.",
                "Potassium (K)": "Supports water regulation and plant resilience.",
                "Organic matter and micronutrients": "May be present depending on the material."
            },
            "nutrient_functions": [
                "Nutrients support crop growth in different ways.",
                "Organic amendments may improve soil structure and biological activity."
            ],
            "description": "The camera found a material that could not be assigned confidently to a specific visual family. This general fertilizer knowledge card provides starting information without claiming an exact identity.",
            "physical_forms": ["Granules", "Powder", "Crystals", "Crumbly or fibrous material"],
            "crop_suitability": "Depends on the actual fertilizer composition and crop requirements.",
            "agricultural_uses": "Nutrient supply or soil improvement, depending on the confirmed material.",
            "soil_considerations": "Use soil and product information to select the correct fertilizer.",
            "application_guidance": "Use the confirmed product instructions and local recommendations.",
            "verification": "General family information; exact product identity and grade are not established."
        }

    return None



@app.get("/api/v1/laboratory/diagnose/{code}")
def laboratory_diagnose(code: str, lang: str = "am"):
    import re

    normalized = str(code).strip().upper()
    match = re.fullmatch(r"(1|2|3)(U|D|H|F)", normalized)
    if not match:
        raise HTTPException(
            status_code=422,
            detail="Enter a valid laboratory code: U, D, H or F."
        )

    position_number, fertilizer_code = match.groups()
    language = "en" if str(lang).lower() == "en" else "am"

    positions = {
        "1": ("Top", "ላይኛ ክፍል"),
        "2": ("Middle", "መካከለኛ ክፍል"),
        "3": ("Bottom", "ታችኛ ክፍል"),
    }
    position_en, position_am = positions[position_number]
    position_label = position_en if language == "en" else position_am

    # F means non-fertilizer. It must never map to farmyard manure.
    if fertilizer_code == "F":
        messages = {
            "en": (
                "The submitted material is classified as non-fertilizer. "
                "No fertilizer analysis report has been generated."
            ),
            "am": (
                "የቀረበው ቁሳቁስ ማዳበሪያ እንዳልሆነ ተመድቧል። "
                "የማዳበሪያ ምርመራ ሪፖርት አልተዘጋጀም።"
            )
        }
        return {
            "success": True,
            "is_fertilizer": False,
            "diagnosis_mode": "laboratory_classification",
            "code": normalized,
            "fertilizer_code": "F",
            "sensor_position": position_label,
            "sensor_position_number": int(position_number),
            "language": language,
            "message": messages[language],
        }

    fertilizer_ids = {
        "U": "urea",
        "D": "dap",
        "H": "hawtro",
    }
    fertilizer_id = fertilizer_ids[fertilizer_code]

    database = _load_fertilizer_knowledge()
    profile = next(
        (p for p in database.get("profiles", [])
         if p.get("id") == fertilizer_id),
        None
    )

    if not profile:
        raise HTTPException(
            status_code=503,
            detail="Fertilizer profile unavailable."
        )

    profile = dict(profile)
    translated = profile.get("translations", {}).get(language, {})
    profile.update(translated)

    position_focus = {
        "en": {
            "1": "Analyze the material characteristics and surface conditions indicated at the upper sensor position.",
            "2": "Analyze material consistency and uniformity indicated at the middle sensor position.",
            "3": "Analyze settling, compaction and moisture characteristics indicated at the lower sensor position."
        },
        "am": {
            "1": "በላይኛው የሴንሰር ቦታ የቁሳቁሱን አካላዊ ባህሪና የገጽታ ሁኔታ መተንተን።",
            "2": "በመካከለኛው የሴንሰር ቦታ የቁሳቁሱን ወጥነትና ተመሳሳይነት መተንተን።",
            "3": "በታችኛው የሴንሰር ቦታ የቁሳቁሱን መጠቅጠቅና የእርጥበት ባህሪ መተንተን።"
        }
    }[language][position_number]

    return {
        "success": True,
        "is_fertilizer": True,
        "diagnosis_mode": "laboratory_simulation",
        "code": normalized,
        "fertilizer_code": fertilizer_code,
        "fertilizer_id": fertilizer_id,
        "sensor_position": position_label,
        "sensor_position_number": int(position_number),
        "sensor_position_focus": position_focus,
        "language": language,
        "category": profile.get("name"),
        "colour": position_label,
        "profile": profile,
        "database": database.get(
            "database_name",
            "offline_fertilizer_knowledge"
        )
    }


async def _ef_camera_recognize(payload: CameraAnalyzeRequest):
    features = getattr(payload, "features", {}) or {}
    result = _ef_analyse_physical_character(features)

    analysis = {
        "status": result["status"],
        "identification_en": None,
        "confidence": None,
        "message": result["message"],
        "physical_observations": result["observations"],
        "material_family": result["family"],
        "profile": None,
        "details": None,
        "matches": result.get("matches", [])
    }

    pid = result.get("candidate_profile_id")
    profile = None

    if pid == "__family_nps__":
        profile = _ef_family_summary("compound_nps")
    elif pid == "__family_organic__":
        profile = _ef_family_summary("organic_amendment")
    elif pid == "__family_white__":
        profile = _ef_family_summary("white_fertilizer")
    elif pid == "__family_black__":
        profile = _ef_family_summary("black_fertilizer")
    elif pid == "__family_general__":
        profile = _ef_family_summary("fertilizer_material")
    elif pid:
        profile = _EF_PROFILES.get(pid)

    if profile and result["status"] in ("identified", "candidate"):
        score = next(
            (m["score"] for m in result.get("matches", [])
             if m.get("profile_id") == pid),
            None
        )
        if score is None and pid in ("__family_nps__", "__family_organic__"):
            family_prefix = "compound_nps" if pid == "__family_nps__" else "organic"
            family_ids = {
                profile_id for profile_id, item in _EF_PROFILES.items()
                if str(item.get("physical_characteristics", {}).get("family", "")).startswith(family_prefix)
                or (pid == "__family_nps__" and item.get("physical_characteristics", {}).get("family") == "compound_nps")
            }
            score = max(
                (m["score"] for m in result.get("matches", [])
                 if m.get("profile_id") in family_ids),
                default=0
            )
        analysis.update({
            "status": "candidate",
            "identification_en": profile.get("name", "Fertilizer"),
            "confidence": round(score * 100) if score is not None else None,
            "message": result["message"],
            "profile": profile,
            "details": _ef_profile_details(profile) if pid in _EF_PROFILES else profile
        })

    return {"analysis": analysis, "analysis_source": "physical_character_engine"}

# Replace the old route so FastAPI dispatches to the new engine.
try:
    from fastapi import Request as _EFRequest
    for _route in list(app.routes):
        if getattr(_route, "path", None) == "/api/v1/camera/recognize":
            app.routes.remove(_route)
    app.add_api_route(
        "/api/v1/camera/recognize",
        _ef_camera_recognize,
        methods=["POST"],
        name="ethioferti_physical_character_recognition"
    )
except Exception as _ef_error:
    print("EthioFerti camera route registration failed:", _ef_error)
