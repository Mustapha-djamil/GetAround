import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import numpy as np
import math

def get_checkout_state(row):
    state = 'Unknown'
    if row['state'] == 'ended':
        if row['delay_at_checkout_in_minutes'] <= 0:
            state = "On time checkout"
        elif row['delay_at_checkout_in_minutes'] > 0:
            state = "Late checkout"
    if row['state'] == 'canceled':
        state = "Canceled"
    return state

def get_previous_rental_delay(row, dataframe):
    delay = np.nan
    if not math.isnan(row['previous_ended_rental_id']):
        delay = dataframe[dataframe['rental_id'] == row['previous_ended_rental_id']]['delay_at_checkout_in_minutes'].values[0]
    return delay

def get_impact_of_previous_rental_delay(row):
    impact = 'No previous rental filled out'
    if not math.isnan(row['checkin_delay_in_minutes']):
        if row['checkin_delay_in_minutes'] > 0:
            if row['state'] == 'Canceled':
                impact = 'Cancelation'
            else:
                impact = 'Late checkin'
        else:
            impact = 'No impact'
    return impact

def keep_only_ended_rentals(dataframe):
    return dataframe[(dataframe['state'] == 'On time checkout') | (dataframe['state'] == 'Late checkout')]

def keep_only_late_checkins_canceled(dataframe):
    return dataframe[(dataframe['checkin_delay_in_minutes'] > 0) & (dataframe['state'] == 'Canceled')]

def apply_threshold(dataframe, threshold, scope):
    if scope == 'All':
        rows_to_drop_df = dataframe[dataframe['time_delta_with_previous_rental_in_minutes'] < threshold]
    elif scope == 'Connect':
        rows_to_drop_df = dataframe[(dataframe['time_delta_with_previous_rental_in_minutes'] < threshold) & (dataframe['checkin_type'] == 'connect')]
    elif scope == 'Mobile':
        rows_to_drop_df = dataframe[(dataframe['time_delta_with_previous_rental_in_minutes'] < threshold) & (dataframe['checkin_type'] == 'mobile')]
    nb_ended_rentals_dropped = len(keep_only_ended_rentals(rows_to_drop_df))
    nb_late_checkins_cancelations_dropped = len(keep_only_late_checkins_canceled(rows_to_drop_df))
    output = (
        dataframe.drop(rows_to_drop_df.index),
        nb_ended_rentals_dropped,
        nb_late_checkins_cancelations_dropped  
    )
    return output

def detect_outliers(dataframe, feature_name):
    q1 = dataframe[feature_name].quantile(0.25)
    q3 = dataframe[feature_name].quantile(0.75)
    interquartile_range = q3 - q1
    upper_fence = math.ceil(q3 + 1.5 * interquartile_range)
    nb_rows = len(dataframe)
    mask = (dataframe[feature_name] <= upper_fence) | (dataframe[feature_name].isna())
    nb_rows_without_outliers = len(dataframe[mask])
    nb_outliers = nb_rows - nb_rows_without_outliers
    percent_outliers = round(nb_outliers / nb_rows * 100)
    output = {
        'upper_fence': upper_fence,
        'percent_outliers': percent_outliers
    }
    return output