import logging
import gettext
import pathlib
import os

import pandas
from pandas import Grouper, DataFrame
import plotly.graph_objects as go
import numpy as np

import dash_core_components as dcc
import dash_html_components as html
from plotly.subplots import make_subplots
import networkx as nx
import dash_bootstrap_components as dbc

from colorhash import ColorHash
from statsmodels.tsa.seasonal import seasonal_decompose

from timex.data_prediction import ValidationPerformance
from timex.data_prediction.models.predictor import SingleResult
from timex.scenario import Scenario
import calendar

log = logging.getLogger(__name__)

# Default method to get a translated text.
global _
_ = lambda x: x


def create_scenario_children(scenario: Scenario, param_config: dict):
    """
    Creates the Dash children for a specific scenario. They include a line plot,
    histogram, box plot and autocorrelation plot. For each model on the scenario
    the prediction plot and performance plot are also added.
    
    Parameters
    ----------
    scenario: Scenario
    
    param_config : dict
    
    True to display the cross-correlation plot. Default True.

    Returns
    -------
    List of Dash children.
    """
    children = []

    visualization_parameters = param_config["visualization_parameters"]
    scenario_data = scenario.scenario_data

    name = scenario_data.columns[0]

    locale_dir = pathlib.Path(os.path.abspath(__file__)).parent / "locales"

    try:
        gt = gettext.translation('messages', localedir=locale_dir, languages=[visualization_parameters["language"]])
        gt.install()
        _ = gt.gettext
    except:
        gt = gettext.translation('messages', localedir=locale_dir, languages=['en'])
        gt.install()
        _ = gt.gettext

    # Data visualization with plots
    children.extend([
        html.H2(children=name + _(' analysis'), id=name),
        html.H3(_("Data visualization")),
        line_plot(scenario_data),
        histogram_plot(scenario_data, visualization_parameters),
        box_plot(scenario_data, visualization_parameters),
        box_plot_aggregate(scenario_data, visualization_parameters),
        components_plot(scenario_data),
        autocorrelation_plot(scenario_data),
    ])

    # Plot cross-correlation plot and graphs, if requested.
    if scenario.xcorr is not None:
        graph_corr_threshold = visualization_parameters[
            "xcorr_graph_threshold"] if "xcorr_graph_threshold" in visualization_parameters else None

        children.extend([
            html.H3(_("Cross-correlation")),
            html.Div(_("Negative lags (left part) show the correlation between this scenario and the future of the "
                       "others.")),
            html.Div(_("Meanwhile, positive lags (right part) shows the correlation between this scenario "
                       "and the past of the others.")),
            cross_correlation_plot(scenario.xcorr),
            html.Div(_("The peaks found using each cross-correlation modality are shown in the graphs:")),
            cross_correlation_graph(name, scenario.xcorr, graph_corr_threshold)
        ])

    # Plot the prediction results, if requested.
    if scenario.models is not None:
        model_parameters = param_config["model_parameters"]

        models = scenario.models

        children.append(
            html.H3(_("Training & Validation results")),
        )

        for model_name in models:
            model = models[model_name]
            model_results = model.results
            model_characteristic = model.characteristics

            test_values = model_characteristic["test_values"]
            main_accuracy_estimator = model_parameters["main_accuracy_estimator"]
            model_results.sort(key=lambda x: getattr(x.testing_performances, main_accuracy_estimator.upper()))

            best_prediction = model_results[0].prediction
            testing_performances = [x.testing_performances for x in model_results]

            children.extend([
                html.H4(f"{model_name}"),
                characteristics_list(model_characteristic, testing_performances),
                # html.Div("Testing performance:"),
                # html.Ul([html.Li(key + ": " + str(testing_performances[key])) for key in testing_performances]),
                prediction_plot(scenario_data, best_prediction, test_values),
                performance_plot(scenario_data, best_prediction, testing_performances, test_values),
            ])

            # EXTRA
            # Warning: this will plot every model result, with every training set used!
            # children.extend(plot_every_prediction(ingested_data, model_results, main_accuracy_estimator, test_values))

    if scenario.historical_prediction is not None:
        children.extend([
            html.H3(_("Prediction")),
            html.Div(_("For every model the best predictions for each past date are plotted."))
        ])
        for model in scenario.historical_prediction:
            children.extend([
                html.H4(f"{model}"),
                historical_prediction_plot(scenario_data, scenario.historical_prediction[model], scenario.models[model].best_prediction)
            ])

    return children


def create_dash_children(scenarios: [Scenario], param_config: dict):
    """
    Create Dash children, in order, for a list of Scenarios.
    Parameters
    ----------
    scenarios : [Scenario]

    param_config : dict

    Returns
    -------
    List of Dash children.

    """
    children = []
    for s in scenarios:
        children.extend(create_scenario_children(s, param_config))

    return children


def line_plot(df: DataFrame) -> dcc.Graph:
    """
    Create and return the line plot for a dataframe.

    Parameters
    ----------
    df : DataFrame
    Dataframe to plot.

    Returns
    -------
    g : dcc.Graph
    """
    fig = go.Figure(data=go.Scatter(x=df.index, y=df.iloc[:, 0], mode='lines+markers'))
    fig.update_layout(title=_('Line plot'), xaxis_title=df.index.name, yaxis_title=df.columns[0])

    g = dcc.Graph(
        figure=fig
    )
    return g


def line_plot_multiIndex(df: DataFrame) -> dcc.Graph:
    """
    Returns a line plot for a dataframe with a MultiIndex.
    It is assumed that the first-level index is the real index,
    and that data should be grouped using the second-level one.

    Parameters
    ----------
    df : DataFrame
    Dataframe to plot. It is a multiIndex dataframe.

    Returns
    -------
    g : dcc.Graph
    """
    fig = go.Figure()
    for region in df.index.get_level_values(1).unique():
        fig.add_trace(go.Scatter(x=df.index.get_level_values(0).unique(), y=df.loc[
            (df.index.get_level_values(1) == region), df.columns[0]], name=region))

    fig.update_layout(title=_('Line plot'), xaxis_title=df.index.get_level_values(0).name,
                      yaxis_title=df.columns[0])
    g = dcc.Graph(
        figure=fig
    )
    return g


def histogram_plot(df: DataFrame, visualization_parameters: dict) -> dcc.Graph:
    """
    Create and return the histogram plot for a dataframe.

    Parameters
    ----------
    df : DataFrame
    Dataframe to plot.

    visualization_parameters : dict
    Options set by the user.

    Returns
    -------
    g : dcc.Graph
    """

    try:
        p = {'nbinsx': visualization_parameters["histogram_bins"]}
    except KeyError:
        p = {}

    fig = go.Figure(data=[go.Histogram(x=df.iloc[:, 0], **p)])

    fig.update_layout(title=_('Histogram'), xaxis_title_text=df.columns[0], yaxis_title_text=_('Count'))
    g = dcc.Graph(
        figure=fig
    )
    return g


def components_plot(ingested_data: DataFrame) -> html.Div:
    """
    Create and return the plots of all the components of the time series: level, trend, residual.
    It uses both an additive and multiplicative model, with a subplot.

    Parameters
    ----------
    ingested_data : DataFrame
        Original time series values.

    Returns
    -------
    g : dcc.Graph
    """
    modes = ["additive", "multiplicative"]

    fig = make_subplots(
        rows=3,
        cols=1,
        subplot_titles=[_("Trend"), _("Seasonality"), _("Residual")], shared_xaxes=True, vertical_spacing=0.05,
        specs=[[{"secondary_y": True}], [{"secondary_y": True}], [{"secondary_y": True}]]
    )

    interpolated = ingested_data.interpolate()
    interpolated = interpolated.fillna(0)

    for mode in modes:
        try:
            result = seasonal_decompose(interpolated, model=mode)
            trend = result.trend
            seasonal = result.seasonal
            residual = result.resid

            secondary_y = False if mode == "additive" else True

            fig.add_trace(go.Scatter(x=trend.index, y=trend,
                                     mode='lines+markers',
                                     name=_(mode.capitalize()), legendgroup=_(mode.capitalize()), line=dict(color=ColorHash(mode).hex)),
                          row=1, col=1, secondary_y=secondary_y)
            fig.add_trace(go.Scatter(x=seasonal.index, y=seasonal,
                                     mode='lines+markers', showlegend=False,
                                     name=_(mode.capitalize()), legendgroup=_(mode.capitalize()), line=dict(color=ColorHash(mode).hex)),
                          row=2, col=1, secondary_y=secondary_y)
            fig.add_trace(go.Scatter(x=residual.index, y=residual,
                                     mode='lines+markers', showlegend=False,
                                     name=_(mode.capitalize()), legendgroup=_(mode.capitalize()), line=dict(color=ColorHash(mode).hex)),
                          row=3, col=1, secondary_y=secondary_y)
        except ValueError:
            log.warning(f"Multiplicative decomposition not available for {ingested_data.columns[0]}")

    fig.update_layout(title=_("Components decomposition"), height=1000, legend_title_text=_('Decomposition model'))
    fig.update_yaxes(title_text="<b>" + _('Additive') + "</b>", secondary_y=False)
    fig.update_yaxes(title_text="<b>" + _('Multiplicative') + "</b>", secondary_y=True)

    g = dcc.Graph(
        figure=fig
    )

    warning = html.H5(_("Multiplicative model is not available for series which contain zero or negative values."))

    return html.Div([g, warning])


def autocorrelation_plot(df: DataFrame) -> dcc.Graph:
    """
    Create and return the autocorrelation plot for a dataframe.

    Parameters
    ----------
    df : DataFrame
    Dataframe to use in the autocorrelation plot.

    Returns
    -------
    g : dcc.Graph
    """

    # Code from https://github.com/pandas-dev/pandas/blob/v1.1.4/pandas/plotting/_matplotlib/misc.py
    n = len(df)
    data = np.asarray(df)
    mean = np.mean(data)
    c0 = np.sum((data - mean) ** 2) / float(n)

    def r(h):
        return ((data[: n - h] - mean) * (data[h:] - mean)).sum() / float(n) / c0

    x = np.arange(n) + 1
    y = [r(loc) for loc in x]

    z95 = 1.959963984540054
    z99 = 2.5758293035489004

    c1 = z99 / np.sqrt(n)
    c2 = z95 / np.sqrt(n)
    c3 = -z95 / np.sqrt(n)
    c4 = -z99 / np.sqrt(n)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode='lines', name=_('autocorrelation')))
    fig.add_trace(go.Scatter(x=x, y=np.full(n, c1), line=dict(color='gray', width=1), name='z99'))
    fig.add_trace(go.Scatter(x=x, y=np.full(n, c2), line=dict(color='gray', width=1), name='z95'))
    fig.add_trace(go.Scatter(x=x, y=np.full(n, c3), line=dict(color='gray', width=1), name='-z95'))
    fig.add_trace(go.Scatter(x=x, y=np.full(n, c4), line=dict(color='gray', width=1), name='-z99'))
    fig.update_layout(title=_('Autocorrelation plot'), xaxis_title=_('Lags'), yaxis_title=_('Autocorrelation'))
    fig.update_yaxes(tick0=-1.0, dtick=0.25)
    fig.update_yaxes(range=[-1.2, 1.2])
    g = dcc.Graph(
        figure=fig
    )
    return g


def cross_correlation_plot(xcorr: dict):
    """
    Create and return the cross-correlation plot for all the columns in the dataframe.
    The scenario column is used as target; the correlation is shown in a subplot for every modality used to compute the
    x-correlation.

    Parameters
    ----------
    xcorr : dict
    Cross-correlation values.

    Returns
    -------
    g : dcc.Graph
    """
    subplots = len(xcorr)
    combs = [(1, 1), (1, 2), (2, 1), (2, 2)]

    rows = 1 if subplots < 3 else 2
    cols = 1 if subplots < 2 else 2

    fig = make_subplots(
        rows=rows, cols=cols,
        subplot_titles=([*xcorr.keys()]))

    i = 0
    for mode in xcorr:
        for col in xcorr[mode].columns:
            fig.add_trace(go.Scatter(x=xcorr[mode].index, y=xcorr[mode][col],
                                     mode='lines',
                                     name=col, legendgroup=col, line=dict(color=ColorHash(col).hex),
                                     showlegend=True if i == 0 else False),
                          row=combs[i][0], col=combs[i][1])
        i += 1

    # Formula from https://support.minitab.com/en-us/minitab/18/help-and-how-to/modeling-statistics/time-series/how-to/cross-correlation/interpret-the-results/all-statistics-and-graphs/
    # significance_level = DataFrame(columns=['Value'], dtype=np.float64)
    # for i in range(-lags, lags):
    #     significance_level.loc[i] = 2 / np.sqrt(lags - abs(i))

    # fig.add_trace(
    #     go.Scatter(x=significance_level.index, y=significance_level['Value'], line=dict(color='gray', width=1), name='z95'))
    # fig.add_trace(
    #     go.Scatter(x=significance_level.index, y=-significance_level['Value'], line=dict(color='gray', width=1), name='-z95'))

    fig.update_layout(title=_("Cross-correlation using different algorithms"))
    fig.update_xaxes(title_text=_("Lags"))
    fig.update_yaxes(tick0=-1.0, dtick=0.25, range=[-1.2, 1.2], title_text=_("Correlation"))

    g = dcc.Graph(
        figure=fig
    )
    return g


def cross_correlation_graph(name: str, xcorr: dict, threshold: int = 0) -> dcc.Graph:
    """
    Create and return the cross-correlation graphs for all the columns in the dataframe.
    A graph is created for each mode used to compute the x-correlation.

    Parameters
    ----------
    name : str
    Name of the target.

    xcorr : dict
    Cross-correlation dataframe.

    threshold : int
    Minimum value of correlation for which a edge should be drawn. Default 0.

    Returns
    -------
    g : dcc.Graph
    """
    figures = []

    i = 0
    for mode in xcorr:
        G = nx.DiGraph()
        G.add_nodes_from(xcorr[mode].columns)
        G.add_node(name)

        for col in xcorr[mode].columns:
            index_of_max = xcorr[mode][col].abs().idxmax()
            corr = xcorr[mode].loc[index_of_max, col]
            if abs(corr) > threshold:
                G.add_edge(name, col, corr=corr, lag=index_of_max)

        pos = nx.layout.spring_layout(G)

        # Create Edges
        edge_trace = go.Scatter(
            x=[],
            y=[],
            line=dict(color='black'),
            mode='lines',
            hoverinfo='skip',
        )

        for edge in G.edges():
            start = edge[0]
            end = edge[1]
            x0, y0 = pos.get(start)
            x1, y1 = pos.get(end)
            edge_trace['x'] += tuple([x0, x1, None])
            edge_trace['y'] += tuple([y0, y1, None])

        # Create Nodes
        node_trace = go.Scatter(
            x=[],
            y=[],
            mode='markers+text',
            text=[node for node in G.nodes],
            textposition="bottom center",
            hoverinfo='skip',
            marker=dict(
                color='green',
                size=15)
        )

        for node in G.nodes():
            x, y = pos.get(node)
            node_trace['x'] += tuple([x])
            node_trace['y'] += tuple([y])

        # Annotations to support arrows
        edges_positions = [e for e in G.edges]
        annotateArrows = [dict(showarrow=True, arrowsize=1.0, arrowwidth=2, arrowhead=2, standoff=2, startstandoff=2,
                               ax=pos[arrow[0]][0], ay=pos[arrow[0]][1], axref='x', ayref='y',
                               x=pos[arrow[1]][0], y=pos[arrow[1]][1], xref='x', yref='y',
                               text="bla") for arrow in edges_positions]

        graph = go.Figure(data=[node_trace, edge_trace],
                          layout=go.Layout(title=str(mode),
                                           xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                           yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                           showlegend=False,
                                           annotations=annotateArrows,
                                           height=400, margin=dict(l=10, r=10, t=50, b=30)))

        # Add annotations on edges
        for e in G.edges:
            lag = str(G.edges[e]['lag'])
            corr = str(round(G.edges[e]['corr'], 3))

            end = e[1]
            x, y = pos.get(end)

            graph.add_annotation(x=x, y=y, text=_("Lag: ") + lag + ", corr: " + corr, yshift=20, showarrow=False,
                                 bgcolor='white')

        figures.append(graph)
        i += 1

    n_graphs = len(figures)
    if n_graphs == 1:
        g = dcc.Graph(figure=figures[0])
    elif n_graphs == 2:
        g = html.Div(dbc.Row([
            dbc.Col(dcc.Graph(figure=figures[0])),
            dbc.Col(dcc.Graph(figure=figures[1]))
        ]))
    elif n_graphs == 3:
        g = html.Div([
            dbc.Row([
                dbc.Col(dcc.Graph(figure=figures[0])),
                dbc.Col(dcc.Graph(figure=figures[1]))
            ]),
            dbc.Row([
                dbc.Col(dcc.Graph(figure=figures[2]))
            ])
        ])
    elif n_graphs == 4:
        g = html.Div([
            dbc.Row([
                dbc.Col(dcc.Graph(figure=figures[0])),
                dbc.Col(dcc.Graph(figure=figures[1])),
            ]),
            dbc.Row([
                dbc.Col(dcc.Graph(figure=figures[2])),
                dbc.Col(dcc.Graph(figure=figures[3]))
            ])
        ])
    else:
        g = html.Div()

    return g


def box_plot(df: DataFrame, visualization_parameters: dict) -> dcc.Graph:
    """
    Create and return the box plot for a dataframe.

    Parameters
    ----------
    df : DataFrame
    Dataframe to use in the box plot.

    visualization_parameters : dict
    Options set by the user.

    Returns
    -------
    g : dcc.Graph
    """
    try:
        freq = visualization_parameters['box_plot_frequency']
    except KeyError:
        freq = '1W'

    temp = df.iloc[:, 0]
    groups = temp.groupby(Grouper(freq=freq))

    boxes = []

    for group in groups:
        boxes.append(go.Box(
            name=str(group[0]),
            y=group[1]
        ))

    fig = go.Figure(data=boxes)
    fig.update_layout(title=_('Box plot'), xaxis_title=df.index.name, yaxis_title=_('Count'), showlegend=False)

    g = dcc.Graph(
        figure=fig
    )
    return g


def box_plot_aggregate(df: DataFrame, visualization_parameters: dict) -> dcc.Graph:
    """
    Create and return the aggregate box plot for a dataframe, i.e. a box plot which shows, for each day of the week/for
    each month of the year the distribution of the values.

    Parameters
    ----------
    df : DataFrame
    Dataframe to use in the box plot.

    visualization_parameters : dict
    Options set by the user.

    Returns
    -------
    g : dcc.Graph
    """

    temp = df.iloc[:, 0]
    try:
        freq = visualization_parameters['aggregate_box_plot_frequency']
    except KeyError:
        freq = 'weekday'

    if freq == 'weekday':
        groups = temp.groupby(temp.index.weekday)
        boxes = []

        for group in groups:
            boxes.append(go.Box(
                name=calendar.day_name[group[0]],
                y=group[1]
            ))
    else:
        groups = temp.groupby(temp.index.month)
        boxes = []

        for group in groups:
            boxes.append(go.Box(
                name=calendar.month_name[group[0]],
                y=group[1]
            ))

    fig = go.Figure(data=boxes)
    fig.update_layout(title=_('Aggregate box plot'), yaxis_title=_('Count'), showlegend=False)

    g = dcc.Graph(
        figure=fig
    )
    return g


def prediction_plot(df: DataFrame, predicted_data: DataFrame, test_values: int) -> dcc.Graph:
    """
    Create and return a plot which contains the prediction for a dataframe.
    The plot is built using two dataframe: ingested_data and predicted_data.

    ingested_data includes the raw data ingested by the app, while predicted_data
    contains the actual prediction made by a model.

    Note that predicted_data starts at the first value used for training.

    The data not used for training is plotted in black, the data used for training
    is plotted in green and the test values are red.

    Note that predicted_data may or not have the columns "yhat_lower" and "yhat_upper".

    Parameters
    ----------
    df : DataFrame
    Raw values ingested by the app.

    predicted_data : DataFrame
    Prediction created by a model.

    test_values : int
    Number of test values used in the testing.

    Returns
    -------
    g : dcc.Graph
    """
    fig = go.Figure()

    not_training_data = df.loc[:predicted_data.index[0]]
    training_data = df.loc[predicted_data.index[0]:]
    training_data = training_data.iloc[:-test_values]
    test_data = df.iloc[-test_values:]

    fig.add_trace(go.Scatter(x=predicted_data.index, y=predicted_data['yhat'],
                             mode='lines+markers',
                             name=_('yhat')))
    try:
        fig.add_trace(go.Scatter(x=predicted_data.index, y=predicted_data['yhat_lower'],
                                 line=dict(color='lightgreen', dash='dash'),
                                 name=_('yhat_lower')))
        fig.add_trace(go.Scatter(x=predicted_data.index, y=predicted_data['yhat_upper'],
                                 line=dict(color='lightgreen', dash='dash'),
                                 name=_('yhat_upper')))
    except:
        pass

    fig.add_trace(go.Scatter(x=not_training_data.index, y=not_training_data.iloc[:, 0],
                             line=dict(color='black'),
                             mode='markers',
                             name=_('unused data')))
    fig.add_trace(go.Scatter(x=training_data.index, y=training_data.iloc[:, 0],
                             line=dict(color='green', width=4, dash='dash'),
                             mode='markers',
                             name=_('training data'),
                             ))

    fig.add_trace(go.Scatter(x=test_data.index, y=test_data.iloc[:, 0],
                             line=dict(color='green', width=3, dash='dot'),
                             name=_('validation data')))
    fig.update_layout(title=_("Best prediction for the validation set"), xaxis_title=df.index.name,
                      yaxis_title=df.columns[0])
    g = dcc.Graph(
        figure=fig
    )
    return g


def historical_prediction_plot(real_data: DataFrame, predicted_data: DataFrame, best_prediction: DataFrame) -> html.Div:
    """
    Create and return a plot which contains the best prediction found by this model for this time series.

    Note that predicted_data may or not have the columns "yhat_lower" and "yhat_upper".

    Parameters
    ----------
    predicted_data
    real_data : DataFrame
    Raw values ingested by the app.

    Returns
    -------
    g : dcc.Graph
    """
    new_children = []
    fig = go.Figure()

    # not_training_data = df.loc[:predicted_data.index[0]]
    # training_data = df.loc[predicted_data.index[0]:]
    # training_data = training_data.iloc[:-test_values]
    # test_data = df.iloc[-test_values:]
    scenario_name = real_data.columns[0]
    first_predicted_index = predicted_data.index[0]
    last_real_index = real_data.index[-1]

    testing_performance = ValidationPerformance(first_predicted_index)
    testing_performance.set_testing_stats(actual=real_data.loc[first_predicted_index:, scenario_name],
                                          predicted=predicted_data.loc[:last_real_index, scenario_name])
    new_children.extend([
        html.Div(_("This model, during the history, reached these performances on unseen data:")),
        show_errors(testing_performance)])

    fig.add_trace(go.Scatter(x=predicted_data.index, y=predicted_data.iloc[:, 0],
                             mode='lines+markers',
                             name=_('prediction')))

    fig.add_trace(go.Scatter(x=real_data.index, y=real_data.iloc[:, 0],
                             line=dict(color='red'),
                             mode='markers',
                             name=_('real data')))

    best_prediction.loc[predicted_data.index[-1], 'yhat'] = predicted_data.iloc[-1, 0]
    best_prediction = best_prediction.loc[predicted_data.index[-1]:, :]

    fig.add_trace(go.Scatter(x=best_prediction.index, y=best_prediction['yhat'],
                             mode='lines+markers',
                             name=_('yhat')))

    # try:
    #     fig.add_trace(go.Scatter(x=predicted_data.index, y=predicted_data['yhat_lower'],
    #                              line=dict(color='lightgreen', dash='dash'),
    #                              name='yhat_lower'))
    #     fig.add_trace(go.Scatter(x=predicted_data.index, y=predicted_data['yhat_upper'],
    #                              line=dict(color='lightgreen', dash='dash'),
    #                              name='yhat_upper'))
    # except:
    #     pass

    # fig.add_trace(go.Scatter(x=not_training_data.index, y=not_training_data.iloc[:, 0],
    #                          line=dict(color='black'),
    #                          mode='markers',
    #                          name='unused data'))
    # fig.add_trace(go.Scatter(x=training_data.index, y=training_data.iloc[:, 0],
    #                          line=dict(color='green'),
    #                          mode='markers',
    #                          name='training data'))
    #
    # fig.add_trace(go.Scatter(x=test_data.index, y=test_data.iloc[:, 0],
    #                          line=dict(color='red'),
    #                          mode='markers',
    #                          name='test data'))
    fig.update_layout(title=_("Historical prediction"), xaxis_title=real_data.index.name,
                      yaxis_title=real_data.columns[0])
    g = dcc.Graph(
        figure=fig
    )

    new_children.append(g)

    return html.Div(new_children)


def performance_plot(df: DataFrame, predicted_data: DataFrame, testing_performances: [ValidationPerformance],
                     test_values: int) -> dcc.Graph:
    """
    Create and return the performance plot of the model; for every error kind (i.e. MSE, MAE, etc)
    plot the values it assumes using different training windows.
    Plot the training data in the end.

    Parameters
    ----------
    df : DataFrame
    Raw values ingested by the app.

    predicted_data : DataFrame
    Prediction created by a model.

    testing_performances : [ValidationPerformance]
    List of ValidationPerformance object. Every object is related to a specific training windows, hence
    it shows the performance using that window.

    test_values : int
    Number of values used for testing performance.

    Returns
    -------
    g : dcc.Graph
    """
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.02)

    training_data = df.iloc[:-test_values]

    data_performances = []

    for tp in testing_performances:
        data_performances.append([tp.first_used_index, tp.MAE, tp.MSE, tp.AM])

    df_performances = pandas.DataFrame(data_performances, columns=['index', 'mae', 'mse', 'am'])
    df_performances.set_index('index', drop=True, inplace=True)
    df_performances.sort_index(inplace=True)

    fig.append_trace(go.Scatter(x=df_performances.index, y=df_performances['mae'],
                                line=dict(color='red'),
                                mode="lines+markers",
                                name='MAE'), row=1, col=1)

    fig.append_trace(go.Scatter(x=df_performances.index, y=df_performances['mse'],
                                line=dict(color='green'),
                                mode="lines+markers",
                                name='MSE'), row=2, col=1)

    fig.append_trace(go.Scatter(x=df_performances.index, y=df_performances['am'],
                                line=dict(color='blue'),
                                mode="lines+markers",
                                name='AM'), row=3, col=1)

    fig.append_trace(go.Scatter(x=training_data.index, y=training_data.iloc[:, 0],
                                line=dict(color='black'),
                                mode='markers',
                                name=_('training data')), row=4, col=1)

    # Small trick to make the x-axis have the same length of the "Prediction plot"
    predicted_data.iloc[:, 0] = "nan"
    fig.append_trace(go.Scatter(x=predicted_data.index, y=predicted_data.iloc[:, 0],
                                mode='lines+markers',
                                name='yhat', showlegend=False), row=4, col=1)

    fig.update_yaxes(title_text="MAE", row=1, col=1)
    fig.update_yaxes(title_text="MSE", row=2, col=1)
    fig.update_yaxes(title_text="AM", row=3, col=1)
    fig.update_yaxes(title_text=df.columns[0], row=4, col=1)

    fig.update_layout(title=_('Performances with different training windows'), height=900)
    g = dcc.Graph(
        figure=fig
    )
    return g


def plot_every_prediction(df: DataFrame, model_results: [SingleResult],
                          main_accuracy_estimator: str, test_values: int):
    new_childrens = [html.Div("EXTRA: plot _EVERY_ prediction\n")]

    model_results.sort(key=lambda x: len(x.prediction))

    for r in model_results:
        predicted_data = r.prediction
        testing_performance = r.testing_performances
        plot = prediction_plot(df, predicted_data, test_values)
        plot.figure.update_layout(title="")
        new_childrens.extend([
            html.Div(main_accuracy_estimator.upper()
                     + ": " + str(getattr(testing_performance, main_accuracy_estimator.upper()))),
            plot
        ])

    return new_childrens


def characteristics_list(model_characteristics: dict, testing_performances: [ValidationPerformance]) -> html.Div:
    """
    Create and return an HTML Div which contains a list of natural language characteristic
    relative to a prediction model.

    Parameters
    ----------
    model_characteristics : dict
    key-value for each characteristic to write in natural language.

    testing_performances : [ValidationPerformance]
    Useful to write also information about the testing performances.

    Returns
    -------
    html.Div()
    """

    def get_text_char(key: str, value: any) -> str:
        value = str(value)
        switcher = {
            "name": _("Model type: ") + value,
            "test_values": _('Values used for testing: last ') + value + _(' values'),
            "delta_training_percentage": _('The length of the training windows is the ') + value
                                         + "%" + _(' of the length of the time series.'),
            "delta_training_values": _('Training windows are composed of ') + value + _(' values.'),
            "extra_regressors": _("The model has used ") + value + _(" as extra-regressor(s) to improve the training."),
            "transformation": _('The model has used a ') + value + _(' transformation on the input data.') if value != "none "
                              else _('The model has not used any pre/post transformation on input data.')
        }
        return switcher.get(key, "Invalid choice!")

    elems = [html.Div(_('Model characteristics:')),
             html.Ul([html.Li(get_text_char(key, model_characteristics[key])) for key in model_characteristics]),
             html.Div(_("This model, using the best training window, reaches these performances:")),
             show_errors(testing_performances[0])]

    return html.Div(elems)


def show_errors(testing_performances: ValidationPerformance) -> html.Div:
    """

    Parameters
    ----------
    testing_performances

    Returns
    -------


    """

    def get_text_perf(key: str, value: any) -> str:
        switcher = {
            "MAE": "MAE: " + str(round(value, 2)),
            "RMSE": "RMSE: " + str(round(value, 2)),
            "MSE": "MSE: " + str(round(value, 2)),
            "AM": _('Arithmetic mean of errors:') + str(round(value, 2))
        }
        return switcher.get(key, "Invalid choice!")

    testing_performances = testing_performances.get_dict()
    del testing_performances["first_used_index"]

    return html.Ul([html.Li(get_text_perf(key, testing_performances[key])) for key in testing_performances])