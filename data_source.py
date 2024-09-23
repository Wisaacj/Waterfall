import re
import warnings
import pandas as pd
import sqlalchemy
import utils

from pathlib import Path
from decouple import config
from sqlalchemy import Engine

# CSV Files
DATA_DIR = Path("data")
LOANS_CSV = DATA_DIR / "loan_uk_20240909.csv"
DEALS_CSV = DATA_DIR / "deal_uk_20240911.csv"
TRANCHES_CSV = DATA_DIR / "tranche_uk_20240911.csv"

# DB Connections
DIALECT = 'oracle'
SQL_DRIVER = 'cx_oracle'
USERNAME = config('US_ORACLE_PROD_USERNAME')
PASSWORD = config('US_ORACLE_PROD_PASSWORD')
HOST = config('US_ORACLE_PROD_HOST')
PORT = config('US_ORACLE_PROD_PORT')
SERVICE = 'PLI'
ENGINE_PATH_WITH_AUTH = f"{DIALECT}+{SQL_DRIVER}://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{SERVICE}"
US_ORACLE_CONNECTION_PROD = sqlalchemy.create_engine(ENGINE_PATH_WITH_AUTH)

# Default Oracle Tables
ORACLE_CURVES = "FO_SEC.CF_VECTOR_ITX_RATES"


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:

    def to_snake_case(name: str) -> str:
        # Remove special characters.
        name = re.sub(r'[^\w\s]', '', name)
        # Convert to lowercase and replace spaces with underscores.
        name = re.sub(r'\s+', '_', name.strip().lower())
        # Remove consecutive underscores.
        name = re.sub(r'_+', '_', name)
        return name
    
    # Create a dictionary to map old column names to new snake_case names.
    column_mapping = {col: to_snake_case(col) for col in df.columns}
    # Rename the columns using the mapping
    df = df.rename(columns=column_mapping)

    return df


def load_deal_data(deal_id: str):
    with warnings.catch_warnings(action='ignore'):
        deals = pd.read_csv(DEALS_CSV)
        loans = pd.read_csv(LOANS_CSV)
        tranches = pd.read_csv(TRANCHES_CSV)

    # Clean the dataframes
    deals = clean_dataframe(deals)
    loans = clean_dataframe(loans)
    tranches = clean_dataframe(tranches)

    # Filter for the relevant deal.
    deals = deals[deals['deal_id'] == deal_id]
    loans = loans[loans['dealid'] == deal_id]
    tranches = tranches[tranches['deal_id'] == deal_id]

    # Ignore equity assets.
    loans = loans[loans['type'] != 'Equity']
    # Fill NaNs.
    tranches.fillna({'margin': 0}, inplace=True)
    # Convert `deals` to a series.
    deal = deals.iloc[0]

    return deal, loans, tranches


def load_loan_data(deal_id: str) -> pd.DataFrame:
    loans = pd.read_csv(LOANS_CSV, low_memory=False)

    # Clean dataframe
    loans = clean_dataframe(loans)
    # Filter for the relevant deal
    loans = loans[loans['dealid'] == deal_id]
    # Ignore equity assets
    loans = loans[loans['type'] != 'Equity']

    return loans


def load_latest_forward_curves(
        forward_curves_table: str = ORACLE_CURVES, 
        us_oracle_db: Engine = US_ORACLE_CONNECTION_PROD, 
        custom_indices: list[str] = None
    ) -> pd.DataFrame:
    default_indices = ['EURIBOR_1MO', 'EURIBOR_3MO', 'EURIBOR_6MO']
    indices = utils.format_list_to_sql_string(custom_indices or default_indices)
    
    query = f"""
    SELECT 
        value_dt,
        key AS curve,
        val as rate
    FROM {forward_curves_table}
    WHERE 
        key IN ({indices})
        AND type = 'fwdrate'
        AND TRUNC(create_dt) = (
            SELECT MAX(TRUNC(create_dt)) 
            FROM {forward_curves_table} 
            WHERE type='fwdrate'
        )
        AND TRUNC(create_dt) IN (
            SELECT TRUNC(create_dt)
            FROM {forward_curves_table} 
            WHERE type = 'fwdrate'
            GROUP BY TRUNC(create_dt)
            HAVING COUNT(DISTINCT CASE WHEN key = 'EURIBOR_3MO' THEN 1 END) > 0
               AND COUNT(DISTINCT CASE WHEN key = 'SOFR_3MO' THEN 1 END) > 0
               AND COUNT(DISTINCT CASE WHEN key = 'EURIBOR_1MO' THEN 1 END) > 0
               AND COUNT(DISTINCT CASE WHEN key = 'EURIBOR_6MO' THEN 1 END) > 0
        )
    """
    
    curves = pd.read_sql(query, us_oracle_db)
    
    curves_split = curves['rate'].str.split(' ', expand=True)
    future_dates = [
        (curves['value_dt'].iloc[0] + pd.DateOffset(months=i + 1)).strftime('%Y-%m-%d')
        for i in range(curves_split.shape[1])
    ]
    
    curves_split.columns = future_dates
    df_combined = pd.concat([curves, curves_split], axis=1).drop(columns=['rate'])
    
    df_melted = df_combined.melt(
        id_vars=['curve', 'value_dt'], 
        var_name='future_date', 
        value_name='value'
    )
    
    df_melted = df_melted.dropna(subset=['value_dt'])
    df_melted = df_melted[df_melted.value != '']
    df_melted['value'] = df_melted['value'].astype(float)
    
    df_pivoted = df_melted.pivot_table(
        index='future_date', 
        columns='curve', 
        values='value'
    )
    
    df_pivoted = df_pivoted.sort_index().reset_index()
    df_pivoted = df_pivoted.rename(columns={'future_date': 'reporting_date'})
    
    return df_pivoted