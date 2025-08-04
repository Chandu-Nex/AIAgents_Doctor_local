import json
import os
import logging
import hashlib
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("logs/app.log"), logging.StreamHandler()]
)

def clean_text(text):
    """Remove newline chars and extra spaces"""
    return ' '.join(str(text).strip().replace('\n', ' ').split())

def build_chunk_from_entry(entry):
    name = clean_text(entry.get("name", "Unknown"))
    description = clean_text(entry.get("description", ""))
    symptoms = clean_text(entry.get("symptoms", ""))
    cause = clean_text(entry.get("cause", ""))
    precautions = clean_text(entry.get("precautions", ""))
    drugs = entry.get("drugs", "")
    drug_desc = entry.get("drug_descriptions", {})

    chunk = f"Disease: {name}. Description: {description}."

    if symptoms:
        chunk += f" Symptoms: {symptoms}."
    if cause:
        chunk += f" Cause: {cause}."
    if precautions:
        chunk += f" Precautions: {precautions}."
    if drugs:
        chunk += f" Drugs: {drugs}."

    if isinstance(drug_desc, dict):
        for drug, desc in drug_desc.items():
            chunk += f" Drug Detail - {drug}: {clean_text(desc)}."

    return chunk

def load_and_chunk(data_dir="./RAG/data"):
    chunks = []
    seen = set()

    all_files = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith(".json")]
    logging.info(f"🔍 Found {len(all_files)} JSON files in {data_dir}")

    for file in all_files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logging.error(f"❌ Failed to load {file}: {e}")
            continue

        count_before = len(chunks)

        for item in data:
            if not isinstance(item, dict):
                continue

            if "name" in item and "description" in item:
                if len(item.keys()) > 2:
                    chunk = build_chunk_from_entry(item)
                else:
                    chunk = f"Drug Name: {clean_text(item['name'])}. Description: {clean_text(item['description'])}."

                chunk_hash = hashlib.sha256(chunk.encode()).hexdigest()

                if chunk_hash not in seen:
                    seen.add(chunk_hash)
                    chunks.append(chunk)

        logging.info(f"📦 Processed {file} — added {len(chunks) - count_before} unique chunks.")

    with open(f"./RAG/chunks/{datetime.now().strftime('%Y%m%d_%H%M%S')}_chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    logging.info(f"✅ Finished: Created and saved {len(chunks)} unique chunks.")

if __name__ == "__main__":
    load_and_chunk()
 