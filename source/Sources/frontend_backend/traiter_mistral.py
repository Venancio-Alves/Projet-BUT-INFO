#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de traitement des médicaments bruts avec Mistral
- Récupère les données brutes de MongoDB
- Traite avec Mistral pour résumer les champs importants
- Sauvegarde dans MongoDB avec structure complète
- Index dans Qdrant pour recherche vectorielle
"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from dotenv import load_dotenv
from datetime import datetime
import json
import re
import unicodedata
import time
from threading import Lock, Semaphore
import hashlib

# Charger le .env depuis le répertoire du script
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
load_dotenv(env_path)

# Configuration
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/medicsearch')
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')

if not MISTRAL_API_KEY:
    print(f"❌ Erreur: MISTRAL_API_KEY non configurée")
    print(f"   Cherché dans: {env_path}")
    print(f"   Existe: {os.path.exists(env_path)}")
    sys.exit(1)

# Client Mistral (lazy loading)
client_mistral = None

def get_mistral_client():
    """Retourne les paramètres Mistral API (utilise REST directement)"""
    return None  # Pas besoin de client, on utilise requests directement

# Qdrant (lazy loading)
qdrant_client = None
qdrant_available = False

def get_qdrant_client():
    """Initialise Qdrant à la demande"""
    global qdrant_client, qdrant_available
    if qdrant_client is None:
        try:
            from qdrant_client import QdrantClient
            qdrant_client = QdrantClient("localhost", port=6333)
            qdrant_available = True
        except Exception as e:
            print(f"⚠️  Qdrant non disponible: {e}")
            qdrant_available = False
    return qdrant_client if qdrant_available else None

# Embedding model (lazy loading)
embedding_model = None

def get_embedding_model():
    """Charge le modèle d'embedding"""
    global embedding_model
    if embedding_model is None:
        from sentence_transformers import SentenceTransformer
        print("⏳ Chargement du modèle d'embedding...")
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return embedding_model


# Stats
stats_lock = Lock()
stats = {'processed': 0, 'errors': 0, 'total': 0}

# Semaphore pour throttle les appels Mistral (max 3 simultanés)
mistral_semaphore = Semaphore(3)


def nettoyer_texte(texte):
    """Nettoie et formate le texte pour plus de lisibilité"""
    if not texte:
        return ""
    
    # Normaliser les accents
    texte = unicodedata.normalize('NFKD', texte)
    
    # Supprimer TOUTES les références aux rubriques (variations multiples)
    texte = re.sub(r'\(voir rubrique[s]?\s+[\d.]+(?:\s+et\s+[\d.]+)*\)', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'voir rubrique[s]?\s+[\d.]+(?:\s+et\s+[\d.]+)*', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'voir\s+rubriques?\s+[\d.]+ et [\d.]+', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'\[voir rubrique.*?\]', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'\(voir\s+.*?rubrique.*?\)', '', texte, flags=re.IGNORECASE)
    
    # Supprimer les renvois aux pieds de page/notes
    texte = re.sub(r'[⁰¹²³⁴⁵⁶⁷⁸⁹]', '', texte)
    
    # Normaliser les espaces multiples et les sauts de ligne
    texte = re.sub(r'\s+', ' ', texte)
    texte = re.sub(r'\n\s*\n\s*\n', '\n\n', texte)
    
    # Supprimer les balises HTML
    texte = re.sub(r'<[^>]+>', '', texte)
    
    # Supprimer les codes HTML d'entités
    texte = re.sub(r'&[a-z]+;', '', texte)
    
    # Supprimer les points de suspension et caractères bizarres
    texte = re.sub(r'\.\.\.+', '', texte)
    texte = re.sub(r"[…ˈ′°']", '', texte)
    
    # Normaliser les tirets
    texte = re.sub(r'[‑–−]', '-', texte)
    
    # Supprimer les fragments de mots mal encodés (pattern: lettre seule suivi d'espace et texte)
    # Exemple: "s avec d'autres" → "avec d'autres"
    texte = re.sub(r'\b[a-z]\s+(?=avec|et|ou|pour|sur|dans|par|que|dont|leurs)', '', texte, flags=re.IGNORECASE)
    
    # Supprimer les "et autres formes" qui reste après suppression de fragments
    texte = re.sub(r"\s*et autres formes\s*d['']?\s*", ' ', texte, flags=re.IGNORECASE)
    
    # Espacement correct avant la ponctuation
    texte = re.sub(r'\s+([?!.,;:\)])', r'\1', texte)
    
    # Espacement après la ponctuation
    texte = re.sub(r'([.!?])\s*([A-Z])', r'\1 \2', texte)
    
    # Corriger les espaces après les tirets de listes
    texte = re.sub(r'^[\s•·\-\*]+\s+', '• ', texte, flags=re.MULTILINE)
    
    # Supprimer les espaces en début/fin
    texte = texte.strip()
    
    # Couper aux limites de phrases complètes si tronqué
    if len(texte) > 100:
        if texte[-1] not in '.!?,;:\n':
            last_period = texte.rfind('.')
            last_semi = texte.rfind(';')
            last_comma = texte.rfind(',')
            last_punct_idx = max(last_period, last_semi, last_comma)
            if last_punct_idx > len(texte) * 0.7:
                texte = texte[:last_punct_idx+1]
    
    return texte


def extraire_sans_mistral(nom, contenu_brut):
    """Fallback basique si Mistral échoue"""
    return {
        "composition": "Aucune donnée disponible pour ce champ.",
        "posologie": "Aucune donnée disponible pour ce champ.",
        "indications": "Aucune donnée disponible pour ce champ.",
        "effets_secondaires": "Aucune donnée disponible pour ce champ.",
        "contre_indications": "Aucune donnée disponible pour ce champ.",
        "interactions": "Aucune donnée disponible pour ce champ.",
        "mises_en_garde": "Aucune donnée disponible pour ce champ."
    }

def extraire_sans_mistral_ancien(nom, contenu_brut):
    """Extraction basique directement du contenu - génère des phrases structurées"""
    try:
        infos = {
            "composition": "Aucune donnée disponible pour ce champ.",
            "posologie": "Aucune donnée disponible pour ce champ.",
            "indications": "Aucune donnée disponible pour ce champ.",
            "effets_secondaires": "Aucune donnée disponible pour ce champ.",
            "contre_indications": "Aucune donnée disponible pour ce champ.",
            "interactions": "Aucune donnée disponible pour ce champ.",
            "mises_en_garde": "Aucune donnée disponible pour ce champ."
        }
        
        contenu_lower = contenu_brut.lower()
        
        # Extraire les sections par mots-clés simples
        sections_keywords = {
            "composition": ["composition qualitative", "composition quantitative", "composé de"],
            "posologie": ["posologie", "mode d'administration", "dose", "dosage"],
            "indications": ["indication thérapeutique", "indication", "traitement de", "utilisé pour"],
            "effets_secondaires": ["effet indésirable", "effets indésirables", "effet secondaire"],
            "contre_indications": ["contre-indication", "contre-indications", "ne pas administrer"],
            "interactions": ["interaction", "co-administration", "association"],
            "mises_en_garde": ["mise en garde", "mises en garde", "précaution", "attention"]
        }
        
        # Pour chaque champ, chercher le texte après le mot-clé
        for champ, keywords in sections_keywords.items():
            for keyword in keywords:
                idx = contenu_lower.find(keyword)
                if idx != -1:
                    # Extraire le texte après le mot-clé
                    start = idx
                    # Chercher où s'arrête cette section (prochain titre ou fin)
                    max_end = min(idx + 5000, len(contenu_brut))
                    
                    # Chercher le prochain titre/rubrique
                    end = max_end
                    for next_keyword in sections_keywords.values():
                        for nk in next_keyword:
                            next_idx = contenu_lower.find(nk, idx + len(keyword))
                            if next_idx != -1 and next_idx < end:
                                end = next_idx
                    
                    texte = contenu_brut[start:end]
                    
                    # Chercher la DERNIÈRE phrase complète
                    last_period = texte.rfind('.')
                    last_semi = texte.rfind(';')
                    last_newline = texte.rfind('\n')
                    last_punct_idx = max(last_period, last_semi, last_newline)
                    
                    if last_punct_idx > 10:
                        texte = texte[:last_punct_idx+1]
                    
                    texte = nettoyer_texte(texte)
                    
                    # Supprimer le mot-clé lui-même du début
                    if texte.lower().startswith(keyword):
                        texte = texte[len(keyword):].strip()
                    
                    # Limiter à 2000 caractères max
                    if len(texte) > 2000:
                        texte = texte[:2000].rsplit(' ', 1)[0]
                        # S'assurer que ça se termine par un point
                        if not texte.endswith(('.', '!', '?')):
                            texte = texte + '.'
                    
                    # Formater en phrases structurées
                    if texte:
                        # S'assurer que ça commence par une majuscule
                        if texte and not texte[0].isupper():
                            texte = texte[0].upper() + texte[1:] if len(texte) > 1 else texte.upper()
                        
                        # S'assurer que ça se termine par un point
                        if not texte.endswith(('.', '!', '?')):
                            texte = texte + '.'
                        
                        # Vérifier que la longueur est acceptable
                        if len(texte) > 30:
                            infos[champ] = texte
                            break
            
            # Fallback: Si aucun champ n'a été rempli, extraire le contenu brut
            if infos[champ] == "Aucune donnée disponible pour ce champ.":
                # Essayer d'extraire une phrase significative du contenu
                lignes = [l.strip() for l in contenu_brut.split('\n') if l.strip() and len(l.strip()) > 20]
                if lignes:
                    texte_brut = lignes[0]
                    # Nettoyer et formater
                    texte_brut = nettoyer_texte(texte_brut)
                    if texte_brut:
                        # Capitaliser
                        if not texte_brut[0].isupper():
                            texte_brut = texte_brut[0].upper() + texte_brut[1:] if len(texte_brut) > 1 else texte_brut.upper()
                        # Ajouter un point si absent
                        if not texte_brut.endswith(('.', '!', '?')):
                            texte_brut = texte_brut + '.'
                        if len(texte_brut) > 50:
                            infos[champ] = texte_brut
        
        return infos
        
    except Exception as e:
        print(f"   ⚠️  Erreur extraction: {str(e)[:30]}")
        return None


def extraire_avec_mistral(nom, contenu_brut):
    """Extraction rapide ET cohérente avec Mistral (throttled)"""
    # THROTTLE: Limiter à 2 appels Mistral simultanés max
    mistral_semaphore.acquire()
    
    try:
        prompt = f"""Pharmacologie: {nom}

{contenu_brut[:3000]}

JSON avec 8 champs (phrases complètes, tirets séparés):
{{
  "composition": "Principes actifs, dosages et excipients (3 phrases)",
  "posologie": "Doses recommandées:\\n- Item 1.\\n- Item 2.\\n- Item 3.",
  "indications": "Utilisations du médicament:\\n- Item 1.\\n- Item 2.\\n- Item 3.",
  "effets_secondaires": "Effets indésirables courants et fréquence (3 phrases)",
  "contre_indications": "Situations à éviter (3 phrases)",
  "interactions": "Interactions médicamenteuses principales (3 phrases)",
  "interactions_graves": "Interactions dangereuses ou 'Aucune':\\n- Item.",
  "mises_en_garde": "Avertissements cliniques (3 phrases)"
}}"""

        import time
        time.sleep(0.3)  # Délai sûr
        
        # Une seule tentative - pas de retry ici
        try:
            import requests
            
            response = requests.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {MISTRAL_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "mistral-small-latest",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 1500
                },
                timeout=20
            )
            
            response.raise_for_status()
            message = response.json()
        except Exception as e:
            raise Exception(f"Mistral failed: {str(e)[:50]}")
        
        # Extraire le texte de la réponse API REST
        response_text = message['choices'][0]['message']['content'].strip()
        
        # Nettoyer les blocs de code
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()
        
        # Extraire JSON
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        if start_idx != -1 and end_idx > start_idx:
            response_text = response_text[start_idx:end_idx+1]
        
        infos = json.loads(response_text)
        
        # Nettoyer les valeurs mais garder la structure des phrases
        for key in infos:
            if isinstance(infos[key], str):
                # Nettoyage léger pour garder les phrases
                texte = nettoyer_texte(infos[key])
                # S'assurer que ça commence par une majuscule
                if texte and not texte[0].isupper():
                    texte = texte[0].upper() + texte[1:] if len(texte) > 1 else texte.upper()
                # S'assurer que ça se termine par un point
                if texte and not texte.endswith(('.', '!', '?')):
                    texte = texte + '.'
                infos[key] = texte
            else:
                infos[key] = ""
        
        return infos
    
    except Exception as e:
        print(f"   ⚠️  Erreur Mistral: {str(e)[:30]}")
        return None
    finally:
        mistral_semaphore.release()  # Libérer le sémaphore


def compter_completude(infos):
    """Compte le pourcentage de complétude"""
    if not infos:
        return 0
    
    champs_total = len(infos)
    champs_remplis = sum(1 for v in infos.values() if v and isinstance(v, str) and len(v.strip()) > 5)
    pourcentage = (champs_remplis / champs_total * 100) if champs_total > 0 else 0
    
    return round(pourcentage, 1)


def determiner_statut(pourcentage):
    """Détermine le statut de complétude"""
    if pourcentage >= 80:
        return 'complet'
    elif pourcentage >= 60:
        return 'partiellement_complet'
    else:
        return 'incomplet'


def creer_collection_qdrant():
    """Crée la collection Qdrant si elle n'existe pas"""
    client = get_qdrant_client()
    if client is None:
        return False
    
    try:
        from qdrant_client.models import VectorParams, Distance
        collections = client.get_collections()
        collection_names = [col.name for col in collections.collections]
        
        if "medicaments_mistral" not in collection_names:
            print("🔧 Création de la collection Qdrant 'medicaments_mistral'...")
            client.create_collection(
                collection_name="medicaments_mistral",
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            print("✅ Collection créée")
        else:
            print("✅ Collection 'medicaments_mistral' existe déjà")
        
        return True
    except Exception as e:
        print(f"❌ Erreur création collection: {e}")
        return False


def sauvegarder_dans_mongodb(doc_final, col_mongodb):
    """Sauvegarde le document dans MongoDB (upsert - pas de doublons)"""
    try:
        # Utiliser replace_one avec upsert pour éviter les doublons
        result = col_mongodb.replace_one(
            {"_id": doc_final["_id"]},
            doc_final,
            upsert=True
        )
        return True
    except Exception as e:
        print(f"   ❌ Erreur MongoDB: {str(e)[:30]}")
        return False


def traiter_document(doc_brut, col_mongodb, idx, total):
    """Traite un document brut et le sauvegarde dans MongoDB"""
    try:
        nom = nettoyer_texte(doc_brut.get('nom', 'Inconnu'))
        url = doc_brut.get('url', '')
        
        # Récupérer le contenu brut depuis les sections RCP (nouvelle structure numérotée)
        sections_rcp = doc_brut.get('sections_rcp', {})
        if isinstance(sections_rcp, dict) and sections_rcp:
            # Reconstruire le contenu RCP numéroté avec titres
            contenus = []
            try:
                for num in sorted(sections_rcp.keys(), key=lambda x: float(x)):
                    section = sections_rcp[num]
                    if isinstance(section, dict):
                        titre = section.get('titre', '')
                        contenu = section.get('contenu', '')
                        if titre or contenu:
                            contenus.append(f"{num}. {titre}\n{contenu}")
                    else:
                        # Fallback si format différent
                        contenus.append(str(section))
            except (ValueError, TypeError):
                # Si le tri échoue, utiliser l'ordre par défaut
                for num in sections_rcp.keys():
                    section = sections_rcp[num]
                    if isinstance(section, dict):
                        titre = section.get('titre', '')
                        contenu = section.get('contenu', '')
                        if titre or contenu:
                            contenus.append(f"{num}. {titre}\n{contenu}")
                    else:
                        contenus.append(str(section))
            contenu_brut = '\n\n'.join(contenus)
        else:
            # Fallback sur contenu_brut s'il existe
            contenu_brut = doc_brut.get('contenu_brut', '')
            if isinstance(contenu_brut, list):
                contenu_brut = '\n'.join(str(x) for x in contenu_brut if x)
            else:
                contenu_brut = str(contenu_brut)
        
        # Vérifier que le contenu n'est pas vide
        if not contenu_brut or len(contenu_brut.strip()) < 100:
            return f"⏭ [{idx}/{total}] {nom[:40]} (contenu vide)"
        
        # Traiter UNIQUEMENT avec Mistral avec retry logic
        infos = None
        max_retries = 4
        retry_count = 0
        
        while retry_count < max_retries and not infos:
            infos = extraire_avec_mistral(nom, contenu_brut)
            if not infos:
                retry_count += 1
                if retry_count < max_retries:
                    import time
                    wait_time = 5 * retry_count  # 5s, 10s, 15s
                    print(f"   ⏱️  Retry {retry_count}/{max_retries-1} après {wait_time}s...", flush=True)
                    time.sleep(wait_time)
        
        # Si Mistral a échoué après les retries, c'est une erreur réelle
        if not infos:
            with stats_lock:
                stats['errors'] += 1
            return f"❌ [{idx}/{total}] {nom[:40]}"
        
        # Calculer le pourcentage de complétude
        pourcentage_completude = compter_completude(infos)
        statut_completude = determiner_statut(pourcentage_completude)
        
        # Créer le document final avec la structure demandée
        doc_final = {
            "_id": doc_brut.get('_id'),
            "nom": nom,
            "url": url,
            "composition": infos.get('composition', ''),
            "posologie": infos.get('posologie', ''),
            "indications": infos.get('indications', ''),
            "effets_secondaires": infos.get('effets_secondaires', ''),
            "contre_indications": infos.get('contre_indications', ''),
            "interactions": infos.get('interactions', ''),
            "interactions_graves": infos.get('interactions_graves', ''),
            "mises_en_garde": infos.get('mises_en_garde', ''),
            "statut_completude": statut_completude,
            "pourcentage_completude": pourcentage_completude,
            "date_traitement": datetime.now().isoformat()
        }
        
        # Sauvegarder dans MongoDB
        if sauvegarder_dans_mongodb(doc_final, col_mongodb):
            with stats_lock:
                stats['processed'] += 1
            
            icon = "✓" if statut_completude == 'complet' else "◐" if statut_completude == 'partiellement_complet' else "⚠"
            return f"{icon} [{idx}/{total}] {nom[:40]} ({pourcentage_completude}%)"
        else:
            with stats_lock:
                stats['errors'] += 1
            return f"❌ [{idx}/{total}] {nom[:40]} (save failed)"
        
    except Exception as e:
        with stats_lock:
            stats['errors'] += 1
        return f"❌ [{idx}/{total}] {str(e)[:40]}"


def main():
    print("=" * 80, flush=True)
    print("🚀 TRAITEMENT DES MÉDICAMENTS AVEC MISTRAL → QDRANT", flush=True)
    print("=" * 80, flush=True)
    print(flush=True)
    
    try:
        # Connexion MongoDB
        print("🔌 Connexion MongoDB...", flush=True)
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client['medicsearch']
        col_brut = db['medic_brut']
        col_traitement = db['medicaments_traites']
        
        print("✅ MongoDB connecté", flush=True)
        
        # Récupérer les documents bruts
        print("📥 Récupération des documents bruts...", flush=True)
        docs = list(col_brut.find())
        print(f"✅ {len(docs)} documents trouvés", flush=True)
        
        if not docs:
            print("❌ Aucun document trouvé", flush=True)
            client.close()
            return
        
        # Vérifier quels documents ont déjà été traités dans MongoDB
        # Utiliser l'ID MongoDB comme clé unique, pas l'URL (qui peut être None ou différente)
        docs_traites_ids = set(str(doc['_id']) for doc in col_traitement.find({}, {'_id': 1}))
        docs_a_traiter = [doc for doc in docs if str(doc.get('_id')) not in docs_traites_ids]
        
        print(f"📊 Documents à traiter: {len(docs_a_traiter)} / {len(docs)}", flush=True)
        print(flush=True)
        
        if not docs_a_traiter:
            print("✅ Tous les documents ont été traités!", flush=True)
            client.close()
            return
        
        stats['total'] = len(docs_a_traiter)
        docs = docs_a_traiter
        
        # Créer la collection Qdrant
        creer_collection_qdrant()
        print(flush=True)
        
        print(f"🚀 Traitement {len(docs)} docs", flush=True)
        print(f"   • 12 workers en parallèle", flush=True)
        print(flush=True)
        print("=" * 80, flush=True)
        print(flush=True)
        
        start_time = time.time()
        
        # Traitement multi-thread
        try:
            with ThreadPoolExecutor(max_workers=12) as executor:
                futures = {
                    executor.submit(traiter_document, doc, col_traitement, idx+1, len(docs)): idx
                    for idx, doc in enumerate(docs)
                }
                
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        print(result, flush=True)
                        
                        total_done = stats['processed'] + stats['errors']
                        if total_done > 0 and total_done % 10 == 0:
                            temps_ecoule = int(time.time() - start_time)
                            pourcentage = round((total_done / stats['total']) * 100, 1)
                            vitesse = total_done / temps_ecoule if temps_ecoule > 0 else 0
                            temps_restant = int((stats['total'] - total_done) / vitesse) if vitesse > 0 else 0
                            
                            print(f"   📊 {total_done}/{stats['total']} ({pourcentage}%) | ✓: {stats['processed']} | ❌: {stats['errors']}", flush=True)
                            print(f"   ⏱️  {temps_ecoule}s écoulé | ~{temps_restant}s restant", flush=True)
                            print(flush=True)
                        
                    except Exception as e:
                        print(f"❌ Erreur: {str(e)[:50]}", flush=True)
        
        except KeyboardInterrupt:
            print("\n\n⏸️  ARRÊT DEMANDÉ", flush=True)
            raise
        
        # Résumé final
        temps_total = int(time.time() - start_time)
        print(f"\n" + "=" * 80, flush=True)
        print(f"✅ TRAITEMENT TERMINÉ", flush=True)
        print(f"=" * 80, flush=True)
        print(f"  ✓ Réussis: {stats['processed']}", flush=True)
        print(f"  ❌ Erreurs: {stats['errors']}", flush=True)
        print(f"  📦 Total traité: {stats['processed'] + stats['errors']}/{stats['total']}")
        print(f"  🎯 Collection Qdrant: medicaments_mistral")
        print(f"  ⏱️  Temps total: {temps_total}s")
        print(f"=" * 80)
        
        client.close()
        
    except KeyboardInterrupt:
        print("\n❌ Interruption utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur critique: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
