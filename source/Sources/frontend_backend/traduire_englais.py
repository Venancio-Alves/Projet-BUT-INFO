#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script to translate treated medicines to English
- Retrieves medicines from MongoDB collection
- Translates fields with Mistral
- Saves in a new collection
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import requests
import time

# Load .env
script_dir = Path(__file__).parent
env_path = script_dir / '.env'
load_dotenv(env_path)

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/medicsearch')
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')
DB_NAME = 'medicsearch'

if not MISTRAL_API_KEY:
    print("❌ Error: MISTRAL_API_KEY not configured in .env")
    sys.exit(1)


def translate_with_mistral(text_fr):
    """Translates text from French to English with Mistral"""
    if not text_fr or len(text_fr.strip()) < 2:
        return text_fr
    
    try:
        prompt = f"""Translate this medical text from French to English. 
Keep the same structure and format exactly like the original.
Just provide the translation, nothing else.

French text:
{text_fr}

English translation:"""
        
        time.sleep(0.2)  # Rate limiting
        
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 1000
            },
            timeout=120  # Increased to 120 seconds for slower connections
        )
        
        response.raise_for_status()
        message = response.json()
        translation = message['choices'][0]['message']['content'].strip()
        return translation
    
    except requests.exceptions.Timeout:
        print(f"   ⚠️  Translation timeout (network too slow)")
        return text_fr
    except requests.exceptions.ConnectionError as e:
        print(f"   ⚠️  Connection error: {str(e)[:30]}")
        return text_fr
    except requests.exceptions.SSLError as e:
        print(f"   ⚠️  SSL error: {str(e)[:30]}")
        return text_fr
    except KeyboardInterrupt:
        print(f"\n   ⚠️  Translation interrupted by user")
        raise
    except Exception as e:
        print(f"   ⚠️  Translation error: {str(e)[:50]}")
        return text_fr


def translate_raw_medicine(doc):
    """Translates raw medicine RCP sections"""
    doc_en = {
        '_id': doc['_id'],
        'nom': doc.get('nom', ''),
        'url': doc.get('url', ''),
    }
    
    # Translate sections_rcp if they exist
    if 'sections_rcp' in doc and isinstance(doc['sections_rcp'], dict):
        doc_en['sections_rcp'] = {}
        
        for section_num, section_data in doc['sections_rcp'].items():
            doc_en['sections_rcp'][section_num] = {}
            
            # Translate titre
            titre_fr = section_data.get('titre', '')
            if titre_fr and isinstance(titre_fr, str):
                titre_en = translate_with_mistral(titre_fr)
                doc_en['sections_rcp'][section_num]['titre'] = titre_en
            else:
                doc_en['sections_rcp'][section_num]['titre'] = titre_fr
            
            # Translate contenu
            contenu_fr = section_data.get('contenu', '')
            if contenu_fr and isinstance(contenu_fr, str):
                print(f"      Translating section {section_num} ({titre_fr[:30]})...", end='', flush=True)
                contenu_en = translate_with_mistral(contenu_fr)
                doc_en['sections_rcp'][section_num]['contenu'] = contenu_en
                print(" ✅")
            else:
                doc_en['sections_rcp'][section_num]['contenu'] = contenu_fr
    else:
        doc_en['sections_rcp'] = doc.get('sections_rcp', {})
    
    # Copy metadata
    doc_en['date_creation'] = doc.get('date_creation', '')
    doc_en['date_traduction'] = datetime.now().isoformat()
    doc_en['langue'] = 'english'
    
    return doc_en


def translate_medicine(doc):
    """Translates all fields of a medicine"""
    
    fields_to_translate = [
        'composition',
        'posologie',
        'indications',
        'effets_secondaires',
        'contre_indications',
        'interactions',
        'interactions_graves',
        'mises_en_garde'
    ]
    
    doc_en = {
        '_id': doc['_id'],
        'nom': doc.get('nom', ''),
        'url': doc.get('url', ''),
    }
    
    # Translate fields with Mistral
    for field in fields_to_translate:
        text_fr = doc.get(field, '')
        if text_fr and isinstance(text_fr, str):
            print(f"   Translating: {field[:30]}...", end='', flush=True)
            text_en = translate_with_mistral(text_fr)
            doc_en[field] = text_en
            print(" ✅")
        else:
            doc_en[field] = text_fr
    
    # Copy other fields
    doc_en['statut_completude'] = doc.get('statut_completude', '')
    doc_en['pourcentage_completude'] = doc.get('pourcentage_completude', 0)
    doc_en['date_traitement'] = doc.get('date_traitement', '')
    doc_en['date_traduction'] = datetime.now().isoformat()
    doc_en['langue'] = 'english'
    
    return doc_en


def main():
    print("\n" + "="*60)
    print("🌍 TRANSLATING MEDICINES TO ENGLISH (Mistral)")
    print("="*60)
    print()
    
    # Connect to MongoDB
    try:
        print("🔌 Connecting to MongoDB...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]
        col_treated_fr = db['medicaments_traites']
        col_treated_en = db['medicaments_traites_en']
        col_raw_fr = db['medic_brut']
        col_raw_en = db['medic_brut_en']
        print("✅ Connected!")
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    treated_translated = 0
    raw_translated = 0
    total_errors = 0
    
    print("\n📥 Retrieving medicines...")
    docs_treated = list(col_treated_fr.find({}))
    print(f"✅ {len(docs_treated)} treated medicines found")
    
    if not docs_treated:
        print("❌ No documents to translate")
        return False
    
    print(f"\n🌍 Processing {len(docs_treated)} medicines (treated + raw RCP)...")
    print("="*60)
    
    # Process each medicine: TREATED then RAW for same medicine
    for idx, doc_treated in enumerate(docs_treated, 1):
        nom = doc_treated.get('nom', 'Unknown')[:40]
        print(f"\n[{idx}/{len(docs_treated)}] {nom}")
        
        # === 1. TRANSLATE TREATED MEDICINE ===
        try:
            print(f"  📝 Translating treated...", end='', flush=True)
            doc_en = translate_medicine(doc_treated)
            col_treated_en.replace_one(
                {"_id": doc_en["_id"]},
                doc_en,
                upsert=True
            )
            treated_translated += 1
            print(" ✅")
        except Exception as e:
            total_errors += 1
            print(f" ❌ Error: {str(e)[:40]}")
        
        # === 2. TRANSLATE RAW MEDICINE (same medicine) ===
        try:
            # Search by URL instead of nom (more reliable)
            url_treated = doc_treated.get('url', '').strip()
            if url_treated:
                doc_raw = col_raw_fr.find_one({"url": url_treated})
                if doc_raw:
                    print(f"  🔧 Translating raw (RCP)...", end='', flush=True)
                    doc_raw_en = translate_raw_medicine(doc_raw)
                    col_raw_en.replace_one(
                        {"_id": doc_raw_en["_id"]},
                        doc_raw_en,
                        upsert=True
                    )
                    raw_translated += 1
                    print(" ✅")
                else:
                    print(f"  🔧 No raw data found for this URL")
            else:
                print(f"  🔧 No URL available")
        except Exception as e:
            total_errors += 1
            print(f"  🔧 Error: {str(e)[:40]}")
    
    # Summary
    print("\n" + "="*60)
    print("✅ TRANSLATION COMPLETED")
    print("="*60)
    print(f"  📝 Treated medicines: {treated_translated}/{len(docs_treated)}")
    print(f"  🔧 Raw medicines (RCP): {raw_translated}/{len(docs_treated)}")
    print(f"  ❌ Total errors: {total_errors}")
    print(f"  📁 Collections: medicaments_traites_en, medic_brut_en")
    print("="*60 + "\n")
    
    client.close()
    return True


if __name__ == '__main__':
    main()
