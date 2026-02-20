#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SCRAPER UNIQUE - Scrape ANSM et extrait sections RCP numérotées
Stocke directement dans MongoDB avec sections_rcp (1., 2., 3., 4.1-4.9, etc.)
"""

import sys
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import os
import time
from dotenv import load_dotenv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import pandas as pd

# Essayer d'importer openpyxl directement
try:
    from openpyxl import load_workbook
    HAS_OPENPYXL = True
except:
    HAS_OPENPYXL = False

# Configuration
load_dotenv()
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/medicsearch')
DB_NAME = 'medicsearch'
COLLECTION_BRUT = 'medic_brut'
NOMBRE_THREADS = 20
DELAI_ENTRE_REQUETES = 0.05


def extraire_sections_rcp(texte_complet):
    """Extrait les sections numérotées RCP (1-12) avec contenu"""
    sections_rcp = {}
    
    # Patterns pour toutes les 12 sections RCP officielles
    patterns = [
        (r'^1\.\s+([^\n]+)\n(.*?)(?=^(?:2\.|$))', '1'),
        (r'^2\.\s+([^\n]+)\n(.*?)(?=^(?:3\.|$))', '2'),
        (r'^3\.\s+([^\n]+)\n(.*?)(?=^(?:4\.|$))', '3'),
        (r'^4\.\s+([^\n]+)\n(.*?)(?=^(?:4\.1|5\.|$))', '4'),
        (r'^4\.1\.\s+([^\n]+)\n(.*?)(?=^(?:4\.2|5\.|$))', '4.1'),
        (r'^4\.2\.\s+([^\n]+)\n(.*?)(?=^(?:4\.3|5\.|$))', '4.2'),
        (r'^4\.3\.\s+([^\n]+)\n(.*?)(?=^(?:4\.4|5\.|$))', '4.3'),
        (r'^4\.4\.\s+([^\n]+)\n(.*?)(?=^(?:4\.5|5\.|$))', '4.4'),
        (r'^4\.5\.\s+([^\n]+)\n(.*?)(?=^(?:4\.6|5\.|$))', '4.5'),
        (r'^4\.6\.\s+([^\n]+)\n(.*?)(?=^(?:4\.7|5\.|$))', '4.6'),
        (r'^4\.7\.\s+([^\n]+)\n(.*?)(?=^(?:4\.8|5\.|$))', '4.7'),
        (r'^4\.8\.\s+([^\n]+)\n(.*?)(?=^(?:4\.9|5\.|$))', '4.8'),
        (r'^4\.9\.\s+([^\n]+)\n(.*?)(?=^(?:5\.|$))', '4.9'),
        (r'^5\.\s+([^\n]+)\n(.*?)(?=^(?:5\.1|6\.|$))', '5'),
        (r'^5\.1\.\s+([^\n]+)\n(.*?)(?=^(?:5\.2|6\.|$))', '5.1'),
        (r'^5\.2\.\s+([^\n]+)\n(.*?)(?=^(?:5\.3|6\.|$))', '5.2'),
        (r'^5\.3\.\s+([^\n]+)\n(.*?)(?=^(?:6\.|$))', '5.3'),
        (r'^6\.\s+([^\n]+)\n(.*?)(?=^(?:6\.1|7\.|$))', '6'),
        (r'^6\.1\.\s+([^\n]+)\n(.*?)(?=^(?:6\.2|7\.|$))', '6.1'),
        (r'^6\.2\.\s+([^\n]+)\n(.*?)(?=^(?:6\.3|7\.|$))', '6.2'),
        (r'^6\.3\.\s+([^\n]+)\n(.*?)(?=^(?:6\.4|7\.|$))', '6.3'),
        (r'^6\.4\.\s+([^\n]+)\n(.*?)(?=^(?:6\.5|7\.|$))', '6.4'),
        (r'^6\.5\.\s+([^\n]+)\n(.*?)(?=^(?:6\.6|7\.|$))', '6.5'),
        (r'^6\.6\.\s+([^\n]+)\n(.*?)(?=^(?:7\.|$))', '6.6'),
        (r'^7\.\s+([^\n]+)\n(.*?)(?=^(?:8\.|$))', '7'),
        (r'^8\.\s+([^\n]+)\n(.*?)(?=^(?:9\.|$))', '8'),
        (r'^9\.\s+([^\n]+)\n(.*?)(?=^(?:10\.|$))', '9'),
        (r'^10\.\s+([^\n]+)\n(.*?)(?=^(?:11\.|$))', '10'),
        (r'^11\.\s+([^\n]+)\n(.*?)(?=^(?:12\.|$))', '11'),
        (r'^12\.\s+([^\n]+)\n(.*?)(?=$)', '12'),
    ]
    
    for pattern, numero in patterns:
        match = re.search(pattern, texte_complet, re.MULTILINE | re.DOTALL)
        if match:
            titre = match.group(1).strip()
            contenu = match.group(2).strip()
            if titre and contenu:
                sections_rcp[numero] = {
                    'titre': titre,
                    'contenu': contenu
                }
    
    return sections_rcp


def extraire_nom(soup):
    """Extrait le nom du médicament (ignore navigation, redirections, etc.)"""
    mots_interdits = [
        'nombre', 'mutations', 'inclusion', 'exclusion', 'critère', 'risque',
        'population', 'étude', 'groupe', 'patient', 'classe', 'code', 'atc',
        'remboursable', 'oui', 'non', 'indication', 'posologie', 'dosage',
        'effet', 'secondaire', 'interaction', 'contre', 'précaution', 'avertissement',
        'composition', 'excipient', 'propriété', 'pharmacocinétique', 'pharmacodynamique',
        'accueil', 'recherche', 'menu', 'navigation', 'retour', 'lien', 'accès',
        'vous êtes', 'redirection', 'page', 'aller', 'consulter', 'base de données',
        'brèves', 'historique', 'modification'
    ]
    
    # Enlever les éléments de navigation (nav, aside, header)
    for nav_elem in soup.find_all(['nav', 'aside', 'header']):
        nav_elem.decompose()
    
    # Essayer h3, h2, h1
    for tag in ['h3', 'h2', 'h1']:
        for elem in soup.find_all(tag):
            text = elem.get_text().strip()
            if 5 < len(text) < 200:
                if not any(mot in text.lower() for mot in mots_interdits):
                    if any(c.isupper() for c in text):
                        return text
    
    return None


def lire_urls_fichier(fichier):
    """Lit les URLs depuis un fichier texte ou Excel (utilise pandas pour éviter les verrous)"""
    urls = []
    
    # Si Excel - utiliser pandas
    if fichier.endswith('.xlsx'):
        try:
            print(f"📂 Lecture Excel: {fichier}")
            df = pd.read_excel(fichier, header=None)
            print(f"✓ Excel chargé: {len(df)} lignes")
            
            # Parcourir tous les cellules
            for row in df.values:
                for cell in row:
                    if cell and isinstance(cell, str) and cell.strip().startswith(('http://', 'https://')):
                        urls.append(cell.strip())
            
            print(f"✓ {len(urls)} URLs trouvées dans {fichier}\n")
            return urls
        except Exception as e:
            print(f"❌ Erreur lecture Excel avec pandas: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return []
    
    # Si texte
    if fichier.endswith('.txt'):
        try:
            with open(fichier, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip().startswith(('http://', 'https://'))]
            
            print(f"✓ {len(urls)} URLs trouvées dans {fichier}\n")
            return urls
        except Exception as e:
            print(f"❌ Erreur lecture fichier: {str(e)}")
            return []
    
    return urls


def normaliser_url(url):
    """Normalise les URLs (enlève fragments)"""
    if not url:
        return url
    
    # Enlever le fragment (#tab-rcp, #tab-notice, etc.)
    url = url.split('#')[0]
    
    return url


def scraper_url(url, col):
    """Scrape une URL et extrait les sections RCP numérotées"""
    try:
        # Normaliser l'URL (enlever fragments)
        url_clean = normaliser_url(url)
        
        # Essayer les deux versions du lien
        urls_a_essayer = [url_clean]
        
        # Si le lien contient "/extrait", ajouter aussi la version sans
        if '/extrait' in url_clean:
            urls_a_essayer.append(url_clean.replace('/extrait', ''))
        # Sinon ajouter la version avec /extrait
        else:
            urls_a_essayer.append(url_clean + '/extrait')
        
        # Vérifier si déjà scrapée (par n'importe quelle URL)
        if col.find_one({'url': url_clean}):
            return 'SKIP'
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = None
        url_finale = None
        
        # Essayer chaque URL
        for url_essai in urls_a_essayer:
            try:
                response = requests.get(url_essai, headers=headers, timeout=10)
                if response.status_code == 200:
                    url_finale = url_essai
                    break
            except:
                pass
        
        if not response or response.status_code != 200:
            print(f"  ❌ HTTP {response.status_code if response else 'Error'}: {url_clean}")
            return None
        
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Enlever scripts et styles
        for script in soup(['script', 'style']):
            script.decompose()
        
        # Extraire nom
        nom = extraire_nom(soup)
        if not nom:
            print(f"  ❌ Pas de nom trouvé: {url_finale[:60]}")
            return None
        
        # Extraire texte complet - cibler le contenu RCP uniquement
        texte_complet = ""
        
        # Préférer les panneaux tabs (contenu RCP officiel)
        panels = soup.find_all('div', class_='fr-tabs__panel')
        
        if panels:
            for panel in panels:
                texte_panel = panel.get_text().strip()
                if texte_panel and len(texte_panel) > 50:  # Ignorer les petits panneaux vides
                    texte_complet += texte_panel + "\n\n"
        else:
            # Fallback: chercher le contenu principal
            main_content = soup.find('main') or soup.find('div', class_='content') or soup.find('article')
            if main_content:
                texte_complet = main_content.get_text()
            else:
                texte_complet = soup.get_text()
        
        if not texte_complet or len(texte_complet) < 200:
            print(f"  ❌ Pas assez de texte ({len(texte_complet)} chars): {nom[:40]}")
            return None
        
        # Extraire sections RCP
        sections_rcp = extraire_sections_rcp(texte_complet)
        
        if not sections_rcp:
            print(f"  ❌ Pas de sections RCP trouvées: {nom[:40]}")
            return None
        
        # Stocker dans MongoDB
        info = {
            'url': url_clean,
            'nom': nom,
            'sections_rcp': sections_rcp,
            'date_scrape': datetime.now().isoformat(),
            'nombre_sections': len(sections_rcp)
        }
        
        return info
    except Exception as e:
        print(f"  ❌ Exception: {str(e)[:80]}")
        return None


def main():
    """Fonction principale"""
    print("=" * 70)
    print("SCRAPER UNIQUE - SECTIONS RCP NUMÉROTÉES")
    print("=" * 70)
    
    # Chercher fichier URLs (liens_R.xlsx)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fichiers = [
        os.path.join(script_dir, 'liens_R.xlsx'),
        'liens_R.xlsx',
    ]
    
    fichier_trouve = None
    for f in fichiers:
        if os.path.exists(f):
            fichier_trouve = f
            print(f"✓ Fichier trouvé: {f}\n")
            break
    
    if not fichier_trouve:
        print("\n❌ Aucun fichier liens_R.xlsx trouvé!")
        return
    
    # Lire URLs
    urls = lire_urls_fichier(fichier_trouve)
    if not urls:
        print("❌ Aucune URL trouvée")
        return
    
    # Connexion MongoDB
    try:
        print("🔌 Connexion MongoDB...")
        client = MongoClient(MONGO_URI)
        print("✓ MongoDB connecté")
        
        db = client[DB_NAME]
        col = db[COLLECTION_BRUT]
        col.create_index('url', unique=False)
        print(f"✓ Collection '{COLLECTION_BRUT}' prête")
        
        print("📊 Vérification URLs existantes...")
        existing_urls = set(doc['url'] for doc in col.find({}, {'url': 1}))
        print(f"✓ {len(existing_urls)} URLs existantes")
        
        urls_a_scraper = [u for u in urls if u not in existing_urls]
        print(f"✓ {len(urls_a_scraper)} URLs à scraper\n")
        
        if not urls_a_scraper:
            print("✅ Toutes les URLs ont été scrapées!")
            client.close()
            return
        
        # Scraper en parallèle
        print(f"🔄 Scraping avec {NOMBRE_THREADS} threads...\n")
        inserted = 0
        errors = 0
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=NOMBRE_THREADS) as executor:
            futures = {executor.submit(scraper_url, url, col): url for url in urls_a_scraper}
            
            for idx, future in enumerate(as_completed(futures), 1):
                try:
                    data = future.result()
                    if data and data != 'SKIP':
                        col.insert_one(data)
                        inserted += 1
                        elapsed = time.time() - start_time
                        pct = (idx / len(urls_a_scraper)) * 100
                        print(f"  ✓ [{idx}/{len(urls_a_scraper)} ({pct:.1f}%)] {data['nom'][:40]}... → {len(data['sections_rcp'])} sections | {elapsed:.0f}s")
                    else:
                        errors += 1
                except Exception as e:
                    errors += 1
                    print(f"  ❌ Erreur: {str(e)}")
                
                time.sleep(DELAI_ENTRE_REQUETES)
        
        # Résumé
        total_time = time.time() - start_time
        print(f"\n" + "=" * 70)
        print(f"✅ SCRAPING TERMINÉ")
        print(f"=" * 70)
        print(f"  Total à scraper: {len(urls_a_scraper)}")
        print(f"  Insérées: {inserted}")
        print(f"  Erreurs: {errors}")
        print(f"  Temps total: {total_time:.1f}s ({total_time/60:.1f}min)")
        if inserted > 0:
            print(f"  Vitesse: {inserted/total_time:.1f} docs/s")
        print(f"  Collection: {COLLECTION_BRUT}")
        print(f"=" * 70)
        
        client.close()
        
    except Exception as e:
        print(f"\n❌ Erreur MongoDB: {str(e)}")
        import traceback
        print(traceback.format_exc())



# Point d'entrée principal
if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\n✅ Appuie sur Entrée pour fermer...")
