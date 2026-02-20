#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script pour indexer les données Mistral traitées dans Qdrant
Utilise la collection 'medic_mistral' de MongoDB contenant les données structurées
"""

from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from sentence_transformers import SentenceTransformer
import uuid
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/medicsearch')

print("=" * 75)
print("🔍 INDEXATION QDRANT - Données Mistral")
print("=" * 75)
print()

try:
    print("🔌 Connexion à MongoDB...")
    mongo = MongoClient(MONGO_URI)
    db = mongo["medicsearch"]
    collection = db["medic_mistral"]  # ✅ Collection avec données Mistral
    print("✅ MongoDB connecté")
    print()
    
    print("🔌 Connexion à Qdrant...")
    qdrant = QdrantClient("localhost", port=6333)
    print("✅ Qdrant connecté")
    print()
    
    print("🔧 Vérification collection Qdrant...")
    collections = qdrant.get_collections()
    collection_names = [col.name for col in collections.collections]
    
    if "medicaments_mistral" not in collection_names:
        print("📝 Création de la collection 'medicaments_mistral'...")
        qdrant.create_collection(
            collection_name="medicaments_mistral",
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        print("✅ Collection créée")
    else:
        print("✅ Collection 'medicaments_mistral' existe déjà")
    print()
    
    print("🔬 Chargement du modèle d'embedding...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print("✅ Modèle chargé (all-MiniLM-L6-v2, 384 dimensions)")
    print()
    
    print("📥 Récupération des documents depuis MongoDB...")
    docs = list(collection.find({}))
    total_docs = len(docs)
    print(f"✅ {total_docs} documents récupérés")
    
    if total_docs == 0:
        print("\n⚠️  Aucun document trouvé dans medic_mistral!")
        print("   Assurez-vous d'avoir d'abord exécuté traiter_mistral.py")
        mongo.close()
        exit(1)
    print()
    
    print("📊 Génération des embeddings...")
    points = []
    skipped = 0
    
    for i, doc in enumerate(docs, 1):
        try:
            # Construire le texte à partir des champs Mistral
            texte_parts = [
                doc.get("nom", ""),
                doc.get("composition", ""),
                doc.get("posologie", ""),
                doc.get("indications", ""),
                doc.get("effets_secondaires", ""),
                doc.get("contre_indications", ""),
                doc.get("interactions", ""),
                doc.get("mises_en_garde", "")
            ]
            text = " ".join([str(p) for p in texte_parts if p]).strip()
            
            if not text or len(text) < 10:
                skipped += 1
                continue
            
            mongo_id = doc["_id"]
            # Convertir ObjectId en UUID
            padded = mongo_id.binary + b'\x00' * 4
            point_id = str(uuid.UUID(bytes=padded))
            
            # Générer l'embedding
            embedding = model.encode(text).tolist()
            
            # Créer le point Qdrant
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "nom": doc.get("nom", ""),
                    "mongo_id": str(mongo_id),
                    "posologie": doc.get("posologie", "")[:500],
                    "effets_secondaires": doc.get("effets_secondaires", "")[:500],
                    "contre_indications": doc.get("contre_indications", "")[:500],
                    "interactions": doc.get("interactions", "")[:500],
                    "composition": doc.get("composition", "")[:500],
                    "statut_completude": doc.get("statut_completude", ""),
                    "pourcentage_completude": doc.get("pourcentage_completude", 0)
                }
            )
            
            points.append(point)
            
            if i % 50 == 0:
                print(f"  {i}/{total_docs} traités...", end="\r")
        
        except Exception as e:
            print(f"\n  ⚠️  Erreur doc {i}: {str(e)[:50]}")
            skipped += 1
            continue
    
    print(f"\n✅ {len(points)} embeddings générés ({skipped} ignorés)")
    print()
    
    if len(points) == 0:
        print("❌ Aucun point à indexer!")
        mongo.close()
        exit(1)
    
    print("📤 Indexation dans Qdrant par lots...")
    BATCH_SIZE = 256
    total = len(points)
    
    for i in range(0, total, BATCH_SIZE):
        batch = points[i:i+BATCH_SIZE]
        qdrant.upsert(collection_name="medicaments_mistral", points=batch)
        current = min(i+BATCH_SIZE, total)
        percentage = round((current / total) * 100, 1)
        print(f"  ✓ {current}/{total} ({percentage}%)")
    
    print()
    print("=" * 75)
    print("✅ INDEXATION TERMINÉE")
    print("=" * 75)
    print(f"  📦 Documents indexés: {total}")
    print(f"  🔍 Collection Qdrant: medicaments_mistral")
    print(f"  📐 Dimension vecteurs: 384")
    print(f"  📏 Distance: COSINE")
    print("=" * 75)
    
    mongo.close()
    
except Exception as e:
    print(f"\n❌ Erreur critique: {str(e)}")
    import traceback
    traceback.print_exc()

