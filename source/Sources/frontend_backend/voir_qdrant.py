#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script pour consulter les documents indexés dans Qdrant
"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

print("=" * 75)
print("🔍 QDRANT - CONSULTATION")
print("=" * 75)
print()

try:
    qdrant = QdrantClient("localhost", port=6333)
    print("✅ Connecté à Qdrant")
    
    # Vérifier la collection
    collections = qdrant.get_collections()
    collection_names = [col.name for col in collections.collections]
    
    if "medicaments_mistral" not in collection_names:
        print("❌ Collection 'medicaments_mistral' n'existe pas!")
        print(f"Collections disponibles: {collection_names}")
        sys.exit(1)
    
    info = qdrant.get_collection("medicaments_mistral")
    print(f"✅ Collection 'medicaments_mistral': {info.points_count} documents")
    print()
    
    if info.points_count == 0:
        print("⚠️  Aucun document dans Qdrant")
        sys.exit(0)
    
    # Afficher quelques documents
    print("📋 Premiers documents:")
    print()
    
    # Utiliser une recherche dummy pour récupérer les documents
    model = SentenceTransformer("all-MiniLM-L6-v2")
    dummy_vector = model.encode("test").tolist()
    
    results = qdrant.search(
        collection_name="medicaments_mistral",
        query_vector=dummy_vector,
        limit=20
    )
    
    for i, result in enumerate(results, 1):
        payload = result.payload
        print(f"{i}. {payload.get('nom', 'N/A')}")
        print(f"   URL: {payload.get('url', 'N/A')[:60]}")
        print(f"   Complétude: {payload.get('pourcentage_completude', 0):.1f}%")
        print(f"   Date: {payload.get('date_traitement', 'N/A')[:10]}")
        print()
    
    print("=" * 75)
    print(f"Total dans Qdrant: {info.points_count} documents indexés")
    print("=" * 75)
    
except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
