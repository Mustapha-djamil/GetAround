from helper import get_checkout_state,get_previous_rental_delay,get_impact_of_previous_rental_delay,keep_only_late_checkins_canceled,keep_only_ended_rentals,detect_outliers,apply_threshold
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import numpy as np
import math
import os
import streamlit as st
import uvicorn
from pydantic import BaseModel
from typing import Literal, List, Union
from fastapi import FastAPI, File, UploadFile, Request
from joblib import dump, load
import json



if __name__ == '__main__':
    # Chemin absolu du fichier de données
    current_dir = os.path.dirname(os.path.abspath(__file__))
    DATA_PATH = os.path.join(current_dir, 'data', 'get_around_delay_analysis.xlsx')

    # Vérification si le fichier existe
    if not os.path.exists(DATA_PATH):
        st.error(f"The file at {DATA_PATH} was not found.")
        raise FileNotFoundError(f"The file at {DATA_PATH} was not found.")

    @st.cache_data
    def load_data(nrows=None):
        data = pd.read_excel(DATA_PATH, nrows=nrows)
        return data

    source = load_data(None)
    df = source.copy()

    df['state'] = df.apply(get_checkout_state, axis = 1)
    df['delay_at_checkout_in_minutes'] = df['delay_at_checkout_in_minutes'].apply(lambda x: 0 if x < 0 else x)
    df['previous_rental_checkout_delay_in_minutes'] = df.apply(get_previous_rental_delay, args = [df], axis = 1)
    df['checkin_delay_in_minutes'] = df['previous_rental_checkout_delay_in_minutes'] - df['time_delta_with_previous_rental_in_minutes']
    df['checkin_delay_in_minutes'] = df['checkin_delay_in_minutes'].apply(lambda x: 0 if x < 0 else x)
    df['impact_of_previous_rental_delay'] = df.apply(get_impact_of_previous_rental_delay, axis = 1)
    df = df.sort_values('rental_id')
    late_checkouts_df = df[df['state'] == 'Late checkout']
    previous_rental_delay_df = df[df['previous_rental_checkout_delay_in_minutes'] > 0]
    late_checkins_df = df[df['checkin_delay_in_minutes'] > 0]
    late_checkins_canceled_df = keep_only_late_checkins_canceled(df)
    nb_rentals = len(df)
    nb_ended_rentals = len(keep_only_ended_rentals(df))
    nb_canceled_rentals = len(df[df['state'] == 'Canceled'])
    nb_late_checkouts = len(late_checkouts_df)
    late_checkouts_upper_fence = detect_outliers(late_checkouts_df, 'delay_at_checkout_in_minutes')['upper_fence']
    nb_late_checkins = len(late_checkins_df)
    late_checkins_upper_fence = detect_outliers(late_checkins_df, 'checkin_delay_in_minutes')['upper_fence']
    late_checkins_canceled_upper_fence = detect_outliers(late_checkins_canceled_df, 'checkin_delay_in_minutes')['upper_fence']
    nb_late_checkins_cancelations = len(late_checkins_canceled_df)


    st.header("Getaround dashboard 🚗")
    ### App
    df_copy =df.copy()
    st.title("Get Around's new feature study ")
    st.subheader('Introduction 📗')
    st.markdown("Welcome to our project analysis, where we delve into the implications of a newly introduced feature in the Get Around application. " \
            "This feature, 'Handling of Departure Delays', is designed to enhance user experience by not displaying a future location if it's too close to the previous one due to a delay in check-out by the previous user.  \n" \
            "Our focus will be on two key parameters that define the functionality of this feature:  \n" \
            "- Threshold: We will also examine the minimum time threshold between two rentals. This is crucial to ensure the feature works optimally, balancing between user convenience and operational efficiency. \n" \
            "- Scope: We will explore whether this feature will be implemented for mobile check-ins, or if it will be exclusive to connected check-ins. Understanding the scope will help us determine the breadth of its impact on users. \n")
    st.subheader("Database distribution")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(""" All the rentals """)
        fig = px.pie(df_copy,names='checkin_type')
        st.plotly_chart(fig, use_container_width=True)

    # Texte d'explication dans la deuxième colonne
    with col2:
        st.subheader("Explanation")
        st.write("""
        This pie chart shows As part of the analysis of car rental data through the GetAround application, 
        it is essential to understand the distribution of rentals and the different booking methods used by the users.
        This understanding allows us to optimize the services offered and better meet the needs of the customers. \n
        We have 21,310 cases distributed as follows:
        - **Connect:** 20.2%
        - **Mobile:** 79.8% \n
        We note that a large part of the rentals are done through Mobile (thus a physical meeting between the renter and the owner is mandatory).
        """)
    st.subheader("Repartition of data by state")
    col3,col4 = st.columns(2)
    with col3:
        st.markdown("""Distribution of effective rentals """)
        ended_rentals_df = df_copy.loc[df_copy['state'].isin(['On time checkout', 'Late checkout']), :]
        fig2 = px.pie(ended_rentals_df, names='checkin_type')
        st.plotly_chart(fig2, use_container_width=True)
        st.metric("Number of cases : ", len(ended_rentals_df))

    with col4:
        st.markdown("""Distribution of canceled rentals """)
        fig3 = px.pie(df_copy.loc[df_copy['state']=='Canceled',:],names='checkin_type')
        st.plotly_chart(fig3, use_container_width=True)
        st.metric("Number of cases : ", len(df_copy.loc[df_copy['state']=='Canceled',:]))
    st.markdown("""The data shows that effective and canceled bookings are nearly similar across reservation methods. However, a slight difference is noted in canceled bookings: it is notably easier to cancel a reservation through the 'Connect' system, which does not require physical presence.
    This observation suggests that users may find more flexibility and ease in adjusting their travel plans when opting for the 'Connect' mode, while maintaining relative stability in effective bookings regardless of the chosen mode.""")

    st.subheader("Understand what's going on, Understand our problem. Vizualise problematic cases.")

    st.markdown("""Problematic case [between 2 rentals] = delay_at_checkout_in_minutes > time_delta_with_previous_rental_in_minutes""")
        
    data_join = df_copy.merge(df_copy[['rental_id', 'checkin_type', 'delay_at_checkout_in_minutes']], how='inner' , left_on='previous_ended_rental_id', right_on='rental_id' )
    data_join['problematic'] = data_join['time_delta_with_previous_rental_in_minutes'] < data_join['delay_at_checkout_in_minutes_y']
    data_join['problematic'] = data_join['problematic'].apply(lambda v : 'problematic case' if v==True else 'non problematic case')
    data_join_m = data_join.loc[data_join['checkin_type_x']=='mobile',:]
    data_join_c = data_join.loc[data_join['checkin_type_x']=='connect',:]
    print(data_join.columns)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(""" All the rentals""")
        st.write("Number potential problematic cases : "+str(len(data_join)))
        fig = px.pie(data_join,names='problematic')
        fig.update_traces(sort=False) 
        st.plotly_chart(fig, use_container_width=True)   
    with col2:
        data = {
            'Type de check-in': ['Mobile Check-in', 'Connect Check-in'],
            'Nombre de cas': [len(data_join_m), len(data_join_c)]
        }
        df_copy = pd.DataFrame(data)
        fig_bar = px.bar(df_copy, x='Type de check-in', y='Nombre de cas', text='Nombre de cas',
                        labels={'Nombre de cas':'Nombre de cas', 'Type de check-in':'Type de check-in'},
                        title='Distribution des cas problématiques')
        fig_bar.update_traces(texttemplate='%{text}', textposition='outside')
        fig_bar.update_layout(uniformtext_minsize=8, uniformtext_mode='hide')
        st.plotly_chart(fig_bar)

    st.subheader('Analysis 🔬')
    st.markdown('<p style="text-align: center;"><span style="font-size:1.5em;">Main metrics of dataset</span></p>', unsafe_allow_html=True)
    main_metrics_cols = st.columns(4)

    with main_metrics_cols[0]:
        col1 = main_metrics_cols[0]
        col1.metric("Total rentals", nb_rentals)

    with main_metrics_cols[1]:
        col2 = main_metrics_cols[1]
        col2.metric("Share of 'Connect' rentals", f"{round(df['checkin_type'].eq('connect').sum() / nb_rentals * 100)}%")
        col3 = main_metrics_cols[2]
        col3.metric("Share of 'Mobile' rentals", f"{round(df['checkin_type'].eq('mobile').sum() / nb_rentals * 100)}%")

    with main_metrics_cols[2]:
        col4 = main_metrics_cols[3]
        col4.metric("Number of cars", df['car_id'].nunique())
    st.write()

    checkouts_metrics_cols = st.columns(4)

    with checkouts_metrics_cols[0]:
        col5 = checkouts_metrics_cols[0]
        st.metric("Outliers checkout delays",f"{round(detect_outliers(df, 'delay_at_checkout_in_minutes')['percent_outliers'])}%")

    with checkouts_metrics_cols[1]:
        col6 = checkouts_metrics_cols[1]
        st.metric("Late > 1h",f"{round(len(late_checkouts_df[late_checkouts_df['delay_at_checkout_in_minutes'] >= 60]) / nb_late_checkouts * 100)}%")
    with checkouts_metrics_cols[2]:
        col7 = checkouts_metrics_cols[2]
        st.metric(
            label = "Cancels due to delays", 
            value=f"{round(nb_late_checkins_cancelations / nb_late_checkins * 100)}%"
        )
    st.markdown('<p style="text-align: center;"><span style="font-size:2em;">Visuals</span></p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        # Impacts of checkout delays on checkin state
        impacts_bar = px.bar(
            previous_rental_delay_df,
            x="impact_of_previous_rental_delay",
            color="impact_of_previous_rental_delay",
            height=500,
            category_orders={"impact_of_previous_rental_delay": ['No impact', 'Late checkin', 'Cancelation', 'No previous rental filled out']},
            title="<b>Impacts of checkout delays on checkin state</b>"
        )

        # Calculer les pourcentages
        total = len(previous_rental_delay_df)
        percentages = previous_rental_delay_df['impact_of_previous_rental_delay'].value_counts(normalize=True).mul(100).round(1)

        # Ajouter les pourcentages au-dessus des barres
        for i, label in enumerate(percentages.index):
            impacts_bar.add_annotation(
                x=label,
                y=previous_rental_delay_df['impact_of_previous_rental_delay'].value_counts()[i],
                text=f"{percentages[label]}%",
                showarrow=False,
                yshift=20
            )

        st.plotly_chart(impacts_bar, use_container_width=True)

    with col2:
        # Rental state
        state_hist = px.histogram(
            df, x="state", color="state",
            height=500,
            category_orders={"state": ['On time checkout', 'Late checkout', 'Canceled', 'Unknown']},
            barmode='group',
            title="<b>Rental state</b>",
            labels={'state':'Rental state'}
        )

        st.plotly_chart(state_hist, use_container_width=True)


    st.markdown(
        """
        <style>
        .stButton button {
            width: 100%;
            height: 50px;
            font-size: 16px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown('**You can visualize here the impacts of applying a minimum delay between consecutive rentals:**')
    with st.form(key='simulation_form'):
        simulation_threshold = st.slider(label='Threshold', min_value=15, max_value=266, step=15)
        simulation_scope = st.selectbox('Scope', ['All', 'Connect', 'Mobile'], key=3)
        submit = st.form_submit_button(label='View abstracts')

    ### Simulation results
    if submit:
        with_threshold_df, nb_ended_rentals_lost, nb_late_checkins_cancelations_avoided = apply_threshold(df, simulation_threshold, simulation_scope)
        previous_rental_delay_with_threshold_df = with_threshold_df[with_threshold_df['previous_rental_checkout_delay_in_minutes'] > 0]

        ##### Influence on business metrics
        st.write("Pour un threshold de "+str(simulation_threshold)+" on obtient une baisse du revenu probable de "+str(round(nb_ended_rentals_lost / nb_ended_rentals * 100, 1))+"%")
        st.write("Mais permet d'éviter un taux d'annulation de "+str(round(nb_late_checkins_cancelations_avoided / nb_late_checkins_cancelations * 100))+"% des locations")   

        st.write('Un seuil de '+str(simulation_threshold)+' a un effet de:')
        no_impact_share = (previous_rental_delay_df['impact_of_previous_rental_delay'].value_counts(normalize=True).get('No impact', 0)*100)-(previous_rental_delay_with_threshold_df['impact_of_previous_rental_delay'].value_counts(normalize=True).get('No impact', 0)*100)
        st.write(f"{round(-no_impact_share,2)}% sur portion des locations qui ne seront pas impacter")

        late_checkin_share = (previous_rental_delay_df['impact_of_previous_rental_delay'].value_counts(normalize=True).get('Late checkin', 0)*100)-(previous_rental_delay_with_threshold_df['impact_of_previous_rental_delay'].value_counts(normalize=True).get('Late checkin', 0)*100)
        st.write(f"{round(-late_checkin_share,2)} % sur portion des locations retardées")

        cancelation_share = (previous_rental_delay_df['impact_of_previous_rental_delay'].value_counts(normalize=True).get('Cancelation', 0)*100)-(previous_rental_delay_with_threshold_df['impact_of_previous_rental_delay'].value_counts(normalize=True).get('Cancelation', 0)*100)
        st.write(f"{round(-cancelation_share,2)} % sur portion des locations retardées")
