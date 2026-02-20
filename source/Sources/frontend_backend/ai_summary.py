import os
import re
from dotenv import load_dotenv
import time
import logging
from mistralai import Mistral

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variables
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')

# Cache duration in seconds (10 minutes)
CACHE_DURATION = 600

def clean_summary_format(text):
    """
    Clean and format the summary text from Mistral.
    Removes code blocks, fixes formatting, and ensures proper HTML.
    
    Args:
        text (str): Raw text from Mistral API
        
    Returns:
        str: Cleaned text ready for HTML display
    """
    # Remove markdown code blocks
    text = text.replace("```html", "").replace("```", "").strip()
    
    # Remove HTML comments
    import re
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # Clean up excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def call_mistral_reformulate(user_query):
    """Reformule avec Mistral + expansion de synonymes médicaux"""
    
    # Dictionnaire de synonymes médicaux pour fallback
    medical_synonyms = {
        'tete': ['cephalee', 'migraine', 'cranien', 'douleur', 'cephalalgies'],
        'grippe': ['influenza', 'viral', 'infection', 'fievre'],
        'fievre': ['pyrexie', 'hyperthermie', 'temperature'],
        'respiration': ['dyspnee', 'asthme', 'bronchite', 'pulmonaire', 'toux'],
        'ventre': ['abdomen', 'abdominal', 'gastrite'],
        'migraine': ['cephalee', 'tete', 'cranien'],
        'nausee': ['vomissement', 'digestif'],
        'toux': ['expectorant', 'respiratoire', 'bronchite'],
        'allergie': ['allergique', 'reaction', 'urticaire'],
    }
    
    stopwords = {
        'j\'ai', 'ai', 'je', 'me', 'ma', 'mon', 'mes', 'tu', 'te', 'ta', 'ton', 'tes',
        'il', 'elle', 'elles', 'ils', 'leur', 'lui', 'nous', 'vous', 'et', 'ou', 'mais',
        'car', 'donc', 'par', 'pour', 'avec', 'sans', 'sous', 'sur', 'dans', 'à', 'au', 'aux',
        'un', 'une', 'des', 'du', 'la', 'le', 'les', 'de', 'que', 'qui', 'ce', 'ses', 'son',
        'beaucoup', 'très', 'un peu', 'trop', 'assez', 'plus', 'moins', 'plutôt',
        'depuis', 'jours', 'jour', 'nuit', 'semaine', 'mois', 'ans', 'an', 'heure',
        'souffre', 'souffrir', 'problème', 'trouble', 'suis', 'est', 'avoir', 
        'quoi', 'comment', 'pourquoi', 'quand', 'où', 'ça', 'pas', 'ne', 'ni'
    }
    
    if not MISTRAL_API_KEY:
        # Fallback sans Mistral
        words = user_query.lower().split()
        expanded = set()
        for word in words:
            word_clean = word.strip('.,!?;:-')
            if word_clean not in stopwords and len(word_clean) > 2:
                expanded.add(word_clean)
                if word_clean in medical_synonyms:
                    expanded.update(medical_synonyms[word_clean])
        return ' '.join(sorted(expanded)) if expanded else user_query
    
    prompt = f"""Tu es un assistant médical. Réforme cette question en mots-clés pour chercher des médicaments.

RÈGLES STRICTES:
1. Enlève articles, pronoms, verbes inutiles (je, j'ai, la, le, avoir, est, etc.)
2. Garde UNIQUEMENT symptômes, maladies, noms pertinents
3. Ajoute synonymes médicaux
4. Retourne JUSTE les mots séparés par des espaces
5. Pas de ponctuation, pas de majuscules

EXEMPLES:
- "j'ai mal à la tête" → tete cephalee migraine douleur cranien
- "j'ai la grippe" → grippe influenza viral fievre
- "mal au ventre" → ventre abdomen douleur gastrite
- "j'ai beaucoup de nausées" → nausee vomissement digestif

Question: {user_query}
Mots-clés:"""
    
    try:
        client = Mistral(api_key=MISTRAL_API_KEY)
        response = client.chat.complete(
            model="mistral-small-2503",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=50
        )
        reformulated = response.choices[0].message.content.strip().lower()
        
        # Nettoyage
        reformulated = reformulated.replace('"', '').replace("'", '').replace(':', '').replace(',', ' ')
        
        # Enlever les lignes parasites
        for line in reformulated.splitlines():
            line = line.strip()
            if line and not any(x in line for x in ['question', 'reponse', 'exemple', 'mots']):
                # Filtrer stopwords
                words = line.split()
                cleaned = [w.strip() for w in words if w.strip() not in stopwords and len(w.strip()) > 2]
                
                # Ajouter synonymes pour chaque mot
                expanded = set(cleaned)
                for word in cleaned:
                    if word in medical_synonyms:
                        expanded.update(medical_synonyms[word])
                
                if expanded:
                    result = ' '.join(sorted(expanded))
                    print(f"DEBUG Reformulation (Mistral): '{user_query}' → '{result}'")
                    return result
        
        # Fallback si Mistral retourne rien
        raise Exception("Mistral returned empty")
        
    except Exception as e:
        logger.error(f"Erreur Mistral: {e}")
        # Fallback avec expansion locale
        words = user_query.lower().split()
        expanded = set()
        for word in words:
            word_clean = word.strip('.,!?;:-')
            if word_clean not in stopwords and len(word_clean) > 2:
                expanded.add(word_clean)
                if word_clean in medical_synonyms:
                    expanded.update(medical_synonyms[word_clean])
        result = ' '.join(sorted(expanded)) if expanded else user_query
        print(f"DEBUG Reformulation (fallback): '{user_query}' → '{result}'")
        return result

def call_mistral_summarize(user_query, docs):
    """
    Utilise Mistral pour générer une réponse synthétique à partir de documents trouvés (RAG).
    Args:
        user_query (str): Question utilisateur
        docs (list): Liste de documents (dict) pertinents trouvés
    Returns:
        str: Réponse synthétique générée par l'IA
    """
    if not MISTRAL_API_KEY:
        return "<p>Erreur : Clé API Mistral manquante.</p>"
    # Préparer un contexte court à partir des documents (extraits, titres)
    context = ""
    for i, doc in enumerate(docs):
        title = doc.get('title', f'Document {i+1}')
        laboratoire = doc.get('medicine_details', {}).get('laboratoire', '')
        substances = doc.get('medicine_details', {}).get('substances_actives', [])
        extrait = ""
        # Prendre un extrait du contenu si possible
        if 'sections' in doc and doc['sections']:
            for section in doc['sections']:
                if 'content' in section and section['content']:
                    for content_item in section['content']:
                        if 'text' in content_item and content_item['text']:
                            extrait = content_item['text'][:300]
                            break
                    if extrait:
                        break
        context += f"\n- Titre : {title}\n  Laboratoire : {laboratoire}\n  Substances : {', '.join(substances)}\n  Extrait : {extrait}"
    # Prompt pour la génération de réponse
    prompt = f"""
    Tu es un assistant médical. À partir de la question utilisateur et des documents médicaux trouvés ci-dessous, rédige une réponse synthétique, claire et adaptée à la question.
    
    Question utilisateur : {user_query}
    
    Documents trouvés :
    {context}
    
    INSTRUCTIONS DE FORMATAGE :
    - Réponds en français, en 1 à 3 paragraphes maximum.
    - Utilise uniquement du HTML simple (<p>, <strong>, <em>).
    - Mets en gras les termes médicaux importants.
    - Ne commence pas par "Voici les documents" ou "D'après les documents".
    - Sois synthétique, informatif et accessible.
    """
    try:
        client = Mistral(api_key=MISTRAL_API_KEY)
        chat_response = client.chat.complete(
            model="mistral-small-2503",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=350
        )
        answer = chat_response.choices[0].message.content.strip()
        answer = clean_summary_format(answer)
        if not answer.strip().startswith('<p>'):
            answer = "<p>" + answer.replace("\n\n", "</p><p>") + "</p>"
            answer = answer.replace("<p></p>", "")
        return answer
    except Exception as e:
        logger.error(f"Erreur lors de la génération de réponse Mistral : {e}")
        return "<p>Impossible de générer une réponse IA pour le moment.</p>"

def generate_medicine_summary(medicine):
    """
    Generate an AI summary of the medicine using Mistral AI
    
    Args:
        medicine (dict): Medicine data
        
    Returns:
        str: AI-generated summary of the medicine
    """
    # Check if API key is available
    if not MISTRAL_API_KEY:
        return "<p>Erreur: Clé API non trouvée. Impossible de générer un résumé.</p>"
    
    # Extract basic information for the summary
    title = medicine.get('title', 'Médicament inconnu')
    substances = medicine.get('medicine_details', {}).get('substances_actives', [])
    forme = medicine.get('medicine_details', {}).get('forme', 'Non spécifié')
    laboratoire = medicine.get('medicine_details', {}).get('laboratoire', 'Non spécifié')
    dosages = medicine.get('medicine_details', {}).get('dosages', [])
    
    # Extract ALL content from sections
    all_sections_text = ""
    
    if 'sections' in medicine:
        for section in medicine['sections']:
            section_title = section.get('title', '')
            all_sections_text += f"\n### {section_title}\n"
            
            # Get content from this section
            if 'content' in section and section['content']:
                for content_item in section['content']:
                    if 'text' in content_item:
                        all_sections_text += content_item['text'] + "\n"
            
            # Get content from subsections
            if 'subsections' in section:
                for subsection in section['subsections']:
                    subsection_title = subsection.get('title', '')
                    all_sections_text += f"\n#### {subsection_title}\n"
                    
                    if 'content' in subsection and subsection['content']:
                        for content_item in subsection['content']:
                            if 'text' in content_item:
                                all_sections_text += content_item['text'] + "\n"
    
    # Limit the total content length to avoid exceeding API limits
    if len(all_sections_text) > 5000:
        all_sections_text = all_sections_text[:5000] + "...[contenu tronqué]"
    
    # Create a prompt for the API
    prompt = f"""
    Génère un résumé concis en français pour le médicament suivant:
    
    Nom: {title}
    Substances actives: {', '.join(substances) if substances else 'Non spécifié'}
    Forme pharmaceutique: {forme}
    Laboratoire: {laboratoire}
    Dosages: {', '.join(str(d) for d in dosages) if dosages else 'Non spécifié'}
    
    Informations détaillées sur le médicament:
    {all_sections_text}
    
    Le résumé doit inclure:
    1. Les utilisations principales de ce médicament
    2. Comment il fonctionne en termes simples
    3. Mention brève des effets secondaires courants le cas échéant
    4. Précautions d'emploi importantes
    
    INSTRUCTIONS DE FORMATAGE IMPORTANTES:
    - Utilise UNIQUEMENT du HTML simple (pas de Markdown)
    - Format: paragraphes avec balises <p> </p>
    - Pour le texte en gras, utilise <strong> </strong>
    - Pour l'italique, utilise <em> </em>
    - Mets en gras (<strong>) les noms de maladies, symptômes et termes médicaux importants
    - Mets également en gras les précautions d'emploi cruciales
    - Maximum 3-4 paragraphes
    - Ton: Informatif et accessible, adapté à un large public
    - N'UTILISE PAS de balises de code comme ```html au début ou à la fin
    """
    
    try:
        # Initialize Mistral client
        client = Mistral(api_key=MISTRAL_API_KEY)
        
        # Make the API request using the Mistral client - using the exact format as our successful test
        chat_response = client.chat.complete(
            model="mistral-small-2503",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        # Extract the generated summary
        summary = chat_response.choices[0].message.content
        
        # Clean up the formatting
        summary = clean_summary_format(summary)
        
        # Ensure the summary has proper HTML formatting
        if not summary.strip().startswith('<p>'):
            summary = "<p>" + summary.replace("\n\n", "</p><p>") + "</p>"
            summary = summary.replace("<p></p>", "")
        
        return summary
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du résumé IA: {e}")
        return f"<p>Impossible de générer un résumé pour le moment. Veuillez réessayer plus tard. Erreur: {str(e)}</p>"


def get_or_generate_summary(medicine, db=None):
    """
    Get cached summary from database or generate a new one
    
    Args:
        medicine (dict): Medicine data
        db (pymongo.database.Database, optional): MongoDB database connection
        
    Returns:
        str: AI-generated or cached summary
    """
    medicine_id = medicine.get('_id')
    current_time = int(time.time())
    
    # Check if we already have a summary in the medicine object
    if medicine.get('ai_summary'):
        # If we have summary_timestamp and it's less than 10 minutes old, use it
        if medicine.get('summary_timestamp') and (current_time - medicine.get('summary_timestamp') < CACHE_DURATION):
            return medicine['ai_summary']
    
    # If db is provided, check if summary exists in database and is recent enough
    if db is not None:
        try:
            # Find the medicine and check if it has an ai_summary field
            stored_medicine = db.medicines.find_one(
                {"_id": medicine_id}, 
                {"ai_summary": 1, "summary_timestamp": 1}
            )
            
            if stored_medicine and 'ai_summary' in stored_medicine:
                # Check if summary is less than 10 minutes old
                if 'summary_timestamp' in stored_medicine and (current_time - stored_medicine['summary_timestamp'] < CACHE_DURATION):
                    return stored_medicine['ai_summary']
                    
        except Exception as e:
            logger.error(f"Error checking for cached summary: {e}")
    
    # Generate new summary
    summary = generate_medicine_summary(medicine)
    
    # Save to database if possible with timestamp
    if db is not None:
        try:
            db.medicines.update_one(
                {"_id": medicine_id},
                {"$set": {
                    "ai_summary": summary,
                    "summary_timestamp": current_time
                }}
            )
        except Exception as e:
            logger.error(f"Error saving summary to database: {e}")
    
    return summary
