from datetime import date, datetime
from dateutil.rrule import DAILY, rrule, MO, TU, WE, TH, FR
from govuk_bank_holidays.bank_holidays import BankHolidays

# Get UK bank holidays as supplied by GOV.UK
BANK_HOLIDAYS = BankHolidays()
DCF_DENOMINATOR = 360


def add_uk_business_days(start: date, days: int) -> date:
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