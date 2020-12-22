import itertools
import json
import pkgutil
import logging
import os

from fbprophet import Prophet
import pandas as pd
from fbprophet.diagnostics import cross_validation, performance_metrics
from pandas import DataFrame
import numpy as np

from timex.data_prediction.data_prediction import PredictionModel, TestingPerformance
logging.getLogger('fbprophet').setLevel(logging.WARNING)


class FBProphet(PredictionModel):
    """Facebook's Prophet prediction model."""

    def __init__(self, params: dict, transformation: str = None):
        super().__init__(params, name="FBProphet", transformation=transformation)

        # Stuff needed to make Prophet shut up during training.
        self.suppress_stdout_stderr = suppress_stdout_stderr
        self.fbmodel = Prophet()

    def train(self, input_data: DataFrame, extra_regressors: DataFrame = None):
        """Overrides PredictionModel.train()"""
        # deals_dates = pd.date_range('2019-02-07', periods=12, freq='D').union_many([
        #     pd.date_range('2019-03-28', periods=12, freq='D'),
        #     pd.date_range('2019-06-05', periods=12, freq='D'),
        #     pd.date_range('2019-07-17', periods=12, freq='D'),
        #     pd.date_range('2019-10-02', periods=12, freq='D'),
        #     pd.date_range('2019-11-09', periods=12, freq='D'),
        #     pd.date_range('2020-02-05', periods=12, freq='D'),
        #     pd.date_range('2020-03-04', periods=12, freq='D'),
        #     pd.date_range('2020-04-29', periods=12, freq='D'),
        #     pd.date_range('2020-06-10', periods=12, freq='D'),
        #     pd.date_range('2020-07-11', periods=12, freq='D'),
        #     pd.date_range('2020-10-13', periods=12, freq='D'),
        #     pd.date_range('2020-11-30', periods=40, freq='D'),
        # ])
        # deals = pd.DataFrame({
        #     'holiday': 'deals',
        #     'ds': deals_dates,
        # })
        self.fbmodel = Prophet()

        if extra_regressors is not None:
            # We could apply self.transformation also on the extra regressors.
            # From tests, it looks like it doesn't change much/it worsens the forecasts.
            input_data = input_data.join(extra_regressors)
            input_data.reset_index(inplace=True)
            column_indices = [0, 1]
            new_names = ['ds', 'y']
            old_names = input_data.columns[column_indices]
            input_data.rename(columns=dict(zip(old_names, new_names)), inplace=True)
            [self.fbmodel.add_regressor(col) for col in extra_regressors.columns]

        else:
            input_data.reset_index(inplace=True)
            input_data.columns = ['ds', 'y']

        with self.suppress_stdout_stderr():
            self.fbmodel.fit(input_data)

        #######################
        # param_grid = {
        #     'changepoint_prior_scale': [0.001, 0.01, 0.1, 0.5],
        #     'seasonality_prior_scale': [0.01, 0.1, 1.0, 10.0],
        # }
        # param_grid = {
        #     'changepoint_prior_scale': [0.001, 0.01],
        #     'seasonality_prior_scale': [0.01, 0.1],
        # }
        #
        # if extra_regressors is not None:
        #     input_data = input_data.join(extra_regressors)
        #     input_data.reset_index(inplace=True)
        #     column_indices = [0, 1]
        #     new_names = ['ds', 'y']
        #     old_names = input_data.columns[column_indices]
        #     input_data.rename(columns=dict(zip(old_names, new_names)), inplace=True)
        #
        # else:
        #     input_data.reset_index(inplace=True)
        #     input_data.columns = ['ds', 'y']
        #
        # # Generate all combinations of parameters
        # all_params = [dict(zip(param_grid.keys(), v)) for v in itertools.product(*param_grid.values())]
        # rmses = []  # Store the RMSEs for each params here
        #
        # # Use cross validation to evaluate all parameters
        # for params in all_params:
        #     m = Prophet(**params)
        #     [m.add_regressor(col) for col in extra_regressors.columns] if extra_regressors is not None else None
        #     with self.suppress_stdout_stderr():
        #         m.fit(input_data)  # Fit model with given params
        #         df_cv = cross_validation(m, horizon=self.prediction_lags, parallel="processes")
        #         df_p = performance_metrics(df_cv, rolling_window=1)
        #         rmses.append(df_p['rmse'].values[0])
        #
        # # Find the best parameters
        # tuning_results = pd.DataFrame(all_params)
        # tuning_results['rmse'] = rmses
        #
        # best_params = all_params[np.argmin(rmses)]
        # print(best_params)
        #
        # self.fbmodel = Prophet(**best_params)
        # [self.fbmodel.add_regressor(col) for col in extra_regressors.columns] if extra_regressors is not None else None
        # with self.suppress_stdout_stderr():
        #     self.fbmodel.fit(input_data)

    def predict(self, future_dataframe: DataFrame, extra_regressors: DataFrame = None) -> DataFrame:
        """Overrides PredictionModel.predict()"""
        future = future_dataframe.reset_index()
        future.rename(columns={'index': 'ds'}, inplace=True)

        if extra_regressors is not None:
            future.set_index('ds', inplace=True)
            future = future.join(extra_regressors.copy())
            future.reset_index(inplace=True)

        forecast = self.fbmodel.predict(future)

        forecast.loc[:, 'yhat'] = self.transformation.inverse(forecast['yhat'])
        forecast.loc[:, 'yhat_lower'] = self.transformation.inverse(forecast['yhat_upper'])
        forecast.loc[:, 'yhat_upper'] = self.transformation.inverse(forecast['yhat_upper'])

        forecast.set_index('ds', inplace=True)

        return forecast


class suppress_stdout_stderr(object):
    """
    A context manager for doing a "deep suppression" of stdout and stderr in
    Python, i.e. will suppress all print, even if the print originates in a
    compiled C/Fortran sub-function.
       This will not suppress raised exceptions, since exceptions are printed
    to stderr just before a script exits, and after the context manager has
    exited (at least, I think that is why it lets exceptions through).

    """

    def __init__(self):
        # Open a pair of null files
        self.null_fds = [os.open(os.devnull, os.O_RDWR) for x in range(2)]
        # Save the actual stdout (1) and stderr (2) file descriptors.
        self.save_fds = [os.dup(1), os.dup(2)]

    def __enter__(self):
        # Assign the null pointers to stdout and stderr.
        os.dup2(self.null_fds[0], 1)
        os.dup2(self.null_fds[1], 2)

    def __exit__(self, *_):
        # Re-assign the real stdout/stderr back to (1) and (2)
        os.dup2(self.save_fds[0], 1)
        os.dup2(self.save_fds[1], 2)
        # Close the null files
        for fd in self.null_fds + self.save_fds:
            os.close(fd)
