import streamlit as st
import pandas as pd
import plotly.express as px
import boto3
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sqlalchemy
from sqlalchemy import create_engine, text
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error

# -----------------------
# Athena Query Function
# -----------------------
@st.cache_data(ttl=3600)
def run_athena_query(hour, query: str, database: str, s3_output: str) -> pd.DataFrame:
    athena_client = boto3.client('athena', region_name="us-east-1")

    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': s3_output}
    )

    query_execution_id = response['QueryExecutionId']
    state = 'RUNNING'

    while state in ['RUNNING', 'QUEUED']:
        response = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        state = response['QueryExecution']['Status']['State']
        if state in ['RUNNING', 'QUEUED']:
            time.sleep(1)

    if state != 'SUCCEEDED':
        reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        raise Exception(f"Athena query failed: {state} - {reason}")

    results = []
    columns = []
    next_token = None
    first_page = True

    while True:
        if next_token:
            result_set = athena_client.get_query_results(QueryExecutionId=query_execution_id, NextToken=next_token)
        else:
            result_set = athena_client.get_query_results(QueryExecutionId=query_execution_id)

        if first_page:
            columns = [col['Label'] for col in result_set['ResultSet']['ResultSetMetadata']['ColumnInfo']]
            first_page = False

        rows = result_set['ResultSet']['Rows']
        if next_token is None:
            rows = rows[1:]

        for row in rows:
            results.append([field.get('VarCharValue', '') for field in row['Data']])

        next_token = result_set.get('NextToken')
        if not next_token:
            break

    df = pd.DataFrame(results, columns=columns)

    for col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col])
        except:
            try:
                df[col] = pd.to_numeric(df[col])
            except:
                pass

    return df

# -----------------------
# RDS Query Function (cached)
# -----------------------
@st.cache_data(ttl=3600)
def run_rds_queries(location_id, start_str, end_str):
    rds_engine = create_engine("postgresql+psycopg2://postgres:#99Covprp8@postgres.caz82yys229h.us-east-1.rds.amazonaws.com/postgres")

    with rds_engine.connect() as conn:
        actual_sql = text("""
            SELECT pickup_hour, rides
            FROM taxi_rides
            WHERE pickup_location_id = :loc
            AND pickup_hour BETWEEN :start AND :end
            ORDER BY pickup_hour;
        """)
        predicted_sql = text("""
            SELECT prediction_datetime, predicted_rides
            FROM predicted_rides
            WHERE location_id = :loc
            AND prediction_datetime BETWEEN :start AND :end
            ORDER BY prediction_datetime;
        """)

        actual_df_rds = pd.read_sql(actual_sql, conn, params={
            'loc': location_id,
            'start': start_str,
            'end': end_str
        })

        predicted_df_rds = pd.read_sql(predicted_sql, conn, params={
            'loc': location_id,
            'start': start_str,
            'end': end_str
        })

    # Convert to datetime
    actual_df_rds['pickup_hour'] = pd.to_datetime(actual_df_rds['pickup_hour'])
    predicted_df_rds['prediction_datetime'] = pd.to_datetime(predicted_df_rds['prediction_datetime'])

    return actual_df_rds, predicted_df_rds

# -----------------------
# Streamlit App
# -----------------------
st.title("NYC Taxi Rides Forecast")

# Select locations
location_names = {
    43: "Grand Central",
    60: "Lincoln Square East",
    89: "Midtown Center"
}

selected_location = st.selectbox("Select a pickup location:", options=list(location_names.keys()), format_func=lambda x: f"{x} - {location_names[x]}")

# Tabs
tab1, tab2 = st.tabs(["Athena", "RDS"])

# Setup time window
est = ZoneInfo("America/New_York")
now_ny = datetime.now(tz=est)
end_date = now_ny - timedelta(days=358)
start_date = now_ny - timedelta(days=365)
start_rounded = start_date.replace(minute=0, second=0, microsecond=0)
end_rounded = (end_date + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
start_str = start_rounded.strftime("%Y-%m-%d %H:%M:%S")
end_str = end_rounded.strftime("%Y-%m-%d %H:%M:%S")

# -----------------------
# Tab 1: Athena
# -----------------------
with tab1:
    s3_output = 's3://saivigne-etl-d6378f06-3f84-4475-b4b7-cd15f148c55b/athena/'

    actual_query = f"""
    SELECT DISTINCT pickup_hour, rides
    FROM glue_transformed
    WHERE pickup_location_id = {selected_location}
    AND pickup_hour BETWEEN '{start_str}' AND '{end_str}'
    ORDER BY pickup_hour;
    """

    predicted_query = f"""
    SELECT DISTINCT prediction_datetime, predicted_rides
    FROM model_lightgbm
    WHERE location_id = '{selected_location}'
    AND prediction_datetime BETWEEN '{start_str}' AND '{end_str}'
    ORDER BY prediction_datetime;
    """

    try:
        actual_df = run_athena_query(now_ny.hour, actual_query, 'etl_taxi_transformed', s3_output)
        predicted_df = run_athena_query(now_ny.hour, predicted_query, 'lightbgm_database', s3_output)

        merged_df = pd.merge(actual_df, predicted_df, left_on='pickup_hour', right_on='prediction_datetime')
        mae = mean_absolute_error(merged_df['rides'], merged_df['predicted_rides'])
        mape = mean_absolute_percentage_error(merged_df['rides'], merged_df['predicted_rides'])

        st.metric("MAE", f"{mae:.2f}")
        st.metric("MAPE", f"{mape*100:.2f}%")

        fig = px.line()
        fig.add_scatter(x=merged_df['pickup_hour'], y=merged_df['rides'], name='Actual')
        fig.add_scatter(x=merged_df['prediction_datetime'], y=merged_df['predicted_rides'], name='Predicted')
        fig.update_layout(title=f"Athena - Location {selected_location} ({location_names[selected_location]})",
                          xaxis_title="Time", yaxis_title="Rides")
        st.plotly_chart(fig)
    except Exception as e:
        st.error(f"Athena Error: {e}")

# -----------------------
# Tab 2: RDS
# -----------------------
with tab2:
    try:
        actual_df_rds, predicted_df_rds = run_rds_queries(selected_location, start_str, end_str)

        merged_df_rds = pd.merge(
            actual_df_rds,
            predicted_df_rds,
            left_on='pickup_hour',
            right_on='prediction_datetime'
        )

        mae_rds = mean_absolute_error(merged_df_rds['rides'], merged_df_rds['predicted_rides'])
        mape_rds = mean_absolute_percentage_error(merged_df_rds['rides'], merged_df_rds['predicted_rides'])

        st.metric("MAE (RDS)", f"{mae_rds:.2f}")
        st.metric("MAPE (RDS)", f"{mape_rds*100:.2f}%")

        fig_rds = px.line()
        fig_rds.add_scatter(x=merged_df_rds['pickup_hour'], y=merged_df_rds['rides'], name='Actual')
        fig_rds.add_scatter(x=merged_df_rds['prediction_datetime'], y=merged_df_rds['predicted_rides'], name='Predicted')
        fig_rds.update_layout(title=f"RDS - Location {selected_location} ({location_names[selected_location]})",
                              xaxis_title="Time", yaxis_title="Rides")
        st.plotly_chart(fig_rds)
    except Exception as e:
        st.error(f"RDS Error: {e}")
