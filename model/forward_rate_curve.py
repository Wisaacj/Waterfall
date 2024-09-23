import numpy as np
import pandas as pd

from datetime import date
from scipy import interpolate


class ForwardRateCurve:
    """
    Class representing a forward rate curve. Stores a set of interest rates
    over time and manages interpolation to estimate rates between known data points.
    """

    def __init__(self, dates: list[date], rates: list[float]):
        """
        Instantiates a ForwardRateCurve.

        :param dates: a list of dates for which the rates are provided.
        :param rates: a list of rates for the provided dates.
        """
        assert len(dates) == len(
            rates), "Dates and rates must have the same length."

        # An interpolator is used to estimate interest rates for dates that fall
        # between two known data points. This allows us to provide estimated interest
        # rates for any date, even if it's not one of the exact dates provided in the
        # original data.
        self.interpolator = interpolate.interp1d(
            [d.toordinal() for d in dates],
            rates,
            kind='linear',  # Use cubic splines to interpolate between points.
            # Do not raise an error if the interpolation is out of bounds.
            bounds_error=False,
            # Use the first or last known rate if the interpolation is out of bounds.
            fill_value=(rates[0], rates[-1])
        )

    def get_rate(self, dt: date) -> float:
        """
        Returns the forward rate for the given date.

        :param dt: the date to get the rate for.
        :return: the rate for the given date.
        """
        return self.interpolator(dt.toordinal())

    def get_average_rate(self, start: date, end: date) -> float:
        """
        Returns the average rate for the given date range.

        :param start: the start date of the range.
        :param end: the end date of the range.
        :return: the average rate for the given date range.
        """
        # `pd.date_range` generates a range of dates between the start and end dates inclusive.
        # We then map these dates to the forward rate curve to get the rate for each date,
        # and take the mean of these rates to get the average rate for the range.
        return np.mean([self.get_rate(d) for d in pd.date_range(start, end)])
