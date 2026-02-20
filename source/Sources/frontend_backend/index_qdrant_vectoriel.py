#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Indexation AMÉLIORÉE avec beaucoup plus de contexte médical
Pour requête: "antibiotique infections graves"
Les résultats seront VRAIS
"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv
import time
import hashlib

# CONFIG
load_dotenv()
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/medicsearch')
QDRANT_HOST = os.getenv('QDRANT_HOST', 'localhost')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', 6333))

BATCH_SIZE_UPSERT = 256
BATCH_SIZE_EMBEDDING = 128
COLLECTION = "medicaments"
MODEL = "all-MiniLM-L6-v2"


class IndexerAmeliore:
    def __init__(self):
        self.model = None
        self.mongo = None
        self.qdrant = None

    def load_model(self):
        if self.model is None:
            print("⏳ Chargement modèle...", flush=True)
            self.model = SentenceTransformer(MODEL)
            print(f"✅ {MODEL} chargé", flush=True)
        return self.model

    def create_id(self, text):
        return int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**63 - 1)

    def create_collection(self):
        print(f"📦 Collection: {COLLECTION}", flush=True)
        cols = [c.name for c in self.qdrant.get_collections().collections]
        
        if COLLECTION in cols:
            print("🔄 Suppression...", flush=True)
            self.qdrant.delete_collection(COLLECTION)
        
        self.qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        print(f"✅ {COLLECTION} créée", flush=True)

    def creer_texte_riche(self, doc):
        """
        Crée un texte riche avec le contexte complet du médicament
        """
        nom = doc.get('nom', 'Unknown')
        composition = doc.get('composition', '')
        indications = doc.get('indications', '')
        interactions = doc.get('interactions', '')
        effets_secondaires = doc.get('effets_secondaires', '')
        contre_indications = doc.get('contre_indications', '')
        posologie = doc.get('posologie', '')
        mises_en_garde = doc.get('mises_en_garde', '')
        interactions_graves = doc.get('interactions_graves', '')
        
        # Texte enrichi avec tous les champs disponibles
        texte_riche = f"""
        [NOM] {nom}
        [COMPOSITION] {composition}
        [INDICATIONS] {indications}
        [POSOLOGIE] {posologie}
        [CONTRE_INDICATIONS] {contre_indications}
        [EFFETS_SECONDAIRES] {effets_secondaires}
        [INTERACTIONS] {interactions}
        [INTERACTIONS_GRAVES] {interactions_graves}
        [MISES_EN_GARDE] {mises_en_garde}
        """.strip()
        
        return texte_riche

    def prepare_batch(self, documents):
        model = self.load_model()
        texts = []
        metadatas = []

        for doc in documents:
            nom = doc.get('nom', 'Unknown')
            
            # Utiliser le texte RICHE
            texte_riche = self.creer_texte_riche(doc)
            
            texts.append(texte_riche)
            metadatas.append({
                'nom': nom,
                'composition': doc.get('composition', '')[:200],
                'indications': doc.get('indications', '')[:200],
                'interactions': doc.get('interactions', '')[:200],
                'effets_secondaires': doc.get('effets_secondaires', '')[:150],
                'contre_indications': doc.get('contre_indications', '')[:150],
                'posologie': doc.get('posologie', '')[:200],
                'mises_en_garde': doc.get('mises_en_garde', '')[:150],
                'interactions_graves': doc.get('interactions_graves', '')[:200],
                'url': doc.get('url', ''),
                'completude': doc.get('pourcentage_completude', 0),
                'mongo_id': str(doc.get('_id', ''))  # ✅ Stocker l'ObjectId MongoDB
            })

        # Encoder TOUS les textes riches en batch
        vectors = model.encode(texts, batch_size=BATCH_SIZE_EMBEDDING, show_progress_bar=False)

        points = []
        for vector, metadata, doc in zip(vectors, metadatas, documents):
            point = PointStruct(
                id=self.create_id(metadata['nom']),
                vector=vector.tolist() if hasattr(vector, 'tolist') else list(vector),
                payload=metadata
            )
            points.append(point)

        return points

    def index(self, documents):
        total = len(documents)
        start = time.time()

        print(f"🚀 Indexation {total} documents (VERSION AMÉLIORÉE)", flush=True)
        print()

        for batch_idx in range(0, total, BATCH_SIZE_UPSERT):
            batch = documents[batch_idx:batch_idx + BATCH_SIZE_UPSERT]
            points = self.prepare_batch(batch)
            
            self.qdrant.upsert(collection_name=COLLECTION, points=points)

            percent = ((batch_idx + len(batch)) / total) * 100
            elapsed = int(time.time() - start)

            print(f"✓ [{batch_idx + len(batch)}/{total}] ({percent:.1f}%) - {elapsed}s", flush=True)

        elapsed = int(time.time() - start)
        speed = total / elapsed if elapsed > 0 else 0

        print("\n" + "="*80)
        print(f"✅ {total} documents indexés (AMÉLIORÉ)")
        print(f"📁 Collection: {COLLECTION}")
        print(f"⏱️  Temps: {elapsed}s")
        print(f"⚡ Vitesse: {speed:.1f} docs/sec")
        print("="*80)
        print("\n✨ Indexation complète avec:")
        print("  ✓ Composition")
        print("  ✓ Indications")
        print("  ✓ Posologie")
        print("  ✓ Contre-indications")
        print("  ✓ Effets secondaires")
        print("  ✓ Interactions")
        print("  ✓ Interactions graves")
        print("  ✓ Mises en garde")
        print("="*80)

        return elapsed


def main():
    print("\n" + "="*80)
    print("🔍 INDEXATION VECTORIELLE AMÉLIORÉE")
    print("="*80)

    indexer = IndexerAmeliore()

    try:
        print("\n🔌 Connexion MongoDB...", flush=True)
        indexer.mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = indexer.mongo['medicsearch']
        col = db['medicaments_traites']
        print("✅ OK", flush=True)

        print("🔌 Connexion Qdrant...", flush=True)
        indexer.qdrant = QdrantClient(QDRANT_HOST, port=QDRANT_PORT)
        print("✅ OK", flush=True)

        indexer.create_collection()

        print("\n📥 Récupération documents...", flush=True)
        documents = list(col.find())
        print(f"✅ {len(documents)} trouvés", flush=True)

        if documents:
            indexer.index(documents)

        indexer.mongo.close()

    except Exception as e:
        print(f"❌ Erreur: {e}", flush=True)
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()