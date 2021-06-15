import datetime

import dash
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_table
import plotly
from dash.dependencies import Input, Output
from euro_prediction import Tournament

#------------------------------ LOAD DATA ------------------------------- #

tournament = Tournament('./', 'https://www.livescores.com/soccer/euro-2020/')

# ----------------------------- DASH ---------------------------------- #


external_stylesheets=[dbc.themes.SUPERHERO]
app  = dash.Dash(__name__ , external_stylesheets=external_stylesheets)
server = app.server
app.config.suppress_callback_exceptions = True


# -------------------------- PROJECT DASHBOARD ---------------------------- #
tab1_content = dbc.Card(
    dbc.CardBody(
        [
            html.H2(
                "Standings",
                style={
                    "width": "100%",
                    "text-align": "center",
                    "padding-top": "2%",
                    "padding-bottom": "2%",
                },
            ),
            html.Div(id='scoring-table'),		
        ]
    ),
    className="mt-3",
)

tab2_content = dbc.Card(
    dbc.CardBody(
        [
            html.H2(
                "Upcoming Predictions",
                style={
                    "width": "100%",
                    "text-align": "center",
                    "padding-bottom": "2%",
                },
            ),
            html.Div(id='pred-table'),		
        ]
    ),
    className="mt-3",
)

tabs = dbc.Tabs(
    [
        dbc.Tab(tab1_content, label="Standings"),
        dbc.Tab(tab2_content, label="Upcoming Predictions"),
    ]
)

app.layout = html.Div(
    html.Div([
        html.H1('CxF Euro 2020 Pools',
                style={
                    "width": "100%",
                    "text-align": "center",
                    "padding-top": "2%",
                    "padding-bottom": "2%",
                    },
                ),
       dbc.Tabs(
            [
                dbc.Tab(tab1_content, label="Standings"),
                dbc.Tab(tab2_content, label="Upcoming Predictions"),
            ]
                ),
        dcc.Interval(
            id='scoring-interval-component',
            interval=1*60*1*1000, # in milliseconds
            n_intervals=0
        ),
        dcc.Interval(
            id='pred-interval-component',
            interval=24*60*60*1*1000, # in milliseconds
            n_intervals=0
        ),

    ])
    )


# Multiple components can update everytime interval gets fired.
@app.callback(
              Output('scoring-table', 'children'),
              Input('scoring-interval-component', 'n_intervals'))
def update_scoring_live(n):
    tournament.reload()
    df = tournament.standings
    df.index.name = 'Name'
    df = df.loc[:, (df.sum() > 0)]
    df = df.reset_index(col_fill=None)
    df.columns = df.columns.droplevel(0)
    df['Total'] = df.sum(axis=1)
    df = df.sort_index().sort_values('Total', ascending=False)
    df['Ranking'] = df.Total.rank(method='min', ascending=False)
    df = df[['Ranking'] + list(df.columns)[:-1]]
    return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True)


# Multiple components can update everytime interval gets fired.
@app.callback(
              Output('pred-table', 'children'),
              Input('pred-interval-component', 'n_intervals'))
def update_pred_live(n):
    df = tournament.predicted_scores
    df.index.name = 'Name'
    df = df.reset_index()
    return dbc.Table.from_dataframe(df, dark=True, striped=True, bordered=True, hover=True)

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=True, use_reloader=False)
