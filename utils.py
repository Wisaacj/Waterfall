from typing import Any
from datetime import date
from pandas import Timestamp
from dateutil import parser


def format_list_to_sql_string(items: list[Any] | Any, sql_type: str = 'MsSQL') -> str:
    """
    Convert a list of items to a comma-delimited string for SQL queries.

    This function takes a list of items and formats them into a string
    suitable for use in SQL IN clauses. It handles both MsSQL and MySQL
    syntax.

    :param items: A single item or a list of items to be formatted.
    :param sql_type: The SQL dialect to use. 'MsSQL' uses single quotes,
                     while 'MySQL' uses backticks. Defaults to 'MsSQL'.
    :return: A formatted string ready for use in SQL queries.

    :raises ValueError: If an unsupported sql_type is provided.
    """
    if not isinstance(items, list):
        items = [items]

    items = [str(item) for item in items]

    if sql_type == 'MsSQL':
        delimiter = "'"
    elif sql_type == 'MySQL':
        delimiter = "`"
    else:
        raise ValueError("Unsupported sql_type. Use 'MsSQL' or 'MySQL'.")

    formatted_items = f"{delimiter},{delimiter}".join(items)
    return f"{delimiter}{formatted_items}{delimiter}"


def parse_date(date_value: str | date | Timestamp) -> date:
    """
    Parse various date formats into a standard date object.

    This function takes a date value in different formats (string, date, or Timestamp)
    and converts it into a standard date object. It handles string parsing with
    day-first format, Timestamp conversion, and direct date passing.

    :param date_value: The date value to be parsed. Can be a string, date object, or Timestamp.
    :return: A date object representing the parsed date.

    :raises ValueError: If an unsupported date type is provided.
    """
    if isinstance(date_value, str):
        return parser.parse(date_value, dayfirst=True).date()
    elif isinstance(date_value, Timestamp):
        return date_value.date()
    elif isinstance(date_value, date):
        return date_value
    else:
        raise ValueError(f"Unsupported date type: {type(date_value)}")
