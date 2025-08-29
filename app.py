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
# Toutes les fonctions et variables de cette section sont renommées avec le 
# suffixe '_radio' pour éviter les conflits avec le futur deuxième onglet.
# #############################################################################

diametre_lettre_radio = {
    15: ['A', 'U', 'V'], 20: ['B'], 25: ['C'], 30: ['D'], 40: ['E'],
    50: ['F'], 60: ['G'], 65: ['G'], 80: ['H'], 100: ['I'],
    125: ['J'], 150: ['K']
}

def get_csv_delimiter_radio(file):
    """Détecte automatiquement le délimiteur d'un fichier CSV."""
    try:
        sample = file.read(2048).decode('utf-8')
        dialect = csv.Sniffer().sniff(sample)
        file.seek(0)
        return dialect.delimiter
    except Exception:
        file.seek(0)
        return ','

def check_fp2e_details_radio(row):
    """Vérifie les détails de la norme FP2E."""
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
        
        annee_non_conforme = False
        if annee_fabrication_val == '' or not annee_fabrication_val.isdigit():
            anomalies.append('L\'année de millésime n\'est pas conforme')
            annee_non_conforme = True
        else:
            annee_fabrication_padded = annee_fabrication_val.zfill(2)
            if annee_compteur != annee_fabrication_padded:
                anomalies.append('L\'année de millésime n\'est pas conforme')
                annee_non_conforme = True
        
        diametre_non_conforme = False
        fp2e_map = {'A': 15, 'U': 15, 'V': 15, 'B': 20, 'C': 25, 'D': 30, 'E': 40, 'F': 50, 'G': [60, 65], 'H': 80, 'I': 100, 'J': 125, 'K': 150}
        expected_diametres = fp2e_map.get(lettre_diam, [])
        if not isinstance(expected_diametres, list):
            expected_diametres = [expected_diametres]

        if pd.isna(diametre_val) or diametre_val not in expected_diametres:
            anomalies.append('Le diamètre n\'est pas conforme')
            diametre_non_conforme = True
        
        if not anomalies and (not annee_non_conforme and not diametre_non_conforme):
            pass
            
    except (TypeError, ValueError, IndexError):
        anomalies.append('Le numéro de compteur n\'est pas conforme')
    
    if not anomalies:
        return 'Conforme'
    else:
        return ' / '.join(anomalies)

def check_data_radio(df):
    """Vérifie les données du DataFrame pour détecter les anomalies."""
    df_with_anomalies = df.copy()

    df_with_anomalies['Année de fabrication'] = df_with_anomalies['Année de fabrication'].astype(str).replace('nan', '', regex=False)
    df_with_anomalies['Année de fabrication'] = df_with_anomalies['Année de fabrication'].apply(
        lambda x: str(int(float(x))) if x.replace('.', '', 1).isdigit() and x != '' else x
    )
    df_with_anomalies['Année de fabrication'] = df_with_anomalies['Année de fabrication'].str.slice(-2).str.zfill(2)
    
    required_columns = ['Protocole Radio', 'Marque', 'Numéro de tête', 'Numéro de compteur', 'Latitude', 'Longitude', 'Commune', 'Année de fabrication', 'Diametre', 'Mode de relève']
    if not all(col in df_with_anomalies.columns for col in required_columns):
        missing_columns = [col for col in required_columns if col not in df_with_anomalies.columns]
        st.error(f"Colonnes requises manquantes : {', '.join(missing_columns)}")
        st.stop()

    df_with_anomalies['Anomalie'] = ''
    df_with_anomalies['Anomalie Détaillée FP2E'] = ''

    for col in ['Numéro de compteur', 'Numéro de tête', 'Marque', 'Protocole Radio', 'Mode de relève']:
        df_with_anomalies[col] = df_with_anomalies[col].astype(str).replace('nan', '', regex=False)
    
    df_with_anomalies['Latitude'] = pd.to_numeric(df_with_anomalies['Latitude'], errors='coerce')
    df_with_anomalies['Longitude'] = pd.to_numeric(df_with_anomalies['Longitude'], errors='coerce')

    is_kamstrup = df_with_anomalies['Marque'].str.upper() == 'KAMSTRUP'
    is_sappel = df_with_anomalies['Marque'].str.upper().isin(['SAPPEL (C)', 'SAPPEL (H)'])
    is_itron = df_with_anomalies['Marque'].str.upper() == 'ITRON'
    annee_fabrication_num = pd.to_numeric(df_with_anomalies['Année de fabrication'], errors='coerce')
    df_with_anomalies['Diametre'] = pd.to_numeric(df_with_anomalies['Diametre'], errors='coerce')

    # ANOMALIES GÉNÉRALES
    condition_protocole_manquant = (df_with_anomalies['Protocole Radio'].isin(['', 'nan'])) & (df_with_anomalies['Mode de relève'].str.upper() != 'MANUELLE')
    df_with_anomalies.loc[condition_protocole_manquant, 'Anomalie'] += 'Protocole Radio manquant / '
    df_with_anomalies.loc[df_with_anomalies['Marque'].isin(['', 'nan']), 'Anomalie'] += 'Marque manquante / '
    df_with_anomalies.loc[df_with_anomalies['Numéro de compteur'].isin(['', 'nan']), 'Anomalie'] += 'Numéro de compteur manquant / '
    df_with_anomalies.loc[df_with_anomalies['Diametre'].isnull(), 'Anomalie'] += 'Diamètre manquant / '
    df_with_anomalies.loc[df_with_anomalies['Année de fabrication'].isnull(), 'Anomalie'] += 'Année de fabrication manquante / '
    condition_tete_manquante = (df_with_anomalies['Numéro de tête'].isin(['', 'nan'])) & (~is_sappel | (annee_fabrication_num >= 22)) & (df_with_anomalies['Mode de relève'].str.upper() != 'MANUELLE')
    df_with_anomalies.loc[condition_tete_manquante, 'Anomalie'] += 'Numéro de tête manquant / '
    df_with_anomalies.loc[df_with_anomalies['Latitude'].isnull() | df_with_anomalies['Longitude'].isnull(), 'Anomalie'] += 'Coordonnées GPS non numériques / '
    coord_invalid = ((df_with_anomalies['Latitude'] == 0) | (~df_with_anomalies['Latitude'].between(-90, 90))) | ((df_with_anomalies['Longitude'] == 0) | (~df_with_anomalies['Longitude'].between(-180, 180)))
    df_with_anomalies.loc[coord_invalid, 'Anomalie'] += 'Coordonnées GPS invalides / '

    # ANOMALIES SPÉCIFIQUES AUX MARQUES
    kamstrup_valid = is_kamstrup & (~df_with_anomalies['Numéro de tête'].isin(['', 'nan']))
    df_with_anomalies.loc[is_kamstrup & (df_with_anomalies['Numéro de compteur'].str.len() != 8), 'Anomalie'] += 'KAMSTRUP: Compteur ≠ 8 caractères / '
    df_with_anomalies.loc[kamstrup_valid & (df_with_anomalies['Numéro de compteur'] != df_with_anomalies['Numéro de tête']), 'Anomalie'] += 'KAMSTRUP: Compteur ≠ Tête / '
    df_with_anomalies.loc[kamstrup_valid & (~df_with_anomalies['Numéro de compteur'].str.isdigit() | ~df_with_anomalies['Numéro de tête'].str.isdigit()), 'Anomalie'] += 'KAMSTRUP: Compteur ou Tête non numérique / '
    df_with_anomalies.loc[is_kamstrup & (~df_with_anomalies['Diametre'].between(15, 80)), 'Anomalie'] += 'KAMSTRUP: Diamètre hors plage / '
    df_with_anomalies.loc[is_kamstrup & (df_with_anomalies['Protocole Radio'].str.upper() != 'WMS'), 'Anomalie'] += 'KAMSTRUP: Protocole ≠ WMS / '

    sappel_valid_tete_dme = is_sappel & (df_with_anomalies['Numéro de tête'].astype(str).str.upper().str.startswith('DME'))
    df_with_anomalies.loc[sappel_valid_tete_dme & (df_with_anomalies['Numéro de tête'].str.len() != 15), 'Anomalie'] += 'SAPPEL: Tête DME ≠ 15 caractères / '
    sappel_non_manuelle = is_sappel & (df_with_anomalies['Mode de relève'].str.upper() != 'MANUELLE')
    df_with_anomalies.loc[sappel_non_manuelle & (~df_with_anomalies['Numéro de compteur'].str.startswith(('C', 'H'))), 'Anomalie'] += 'SAPPEL: Compteur ne commence pas par C ou H / '
    df_with_anomalies.loc[(is_sappel) & (df_with_anomalies['Numéro de compteur'].str.startswith('C')) & (df_with_anomalies['Marque'].str.upper() != 'SAPPEL (C)'), 'Anomalie'] += 'SAPPEL: Incohérence Marque/Compteur (C) / '
    df_with_anomalies.loc[(is_sappel) & (df_with_anomalies['Numéro de compteur'].str.startswith('H')) & (df_with_anomalies['Marque'].str.upper() != 'SAPPEL (H)'), 'Anomalie'] += 'SAPPEL: Incohérence Marque/Compteur (H) / '
    df_with_anomalies.loc[is_sappel & (annee_fabrication_num > 22) & (~df_with_anomalies['Numéro de tête'].astype(str).str.upper().str.startswith('DME')), 'Anomalie'] += 'SAPPEL: Année >22 & Tête ≠ DME / '
    df_with_anomalies.loc[is_sappel & (annee_fabrication_num > 22) & (df_with_anomalies['Protocole Radio'].str.upper() != 'OMS'), 'Anomalie'] += 'SAPPEL: Année >22 & Protocole ≠ OMS / '

    itron_non_manuelle = is_itron & (df_with_anomalies['Mode de relève'].str.upper() != 'MANUELLE')
    df_with_anomalies.loc[itron_non_manuelle & (~df_with_anomalies['Numéro de compteur'].str.startswith(('I', 'D'))), 'Anomalie'] += 'ITRON: Compteur ne commence pas par I ou D / '

    # LOGIQUE POUR LA NORME FP2E
    fp2e_regex = r'^[A-Z]\d{2}[A-Z]{2}\d{6}$'
    sappel_non_manuelle_fp2e = is_sappel & (df_with_anomalies['Mode de relève'].str.upper() != 'MANUELLE')
    manuelle_format_ok = (df_with_anomalies['Mode de relève'].str.upper() == 'MANUELLE') & (df_with_anomalies['Numéro de compteur'].str.match(fp2e_regex, na=False))
    fp2e_check_condition = sappel_non_manuelle_fp2e | manuelle_format_ok
    
    # Appel à la fonction renommée
    fp2e_results = df_with_anomalies[fp2e_check_condition].apply(check_fp2e_details_radio, axis=1)
    
    for index, anomaly_str in fp2e_results.items():
        if anomaly_str != 'Conforme':
            df_with_anomalies.loc[index, 'Anomalie'] += anomaly_str + ' / '
            df_with_anomalies.loc[index, 'Anomalie Détaillée FP2E'] = anomaly_str
    
    df_with_anomalies['Anomalie'] = df_with_anomalies['Anomalie'].str.strip().str.rstrip(' /')
    anomalies_df = df_with_anomalies[df_with_anomalies['Anomalie'] != ''].copy()
    anomalies_df.reset_index(inplace=True)
    anomalies_df.rename(columns={'index': 'Index original'}, inplace=True)
    
    anomaly_counter = anomalies_df['Anomalie'].str.split(' / ').explode().value_counts()
    return anomalies_df, anomaly_counter

def afficher_resume_anomalies_radio(anomaly_counter):
    """Affiche un résumé des anomalies."""
    if not anomaly_counter.empty:
        summary_df = pd.DataFrame(anomaly_counter).reset_index()
        summary_df.columns = ["Type d'anomalie", "Nombre de cas"]
        st.subheader("Récapitulatif des anomalies")
        st.dataframe(summary_df)

# #############################################################################
# --- CRÉATION DES ONGLETS ---
# #############################################################################

tab1, tab2 = st.tabs(["📊 Contrôle Radiorelève", "⚙️ Autre Contrôle (à définir)"])

# --- ONGLET 1 : RADIORELÈVE (INTERFACE UTILISATEUR) ---
with tab1:
    st.header("Contrôle des données de Radiorelève")
    st.markdown("Veuillez téléverser votre fichier pour lancer les contrôles.")

    uploaded_file_radio = st.file_uploader("Choisissez un fichier", type=['csv', 'xlsx'], key="uploader_radio")

    if uploaded_file_radio is not None:
        st.success("Fichier chargé avec succès !")
        try:
            file_extension = uploaded_file_radio.name.split('.')[-1]
            dtype_mapping = {'Numéro de branchement': str, 'Abonnement': str}

            if file_extension == 'csv':
                delimiter = get_csv_delimiter_radio(uploaded_file_radio)
                df = pd.read_csv(uploaded_file_radio, sep=delimiter, dtype=dtype_mapping)
            elif file_extension == 'xlsx':
                df = pd.read_excel(uploaded_file_radio, dtype=dtype_mapping)
            else:
                st.error("Format de fichier non pris en charge.")
                st.stop()

            st.subheader("Aperçu des 5 premières lignes")
            st.dataframe(df.head())

            if st.button("Lancer les contrôles", key="button_radio"):
                with st.spinner("Contrôles en cours..."):
                    anomalies_df, anomaly_counter = check_data_radio(df)

                if not anomalies_df.empty:
                    st.error(f"Anomalies détectées : {len(anomalies_df)} lignes concernées.")
                    anomalies_df_display = anomalies_df.drop(columns=['Anomalie Détaillée FP2E'])
                    st.dataframe(anomalies_df_display)
                    afficher_resume_anomalies_radio(anomaly_counter)
                    
                    anomaly_columns_map = {
                        "Protocole Radio manquant": ['Protocole Radio'], "Marque manquante": ['Marque'],
                        "Numéro de compteur manquant": ['Numéro de compteur'], "Numéro de tête manquant": ['Numéro de tête'],
                        "Coordonnées GPS non numériques": ['Latitude', 'Longitude'], "Coordonnées GPS invalides": ['Latitude', 'Longitude'],
                        "Diamètre manquant": ['Diametre'], "Année de fabrication manquante": ['Année de fabrication'],
                        "KAMSTRUP: Compteur ≠ 8 caractères": ['Numéro de compteur'], "KAMSTRUP: Compteur ≠ Tête": ['Numéro de compteur', 'Numéro de tête'],
                        "KAMSTRUP: Compteur ou Tête non numérique": ['Numéro de compteur', 'Numéro de tête'], "KAMSTRUP: Diamètre hors plage": ['Diametre'],
                        "KAMSTRUP: Protocole ≠ WMS": ['Protocole Radio'], "SAPPEL: Tête DME ≠ 15 caractères": ['Numéro de tête'],
                        "SAPPEL: Compteur ne commence pas par C ou H": ['Numéro de compteur'], "SAPPEL: Incohérence Marque/Compteur (C)": ['Numéro de compteur'],
                        "SAPPEL: Incohérence Marque/Compteur (H)": ['Marque', 'Numéro de compteur'], "SAPPEL: Année >22 & Tête ≠ DME": ['Année de fabrication', 'Numéro de tête'],
                        "SAPPEL: Année >22 & Protocole ≠ OMS": ['Année de fabrication', 'Protocole Radio'], "ITRON: Compteur ne commence pas par I ou D": ['Numéro de compteur'],
                        "Le numéro de compteur n'est pas conforme": ['Numéro de compteur'], "Le diamètre n'est pas conforme": ['Diametre'],
                        "L'année de millésime n'est pas conforme": ['Année de fabrication'],
                    }

                    if file_extension == 'csv':
                        csv_file = anomalies_df_display.to_csv(index=False, sep=delimiter).encode('utf-8')
                        st.download_button(
                            label="📥 Télécharger les anomalies en CSV", data=csv_file,
                            file_name='anomalies_radioreleve.csv', mime='text/csv',
                        )
                    elif file_extension == 'xlsx':
                        excel_buffer = io.BytesIO()
                        wb = Workbook()
                        if "Sheet" in wb.sheetnames: wb.remove(wb["Sheet"])
                        
                        ws_summary = wb.create_sheet(title="Récapitulatif", index=0)
                        ws_all_anomalies = wb.create_sheet(title="Toutes_Anomalies", index=1)
                        for r in dataframe_to_rows(anomalies_df_display, index=False, header=True):
                            ws_all_anomalies.append(r)

                        header_font = Font(bold=True)
                        red_fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')

                        for cell in ws_all_anomalies[1]: cell.font = header_font

                        for row_num_all, df_row in enumerate(anomalies_df.iterrows(), 2):
                            anomalies = str(df_row[1]['Anomalie']).split(' / ')
                            for anomaly in anomalies:
                                anomaly_key = anomaly.strip()
                                if anomaly_key in anomaly_columns_map:
                                    for col_name in anomaly_columns_map[anomaly_key]:
                                        try:
                                            col_index = list(anomalies_df_display.columns).index(col_name) + 1
                                            ws_all_anomalies.cell(row=row_num_all, column=col_index).fill = red_fill
                                        except ValueError:
                                            pass
                        
                        for col in ws_all_anomalies.columns:
                            max_length = max(len(str(cell.value)) for cell in col if cell.value)
                            ws_all_anomalies.column_dimensions[get_column_letter(col[0].column)].width = max_length + 2

                        ws_summary['A1'] = "Récapitulatif des anomalies"
                        ws_summary['A1'].font = Font(bold=True, size=16)
                        ws_summary.append([])
                        ws_summary.append(["Type d'anomalie", "Nombre de cas"])
                        ws_summary['A3'].font = header_font
                        ws_summary['B3'].font = header_font
                        
                        created_sheet_names = {"Récapitulatif", "Toutes_Anomalies"}
                        
                        link_row = ws_summary.max_row + 1
                        ws_summary.cell(row=link_row, column=1, value="Toutes les anomalies").hyperlink = f"#Toutes_Anomalies!A1"
                        ws_summary.cell(row=link_row, column=1).font = Font(underline="single", color="0563C1")
                        ws_summary.cell(row=link_row, column=2, value=len(anomalies_df))

                        for anomaly_type, count in anomaly_counter.items():
                            sheet_name_base = anomaly_type[:28]
                            sheet_name = re.sub(r'[\\/?*\[\]:()\'"<>|]', '', sheet_name_base).replace(' ', '_').strip()
                            original_sheet_name = sheet_name
                            s_counter = 1
                            while sheet_name in created_sheet_names:
                                sheet_name = f"{original_sheet_name[:28]}_{s_counter}"
                                s_counter += 1
                            created_sheet_names.add(sheet_name)

                            row_num = ws_summary.max_row + 1
                            ws_summary.cell(row=row_num, column=1, value=anomaly_type)
                            ws_summary.cell(row=row_num, column=2, value=count)
                            ws_summary.cell(row=row_num, column=1).hyperlink = f"#'{sheet_name}'!A1"
                            ws_summary.cell(row=row_num, column=1).font = Font(underline="single", color="0563C1")
                            
                            ws_detail = wb.create_sheet(title=sheet_name)
                            filtered_df = anomalies_df[anomalies_df['Anomalie'].str.contains(re.escape(anomaly_type), regex=True)]
                            for r in dataframe_to_rows(filtered_df.drop(columns=['Anomalie Détaillée FP2E']), index=False, header=True):
                                ws_detail.append(r)
                            
                            for cell in ws_detail[1]: cell.font = header_font
                            # (La logique de coloration pourrait être ajoutée aussi pour les feuilles détaillées si besoin)
                            for col in ws_detail.columns:
                                max_length = max(len(str(cell.value)) for cell in col if cell.value)
                                ws_detail.column_dimensions[get_column_letter(col[0].column)].width = max_length + 2

                        excel_buffer.seek(0)
                        wb.save(excel_buffer)

                        st.download_button(
                            label="📥 Télécharger le rapport d'anomalies (.xlsx)", data=excel_buffer,
                            file_name='anomalies_radioreleve.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        )

                else:
                    st.success("✅ Aucune anomalie détectée. Les données sont conformes.")
        
        except Exception as e:
            st.error(f"Une erreur est survenue lors du traitement du fichier : {e}")


# --- ONGLET 2 : CONTENU À DÉFINIR ---
with tab2:
    st.header("Application de contrôle n°2")
    st.info("Le code et la logique pour cette deuxième application seront ajoutés ici.")
    st.markdown("---")
    # Vous pouvez ajouter un placeholder si vous le souhaitez
    st.write("En attente des spécifications...")
