#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script simple pour exporter la base MongoDB
Crée un fichier ZIP avec toutes les données
"""

import json
import os
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import zipfile
import shutil

# Charger .env
script_dir = Path(__file__).parent
env_path = script_dir / '.env'
load_dotenv(env_path)

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/medicsearch')
DB_NAME = 'medicsearch'


class MongoEncoder(json.JSONEncoder):
    """Convertir ObjectId et datetime en strings"""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def exporter_base():
    """Exporte la base et crée un ZIP"""
    
    print("\n" + "="*60)
    print("📦 EXPORT BASE MONGODB")
    print("="*60)
    
    # Connexion MongoDB
    try:
        print("🔌 Connexion MongoDB...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]
        print("✅ Connecté!")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False
    
    # Créer dossier temporaire
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = Path("export_temp")
    temp_dir.mkdir(exist_ok=True)
    
    # Exporter chaque collection
    print("\n📥 Export collections...")
    try:
        for collection_name in db.list_collection_names():
            docs = list(db[collection_name].find({}))
            
            if docs:
                filename = temp_dir / f"{collection_name}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(docs, f, cls=MongoEncoder, indent=2, ensure_ascii=False)
                print(f"  ✅ {collection_name}: {len(docs)} documents")
            else:
                print(f"  ⏭️  {collection_name}: vide")
    
    except Exception as e:
        print(f"❌ Erreur export: {e}")
        return False
    
    # Créer ZIP
    print("\n📦 Compression...")
    zip_name = f"medicsearch_backup_{timestamp}.zip"
    
    try:
        shutil.make_archive(zip_name[:-4], 'zip', temp_dir)
        shutil.rmtree(temp_dir)
        
        size_mb = Path(zip_name).stat().st_size / 1024 / 1024
        print(f"✅ Fichier créé: {zip_name} ({size_mb:.1f} MB)")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False
    
    # Résumé
    print("\n" + "="*60)
    print(f"✅ EXPORT TERMINÉ!")
    print(f"📁 Fichier: {zip_name}")
    print(f"📤 Tu peux envoyer ce fichier à tes potes")
    print("="*60 + "\n")
    
    client.close()
    return True


if __name__ == '__main__':
    exporter_base()
