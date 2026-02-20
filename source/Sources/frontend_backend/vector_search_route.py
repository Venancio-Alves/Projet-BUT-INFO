#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Route de recherche vectorielle pour Flask
À intégrer dans app.py
"""

from flask import Blueprint, request, jsonify, render_template
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv

# Configuration
load_dotenv()
QDRANT_HOST = os.getenv('QDRANT_HOST', 'qdrant')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', 6333))

# Clients
qdrant_client = QdrantClient(QDRANT_HOST, port=QDRANT_PORT)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# Blueprint
vector_search_bp = Blueprint('vector_search', __name__)

# Note: medicines_collection sera passé dynamiquement par app.py
# Voir app.py register_vector_search_blueprint()
medicines_collection = None

def register_vector_search_blueprint(app, medicines_coll):
    """Enregistrer le blueprint avec la collection MongoDB"""
    global medicines_collection
    medicines_collection = medicines_coll
    app.register_blueprint(vector_search_bp)
    print(f"🔗 Vector search blueprint registered with MongoDB collection", flush=True)


def create_id(text):
    """Génère un ID unique basé sur le hash"""
    import hashlib
    return int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**63 - 1)


def get_medicine_by_id(qdrant_id):
    """Récupère un médicament MongoDB par l'ID Qdrant"""
    try:
        # Chercher dans MongoDB par le nom
        for doc in medicines_collection.find():
            doc_id = create_id(doc.get('nom', ''))
            if doc_id == qdrant_id:
                return doc
    except Exception as e:
        print(f"Erreur recherche MongoDB: {e}")
    return None


@vector_search_bp.route('/vector-search', methods=['GET', 'POST'])
def vector_search():
    """Page de recherche vectorielle"""
    query = request.args.get('query', '').strip()
    results = []
    error_msg = None
    
    if query:
        try:
            # Encoder la requête
            query_vector = embedding_model.encode(query).tolist()
            
            # Chercher dans Qdrant
            search_results = qdrant_client.query_points(
                collection_name="medicaments",
                query=query_vector,
                limit=50,
                with_vectors=False,
                with_payload=True
            ).points
            
            # Traiter les résultats
            results = []
            for idx, hit in enumerate(search_results):
                try:
                    # Récupérer le payload
                    payload = hit.payload if hasattr(hit, 'payload') else {}
                    
                    # Utiliser le mongo_id du payload s'il existe
                    mongo_id_str = payload.get('mongo_id', '') if payload else ''
                    nom = payload.get('nom', 'Unknown') if payload else 'Unknown'
                    mongo_id = None
                    
                    # Si mongo_id existe, l'utiliser avec conversion ObjectId
                    if mongo_id_str:
                        try:
                            mongo_obj_id = ObjectId(mongo_id_str)
                            medicine = medicines_collection.find_one({'_id': mongo_obj_id})
                            if medicine:
                                mongo_id = str(medicine.get('_id', ''))
                            else:
                                # Fallback : chercher par nom
                                medicine = medicines_collection.find_one({'nom': nom})
                                if medicine:
                                    mongo_id = str(medicine.get('_id', ''))
                        except Exception as e:
                            # Fallback : utiliser juste le mongo_id du payload
                            mongo_id = mongo_id_str
                    else:
                        # Si mongo_id n'existe pas, chercher par le nom dans MongoDB
                        medicine = medicines_collection.find_one({'nom': nom})
                        if medicine:
                            mongo_id = str(medicine.get('_id', ''))
                    
                    if mongo_id:
                        result_item = {
                            'id': mongo_id,
                            'nom': nom,
                            'composition': payload.get('composition', '')[:200] if payload else '',
                            'indications': payload.get('indications', '')[:200] if payload else '',
                            'interactions': payload.get('interactions', '')[:200] if payload else '',
                            'score': float(hit.score),
                            'payload': payload
                        }
                        results.append(result_item)
                except Exception as e:
                    continue
        
        except Exception as e:
            error_msg = f"Erreur recherche: {str(e)}"
            print(f"❌ {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            results = []
    
    return render_template(
        'vector_search.html',
        query=query,
        results=results,
        error=error_msg,
        initial_count=10
    )


@vector_search_bp.route('/api/vector-search', methods=['POST'])
def api_vector_search():
    """API pour recherche vectorielle JSON"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        limit = data.get('limit', 50)
        
        if not query:
            return jsonify({'error': 'Query required'}), 400
        
        # Encoder la requête
        query_vector = embedding_model.encode(query).tolist()
        
        # Chercher dans Qdrant
        search_results = qdrant_client.query_points(
            collection_name="medicaments",
            query=query_vector,
            limit=limit,
            with_vectors=False,
            with_payload=True
        ).points
        
        # Traiter les résultats
        results = []
        for hit in search_results:
            try:
                # Récupérer le payload
                payload = hit.payload if hasattr(hit, 'payload') else {}
                
                # Utiliser le mongo_id du payload s'il existe
                mongo_id_str = payload.get('mongo_id', '') if payload else ''
                nom = payload.get('nom', 'Unknown') if payload else 'Unknown'
                mongo_id = None
                
                # Si mongo_id existe, l'utiliser avec conversion ObjectId
                if mongo_id_str:
                    try:
                        mongo_obj_id = ObjectId(mongo_id_str)
                        medicine = medicines_collection.find_one({'_id': mongo_obj_id})
                        if medicine:
                            mongo_id = str(medicine.get('_id', ''))
                    except:
                        # Fallback : chercher par nom
                        medicine = medicines_collection.find_one({'nom': nom})
                        if medicine:
                            mongo_id = str(medicine.get('_id', ''))
                else:
                    # Si mongo_id n'existe pas, chercher par le nom dans MongoDB
                    medicine = medicines_collection.find_one({'nom': nom})
                    if medicine:
                        mongo_id = str(medicine.get('_id', ''))
                
                if mongo_id:
                    results.append({
                        'id': mongo_id,
                        'nom': nom,
                        'composition': payload.get('composition', '')[:200],
                        'indications': payload.get('indications', '')[:200],
                        'interactions': payload.get('interactions', ''),
                        'score': float(hit.score),
                        'metadata': payload
                    })
            except Exception as e:
                continue
        
        return jsonify({
            'query': query,
            'total_results': len(results),
            'results': results
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# from vector_search_route import vector_search_bp
# app.register_blueprint(vector_search_bp)
