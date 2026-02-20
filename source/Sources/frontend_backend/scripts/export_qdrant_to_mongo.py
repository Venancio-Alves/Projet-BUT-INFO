#!/usr/bin/env python3
"""
Script pour exporter les données de Qdrant vers MongoDB
Récupère tous les points de la collection 'medicaments_mistral' dans Qdrant
et les insère dans la collection 'mistral-medic' dans MongoDB
"""

import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient
from pymongo import MongoClient, ASCENDING
import time

def export_qdrant_to_mongo():
    """Exporte les données de Qdrant vers MongoDB"""
    
    # Configuration Qdrant
    QDRANT_HOST = "localhost"  # Utilise localhost quand on exécute depuis la machine hôte
    QDRANT_PORT = 6333
    QDRANT_COLLECTION = "medicaments_mistral"
    
    # Configuration MongoDB
    MONGO_URI = "mongodb://localhost:27017/medicsearch"  # Utilise localhost depuis la machine hôte
    MONGO_COLLECTION = "mistral-medic"
    
    try:
        print("🔌 Connexion à Qdrant...")
        qdrant_client = QdrantClient(QDRANT_HOST, port=QDRANT_PORT)
        
        # Vérifier que la collection existe
        collections = qdrant_client.get_collections()
        collection_names = [col.name for col in collections.collections]
        
        if QDRANT_COLLECTION not in collection_names:
            print(f"❌ La collection '{QDRANT_COLLECTION}' n'existe pas dans Qdrant")
            print(f"Collections disponibles: {collection_names}")
            return False
        
        print(f"✅ Collection Qdrant '{QDRANT_COLLECTION}' trouvée")
        
        # Récupérer tous les points de Qdrant
        print("📥 Récupération des données de Qdrant...")
        all_points = []
        offset = 0
        limit = 100
        total_count = 0
        
        while True:
            points = qdrant_client.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            if not points[0]:
                break
            
            all_points.extend(points[0])
            offset += len(points[0])
            total_count = points[1]
            
            print(f"  Récupéré {len(all_points)}/{total_count} points...")
        
        print(f"✅ {len(all_points)} points récupérés de Qdrant")
        
        if not all_points:
            print("⚠️  Aucun point trouvé dans Qdrant")
            return False
        
        # Connexion MongoDB
        print("🔌 Connexion à MongoDB...")
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client['medicsearch']
        collection = db[MONGO_COLLECTION]
        
        # Préparer les documents pour MongoDB
        print("📝 Préparation des documents...")
        documents = []
        
        for point in all_points:
            # Créer un document avec l'ID Qdrant et tous les champs du payload directement
            doc = {'qdrant_id': point.id}
            if hasattr(point, 'payload') and point.payload:
                doc.update(point.payload)
            documents.append(doc)
        
        # Vider la collection existante
        print(f"🗑️  Vidage de la collection '{MONGO_COLLECTION}'...")
        collection.delete_many({})
        
        # Insérer les documents dans MongoDB
        print(f"💾 Insertion de {len(documents)} documents dans MongoDB...")
        result = collection.insert_many(documents)
        
        # Créer un index sur qdrant_id pour les recherches rapides
        print("📑 Création des index...")
        collection.create_index([('qdrant_id', ASCENDING)], unique=True)
        collection.create_index([('nom', ASCENDING)])
        
        print(f"✅ Succès! {len(result.inserted_ids)} documents insérés dans '{MONGO_COLLECTION}'")
        print(f"   - IDs insérés: {result.inserted_ids[:5]}..." if len(result.inserted_ids) > 5 else f"   - IDs insérés: {result.inserted_ids}")
        
        # Afficher des stats
        count = collection.count_documents({})
        print(f"📊 Collection '{MONGO_COLLECTION}' contient maintenant {count} documents")
        
        # Afficher un exemple de document
        example = collection.find_one({})
        if example:
            print("\n📋 Exemple de document:")
            # Afficher seulement les clés principales
            keys = list(example.keys())[:10]
            for key in keys:
                value = example[key]
                if isinstance(value, str):
                    value = value[:50] + "..." if len(value) > 50 else value
                print(f"   {key}: {value}")
        
        mongo_client.close()
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Export Qdrant → MongoDB")
    print("=" * 60)
    success = export_qdrant_to_mongo()
    print("=" * 60)
    sys.exit(0 if success else 1)
