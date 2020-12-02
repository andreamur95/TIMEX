import unittest

from pandas import Series, DataFrame
import numpy as np

from timex.data_prediction.arima_predictor import ARIMA
from timex.data_prediction.data_prediction import pre_transformation, calc_xcorr, post_transformation
from timex.data_prediction.prophet_predictor import FBProphet
from timex.tests.utilities import get_fake_df

xcorr_modes = ['pearson', 'kendall', 'spearman', 'matlab_normalized']


class MyTestCase(unittest.TestCase):
    def test_pre_transformation_1(self):

        s = Series(np.array([-4, -3, -2, -1, 0, 1, 2, 3, 4]))
        res = pre_transformation(s, "log_modified")

        self.assertEqual(res[0], -np.log(4+1))
        self.assertEqual(res[1], -np.log(3+1))
        self.assertEqual(res[2], -np.log(2+1))
        self.assertEqual(res[3], -np.log(1+1))
        self.assertEqual(res[4],  np.log(1))
        self.assertEqual(res[5],  np.log(1+1))
        self.assertEqual(res[6],  np.log(2+1))
        self.assertEqual(res[7],  np.log(3+1))
        self.assertEqual(res[8],  np.log(4+1))

    def test_post_transformation_1(self):

        s = Series(np.array([-4, -3, -2, -1, 0, 1, 2, 3, 4]))
        res = pre_transformation(s, "log_modified")
        res = post_transformation(res, "log_modified")

        self.assertTrue(np.allclose(s, res))

    def test_pre_transformation_2(self):

        s = Series(np.array([2]))
        res = pre_transformation(s, "none")

        self.assertEqual(res[0], 2)

    def test_pre_transformation_3(self):
        s = Series(np.array([-4, -3, -2, -1, 0, 1, 2, 3, 4]))
        res = pre_transformation(s, "log")

        self.assertEqual(res[0], -np.log(4))
        self.assertEqual(res[1], -np.log(3))
        self.assertEqual(res[2], -np.log(2))
        self.assertEqual(res[3], -np.log(1))
        self.assertEqual(res[4],  0)
        self.assertEqual(res[5],  np.log(1))
        self.assertEqual(res[6],  np.log(2))
        self.assertEqual(res[7],  np.log(3))
        self.assertEqual(res[8],  np.log(4))

    def test_post_transformation_3(self):
        s = Series(np.array([-4, -3, -2, -1, 0, 1, 2, 3, 4]))
        res = pre_transformation(s, "log")

        self.assertEqual(res[0], -np.log(4))
        self.assertEqual(res[1], -np.log(3))
        self.assertEqual(res[2], -np.log(2))
        self.assertEqual(res[3],  0)
        self.assertEqual(res[4],  0)
        self.assertEqual(res[5],  0)
        self.assertEqual(res[6],  np.log(2))
        self.assertEqual(res[7],  np.log(3))
        self.assertEqual(res[8],  np.log(4))

    def test_launch_model_fbprophet_1(self):
        # Percentages' sum is not 100%; adapt the windows.
        param_config = {
            "model_parameters": {
                "test_percentage": 10,
                "delta_training_percentage": 20,
                "prediction_lags": 10,
                "transformation": "none",
                "main_accuracy_estimator": "mae"
            },
        }

        df = get_fake_df(100)
        predictor = FBProphet(param_config)
        model_result = predictor.launch_model(df.copy())

        self.assertEqual(predictor.test_values, 10)
        self.assertEqual(predictor.delta_training_values, 20)
        self.assertEqual(predictor.main_accuracy_estimator, "mae")

        self.assertEqual(len(model_result.results), 5)

        for r in model_result.results:
            prediction = r.prediction
            testing_performances = r.testing_performances
            first_used_index = testing_performances.first_used_index

            used_training_set = df.loc[first_used_index:]
            used_training_set = used_training_set.iloc[:-10]
            self.assertEqual(len(prediction), len(used_training_set) + 10 + 10)

    def test_launch_model_fbprophet_2(self):
        # Percentages' sum is not 100%; adapt the windows.
        param_config = {
            "model_parameters": {
                "test_values": 5,
                "delta_training_percentage": 20,
                "prediction_lags": 10,
                "transformation": "none",
                "main_accuracy_estimator": "mae"
            },
        }

        df = get_fake_df(100)
        predictor = FBProphet(param_config)
        model_result = predictor.launch_model(df.copy())

        self.assertEqual(predictor.test_values, 5)
        self.assertEqual(predictor.delta_training_values, 20)
        self.assertEqual(predictor.main_accuracy_estimator, "mae")

        self.assertEqual(len(model_result.results), 5)

        for r in model_result.results:
            prediction = r.prediction
            testing_performances = r.testing_performances
            first_used_index = testing_performances.first_used_index

            used_training_set = df.loc[first_used_index:]
            used_training_set = used_training_set.iloc[:-5]
            self.assertEqual(len(prediction), len(used_training_set) + 5 + 10)

    def test_launch_model_fbprophet_3(self):
        # Check default parameters.
        param_config = {
            "verbose": "no",
        }

        df = get_fake_df(100)
        predictor = FBProphet(param_config)
        model_result = predictor.launch_model(df.copy())

        self.assertEqual(predictor.test_values, 10)
        self.assertEqual(predictor.delta_training_values, 20)
        self.assertEqual(predictor.main_accuracy_estimator, "mae")
        self.assertEqual(predictor.transformation, "log")

        self.assertEqual(len(model_result.results), 5)

        for r in model_result.results:
            prediction = r.prediction
            testing_performances = r.testing_performances
            first_used_index = testing_performances.first_used_index

            used_training_set = df.loc[first_used_index:]
            used_training_set = used_training_set.iloc[:-5]
            self.assertEqual(len(prediction), len(used_training_set) + 5 + 10)

    def test_launch_model_arima(self):
        param_config = {
            "model_parameters": {
                "test_percentage": 10,
                "delta_training_percentage": 20,
                "prediction_lags": 10,
                "transformation": "none",
                "main_accuracy_estimator": "mae"
            },
        }

        df = get_fake_df(100)
        predictor = ARIMA(param_config)
        model_result = predictor.launch_model(df.copy())

        self.assertEqual(predictor.test_values, 10)
        self.assertEqual(predictor.delta_training_values, 20)
        self.assertEqual(predictor.main_accuracy_estimator, "mae")

        self.assertEqual(len(model_result.results), 5)

        for r in model_result.results:
            prediction = r.prediction
            testing_performances = r.testing_performances
            first_used_index = testing_performances.first_used_index

            used_training_set = df.loc[first_used_index:]
            used_training_set = used_training_set.iloc[:-10]
            self.assertEqual(len(prediction), len(used_training_set) + 10 + 10)

    def test_calc_xcorr_1(self):
        # Example from https://www.mathworks.com/help/matlab/ref/xcorr.html

        x = [np.power(0.84, n) for n in np.arange(0, 16)]
        y = np.roll(x, 5)

        df = DataFrame(data={"x": x, "y": y})

        xcorr = calc_xcorr("x", df, max_lags=10, modes=xcorr_modes)
        for mode in xcorr:
            self.assertEqual(xcorr[mode].idxmax()[0], -5)

    def test_calc_xcorr_2(self):
        # Shift a sin. Verify that highest correlation is in the correct region.

        # Restrict the delay to less than one period of the sin.
        max_delay = 50 - 1
        x = np.linspace(0, 2 * np.pi, 100)
        y = np.sin(x)

        for i in range(-max_delay, max_delay):
            y_delayed = np.roll(y, i)

            df = DataFrame(data={"y": y, "y_delayed": y_delayed})

            xcorr = calc_xcorr("y", df, max_lags=max_delay, modes=xcorr_modes)
            expected_max_lag = -i
            for mode in xcorr:
                self.assertLess(abs(xcorr[mode].idxmax()[0] - expected_max_lag), 4)


if __name__ == '__main__':
    unittest.main()