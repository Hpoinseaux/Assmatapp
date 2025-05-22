import streamlit as st
import streamlit_authenticator as stauth
from datetime import datetime, time, timedelta
import pandas as pd
import calendar
import xlsxwriter
import os


st.markdown(
    """
    <style>
        .stApp {
            background-image: url('https://images.pexels.com/photos/6692943/pexels-photo-6692943.jpeg?cs=srgb&dl=pexels-tara-winstead-6692943.jpg&fm=jpg&_gl=1*qd8whx*_ga*MTMyODI1NjkxMC4xNzQ0NTY5NDIy*_ga_8JE65Q40S6*MTc0NDU2OTQyMS4xLjEuMTc0NDU3MDgwMC4wLjAuMA');
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

credentials = {
    "usernames": {
        "nounou": {"name": "Nounou", "password": "nounoupassword"},
        "parent_caly": {"name": "Caly", "password": "131224"},
        "parent_nate": {"name": "Nate", "password": "010124"}
    },
}

parent_enfants = {"Caly": "Caly", "Nate": "Nate"}

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

    fichier = "suivi.csv"
    if os.path.exists(fichier):
        df = pd.read_csv(fichier)
    else:
        df = pd.DataFrame(columns=["Nom", "Activité", "Heure", "observation"])

    fichier_presence = "presences.csv"
    if os.path.exists(fichier_presence):
        df_presence = pd.read_csv(fichier_presence)
    else:
        df_presence = pd.DataFrame(columns=["Nom", "Date", "Arrivée", "Départ", "Durée"])

    if role == "Nounou":
        nom = st.selectbox("Choisir l'enfant ⬇", ["Caly", "Nate"])
        aujourdhui = datetime.now().date()

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
            df_presence.to_csv(fichier_presence, index=False)
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
                df_presence.to_csv(fichier_presence, index=False)
                st.success(f"Départ enregistré à {heure_depart}")
            else:
                st.warning("Aucune heure d'arrivée trouvée pour aujourd'hui.")

        remarque = st.text_input("Observation", key="repas_remarque")
        col1, col2, col3, col4, col5 = st.columns(5)
        if col1.button("🍲 Repas"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Repas", "Heure": datetime.now(), "observation": remarque}])], ignore_index=True)
        if col2.button("📄 Début sieste"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Début Sieste", "Heure": datetime.now(), "observation": remarque}])], ignore_index=True)
        if col3.button("🌞 Fin sieste"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Fin Sieste", "Heure": datetime.now(), "observation": remarque}])], ignore_index=True)
        if col4.button("🧷 Change"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Change", "Heure": datetime.now(), "observation": remarque}])], ignore_index=True)
        if col5.button("🍎 Goûter"):
            df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Activité": "Goûter", "Heure": datetime.now(), "observation": remarque}])], ignore_index=True)

        df.to_csv(fichier, index=False)

        st.subheader("📜 Historique du jour")
        df["Heure"] = pd.to_datetime(df["Heure"])
        df["Heure"] = df["Heure"].dt.strftime("%d/%m/%Y %H:%M")
        st.dataframe(df.sort_values(by="Heure", ascending=False))

        st.subheader("🗘️ Besoins de la journée")
        besoins = st.text_area("Écrire un besoin à signaler aux parents")
        if st.button("✅ Enregistrer le besoin"):
            if besoins.strip() != "":
                df = pd.concat([df, pd.DataFrame([{
                    "Nom": nom,
                    "Activité": "Besoins",
                    "Heure": datetime.now().strftime("%m/%d/%Y %H:%M"),
                    "observation": besoins
                }])], ignore_index=True)
                df.to_csv(fichier, index=False)
                st.success("Besoin enregistré avec succès ✅")
            else:
                st.warning("Le champ de besoin est vide.")

        st.subheader("📄 Export des heures mensuelles")
        mois = st.selectbox("Choisir un mois", list(range(1, 13)), format_func=lambda x: calendar.month_name[x])
        annee = st.selectbox("Choisir une année", list(range(2025, datetime.now().year + 1)))

        if st.button("📦 Générer le fichier Excel du mois"):
            if os.path.exists(fichier_presence):
                df_presence = pd.read_csv(fichier_presence)
                df_presence["Date"] = pd.to_datetime(df_presence["Date"])
                df_presence["Durée"] = pd.to_timedelta(df_presence["Durée"], errors="coerce")
                df_presence["Durée_excel"] = df_presence["Durée"].dt.total_seconds() / 86400
                filtre = (df_presence["Date"].dt.month == mois) & (df_presence["Date"].dt.year == annee)
                df_mois = df_presence[filtre].copy()
                df_mois["Durée"] = pd.to_timedelta(df_mois["Durée"])
                df_mois["Durée_excel"] = df_mois["Durée"].dt.total_seconds() / 86400 
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

                            # Appliquer le format de durée à la colonne "Durée"
                            worksheet.set_column(3, 3, 12, format_duree)

                            # Ligne de total (une en dessous des données + en-tête)
                            total_row = len(feuille) + 1  # +1 pour l'en-tête
                            worksheet.write(total_row, 2, "Total")
                            worksheet.write_formula(total_row, 3, f'=SUM(D2:D{total_row})', format_duree)

                    st.success(f"Fichier Excel généré : {nom_fichier}")
                    with open(nom_fichier, "rb") as f:
                        st.download_button(label="📅 Télécharger le fichier", data=f, file_name=nom_fichier, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                else:
                    st.warning("Aucune donnée pour ce mois.")
            else:
                st.error("Le fichier de présence n'existe pas encore.")

        st.subheader("📷 Ajouter une photo pour l'enfant")
        uploaded_photo = st.file_uploader("Choisir une photo", type=["jpg", "jpeg", "png"])
        if uploaded_photo is not None:
            enfant_folder = os.path.join("photos", nom)
            os.makedirs(enfant_folder, exist_ok=True)
            photo_path = os.path.join(enfant_folder, uploaded_photo.name)
            with open(photo_path, "wb") as f:
                f.write(uploaded_photo.getbuffer())
            st.success(f"Photo ajoutée pour {nom} 📸")

    elif role == "Parent":
        enfant = parent_enfants.get(name)
        st.subheader(f"📜 Historique de {enfant}")
        df["Heure"] = pd.to_datetime(df["Heure"])
        df_enfant = df[df["Nom"] == enfant]
        df_presence["Date"] = pd.to_datetime(df_presence["Date"])
        df_now = df_presence[df_presence["Nom"] == enfant]
        dates_disponibles = sorted(df_now["Date"].dt.date.unique(), reverse=True)
        date_selectionnee = st.selectbox("Choisir une date :", dates_disponibles)
        maintenant = datetime.now().time()
        heure_visibilite = time(12, 0)

        if maintenant >= heure_visibilite:
            df_presence["Date"] = pd.to_datetime(df_presence["Date"]).dt.date
            df_pres = df_presence[(df_presence["Nom"] == enfant) & (df_presence["Date"] == date_selectionnee)]
            if not df_pres.empty:
                st.subheader(f"⏰ Présences du {date_selectionnee.strftime('%d/%m/%Y')}")
                st.dataframe(df_pres[["Arrivée", "Départ", "Durée"]])
            else:
                st.info("Aucune donnée de présence pour la date sélectionnée.")

            if date_selectionnee == datetime.now().date() and datetime.now().time() < heure_visibilite:
                st.warning("⌛ Les informations d’aujourd’hui seront visibles à partir de 17h.")
            else:
                df_jour = df_enfant[df_enfant["Heure"].dt.date == date_selectionnee]
                df_jour["Heure"] = df_jour["Heure"].dt.strftime("%H:%M")
                st.write(f"🗓️ Activités du {date_selectionnee.strftime('%d/%m/%Y')}")
                st.dataframe(df_jour[df_jour["Activité"] != "Besoins"][["Activité", "Heure", "observation"]].sort_values(by="Heure", ascending=False))

                besoins_du_jour = df_jour[df_jour["Activité"] == "Besoins"]
                if not besoins_du_jour.empty:
                    st.warning("🔔 Besoins pour les prochains jours :")
                    for _, row in besoins_du_jour.iterrows():
                        st.markdown(f"➡️  **{row['observation']}**")

        st.subheader(f"📸 Photos de {enfant}")
        enfant_folder = os.path.join("photos", enfant)
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
    st.error('Username/password is incorrect')
elif st.session_state.get('authentication_status') is None:
    st.warning('Please enter your username and password')