import streamlit as st
import streamlit_authenticator as stauth
from datetime import datetime, timedelta, time
import pandas as pd
import calendar
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload
import tempfile
import xlsxwriter
import io
from pytz import timezone

# 🌈 Personnalisation du style
st.markdown(
    """
    <style>
        .stApp {
            background-image: url('https://images.pexels.com/photos/6692943/pexels-photo-6692943.jpeg?cs=srgb&dl=pexels-tara-winstead-6692943.jpg&fm=jpg');
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }
        section[data-testid="stSidebar"] {
            background-color: #fff3cd;
        }
        h1, h2, h3 {
            color: #4a4a4a;
        }
        .stMarkdown h2 {
            color: black !important;
        }
        .stButton>button {
            background-color: #cc9a56;
            color: white;
            border-radius: 10px;
            height: 3em;
            width: 100%;
        }
        .stButton>button:hover {
            background-color: #b3884e;
            color: white;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# 🌐 Authentification Google Drive
def get_drive_service():
    creds_dict = json.loads(st.secrets["google"]["credentials_json"])
    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

# 📁 Fonctions utilitaires Google Drive
def get_file_from_drive(filename):
    drive_service = get_drive_service()
    folder_id = st.secrets["google"]["folder_id"]
    query = f"'{folder_id}' in parents and trashed = false and name = '{filename}'"
    results = drive_service.files().list(q=query, spaces='drive', fields="files(id, name)").execute()
    items = results.get('files', [])
    if not items:
        return pd.DataFrame()

    file_id = items[0]['id']
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    fh.seek(0)
    return pd.read_csv(fh)

def save_csv_to_drive(df, filename):
    drive_service = get_drive_service()
    folder_id = st.secrets["google"]["folder_id"]

    query = f"'{folder_id}' in parents and trashed = false and name = '{filename}'"
    results = drive_service.files().list(q=query, spaces='drive', fields="files(id, name)").execute()
    items = results.get('files', [])

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp:
        df.to_csv(temp.name, index=False)
        media = MediaFileUpload(temp.name, mimetype='text/csv')

        if items:
            file_id = items[0]['id']
            drive_service.files().update(fileId=file_id, media_body=media).execute()
        else:
            file_metadata = {
                'name': filename,
                'parents': [folder_id],
                'mimeType': 'text/csv'
            }
            drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
# Fonction pour créer/obtenir dossier parent sur Drive
# Récupérer ou créer un dossier enfant dans Drive
def get_or_create_child_folder(child_name):
    drive_service = get_drive_service()
    parent_drive_folder_id = st.secrets["google"]["folder_photos_root"]
    query = f"name = '{child_name}' and mimeType = 'application/vnd.google-apps.folder' and '{parent_drive_folder_id}' in parents and trashed=false"
    results = drive_service.files().list(q=query, spaces='drive', fields="files(id, name)").execute()
    folders = results.get('files', [])
    if folders:
        return folders[0]['id']
    else:
        folder_metadata = {
            'name': child_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_drive_folder_id]
        }
        folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')
# Upload photo dans dossier parent
def upload_photo_to_parent_folder(uploaded_file, parent_folder_id):
    file_buffer = io.BytesIO(uploaded_file.read())
    file_buffer.seek(0)
    media = MediaIoBaseUpload(file_buffer, mimetype=uploaded_file.type, resumable=True)
    file_metadata = {
        'name': uploaded_file.name,
        'parents': [parent_folder_id]
    }
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

def list_files_in_drive_folder(service, folder_id):
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType)").execute()
    return results.get('files', [])

def download_file(service, file_id, destination):
    request = service.files().get_media(fileId=file_id)
    fh = open(destination, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    fh.close()

# 🔐 Authentification utilisateur
credentials = {
    "usernames": {
        "nounou": {
            "name": st.secrets["usernames"]["nounou_name"],
            "password": st.secrets["usernames"]["nounou_password"]
        },
        "parent_caly": {
            "name": st.secrets["usernames"]["parent_caly_name"],
            "password": st.secrets["usernames"]["parent_caly_password"]
        },
        "parent_nate": {
            "name": st.secrets["usernames"]["parent_nate_name"],
            "password": st.secrets["usernames"]["parent_nate_password"]
        }
    }
}


fichier_csv = "suivi.csv"
fichier_presence_csv = "presence.csv"

dossier_photos = "photos"  # ou le dossier cible
os.makedirs(dossier_photos, exist_ok=True)

parent_enfants = {
    "Parent Caly": "Caly",
    "Parent Nate": "Nate"
}
tz = timezone('Europe/Paris') 
authenticator = stauth.Authenticate(credentials, "babyapp_cookie", "random_key", cookie_expiry_days=30)
try:
    authenticator.login()
except Exception as e:
    st.error(e)

if st.session_state.get('authentication_status'):
    authenticator.logout()
    st.write(f'Bonjour *{st.session_state.get("name")}*')
    name = st.session_state.get("name")
    role = "Nounou" if name == "Nounou" else "Parent"

    df = get_file_from_drive(fichier_csv)
    df_presence = get_file_from_drive(fichier_presence_csv)

    if df.empty:
        df = pd.DataFrame(columns=["Nom", "Activité", "Heure", "observation"])
    if df_presence.empty:
        df_presence = pd.DataFrame(columns=["Nom", "Date", "Arrivée", "Départ", "Durée"])
    # 👉 Partie Nounou
    if role == "Nounou":
        nom = st.selectbox("Choisir l'enfant ⬇", ["Caly", "Nate"])
        aujourdhui = datetime.now(tz).strftime("%d/%m/%Y")

        if st.button("👋 Heure d'arrivée"):
            heure = datetime.now(tz).strftime("%H:%M")
            df_presence = df_presence[~((df_presence["Nom"] == nom) & (df_presence["Date"] == str(aujourdhui)))]
            df_presence = pd.concat([df_presence, pd.DataFrame([{
                "Nom": nom,
                "Date": str(aujourdhui),
                "Arrivée": heure,
                "Départ": "",
                "Durée": ""
            }])], ignore_index=True)
            save_csv_to_drive(df_presence, fichier_presence_csv)
            st.success(f"Arrivée enregistrée à {heure}")

        if st.button("👋 Heure de départ"):
            heure_depart = datetime.now(tz).strftime("%H:%M")
            index = df_presence[(df_presence["Nom"] == nom) & (df_presence["Date"] == str(aujourdhui))].index
            if not index.empty:
                idx = index[0]
                df_presence.at[idx, "Départ"] = heure_depart
                try:
                    t1 = datetime.strptime(df_presence.at[idx, "Arrivée"], "%H:%M")
                    t2 = datetime.strptime(heure_depart, "%H:%M")
                    duree = t2 - t1 if t2 > t1 else (t2 + timedelta(days=1) - t1)
                    df_presence.at[idx, "Durée"] = duree
                except Exception as e:
                    st.error(f"Erreur de calcul : {e}")
                df_presence["Départ"] = df_presence["Départ"].astype(str)
                df_presence["Durée"] = df_presence["Durée"].astype(str)
                save_csv_to_drive(df_presence, fichier_presence_csv)
                st.success(f"Départ enregistré à {heure_depart}")
            else:
                st.warning("Aucune heure d'arrivée trouvée pour aujourd'hui.")

        remarque = st.text_input("Observation", key="repas_remarque")
        col1, col2, col3, col4, col5 = st.columns(5)
        date_heure = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
        if col1.button("🍲 Repas"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Repas", "Heure": date_heure, "observation": remarque}])], ignore_index=True)
        if col2.button("📄 Début sieste"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Début Sieste", "Heure": date_heure, "observation": remarque}])], ignore_index=True)
        if col3.button("🌞 Fin sieste"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Fin Sieste", "Heure": date_heure, "observation": remarque}])], ignore_index=True)
        if col4.button("🧷 Change"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Change", "Heure": date_heure, "observation": remarque}])], ignore_index=True)
        if col5.button("🍎 Goûter"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Goûter", "Heure": date_heure, "observation": remarque}])], ignore_index=True)

        save_csv_to_drive(df, fichier_csv)

        st.subheader("📜 Historique du jour")
        try:
            df["Heure"] = pd.to_datetime(df["Heure"], format= "%d/%m/%Y %H:%M", errors="coerce", dayfirst=False)
        except Exception as e:
            st.error(f"Erreur de conversion des dates : {e}")

        df["Heure"] = df["Heure"].dt.strftime("%d/%m/%Y %H:%M")
        st.dataframe(df.sort_values(by="Heure", ascending=False))

        st.subheader("🗘️ Besoins de la journée")
        besoins = st.text_area("Écrire un besoin à signaler aux parents")
        if st.button("✅ Enregistrer le besoin"):
            if besoins.strip():
                df = pd.concat([df, pd.DataFrame([{
                    "Nom": nom,
                    "Activité": "Besoins",
                    "Heure": datetime.now(tz).strftime("%d/%m/%Y %H:%M"),
                    "observation": besoins
                }])], ignore_index=True)
                save_csv_to_drive(df, fichier_csv)
                st.success("Besoin enregistré avec succès ✅")
            else:
                st.warning("Le champ de besoin est vide.")

        st.subheader("📄 Export des heures mensuelles")
        mois = st.selectbox("Choisir un mois", list(range(1, 13)), format_func=lambda x: calendar.month_name[x])
        annee = st.selectbox("Choisir une année", list(range(2025, datetime.now().year + 1)))
        if st.button("📦 Générer le fichier Excel du mois"):
            if not df_presence.empty:
                df_presence = get_file_from_drive(fichier_presence_csv)
                df_presence["Date"] = pd.to_datetime(df_presence["Date"], errors="coerce")
                df_presence["Durée"] = pd.to_timedelta(df_presence["Durée"], errors="coerce")
                df_presence["Durée_excel"] = df_presence["Durée"].dt.total_seconds() / 86400
                filtre = (df_presence["Date"].dt.month == mois) & (df_presence["Date"].dt.year == annee)
                df_mois = df_presence[filtre].copy()
                if not df_mois.empty:
                    recap = df_mois.groupby(["Nom", df_mois["Date"].dt.strftime("%d/%m/%Y")])["Durée"].sum().reset_index()
                    total_par_enfant = recap.groupby("Nom")["Durée"].sum().reset_index()
                    total_par_enfant.rename(columns={"Durée": "Total du mois"}, inplace=True)
                    nom_fichier = f"recap_{annee}-{mois:02d}.xlsx"
                    with pd.ExcelWriter(nom_fichier, engine="xlsxwriter") as writer:
                        workbook = writer.book
                        format_duree = workbook.add_format({'num_format': '[h]:mm:ss'})
                        enfants = df_mois["Nom"].unique()
                        for enfant in enfants:
                            feuille = df_mois[df_mois["Nom"] == enfant].copy()
                            feuille["Date"] = feuille["Date"].dt.strftime("%d/%m/%Y")
                            feuille = feuille[["Date", "Arrivée", "Départ", "Durée_excel"]]
                            feuille.columns = ["Date", "Arrivée", "Départ", "Durée"]
                            feuille.to_excel(writer, sheet_name=enfant, index=False)
                            worksheet = writer.sheets[enfant]
                            worksheet.set_column(3, 3, 12, format_duree)
                            total_row = len(feuille) + 1
                            worksheet.write(total_row, 2, "Total")
                            worksheet.write_formula(total_row, 3, f'=SUM(D2:D{total_row})', format_duree)
                    st.success(f"Fichier Excel généré : {nom_fichier}")
                    with open(nom_fichier, "rb") as f:
                        st.download_button("📅 Télécharger le fichier", f.read(), nom_fichier)
                else:
                    st.warning("Aucune donnée pour ce mois.")
            else:
                st.error("Le fichier de présence n'existe pas encore.")

        st.subheader("📷 Ajouter une photo pour l'enfant")
        # Assure-toi que la variable `nom` est bien définie et non vide
        if nom:
            uploaded_photo = st.file_uploader("Choisir une photo", type=["jpg", "jpeg", "png"])
            if uploaded_photo:
                drive_service = get_drive_service()
                folder_id_enfant = get_or_create_child_folder(nom)

                file_buffer = io.BytesIO(uploaded_photo.read())
                file_buffer.seek(0)
                media = MediaIoBaseUpload(file_buffer, mimetype=uploaded_photo.type, resumable=True)  # ✅ bon uploader

                file_metadata = {
                    'name': uploaded_photo.name,
                    'parents': [folder_id_enfant]
                }
                file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                st.success(f"Photo ajoutée pour {nom} 📸 (ID : {file.get('id')})")
    # 👉 Partie Parent
    elif role == "Parent":
        enfant = parent_enfants.get(name)
        st.subheader(f"📜 Historique de {enfant}")
        df["Heure"] = pd.to_datetime(df["Heure"], format="%d/%m/%Y %H:%M", errors="coerce")
        df_enfant = df[df["Nom"] == enfant]
        df_presence["Date"] = pd.to_datetime(df_presence["Date"], format="%d/%m/%Y", errors="coerce")
        df_now = df_presence[df_presence["Nom"] == enfant]
        dates_disponibles = sorted(df_now["Date"].dt.date.unique(), reverse=True)
        date_selectionnee = st.selectbox("Choisir une date :", dates_disponibles)
        maintenant = datetime.now(tz).time()
        heure_visibilite = time(8, 0)

        if maintenant >= heure_visibilite:
            df_presence["Date"] = pd.to_datetime(df_presence["Date"]).dt.date
            df_pres = df_presence[(df_presence["Nom"] == enfant) & (df_presence["Date"] == date_selectionnee)]
            if not df_pres.empty:
                st.subheader(f"⏰ Présences du {date_selectionnee.strftime('%d/%m/%Y')}")
                st.dataframe(df_pres[["Arrivée", "Départ", "Durée"]])
            else:
                st.info("Aucune donnée de présence pour la date sélectionnée.")

            df_jour = df_enfant[df_enfant["Heure"].dt.date == date_selectionnee]
            df_jour["Heure"] = df_jour["Heure"].dt.strftime("%H:%M")
            st.write(f"🗓️ Activités du {date_selectionnee}")
            st.dataframe(df_jour[df_jour["Activité"] != "Besoins"][["Activité", "Heure", "observation"]].sort_values(by="Heure", ascending=False))

            besoins_du_jour = df_jour[df_jour["Activité"] == "Besoins"]
            if not besoins_du_jour.empty:
                st.warning("🔔 Besoins pour les prochains jours :")
                for _, row in besoins_du_jour.iterrows():
                    st.markdown(f"➡️  **{row['observation']}**")

        st.subheader(f"📸 Photos de {enfant}")
        drive_service = get_drive_service()
        folder_id_enfant = get_or_create_child_folder(enfant)

        files = list_files_in_drive_folder(drive_service, folder_id_enfant)
        if files:
            for file in files:
                file_id = file['id']
                file_name = file['name']

                request = drive_service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                fh.seek(0)

                st.image(fh.read(), caption=file_name, use_container_width=True)
                fh.seek(0)
                st.download_button("📸 Télécharger", fh, file_name=file_name)
        else:
            st.info("Aucune photo disponible pour cet enfant.")

elif st.session_state.get('authentication_status') is False:
    st.error('Nom d’utilisateur ou mot de passe incorrect')
elif st.session_state.get('authentication_status') is None:
    st.warning('Veuillez entrer vos identifiants')
