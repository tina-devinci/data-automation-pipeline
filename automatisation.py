import os
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import dns.resolver
import pandas as pd
from openai import OpenAI

EXPEDITEUR_EMAIL = os.getenv("GMAIL_EMAIL", "")
EXPEDITEUR_MDP = os.getenv("GMAIL_APP_PASSWORD", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

MODE_SIMULATION = True
FICHIER_BRUT = "linkedin-com-2026-09-10-2.xlsx"
FICHIER_RAPPORT = "base_donnees_rh_data_propre.xlsx"
LIMITE_PROSPECTION = None

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

DOMAINES_BANNIS = {"tempmail.com", "yopmail.com", "throwaway.com", "gmail.com", "yahoo.fr", "hotmail.com"}
CACHE_DNS = {}


def resoudre_mx(domaine: str) -> bool:
    domaine = domaine.lower().strip()
    if domaine in DOMAINES_BANNIS:
        return False
    if domaine in CACHE_DNS:
        return CACHE_DNS[domaine]

    try:
        reponses = dns.resolver.resolve(domaine, "MX", lifetime=1.5)
        est_valide = len(reponses) > 0
    except Exception:
        est_valide = False

    CACHE_DNS[domaine] = est_valide
    return est_valide


def parser_et_valider_contact(row: pd.Series) -> dict:
    nom_complet = str(row.get("data", "")).strip()
    if not nom_complet or nom_complet == "nan":
        return None

    morceaux = nom_complet.split()
    prenom = morceaux[0] if morceaux else ""
    nom = " ".join(morceaux[1:]) if len(morceaux) > 1 else ""

    poste = str(row.get("data2", "")).strip()
    champ_poste = str(row.get("data4", ""))

    entreprise = ""
    if "chez " in champ_poste:
        entreprise = champ_poste.split("chez ")[-1].strip()
    elif "@" in poste:
        entreprise = poste.split("@")[-1].split("/")[0].strip()

    if not entreprise or entreprise == "nan":
        return None

    domaine_base = re.sub(r"[^a-zA-Z0-9]", "", entreprise.lower().split()[0])
    nom_clean = re.sub(r"[^a-zA-Z0-9]", "", nom.lower())
    prenom_clean = re.sub(r"[^a-zA-Z0-9]", "", prenom.lower())

    if not domaine_base or not nom_clean or not prenom_clean:
        return None

    domaine_choisi = None
    for ext in [".fr", ".com"]:
        domaine_test = f"{domaine_base}{ext}"
        if resoudre_mx(domaine_test):
            domaine_choisi = domaine_test
            break

    if not domaine_choisi:
        return None

    email = f"{prenom_clean}.{nom_clean}@{domaine_choisi}"
    pattern_email = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(pattern_email, email):
        return None

    loc = str(row.get("data3", "")).strip()

    return {
        "prenom": prenom,
        "nom": nom,
        "poste_rh": poste,
        "entreprise": entreprise,
        "domaine": domaine_choisi,
        "email_professionnel": email,
        "localisation": "" if loc == "nan" else loc,
        "statut_bounce": "Valide"
    }


def rediger_candidature(contact: dict) -> tuple:
    objet = f"Candidature spontanée Data — ({contact['prenom']} {contact['nom']})"

    system_prompt = (
        "Tu es une étudiante en Data Analytics & Systèmes d'Information. "
        "Rédige un e-mail de candidature spontanée percutant à un recruteur RH. "
        "Contraintes : salue par le prénom, cite l'entreprise, valorise tes compétences "
        "en Python, modélisation SQL et automatisation de pipelines, propose un court échange téléphonique. "
        "Longueur : moins de 80 mots. Réponds UNIQUEMENT avec le corps du message."
    )

    user_prompt = (
        f"Destinataire : {contact['prenom']}\n"
        f"Poste RH : {contact['poste_rh']}\n"
        f"Entreprise : {contact['entreprise']}"
    )

    try:
        rep = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        corps = rep.choices[0].message.content.strip()
    except Exception:
        corps = (
            f"Bonjour {contact['prenom']},\n\n"
            f"Intéressée par les enjeux Data de {contact['entreprise']}, je me permets de vous contacter. "
            "Actuellement formée à la modélisation SQL, aux pipelines Python et à l'automatisation, "
            "je souhaiterais échanger quelques minutes avec vous sur vos opportunités actuelles.\n\n"
            "Bien cordialement,\n"
            "Tina NGO"
        )

    return objet, corps


def envoyer_mail_smtp(destinataire: str, objet: str, corps: str):
    msg = MIMEMultipart()
    msg["From"] = EXPEDITEUR_EMAIL
    msg["To"] = destinataire
    msg["Subject"] = objet
    msg.attach(MIMEText(corps, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EXPEDITEUR_EMAIL, EXPEDITEUR_MDP)
        server.send_message(msg)


def executer_pipeline():
    if not os.path.exists(FICHIER_BRUT):
        print(f"Erreur : '{FICHIER_BRUT}' introuvable.")
        return

    df_brut = pd.read_excel(FICHIER_BRUT)
    contacts_valides = []
    rejets = 0

    for _, row in df_brut.iterrows():
        contact = parser_et_valider_contact(row)
        if contact:
            contacts_valides.append(contact)
        else:
            rejets += 1

    total = len(contacts_valides) + rejets
    print(f"Total analysé : {total} | Valides : {len(contacts_valides)} | Rejetés : {rejets}")

    echantillon = contacts_valides if LIMITE_PROSPECTION is None else contacts_valides[:LIMITE_PROSPECTION]
    historique = []

    for i, fiche in enumerate(echantillon, 1):
        objet, message = rediger_candidature(fiche)
        statut = "Simulation"

        if not MODE_SIMULATION:
            try:
                envoyer_mail_smtp(fiche["email_professionnel"], objet, message)
                statut = "Envoyé"
                time.sleep(5)
            except Exception as e:
                statut = f"Erreur : {e}"

        fiche["objet"] = objet
        fiche["message_genere"] = message
        fiche["statut_envoi"] = statut
        historique.append(fiche)
        print(f"[{i}/{len(echantillon)}] {fiche['email_professionnel']} -> {statut}")

    pd.DataFrame(historique).to_excel(FICHIER_RAPPORT, index=False)
    print(f"Export terminé : {FICHIER_RAPPORT}")


if __name__ == "__main__":
    executer_pipeline()