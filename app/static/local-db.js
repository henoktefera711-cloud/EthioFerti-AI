/* EthioFerti AI — device-local database */
(function () {
  "use strict";

  const DB_NAME = "ethioferti_local";
  const DB_VERSION = 1;

  const STORES = {
    products: { keyPath: "id", indexes: { batch_code: true } },
    farmers: { keyPath: "id", indexes: {} },
    quality_records: { keyPath: "id", indexes: { batch_code: false } },
    camera_records: { keyPath: "id", indexes: { batch_code: false } },
    qr_codes: { keyPath: "id", indexes: { batch_code: true, token: true } },
    sync_queue: { keyPath: "id", indexes: { status: false } },
    settings: { keyPath: "key", indexes: {} }
  };

  let databasePromise;

  function openDB() {
    if (databasePromise) return databasePromise;

    databasePromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = () => {
        const db = request.result;

        Object.entries(STORES).forEach(([name, config]) => {
          let store;

          if (!db.objectStoreNames.contains(name)) {
            store = db.createObjectStore(name, {
              keyPath: config.keyPath,
              autoIncrement: config.keyPath !== "key"
            });
          } else {
            store = request.transaction.objectStore(name);
          }

          Object.entries(config.indexes).forEach(([index, unique]) => {
            if (!store.indexNames.contains(index)) {
              store.createIndex(index, index, { unique });
            }
          });
        });
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => {
        databasePromise = null;
        reject(request.error);
      };
      request.onblocked = () => reject(new Error("Database upgrade is blocked by another open tab."));
    });

    return databasePromise;
  }

  async function transaction(storeName, mode, operation) {
    const db = await openDB();

    return new Promise((resolve, reject) => {
      const tx = db.transaction(storeName, mode);
      const store = tx.objectStore(storeName);
      let result;

      try {
        result = operation(store);
      } catch (error) {
        reject(error);
        return;
      }

      tx.oncomplete = () => resolve(result && result.result);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error || new Error("Database operation aborted."));
    });
  }

  async function all(storeName) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const request = db.transaction(storeName, "readonly").objectStore(storeName).getAll();
      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
    });
  }

  async function get(storeName, id) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const request = db.transaction(storeName, "readonly").objectStore(storeName).get(id);
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error);
    });
  }

  async function byIndex(storeName, indexName, value) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const request = db.transaction(storeName, "readonly")
        .objectStore(storeName).index(indexName).get(value);
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error);
    });
  }

  async function add(storeName, record) {
    return transaction(storeName, "readwrite", store => store.add(record));
  }

  async function put(storeName, record) {
    return transaction(storeName, "readwrite", store => store.put(record));
  }

  async function remove(storeName, id) {
    await transaction(storeName, "readwrite", store => store.delete(id));
  }

  function makeToken() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return "ef-" + Date.now().toString(36) + "-" +
      Math.random().toString(36).slice(2, 14);
  }

  async function registerProduct(data) {
    const batch = String(data.batch_code || "").trim();
    if (!batch) throw new Error("Batch code is required.");

    if (await byIndex("products", "batch_code", batch)) {
      throw new Error("A product with this batch code already exists on this device.");
    }

    const record = {
      ...data,
      name: String(data.name || "").trim(),
      category: String(data.category || "").trim(),
      batch_code: batch,
      quantity_kg: Number(data.quantity_kg),
      status: "registered",
      created_at: new Date().toISOString(),
      storage_type: "device-local"
    };

    if (!record.name || !record.category || !(record.quantity_kg > 0)) {
      throw new Error("Enter a valid product name, category and quantity.");
    }

    return add("products", record);
  }

  async function getProductByBatch(batch) {
    return byIndex("products", "batch_code", String(batch || "").trim());
  }

  async function createQR(batch) {
    const product = await getProductByBatch(batch);
    if (!product) throw new Error("Product not found on this device.");

    let existing = await byIndex("qr_codes", "batch_code", product.batch_code);
    if (existing) return { qr: existing, payload: existing.payload };

    const token = makeToken();

    // Compact portable product snapshot. No database ID is needed on another device.
    const snapshot = {
      v: 1,
      n: product.name,
      c: product.category,
      b: product.batch_code,
      q: product.quantity_kg,
      m: product.manufacturer || "",
      o: product.origin || "",
      r: product.registration_number || "",
      pd: product.production_date || "",
      ed: product.expiry_date || "",
      d: product.description || "",
      i: product.ingredients || "",
      nc: product.nutrient_composition || "",
      be: product.benefits || "",
      sc: product.suitable_crops || "",
      ai: product.application_instructions || "",
      si: product.safety_instructions || "",
      st: product.storage_instructions || ""
    };

    const bytes = new TextEncoder().encode(JSON.stringify(snapshot));
    let binary = "";
    bytes.forEach(byte => binary += String.fromCharCode(byte));
    const encoded = btoa(binary)
      .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");

    const payload = "EF1:" + encoded;

    const record = {
      token,
      batch_code: product.batch_code,
      product_id: product.id,
      payload,
      created_at: new Date().toISOString()
    };

    const id = await add("qr_codes", record);
    record.id = id;
    return { qr: record, payload };
  }

  function decodeQR(payload) {
    const value = String(payload || "").trim();
    if (!value.startsWith("EF1:")) return null;

    try {
      let encoded = value.slice(4).replace(/-/g, "+").replace(/_/g, "/");
      encoded += "=".repeat((4 - encoded.length % 4) % 4);
      const binary = atob(encoded);
      const bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
      const data = JSON.parse(new TextDecoder().decode(bytes));

      if (data.v !== 1 || !data.b || !data.n) {
        throw new Error("Invalid product QR data.");
      }
      return data;
    } catch {
      throw new Error("This product QR code could not be read.");
    }
  }

  async function addCameraRecord(record) {
    return add("camera_records", {
      ...record,
      captured_at: record.captured_at || new Date().toISOString(),
      review_status: record.analysis ? "analyzed" : "pending",
      storage_type: "device-local"
    });
  }

  async function queueRecognition(record) {
    return add("sync_queue", {
      ...record,
      status: "pending",
      created_at: new Date().toISOString()
    });
  }

  async function getStats() {
    const [products, farmers, quality, camera] = await Promise.all([
      all("products"), all("farmers"),
      all("quality_records"), all("camera_records")
    ]);

    return {
      products: products.length,
      farmers: farmers.length,
      quality_records: quality.length,
      camera_records: camera.length,
      total_quantity: products.reduce((sum, item) => sum + (Number(item.quantity_kg) || 0), 0)
    };
  }

  async function exportBackup() {
    const backup = { app: "EthioFerti AI", version: 1, exported_at: new Date().toISOString(), data: {} };
    for (const name of Object.keys(STORES)) backup.data[name] = await all(name);
    return backup;
  }

  async function importBackup(backup) {
    if (!backup || backup.app !== "EthioFerti AI" || !backup.data) {
      throw new Error("This is not a valid EthioFerti backup.");
    }

    for (const name of Object.keys(STORES)) {
      const records = backup.data[name];
      if (!Array.isArray(records)) continue;
      for (const record of records) await put(name, record);
    }
    return true;
  }

  async function importExistingServerRecords() {
    const response = await fetch("/api/v1/products");
    if (!response.ok) throw new Error("Could not read existing server products.");

    const products = await response.json();
    let imported = 0;

    for (const product of products) {
      if (!await getProductByBatch(product.batch_code)) {
        const copy = { ...product };
        delete copy.id;
        await registerProduct(copy);
        imported++;
      }
    }
    return imported;
  }

  window.EthioFertiDB = {
    openDB, all, get, byIndex, add, put, remove,
    registerProduct, getProductByBatch,
    createQR, decodeQR, addCameraRecord, queueRecognition,
    getStats, exportBackup, importBackup,
    importExistingServerRecords
  };

  openDB().catch(error => console.error("EthioFerti local database:", error));
})();
