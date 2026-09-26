Automated HR Outreach & DNS Bounce-Check Pipeline

Pipeline de données développé en Python pour automatiser la prospection de recruteurs ciblés, vérifier la délivrabilité réseau des domaines et générer des candidatures sur-mesure via LLM.

## Problématique
Dans le cadre d'un cours et face aux limites des outils payants de prospection (crédits réduits, rebonds d'adresses), l'objectif était de bâtir un système autonome, gratuit et conforme, capable de transformer des données brutes en leads qualifiés sans risque de blacklistage SMTP.

## Architecture du Pipeline
1. **Extraction & Nettoyage :** Traitement d'un jeu brut de 600 profils LinkedIn via `pandas`. Déduction algorithmique des e-mails professionnels (`prenom.nom@entreprise.fr`).
2. **Bounce Check DNS :** Validation programmatique des serveurs de messagerie (enregistrements MX) via `dnspython` pour écarter les adresses non distribuables en amont.
3. **Génération IA :** Intégration de l'API DeepSeek pour rédiger des e-mails d'accroche courts (< 80 mots) et ultra-personnalisés.
4. **Routage SMTP Sécurisé :** Expédition via protocole SMTP SSL avec temporisation anti-spam de 5 secondes et journalisation dans Excel.

## Métriques importantes
- **600** profils bruts traités.
- **35,8 %** d'adresses invalides éliminées avant l'envoi (215 rejets).
- **385** prospects validés à 100 % (0 hard bounce).
- **0 €** de coût en outils tiers.

## Stack Technique
- **Langage :** Python 3.10+
- **Data & Réseau :** Pandas, OpenpyXL, Dnspython
- **IA & Routage :** API DeepSeek, Smtplib, Email MIME
