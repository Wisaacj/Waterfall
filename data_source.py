import re
import warnings
import pandas as pd

from pathlib import Path

DATA_DIR = Path("data")
LOANS_CSV = DATA_DIR / "loan_uk_20240909.csv"
DEALS_CSV = DATA_DIR / "deal_uk_20240911.csv"
TRANCHES_CSV = DATA_DIR / "tranche_uk_20240911.csv"


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


def load_data(deal_id: str):
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