#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script pour supprimer les collections Qdrant
"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv

# Charger variables d'environnement
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
load_dotenv(env_path)

QDRANT_HOST = os.getenv('QDRANT_HOST', 'localhost')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', 6333))

def main():
    print("=" * 80)
    print("🗑️  SUPPRESSION DES COLLECTIONS QDRANT")
    print("=" * 80)
    print()
    
    try:
        # Connexion Qdrant
        print("🔌 Connexion Qdrant...", flush=True)
        client = QdrantClient(QDRANT_HOST, port=QDRANT_PORT)
        print("✅ Qdrant connecté", flush=True)
        print()
        
        # Récupérer les collections
        collections = [c.name for c in client.get_collections().collections]
        print(f"📦 Collections actuelles: {len(collections)}", flush=True)
        for col in collections:
            print(f"   • {col}", flush=True)
        print()
        
        # Collections à supprimer
        collections_to_delete = [
            "medicaments_indications",
            "medicaments_composition",
            "medicaments_interactions"
        ]
        
        print("🗑️  Suppression des collections...", flush=True)
        print()
        
        deleted_count = 0
        for collection_name in collections_to_delete:
            if collection_name in collections:
                try:
                    client.delete_collection(collection_name)
                    print(f"✅ Supprimée: {collection_name}", flush=True)
                    deleted_count += 1
                except Exception as e:
                    print(f"❌ Erreur suppression {collection_name}: {e}", flush=True)
            else:
                print(f"ℹ️  N'existe pas: {collection_name}", flush=True)
        
        print()
        print("=" * 80)
        print(f"✅ SUPPRESSION TERMINÉE - {deleted_count} collection(s) supprimée(s)")
        print("=" * 80)
        print()
    
    except Exception as e:
        print(f"❌ Erreur critique: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
