# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from io import StringIO

# en haut de ton app.py, après st.title()
tab1, tab2 = st.tabs(["Simulation globale", "Édition détaillée"])

with tab2:

    st.set_page_config(page_title="Simulateur CA & Charges", layout="wide")

    st.title("📊 Simulateur CA & Charges — Prototype")
    st.markdown(
        "Prototype interactif — modifie les pourcentages (global ou par année) pour voir l'impact "
        "sur le chiffre d'affaires et les charges. Exporte le scénario si tu veux le partager."
    )

    # ------------- Fake data generation -------------
    YEARS = list(range(2023, 2029))  # données historiques + quelques années futures
    np.random.seed(42)

    base_ca = np.round(np.linspace(800_000, 1_200_000, len(YEARS)) * (1 + np.random.normal(0, 0.03, len(YEARS))))
    base_charges = np.round(base_ca * np.linspace(0.65, 0.55, len(YEARS)) * (1 + np.random.normal(0, 0.02, len(YEARS))))

    df_base = pd.DataFrame({
        "annee": YEARS,
        "ca": base_ca.astype(float),
        "charges": base_charges.astype(float),
    })
    df_base["marge"] = df_base["ca"] - df_base["charges"]
    df_base["marge_pct"] = df_base["marge"] / df_base["ca"]

    # ------------- UI controls -------------
    st.sidebar.header("Contrôles généraux")
    global_ca_pct = st.sidebar.slider("Variation globale CA (%)", -50, 200, 0, step=1)
    global_charges_pct = st.sidebar.slider("Variation globale Charges (%)", -50, 200, 0, step=1)

    st.sidebar.markdown("---")
    st.sidebar.header("Contrôles par année (si tu veux overrides)")
    use_per_year = st.sidebar.checkbox("Activer variations par année", value=False)

    # prepare per-year inputs (default 0%)
    per_year_ca = {}
    per_year_charges = {}
    if use_per_year:
        st.sidebar.markdown("Pourcentage par année (en %). Laisse 0 si pas de changement.")
        for y in YEARS:
            per_year_ca[y] = st.sidebar.number_input(f"CA {y} (%)", value=0, step=1, format="%d", key=f"ca_{y}")
            per_year_charges[y] = st.sidebar.number_input(f"Charges {y} (%)", value=0, step=1, format="%d", key=f"ch_{y}")
    else:
        # fill with zeros
        for y in YEARS:
            per_year_ca[y] = 0
            per_year_charges[y] = 0

    # Quick presets
    st.sidebar.markdown("---")
    st.sidebar.header("Presets rapides")
    col_p1, col_p2 = st.sidebar.columns(2)
    if col_p1.button("Scenario: Réduction coûts 20%"):
        global_charges_pct = -20
    if col_p2.button("Scenario: +10% CA"):
        global_ca_pct = 10

    # ------------- Compute simulation -------------
    df = df_base.copy()
    df["ca_simu"] = df["ca"] * (1 + global_ca_pct / 100.0)
    df["charges_simu"] = df["charges"] * (1 + global_charges_pct / 100.0)

    # apply per-year overrides if any
    if use_per_year:
        df["ca_simu"] = df.apply(lambda r: r["ca"] * (1 + per_year_ca[int(r["annee"])] / 100.0), axis=1)
        df["charges_simu"] = df.apply(lambda r: r["charges"] * (1 + per_year_charges[int(r["annee"])] / 100.0), axis=1)
        # if both global and per-year are used, multiply effects (global applied then per-year)
        # (Optionnel : choix de logique — ici on prioritise per-year overrides.)
    else:
        pass
        # keep global multipliers already applied

    df["marge_simu"] = df["ca_simu"] - df["charges_simu"]
    df["marge_pct_simu"] = df["marge_simu"] / df["ca_simu"]

    # ------------- Layout & viz -------------
    st.subheader("Courbes : CA & Charges (réel vs simulé)")
    col1, col2 = st.columns([2, 1])

    with col1:
        fig = px.line(
            df.melt(id_vars="annee", value_vars=["ca", "ca_simu"], var_name="serie", value_name="montant"),
            x="annee", y="montant", color="serie",
            title="Chiffre d'affaire : réel vs simulé",
            labels={"montant": "€", "annee": "Année"}
        )
        fig.update_traces(mode="lines+markers")
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.line(
            df.melt(id_vars="annee", value_vars=["charges", "charges_simu"], var_name="serie", value_name="montant"),
            x="annee", y="montant", color="serie",
            title="Charges : réel vs simulé",
            labels={"montant": "€", "annee": "Année"}
        )
        fig2.update_traces(mode="lines+markers")
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.metric("Variation globale CA (%)", f"{global_ca_pct:+}")
        st.metric("Variation globale Charges (%)", f"{global_charges_pct:+}")
        st.markdown("### Résumé (année courante et dernière année)")
        last = df.iloc[-1]
        st.write({
            "Année": int(last["annee"]),
            "CA réel": f"{int(last['ca']):,}".replace(",", " "),
            "CA simulé": f"{int(last['ca_simu']):,}".replace(",", " "),
            "Charges réel": f"{int(last['charges']):,}".replace(",", " "),
            "Charges simulé": f"{int(last['charges_simu']):,}".replace(",", " "),
            "Marge réelle": f"{int(last['marge']):,}".replace(",", " "),
            "Marge simulée": f"{int(last['marge_simu']):,}".replace(",", " "),
            "Marge % simulée": f"{last['marge_pct_simu']*100:.1f} %"
        })

    st.markdown("---")
    st.subheader("Table de données")
    st.dataframe(df.style.format({
        "ca": "{:,.0f}",
        "charges": "{:,.0f}",
        "ca_simu": "{:,.0f}",
        "charges_simu": "{:,.0f}",
        "marge_pct": "{:.1%}",
        "marge_pct_simu": "{:.1%}"
    }), height=300)

    # ------------- Export scenario -------------
    def df_to_csv_bytes(d):
        return d.to_csv(index=False).encode("utf-8")

    csv = df_to_csv_bytes(df[["annee", "ca", "charges", "ca_simu", "charges_simu", "marge_simu", "marge_pct_simu"]])
    st.download_button("⬇️ Exporter le scénario (CSV)", data=csv, file_name="scenario_simulation.csv", mime="text/csv")

    st.markdown(
        "— *Astuce* : pour brancher tes vraies données ClickHouse, remplace la génération de `df_base` "
        "par une requête SQL avec `clickhouse_connect` ou `sqlalchemy` et charge directement le DataFrame."
    )

with tab1:
    st.subheader("Édition par sous-catégorie & mois")

    # Charger le fichier tabulaire préparé
    df = pd.read_csv("bp_forecast_tabulaire.csv", sep=";")
    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")

    # Selecteur de catégorie
    cat_choice = st.selectbox("Choisir la catégorie à modifier", df["categorie"].unique())

    # Filtrer sur la catégorie choisie
    df_filtered = df[df["categorie"] == cat_choice].copy()

    # Table éditable
    edited_df = st.data_editor(
        df_filtered,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "date": st.column_config.DateColumn("Date"),
            "valeur": st.column_config.NumberColumn("Montant (€)", step=100),
        }
    )

    st.markdown("### Visualisation dynamique")

    edited_df["date"] = pd.to_datetime(edited_df["date"], errors="coerce", dayfirst=True)
    edited_df["valeur"] = pd.to_numeric(edited_df["valeur"], errors="coerce")

    # Filtrer CA
    df_ca = edited_df[edited_df["categorie"] == "Chiffre d'affaires"]

    # Agréger proprement
    df_ca_sum = df_ca.groupby("date", as_index=False)["valeur"].sum()

    df_ca_sum["valeur_k"] = (df_ca_sum["valeur"] / 1000).round(0)  # arrondi à l’unité K€
    df_ca_sum["valeur_k"] = (df_ca_sum["valeur"] / 1000).round(0).astype(int)
    df_ca_sum["valeur_label"] = df_ca_sum["valeur_k"].astype(str) + " K€"

    fig = px.line(
    df_ca_sum,
    x="date",
    y="valeur_k",
    title="Chiffre d'affaires (K€)",
    markers=True,
    text="valeur_label"  # affiche la valeur sur chaque point
    )

    # Mise en forme
    fig.update_traces(
    textposition="top center",
    line_shape="spline"  # rend la courbe arrondie/lissée
    )

    fig.update_layout(
    yaxis_title="CA (K€)",
    xaxis_title="Date",
    hovermode="x unified",
    yaxis=dict(showgrid=False),  # enlève les lignes horizontales
    )

    fig.update_traces(
    line_shape="spline",
    textposition="top center",
    textfont=dict(size=12, family="Arial Black"),
    texttemplate="%{text}"
    )

    fig.update_layout(
    yaxis=dict(showgrid=False, title="CA (K€)"),
    xaxis_title="Date",
    hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Bien mettre la date en index pour line_chart
    st.line_chart(df_ca_sum.set_index("date")["valeur_k"])

    # Option d’export
    st.download_button(
        "⬇️ Exporter scénario édité",
        edited_df.to_csv(index=False).encode("utf-8"),
        "scenario_edite.csv",
        "text/csv"
    )