from typing import Any


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