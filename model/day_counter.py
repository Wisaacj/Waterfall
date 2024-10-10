from datetime import date, datetime
from dateutil.rrule import DAILY, rrule, MO, TU, WE, TH, FR
from dateutil.relativedelta import relativedelta
from govuk_bank_holidays.bank_holidays import BankHolidays

# Get UK bank holidays as supplied by GOV.UK
BANK_HOLIDAYS = BankHolidays()
DCF_DENOMINATOR = 360


def add_uk_business_days(start: date, days: int) -> date:
    """
    Adds the specified number of UK business days to the given start date.

    :param start: The start date.
    :param days: The number of business days to add.
    :return: The date after adding the specified number of business days.
    """
    business_days = rrule(
        DAILY,
        dtstart=start,
        byweekday=(MO, TU, WE, TH, FR),
    )

    current_date = datetime.combine(start, datetime.min.time())
    days_added = 0

    while days_added < days:
        current_date = business_days.after(current_date)
        if not BANK_HOLIDAYS.is_holiday(current_date):
            days_added += 1

    return current_date.date()


def sub_uk_business_days(start: date, days: int) -> date:
    """
    Subtracts the specified number of UK business days from the given start date.

    :param start: The start date.
    :param days: The number of business days to subtract.
    :return: The date after subtracting the specified number of business days.
    """
    business_days = rrule(
        DAILY,
        dtstart=start-relativedelta(days=days*2),
        byweekday=(MO, TU, WE, TH, FR),
    )

    current_date = datetime.combine(start, datetime.min.time())
    days_subtracted = 0

    while days_subtracted < days:
        current_date = business_days.before(current_date)
        if not BANK_HOLIDAYS.is_holiday(current_date):
            days_subtracted += 1

    return current_date.date()


def safely_set_day(dt: date, day: int) -> date:
    """
    Safely sets the day of the month for a given date.

    :param dt: The date to set the day of the month for.
    :param day: The day of the month to set.
    :return: The date with the specified day of the month.
    :raises ValueError: If the specified day is invalid for the given month and year.
    """
    try:
        return dt.replace(day=day)
    except ValueError:
        return last_day_of_month(dt)
    

def last_day_of_month(dt: date) -> date:
    """
    Returns the last day of the month for the given date.

    Source: https://stackoverflow.com/questions/42950/get-the-last-day-of-the-month

    :param dt: The date to get the last day of the month for.
    :return: The last day of the month for the given date.
    """
    # The day 28 exists in every month. 4 days later, it's always the next month.
    next_month = dt.replace(day=28) + relativedelta(days=4)
    # Subtracting the number of the current day brings us back to the last day 
    # of the current month.
    return next_month - relativedelta(days=next_month.day)