import streamlit as st
import streamlit_authenticator as stauth
from datetime import datetime, timedelta, time
import pandas as pd
import calendar
import os
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import tempfile
import xlsxwriter

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
def init_drive():
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile("credentials.json")
    if gauth.credentials is None:
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()
    gauth.SaveCredentialsFile("credentials.json")
    return GoogleDrive(gauth)

drive = init_drive()
FOLDER_ID = "1DIWaCkgrQ09ra3lP6SHXG43bGnTyC6B2"

# 📁 Fonctions utilitaires Google Drive
def get_file_from_drive(filename):
    file_list = drive.ListFile({'q': f"'{FOLDER_ID}' in parents and trashed=false and title='{filename}'"}).GetList()
    if file_list:
        file_drive = file_list[0]
        content = file_drive.GetContentString()
        return pd.read_csv(pd.compat.StringIO(content))
    return pd.DataFrame()

def save_csv_to_drive(df, filename):
    file_list = drive.ListFile({'q': f"'{FOLDER_ID}' in parents and trashed=false and title='{filename}'"}).GetList()
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    df.to_csv(temp.name, index=False)
    if file_list:
        file_drive = file_list[0]
        file_drive.SetContentFile(temp.name)
        file_drive.Upload()
    else:
        new_file = drive.CreateFile({'title': filename, 'parents': [{'id': FOLDER_ID}]})
        new_file.SetContentFile(temp.name)
        new_file.Upload()

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
        aujourdhui = datetime.now().strftime("%d/%m/%Y")

        if st.button("👋 Heure d'arrivée"):
            heure = datetime.now().strftime("%H:%M")
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
            heure_depart = datetime.now().strftime("%H:%M")
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
        if col1.button("🍲 Repas"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Repas", "Heure": datetime.now().strftime("%Y-%m-%d %H:%M"), "observation": remarque}])], ignore_index=True)
        if col2.button("📄 Début sieste"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Début Sieste", "Heure": datetime.now().strftime("%Y-%m-%d %H:%M"), "observation": remarque}])], ignore_index=True)
        if col3.button("🌞 Fin sieste"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Fin Sieste", "Heure": datetime.now().strftime("%Y-%m-%d %H:%M"), "observation": remarque}])], ignore_index=True)
        if col4.button("🧷 Change"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Change", "Heure": datetime.now().strftime("%Y-%m-%d %H:%M"), "observation": remarque}])], ignore_index=True)
        if col5.button("🍎 Goûter"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Goûter", "Heure": datetime.now().strftime("%Y-%m-%d %H:%M"), "observation": remarque}])], ignore_index=True)

        save_csv_to_drive(df, fichier_csv)

        st.subheader("📜 Historique du jour")
        try:
            df["Heure"] = pd.to_datetime(df["Heure"], errors="coerce", dayfirst=False)
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
                    "Heure": datetime.now().strftime("%d/%m/%Y %H:%M"),
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
        uploaded_photo = st.file_uploader("Choisir une photo", type=["jpg", "jpeg", "png"])
        if uploaded_photo:
            enfant_folder = os.path.join(dossier_photos, nom)
            os.makedirs(enfant_folder, exist_ok=True)
            photo_path = os.path.join(enfant_folder, uploaded_photo.name)
            with open(photo_path, "wb") as f:
                f.write(uploaded_photo.getbuffer())
            st.success(f"Photo ajoutée pour {nom} 📸")

    # 👉 Partie Parent
    elif role == "Parent":
        enfant = parent_enfants.get(name)
        st.subheader(f"📜 Historique de {enfant}")
        df["Heure"] = pd.to_datetime(df["Heure"], format="%d/%m/%Y %H:%M", errors="coerce")
        df_enfant = df[df["Nom"] == enfant]
        df_presence["Date"] = pd.to_datetime(df_presence["Date"])
        df_now = df_presence[df_presence["Nom"] == enfant]
        dates_disponibles = sorted(df_now["Date"].dt.date.unique(), reverse=True)
        date_selectionnee = st.selectbox("Choisir une date :", dates_disponibles)
        maintenant = datetime.now().time()
        heure_visibilite = time(17, 0)

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
        enfant_folder = os.path.join(dossier_photos, enfant)
        if os.path.exists(enfant_folder):
            photos = os.listdir(enfant_folder)
            if photos:
                for photo in photos:
                    file_path = os.path.join(enfant_folder, photo)
                    with open(file_path, "rb") as f:
                        img_bytes = f.read()
                        st.image(img_bytes, caption=photo, use_container_width=True)
                        st.download_button("📸  Télécharger", img_bytes, file_name=photo)
            else:
                st.info("Aucune photo disponible pour aujourd'hui.")
        else:
            st.info("Aucune photo disponible.")
elif st.session_state.get('authentication_status') is False:
    st.error('Nom d’utilisateur ou mot de passe incorrect')
elif st.session_state.get('authentication_status') is None:
    st.warning('Veuillez entrer vos identifiants')
