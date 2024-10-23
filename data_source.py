import re
import utils
import warnings
import functools
import sqlalchemy
import pandas as pd

from pathlib import Path
from datetime import date
from decouple import config
from sqlalchemy import Engine
from dataclasses import dataclass
from urllib.parse import quote_plus


# CSV Files
DATA_DIR = Path("data")
LOANS_CSV = DATA_DIR / "Loan-UK-2024-10-21.csv"
DEALS_CSV = DATA_DIR / "Deal-UK-2024-10-21.csv"
TRANCHES_CSV = DATA_DIR / "Tranche-UK-2024-10-21.csv"
REPO_REPORT_XLSX = DATA_DIR / "RepoLight - 07-10-2024.xlsx"


@dataclass
class EnginePath:
    dialect: str
    sql_driver: str
    username: str
    password: str
    host: str
    port: str
    service: str

    def format(self) -> str:
        return f"{self.dialect}+{self.sql_driver}://{self.username}:{self.password}@{self.host}:{self.port}/{self.service}"


# DB Connections
US_ORACLE_ENGINE_PATH = EnginePath(
    dialect='oracle',
    sql_driver='cx_oracle',
    username=quote_plus(config('US_ORACLE_PROD_USERNAME')),
    password=quote_plus(config('US_ORACLE_PROD_PASSWORD')),
    host=config('US_ORACLE_PROD_HOST'),
    port=config('US_ORACLE_PROD_PORT'),
    service='PLI'
).format()
UK_ORACLE_ENGINE_PATH = EnginePath(
    dialect='oracle',
    sql_driver='cx_oracle',
    username=quote_plus(config('UK_ORACLE_PROD_USERNAME')),
    password=quote_plus(config('UK_ORACLE_PROD_PASSWORD')),
    host=config('UK_ORACLE_PROD_HOST'),
    port=config('UK_ORACLE_PROD_PORT'),
    service='PLI'
).format()
EU_CREDIT_PROD_ENGINE_PATH = EnginePath(
    dialect='mysql',
    sql_driver='pymysql',
    username=quote_plus(config('EU_CREDIT_PROD_USERNAME')),
    password=quote_plus(config('EU_CREDIT_PROD_PASSWORD')),
    host=config('EU_CREDIT_PROD_HOST'),
    port=config('EU_CREDIT_PROD_PORT'),
    service='eu_credit_reporting'
).format()

US_ORACLE_CONNECTION_PROD = sqlalchemy.create_engine(US_ORACLE_ENGINE_PATH)
UK_ORACLE_CONNECTION_PROD = sqlalchemy.create_engine(UK_ORACLE_ENGINE_PATH)
EU_CREDIT_CONNECTION_PROD = sqlalchemy.create_engine(EU_CREDIT_PROD_ENGINE_PATH)

# Tables
ORACLE_CURVES = "FO_SEC.CF_VECTOR_ITX_RATES"
ORACLE_UK_DEAL_HISTORY = "FO_SEC_LN.DEAL_HISTORY"
ORACLE_UK_TRANCHE_HISTORY = "FO_SEC_LN.TRANCHE_HISTORY"
ORACLE_UK_CLO_ASSETS_DATA = "FO_SEC_LN.clo_deal_dtl"


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:

    def to_snake_case(name: str) -> str:
        if type(name) == str:
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
    # Drop rows & columns full of NaNs.
    df = df.dropna(how='all', axis=1)
    df = df.dropna(how='all', axis=0)

    return df


def tidy_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tidies the column names of a dataframe by replacing underscores with spaces
    and capitalising.
    """
    df.columns = df.columns.str.replace('_', ' ').str.upper()

    return df


def get_latest_reporting_date(table: str, database: Engine) -> date:
    query = f"""
        SELECT MAX(deal_hist_date) as latest_date
        FROM {table}
    """

    df = pd.read_sql(query, database, parse_dates=["latest_date"])
    latest_date = df['latest_date'].iloc[0].date()

    return latest_date


def load_deal(deal_id: str):
    """
    Loads a single deal from the EU CLO universe.
    """
    database = US_ORACLE_CONNECTION_PROD
    report_date = get_latest_reporting_date(ORACLE_UK_DEAL_HISTORY, database)

    deal_query = f"""
    SELECT *
    FROM {ORACLE_UK_DEAL_HISTORY}
    WHERE 
        TRUNC(deal_hist_date) = TO_DATE('{report_date}', 'YYYY-MM-DD')
        AND deal_id = '{deal_id}'
    """
    tranches_query = f"""
    SELECT *
    FROM {ORACLE_UK_TRANCHE_HISTORY}
    WHERE 
        TRUNC(tranche_hist_date) = TO_DATE('{report_date}', 'YYYY-MM-DD')
        AND deal_id = '{deal_id}'
    """
    loans_query = f"""
    SELECT *
    FROM {ORACLE_UK_CLO_ASSETS_DATA}
    WHERE 
        TRUNC(create_dt) = TO_DATE('{report_date}', 'YYYY-MM-DD')
        AND deal_id = '{deal_id}'
    """
    
    deal = pd.read_sql(deal_query, database)
    loans = pd.read_sql(loans_query, database)
    tranches = pd.read_sql(tranches_query, database)

    # Clean the dataframes
    deal = clean_dataframe(deal)
    loans = clean_dataframe(loans)
    tranches = clean_dataframe(tranches)

    # Convert deal to a series.
    deal = deal.iloc[0]

    return deal, loans, tranches


@functools.lru_cache(maxsize=1)
def load_universe(
        loans_csv: Path = LOANS_CSV,
        deals_csv: Path = DEALS_CSV,
        tranches_csv: Path = TRANCHES_CSV
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Loads the latest data on the UK CLO universe (deals, loans, and tranches) from CSV files.
    """
    with warnings.catch_warnings(action='ignore'):
        loans = pd.read_csv(loans_csv, low_memory=False)
        deals = pd.read_csv(deals_csv)
        tranches = pd.read_csv(tranches_csv)

    # Clean the dataframes
    loans = clean_dataframe(loans)
    deals = clean_dataframe(deals)
    tranches = clean_dataframe(tranches)

    return deals, loans, tranches


def load_deal_from_disk(deal_id: str):
    deals, loans, tranches = load_universe()

    # Filter for the relevant deal.
    deals = deals[deals['deal_id'] == deal_id]
    loans = loans[loans['dealid'] == deal_id]
    tranches = tranches[tranches['deal_id'] == deal_id]

    # Ignore equity assets.
    loans = loans[loans['type'] != 'Equity']
    # Fill NaNs.
    with warnings.catch_warnings(action='ignore'):
        tranches.fillna({'margin': 0}, inplace=True)
    # Convert `deals` to a series.
    deal = deals.iloc[0]

    return deal, loans, tranches


@functools.lru_cache(maxsize=1)
def load_napier_holdings(repo_report_xlsx: Path = REPO_REPORT_XLSX) -> pd.DataFrame:
    """
    Loads Napier Park's asset holdings from our internal repo report.
    """
    with warnings.catch_warnings(action='ignore'):
        repo_report = pd.read_excel(repo_report_xlsx)

    # Clean the dataframe
    repo_report = clean_dataframe(repo_report)

    return repo_report


def load_deal_holdings(deal_id: str) -> pd.DataFrame:
    """
    Loads Napier Park's asset holdings for a given deal.

    :param deal_id: The ID of the deal to load holdings for.
    :return: A dataframe of Napier Park's asset holdings for the given deal.
    """
    repo_report = load_napier_holdings()
    repo_report = repo_report[repo_report['intex_id'] == deal_id]
    return repo_report


@functools.lru_cache(maxsize=1)
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


@functools.lru_cache(maxsize=1)
def load_forward_curves(
        as_of_date: date = date.today(),
        forward_curves_table: str = ORACLE_CURVES, 
        us_oracle_db: Engine = US_ORACLE_CONNECTION_PROD, 
        custom_indices: list[str] = None
    ) -> pd.DataFrame:
    default_indices = ['EURIBOR_1MO', 'EURIBOR_3MO', 'EURIBOR_6MO']
    indices = utils.format_list_to_sql_string(custom_indices or default_indices)

    query = f"""
    WITH ranked_curves AS (
        SELECT 
            value_dt,
            key AS curve,
            val as rate,
            create_dt,
            ROW_NUMBER() OVER (PARTITION BY key ORDER BY create_dt DESC) as rn
        FROM {forward_curves_table}
        WHERE 
            key IN ({indices})
            AND type = 'fwdrate'
            AND TRUNC(create_dt) <= TO_DATE('{as_of_date.strftime('%Y-%m-%d')}', 'YYYY-MM-DD')
    )
    SELECT value_dt, curve, rate
    FROM ranked_curves
    WHERE rn = 1
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
