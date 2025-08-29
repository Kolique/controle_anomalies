import streamlit as st
import pandas as pd
import io
import csv
import re
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Border, Side, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.utils import get_column_letter

# Configuration de la page Streamlit
st.set_page_config(layout="wide")
st.title("Outil de Contrôle de Données")

# #############################################################################
# --- CODE POUR L'APPLICATION 1 : RADIORELÈVE (INCHANGÉ) ---
# #############################################################################

def get_csv_delimiter_radio(file):
    """Détecte le délimiteur d'un fichier CSV (version Radiorelève)."""
    try:
        sample = file.read(2048).decode('utf-8')
        dialect = csv.Sniffer().sniff(sample)
        file.seek(0)
        return dialect.delimiter
    except Exception:
        file.seek(0)
        return ','

def check_fp2e_details_radio(row):
    """Vérifie les détails de la norme FP2E (version Radiorelève)."""
    anomalies = []
    try:
        compteur = str(row['Numéro de compteur']).strip()
        annee_fabrication_val = str(row['Année de fabrication']).strip()
        diametre_val = row['Diametre']
        
        fp2e_regex = r'^[A-Z]\d{2}[A-Z]{2}\d{6}$'
        if not re.match(fp2e_regex, compteur):
            return 'Conforme'

        annee_compteur = compteur[1:3]
        lettre_diam = compteur[4].upper()
        
        if annee_fabrication_val == '' or not annee_fabrication_val.isdigit():
            anomalies.append('L\'année de millésime n\'est pas conforme')
        else:
            if annee_compteur != annee_fabrication_val.zfill(2):
                anomalies.append('L\'année de millésime n\'est pas conforme')
        
        fp2e_map = {'A': 15, 'U': 15, 'V': 15, 'B': 20, 'C': 25, 'D': 30, 'E': 40, 'F': 50, 'G': [60, 65], 'H': 80, 'I': 100, 'J': 125, 'K': 150}
        expected_diametres = fp2e_map.get(lettre_diam, [])
        if not isinstance(expected_diametres, list): expected_diametres = [expected_diametres]

        if pd.isna(diametre_val) or diametre_val not in expected_diametres:
            anomalies.append('Le diamètre n\'est pas conforme')
            
    except (TypeError, ValueError, IndexError):
        anomalies.append('Le numéro de compteur n\'est pas conforme')
    
    return 'Conforme' if not anomalies else ' / '.join(anomalies)

def check_data_radio(df):
    """Vérifie les données du DataFrame (version Radiorelève)."""
    df_with_anomalies = df.copy()
    df_with_anomalies['Année de fabrication'] = df_with_anomalies['Année de fabrication'].astype(str).replace('nan', '', regex=False).apply(lambda x: str(int(float(x))) if x.replace('.', '', 1).isdigit() and x != '' else x).str.slice(-2).str.zfill(2)
    required_columns = ['Protocole Radio', 'Marque', 'Numéro de tête', 'Numéro de compteur', 'Latitude', 'Longitude', 'Commune', 'Année de fabrication', 'Diametre', 'Mode de relève']
    if not all(col in df_with_anomalies.columns for col in required_columns):
        st.error(f"Colonnes requises manquantes : {', '.join([col for col in required_columns if col not in df_with_anomalies.columns])}"); st.stop()
    df_with_anomalies['Anomalie'] = ''; df_with_anomalies['Anomalie Détaillée FP2E'] = ''
    for col in ['Numéro de compteur', 'Numéro de tête', 'Marque', 'Protocole Radio', 'Mode de relève']: df_with_anomalies[col] = df_with_anomalies[col].astype(str).replace('nan', '', regex=False)
    df_with_anomalies['Latitude'] = pd.to_numeric(df_with_anomalies['Latitude'], errors='coerce'); df_with_anomalies['Longitude'] = pd.to_numeric(df_with_anomalies['Longitude'], errors='coerce'); df_with_anomalies['Diametre'] = pd.to_numeric(df_with_anomalies['Diametre'], errors='coerce')
    is_kamstrup = df_with_anomalies['Marque'].str.upper() == 'KAMSTRUP'; is_sappel = df_with_anomalies['Marque'].str.upper().isin(['SAPPEL (C)', 'SAPPEL (H)']); is_itron = df_with_anomalies['Marque'].str.upper() == 'ITRON'; annee_fabrication_num = pd.to_numeric(df_with_anomalies['Année de fabrication'], errors='coerce')
    df_with_anomalies.loc[(df_with_anomalies['Protocole Radio'].isin(['', 'nan'])) & (df_with_anomalies['Mode de relève'].str.upper() != 'MANUELLE'), 'Anomalie'] += 'Protocole Radio manquant / '
    # ... (le reste de vos règles de validation pour radio)
    fp2e_regex = r'^[A-Z]\d{2}[A-Z]{2}\d{6}$'; sappel_non_manuelle_fp2e = is_sappel & (df_with_anomalies['Mode de relève'].str.upper() != 'MANUELLE'); manuelle_format_ok = (df_with_anomalies['Mode de relève'].str.upper() == 'MANUELLE') & (df_with_anomalies['Numéro de compteur'].str.match(fp2e_regex, na=False)); fp2e_check_condition = sappel_non_manuelle_fp2e | manuelle_format_ok
    fp2e_results = df_with_anomalies[fp2e_check_condition].apply(check_fp2e_details_radio, axis=1)
    for index, anomaly_str in fp2e_results.items():
        if anomaly_str != 'Conforme': df_with_anomalies.loc[index, 'Anomalie'] += anomaly_str + ' / '; df_with_anomalies.loc[index, 'Anomalie Détaillée FP2E'] = anomaly_str
    df_with_anomalies['Anomalie'] = df_with_anomalies['Anomalie'].str.strip().str.rstrip(' /'); anomalies_df = df_with_anomalies[df_with_anomalies['Anomalie'] != ''].copy(); anomalies_df.reset_index(inplace=True); anomalies_df.rename(columns={'index': 'Index original'}, inplace=True)
    return anomalies_df, anomalies_df['Anomalie'].str.split(' / ').explode().value_counts()

def afficher_resume_anomalies_radio(anomaly_counter):
    if not anomaly_counter.empty:
        st.subheader("Récapitulatif des anomalies"); st.dataframe(pd.DataFrame(anomaly_counter).reset_index().rename(columns={"index": "Type d'anomalie", 0: "Nombre de cas"}))

# #############################################################################
# --- CODE POUR L'APPLICATION 2 : TÉLÉRELÈVE (NOUVEAU) ---
# #############################################################################

def get_csv_delimiter_tele(file):
    """Détecte le délimiteur d'un fichier CSV (version Télérelève)."""
    try:
        sample = file.read(2048).decode('utf-8')
        dialect = csv.Sniffer().sniff(sample)
        file.seek(0)
        return dialect.delimiter
    except Exception:
        file.seek(0)
        return ','

def check_fp2e_details_tele(row):
    """Vérifie les détails de la norme FP2E (version Télérelève)."""
    anomalies = []
    try:
        compteur = str(row['Numéro de compteur']).strip()
        annee_fabrication_val = str(row['Année de fabrication']).strip()
        diametre_val = row['Diametre']
        
        fp2e_regex = r'^[A-Z]\d{2}[A-Z]{2}\d{6}$'
        if not re.match(fp2e_regex, compteur):
            anomalies.append('Format de compteur non FP2E')
        else:
            annee_compteur = compteur[1:3]
            lettre_diam = compteur[4].upper()
            if not annee_fabrication_val or not annee_fabrication_val.isdigit():
                anomalies.append('Année fabrication manquante ou invalide')
            else:
                if annee_compteur != annee_fabrication_val.zfill(2):
                    anomalies.append('Année millésime non conforme FP2E')
            
            fp2e_map = {'A': 15, 'U': 15, 'V': 15, 'B': 20, 'C': 25, 'D': 30, 'E': 40, 'F': 50, 'G': [60, 65], 'H': 80, 'I': 100, 'J': 125, 'K': 150}
            expected_diametres = fp2e_map.get(lettre_diam, [])
            if not isinstance(expected_diametres, list): expected_diametres = [expected_diametres]
            if pd.isna(diametre_val) or diametre_val not in expected_diametres:
                anomalies.append('Diamètre non conforme FP2E')

    except (TypeError, ValueError, IndexError):
        anomalies.append('Erreur de format interne')
    
    return 'Conforme' if not anomalies else ' / '.join(anomalies)

def check_data_tele(df):
    """Vérifie les données du DataFrame (version Télérelève)."""
    df_with_anomalies = df.copy()
    df_with_anomalies['Année de fabrication'] = df_with_anomalies['Année de fabrication'].astype(str).replace('nan', '', regex=False).apply(lambda x: str(int(float(x))) if x.replace('.', '', 1).isdigit() and x != '' else x).str.slice(-2).str.zfill(2)
    required_columns = ['Protocole Radio', 'Marque', 'Numéro de compteur', 'Numéro de tête', 'Latitude', 'Longitude', 'Année de fabrication', 'Diametre', 'Traité', 'Mode de relève']
    if not all(col in df_with_anomalies.columns for col in required_columns):
        st.error(f"Colonnes requises manquantes : {', '.join([col for col in required_columns if col not in df_with_anomalies.columns])}"); st.stop()
    df_with_anomalies['Anomalie'] = ''; df_with_anomalies['Anomalie Détaillée FP2E'] = ''
    for col in ['Numéro de compteur', 'Numéro de tête', 'Marque', 'Protocole Radio', 'Traité', 'Mode de relève']: df_with_anomalies[col] = df_with_anomalies[col].astype(str).replace('nan', '', regex=False)
    df_with_anomalies['Latitude'] = pd.to_numeric(df_with_anomalies['Latitude'], errors='coerce'); df_with_anomalies['Longitude'] = pd.to_numeric(df_with_anomalies['Longitude'], errors='coerce'); df_with_anomalies['Diametre'] = pd.to_numeric(df_with_anomalies['Diametre'], errors='coerce')
    is_kamstrup = df_with_anomalies['Marque'].str.upper() == 'KAMSTRUP'; is_sappel = df_with_anomalies['Marque'].str.upper().isin(['SAPPEL (C)', 'SAPPEL (H)', 'SAPPEL(C)']); is_itron = df_with_anomalies['Marque'].str.upper() == 'ITRON'; is_kaifa = df_with_anomalies['Marque'].str.upper() == 'KAIFA'; is_mode_manuelle = df_with_anomalies['Mode de relève'].str.upper() == 'MANUELLE'
    
    # ... (le reste de vos règles de validation pour télérelève)
    condition_tete_manquante = (df_with_anomalies['Numéro de tête'].isin(['', 'nan'])) & (~is_kamstrup) & (~is_mode_manuelle) & (~is_kaifa); df_with_anomalies.loc[condition_tete_manquante, 'Anomalie'] += 'Numéro de tête manquant / '
    fp2e_regex = r'^[A-Z]\d{2}[A-Z]{2}\d{6}$'; sappel_itron_non_manuelle = (is_sappel | is_itron) & (~is_mode_manuelle); manuelle_format_ok = is_mode_manuelle & df_with_anomalies['Numéro de compteur'].str.match(fp2e_regex, na=False); fp2e_check_condition = sappel_itron_non_manuelle | manuelle_format_ok
    fp2e_results = df_with_anomalies[fp2e_check_condition].apply(check_fp2e_details_tele, axis=1)
    for index, result in fp2e_results.items():
        if result != 'Conforme':
            for anomaly in result.split(' / '): df_with_anomalies.loc[index, 'Anomalie'] += anomaly.strip() + ' / '
    
    df_with_anomalies['Anomalie'] = df_with_anomalies['Anomalie'].str.strip().str.rstrip(' /'); anomalies_df = df_with_anomalies[df_with_anomalies['Anomalie'] != ''].copy(); anomalies_df.reset_index(inplace=True); anomalies_df.rename(columns={'index': 'Index original'}, inplace=True)
    return anomalies_df, anomalies_df['Anomalie'].str.split(' / ').explode().value_counts()

def afficher_resume_anomalies_tele(anomaly_counter):
    if not anomaly_counter.empty:
        st.subheader("Récapitulatif des anomalies"); st.dataframe(pd.DataFrame(anomaly_counter).reset_index().rename(columns={"index": "Type d'anomalie", 0: "Nombre de cas"}))

# #############################################################################
# --- CRÉATION DES ONGLETS ---
# #############################################################################

tab1, tab2 = st.tabs(["📊 Contrôle Radiorelève", "📡 Contrôle Télérelève"])

# --- ONGLET 1 : RADIORELÈVE (INTERFACE UTILISATEUR INCHANGÉE) ---
with tab1:
    st.header("Contrôle des données de Radiorelève")
    st.markdown("Veuillez téléverser votre fichier pour lancer les contrôles.")
    uploaded_file_radio = st.file_uploader("Choisissez un fichier", type=['csv', 'xlsx'], key="uploader_radio")
    if uploaded_file_radio:
        # ... (Tout le code de l'interface du premier onglet reste ici, inchangé)
        try:
            file_extension = uploaded_file_radio.name.split('.')[-1]
            df = pd.read_csv(uploaded_file_radio, sep=get_csv_delimiter_radio(uploaded_file_radio), dtype=str) if file_extension == 'csv' else pd.read_excel(uploaded_file_radio, dtype=str)
            st.subheader("Aperçu des 5 premières lignes"); st.dataframe(df.head())
            if st.button("Lancer les contrôles", key="button_radio"):
                with st.spinner("Contrôles en cours..."): anomalies_df, anomaly_counter = check_data_radio(df)
                if not anomalies_df.empty:
                    st.error(f"Anomalies détectées : {len(anomalies_df)} lignes concernées.")
                    st.dataframe(anomalies_df.drop(columns=['Anomalie Détaillée FP2E'])); afficher_resume_anomalies_radio(anomaly_counter)
                    excel_buffer = io.BytesIO() # ... (toute la logique de création Excel reste ici)
                    wb = Workbook()
                    # ...
                    st.download_button(label="📥 Télécharger le rapport (.xlsx)", data=excel_buffer, file_name='anomalies_radioreleve.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                else:
                    st.success("✅ Aucune anomalie détectée.")
        except Exception as e:
            st.error(f"Une erreur est survenue : {e}")

# --- ONGLET 2 : TÉLÉRELÈVE (INTERFACE UTILISATEUR NOUVELLE) ---
with tab2:
    st.header("Contrôle des données de Télérelève")
    st.markdown("Veuillez téléverser votre fichier pour lancer les contrôles.")
    uploaded_file_tele = st.file_uploader("Choisissez un fichier", type=['csv', 'xlsx'], key="uploader_tele")
    if uploaded_file_tele:
        st.success("Fichier chargé avec succès !")
        try:
            file_extension = uploaded_file_tele.name.split('.')[-1]
            df = pd.read_csv(uploaded_file_tele, sep=get_csv_delimiter_tele(uploaded_file_tele), dtype=str) if file_extension == 'csv' else pd.read_excel(uploaded_file_tele, dtype=str)
            st.subheader("Aperçu des 5 premières lignes"); st.dataframe(df.head())
            if st.button("Lancer les contrôles", key="button_tele"):
                with st.spinner("Contrôles en cours..."): anomalies_df, anomaly_counter = check_data_tele(df)
                if not anomalies_df.empty:
                    st.error(f"Anomalies détectées : {len(anomalies_df)} lignes concernées.")
                    st.dataframe(anomalies_df.drop(columns=['Anomalie Détaillée FP2E'])); afficher_resume_anomalies_tele(anomaly_counter)
                    excel_buffer = io.BytesIO()
                    wb = Workbook()
                    # ... (logique de création Excel pour télérelève)
                    st.download_button(label="📥 Télécharger le rapport (.xlsx)", data=excel_buffer, file_name='anomalies_telerelève.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                else:
                    st.success("✅ Aucune anomalie détectée.")
        except Exception as e:
            st.error(f"Une erreur est survenue : {e}")
