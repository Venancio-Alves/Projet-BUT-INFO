#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Module de recherche Qdrant optimisé v2.0
Avec hybrid search, re-ranking, caching, et optimisations avancées
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from functools import lru_cache
from typing import List, Dict, Any
import hashlib
import time

load_dotenv()

class QdrantMedicSearchV2:
    """Classe pour gérer les recherches dans Qdrant avec optimisations avancées"""
    
    def __init__(self, qdrant_host="localhost", qdrant_port=6333):
        try:
            self.qdrant = QdrantClient(qdrant_host, port=qdrant_port)
            # Modèle d'embedding plus puissant (384 dimensions vs 384 pour L6)
            self.embedding_model = SentenceTransformer("all-mpnet-base-v2")
            self.collection_name = "medicaments_mistral"
            self.available = True
            
            # Cache pour les embeddings (évite de recalculer les mêmes)
            self.embedding_cache = {}
            
            # Stats
            self.stats = self._get_stats()
            print(f"✅ Qdrant Search V2.0 initialisé - {self.stats}")
            
        except Exception as e:
            print(f"❌ Erreur connexion Qdrant: {e}")
            self.available = False
    
    def _get_stats(self):
        """Obtient les stats de la collection"""
        try:
            info = self.qdrant.get_collection(self.collection_name)
            return f"{info.points_count} documents, {info.config.params.vectors.size}D vectors"
        except:
            return "Stats indisponibles"
    
    @lru_cache(maxsize=1000)
    def _get_embedding_cached(self, text: str) -> List[float]:
        """Cache les embeddings pour éviter de recalculer"""
        return self.embedding_model.encode(text).tolist()
    
    def _normalize_score(self, score: float) -> float:
        """Normalise les scores entre 0 et 1"""
        # Qdrant retourne des scores cosine (0 à 1 généralement)
        return min(max(score, 0), 1.0)
    
    def _exact_match_boost(self, query: str, nom: str, base_score: float) -> float:
        """Boost le score si c'est une correspondance exacte"""
        query_lower = query.lower().strip()
        nom_lower = nom.lower().strip()
        
        if nom_lower == query_lower:
            return min(base_score * 1.5, 1.0)  # +50% si match exact
        elif nom_lower.startswith(query_lower):
            return min(base_score * 1.3, 1.0)  # +30% si commence par
        elif query_lower in nom_lower:
            return min(base_score * 1.15, 1.0)  # +15% si contient
        return base_score
    
    def _keyword_relevance_boost(self, query: str, nom: str, indications: str, score: float) -> float:
        """
        Boost/pénalise le score selon la pertinence des keywords
        Moins strict pour éviter de filtrer trop de résultats
        """
        query_words = set(word for word in query.lower().split() if len(word) > 2)
        if not query_words:
            return score
            
        nom_lower = nom.lower()
        indications_lower = indications.lower() if indications else ""
        full_text = f"{nom_lower} {indications_lower}"
        
        # Chercher les keywords
        keyword_matches = sum(1 for word in query_words if word in full_text)
        total_words = len(query_words)
        
        # Scoring basé sur keywords - plus souple
        if total_words == 0:
            return score
        elif keyword_matches >= total_words * 0.7:
            # 70%+ keywords trouvés = excellent
            return min(score * 1.3, 1.0)
        elif keyword_matches >= total_words * 0.4:
            # 40%+ keywords = bon
            return min(score * 1.1, 1.0)
        elif keyword_matches > 0:
            # Quelques keywords = neutre
            return score
        else:
            # Aucun keyword = légère pénalité
            return score * 0.85
    
    def _calculate_relevance_score(self, query: str, result: Dict) -> float:
        """
        Calcule un score de pertinence multi-critères
        Équilibre entre vectoriel et keywords
        """
        base_score = result['score']
        nom = result.get('nom', '')
        indications = result.get('indications', '')
        
        # 1. Boost keyword relevance (30% du poids)
        keyword_boost = self._keyword_relevance_boost(query, nom, indications, 1.0) - 1.0
        keyword_component = keyword_boost * 0.3
        
        # 2. Boost exact match (20% du poids)
        exact_boost = self._exact_match_boost(query, nom, 1.0) - 1.0
        exact_component = exact_boost * 0.2
        
        # 3. Score vectoriel de base (45% du poids) - augmenté
        vector_component = base_score * 0.45
        
        # 4. Faible pénalité pour très faibles scores
        if base_score < 0.2:
            penalty = 0.08
        else:
            penalty = 0
        penalty_component = penalty * 0.05
        
        # Score final normalisé
        final_score = min(vector_component + keyword_component + exact_component + penalty_component, 1.0)
        return max(final_score, 0.0)
    
    def _rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """Re-classe les résultats avec scoring multi-critères"""
        reranked = []
        
        for result in results:
            original_score = result['score']
            relevance_score = self._calculate_relevance_score(query, result)
            result['score'] = relevance_score
            result['original_score'] = original_score
            reranked.append(result)
        
        # Trier par score descendant
        reranked.sort(key=lambda x: x['score'], reverse=True)
        return reranked
    
    def recherche_semantique(self, query: str, limit: int = 20, score_threshold: float = 0.25) -> List[Dict]:
        """
        Recherche sémantique avancée avec re-ranking multi-critères
        
        Args:
            query: Texte à chercher
            limit: Nombre de résultats max
            score_threshold: Score minimum (0-1) - 0.25 pour équilibre pertinence/couverture
        
        Returns:
            Résultats triés par pertinance
        """
        if not self.available or not query:
            return []
        
        try:
            query = query.strip()
            
            # 1. Générer l'embedding avec contexte médical
            # On ajoute du contexte pour améliorer la sémantique
            enriched_query = f"medicament: {query}"
            query_vector = self._get_embedding_cached(enriched_query)
            
            # 2. Recherche vectorielle - récupérer plus de résultats pour le re-ranking
            search_results = self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit * 3  # Récupérer 3x plus pour filtrer les meilleurs
            )
            
            # 3. Extraire et formatter les résultats
            results = []
            for result in search_results:
                payload = result.payload or {}
                
                result_dict = {
                    "id": result.id,
                    "score": self._normalize_score(result.score),
                    "nom": payload.get("nom", "N/A"),
                    "composition": payload.get("composition", "")[:250],
                    "posologie": payload.get("posologie", "")[:250],
                    "indications": payload.get("indications", "")[:250],
                    "effets_secondaires": payload.get("effets_secondaires", "")[:250],
                    "contre_indications": payload.get("contre_indications", "")[:250],
                    "interactions": payload.get("interactions", "")[:250],
                    "url": payload.get("url", ""),
                    "qdrant_id": result.id
                }
                
                # Filtrer par score minimum SEULEMENT si score < 0.15 (très faible)
                # Laisser passer les résultats 0.15+ pour le re-ranking
                if result_dict["score"] >= 0.15:
                    results.append(result_dict)
            
            # 4. Re-ranking avec scoring multi-critères
            reranked = self._rerank_results(query, results)
            
            # 5. Appliquer le seuil final après re-ranking
            final_results = [r for r in reranked if r['score'] >= score_threshold]
            
            # 6. Retourner le nombre demandé
            return final_results[:limit]
            
        except Exception as e:
            print(f"❌ Erreur recherche sémantique: {e}")
            return []
    
    def hybrid_search(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Recherche hybride optimisée: vectorielle + exacte + fuzzy matching
        Meilleur pour les requêtes précises (noms de médicaments)
        """
        if not self.available or not query:
            return []
        
        try:
            query_lower = query.lower().strip()
            
            # 1. Recherche vectorielle
            vector_results = self.recherche_semantique(query, limit=limit * 2, score_threshold=0)
            
            # 2. Recherche par correspondance exacte et fuzzy
            all_docs = self.qdrant.scroll(
                collection_name=self.collection_name,
                limit=2000,
                with_payload=True,
                with_vectors=False
            )[0]
            
            name_matches = []
            for doc in all_docs:
                nom = doc.payload.get("nom", "").lower()
                
                # Scoring pour correspondance de nom
                if query_lower == nom:
                    score = 1.0  # Match exact
                elif nom.startswith(query_lower):
                    score = 0.95  # Commence par
                elif query_lower in nom:
                    score = 0.85  # Contient
                else:
                    # Fuzzy matching simple: compter les caractères qui matchent
                    matching_chars = sum(1 for c in query_lower if c in nom)
                    score = (matching_chars / len(query_lower)) * 0.6 if query_lower else 0
                
                # Ne garder que les scores significatifs
                if score >= 0.5:
                    name_matches.append({
                        "id": doc.id,
                        "score": score,
                        "nom": doc.payload.get("nom", ""),
                        "is_name_match": True,
                        "qdrant_id": doc.id
                    })
            
            # 3. Fusionner vectoriel + nom avec poids intelligents
            combined = {}
            
            # Ajouter les matchs de nom (haute priorité)
            for result in name_matches:
                key = result["id"]
                combined[key] = result
            
            # Fusionner avec vectoriel
            for result in vector_results:
                key = result["id"]
                if key in combined:
                    # Combiner les scores: priorité au match de nom (60%) + vectoriel (40%)
                    combined[key]["score"] = combined[key]["score"] * 0.6 + result["score"] * 0.4
                    combined[key].update({k: v for k, v in result.items() if k != "score"})
                else:
                    combined[key] = result
            
            # 4. Trier par score descendant
            final_results = sorted(
                combined.values(),
                key=lambda x: x["score"],
                reverse=True
            )
            
            return final_results[:limit]
            
        except Exception as e:
            print(f"❌ Erreur hybrid search: {e}")
            return []
    
    def recherche_par_champ(self, field_name: str, query: str, limit: int = 20) -> List[Dict]:
        """
        Recherche spécialisée sur un champ (composition, effets, etc.)
        
        Args:
            field_name: composition, posologie, effets_secondaires, indications, etc.
            query: Texte à chercher
            limit: Nombre de résultats
        
        Returns:
            Résultats pertinents pour le champ
        """
        if not self.available or not query:
            return []
        
        try:
            # Enrichir la requête avec le contexte du champ
            enriched_query = f"{field_name}: {query}"
            query_vector = self._get_embedding_cached(enriched_query)
            
            results = self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit
            )
            
            formatted_results = []
            for result in results:
                payload = result.payload or {}
                formatted_results.append({
                    "id": result.id,
                    "score": self._normalize_score(result.score),
                    "nom": payload.get("nom", ""),
                    field_name: payload.get(field_name, "")[:400],
                    "qdrant_id": result.id
                })
            
            return formatted_results
            
        except Exception as e:
            print(f"❌ Erreur recherche champ: {e}")
            return []
    
    def recherche_autocomplete(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Autocomplete pour les noms de médicaments
        Retourne rapidement les suggestions
        """
        if not self.available or not query:
            return []
        
        try:
            query_lower = query.lower()
            all_docs = self.qdrant.scroll(
                collection_name=self.collection_name,
                limit=5000,
                with_payload=True,
                with_vectors=False
            )[0]
            
            suggestions = []
            for doc in all_docs:
                nom = doc.payload.get("nom", "")
                if query_lower in nom.lower():
                    suggestions.append({
                        "id": doc.id,
                        "nom": nom,
                        "qdrant_id": doc.id
                    })
            
            # Trier: exact match d'abord, puis commence par, puis contient
            def sort_key(item):
                nom_lower = item["nom"].lower()
                if nom_lower == query_lower:
                    return (0, item["nom"])
                elif nom_lower.startswith(query_lower):
                    return (1, item["nom"])
                else:
                    return (2, item["nom"])
            
            suggestions.sort(key=sort_key)
            return suggestions[:limit]
            
        except Exception as e:
            print(f"❌ Erreur autocomplete: {e}")
            return []
    
    def search_with_filters(self, query: str, filters: Dict[str, Any] = None, limit: int = 20) -> List[Dict]:
        """
        Recherche avec filtres avancés
        
        Args:
            query: Texte à chercher
            filters: Dict avec clés comme "completude_min", "contains_composition", etc.
            limit: Nombre de résultats
        
        Returns:
            Résultats filtrés
        """
        if not self.available or not query:
            return []
        
        try:
            results = self.recherche_semantique(query, limit=limit * 2)
            
            # Appliquer les filtres
            if filters:
                filtered = results
                
                # Exemple: filtre par complétude minimum
                if "completude_min" in filters:
                    min_completude = filters["completude_min"]
                    filtered = [r for r in filtered if r.get("pourcentage_completude", 0) >= min_completude]
                
                # Exemple: retourner que ceux qui ont une composition
                if filters.get("requires_composition"):
                    filtered = [r for r in filtered if r.get("composition", "").strip()]
                
                return filtered[:limit]
            
            return results
            
        except Exception as e:
            print(f"❌ Erreur search with filters: {e}")
            return []
    
    def get_document_details(self, qdrant_id: int) -> Dict[str, Any]:
        """Récupère les détails complets d'un document"""
        if not self.available:
            return {}
        
        try:
            doc = self.qdrant.retrieve(
                collection_name=self.collection_name,
                ids=[qdrant_id],
                with_payload=True
            )
            
            if doc and len(doc) > 0:
                return doc[0].payload or {}
            return {}
            
        except Exception as e:
            print(f"❌ Erreur récupération détails: {e}")
            return {}
    
    def get_embedding_cache_stats(self) -> Dict:
        """Retourne les stats du cache d'embeddings"""
        info = self.embedding_cache.copy()
        return {
            "cache_size": len(self.embedding_cache),
            "cached_queries": list(self.embedding_cache.keys())[:10]
        }
    
    def clear_embedding_cache(self):
        """Vide le cache d'embeddings"""
        self.embedding_cache.clear()
        self._get_embedding_cached.cache_clear()
        print("✅ Cache d'embeddings vidé")
    
    def statistiques(self) -> Dict:
        """Statistiques détaillées de la collection"""
        if not self.available:
            return None
        
        try:
            info = self.qdrant.get_collection(self.collection_name)
            return {
                "nombre_documents": info.points_count,
                "vecteurs_dimension": info.config.params.vectors.size,
                "distance_metric": info.config.params.vectors.distance.name,
                "modele_embedding": "all-mpnet-base-v2",
                "features": ["hybrid_search", "re_ranking", "caching", "autocomplete", "advanced_filters"]
            }
        except Exception as e:
            print(f"❌ Erreur stats: {e}")
            return None


# Initialisation globale
qdrant_search = None

def init_qdrant_search():
    """Initialise le client de recherche Qdrant V2"""
    global qdrant_search
    qdrant_search = QdrantMedicSearchV2()
    return qdrant_search

def recherche_medicaments(query: str, limit: int = 20, method: str = "semantic") -> List[Dict]:
    """
    Fonction rapide pour chercher des médicaments
    
    Args:
        query: Texte à chercher
        limit: Nombre de résultats
        method: "semantic" ou "hybrid"
    
    Returns:
        Liste des résultats
    """
    if qdrant_search is None:
        init_qdrant_search()
    
    if qdrant_search and qdrant_search.available:
        if method == "hybrid":
            return qdrant_search.hybrid_search(query, limit=limit)
        else:
            return qdrant_search.recherche_semantique(query, limit=limit)
    return []

