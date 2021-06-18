from datetime import datetime
from dateutil.tz import gettz

import dash
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_table
import plotly
from dash.dependencies import Input, Output
from euro_prediction import Tournament

utc = gettz('UTC')
mlt = gettz('Europe/Malta')

def to_local(dt):
    dt = dt.astimezone(utc)
    return dt.astimezone(mlt)
#------------------------------ LOAD DATA ------------------------------- #

tournament = Tournament('./', 'https://www.livescores.com/soccer/euro-2020/')

color_code = {'Group Stage': 'primary',
              'Round of 16': 'secondary',
              'Quarter-finals': 'info',
              'Semi-finals': 'danger',
              'Finals': 'warning',
              'Done': 'success'
            }

# ----------------------------- DASH ---------------------------------- #


external_stylesheets=[dbc.themes.SUPERHERO]
app  = dash.Dash(__name__ , external_stylesheets=external_stylesheets)
server = app.server
app.title = "CxF Euro 2020"
app.config.suppress_callback_exceptions = True

def get_score_cards(matches, tdy=None):
    cards = []
    row = []
    match_list = sorted(list(matches.values()), key=lambda x: x.dt)
    if tdy:
        match_list = [m for m in match_list if m.dt.date() == datetime.utcnow().date()]
    cdt = match_list[0].dt.date()
    for match in match_list: 
        if match.stage:
            col = color_code.get(match.stage, 'light')
        else:
            col = 'light'
        if match.outcome is not None:
            col = color_code['Done']
        if match.dt.date() > cdt:
            cards.append(dbc.Row(row, className="mb-4", justify='center'))
            row = []
            cdt = match.dt.date()
        if match.teams:
            header = to_local(match.dt).strftime('%d/%m/%Y @ %H:%M')
            title = match.__str__() #.replace(' ','\n').replace('-','vs')
            card_content = [
            dbc.CardHeader(header, style={'textAlign': 'center'}),
            dbc.CardBody(
                    [
                        html.H5(title, className="card-title"),
                    ],
                    style={'textAlign': 'center'}
                    ),
                ] 
            row.append(dbc.Col(dbc.Card(card_content, color=col, inverse=True, 
                className="mb-4"), width=3))

    cards.append(dbc.Row(row, className="mb-4", justify='center'))
    return cards


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

tab3_content = dbc.Card(
    dbc.CardBody(
        [
            html.H2(
                "Results and Fixtures",
                style={
                    "width": "100%",
                    "text-align": "center",
                    "padding-bottom": "2%",
                },
            ),
            html.Div(id='score-cards'),		
        ]
    ),
    className="mt-3",
)


app.layout = dbc.Container(
    html.Div([
        html.H1('CxF Euro 2020 Pools',
                style={
                    "width": "100%",
                    "text-align": "center",
                    "padding-top": "2%",
                    "padding-bottom": "2%",
                    },
                ),
        html.H2('Today\'s Matches',
                style={
                    "width": "100%",
                    "text-align": "center",
                    "padding-top": "2%",
                    "padding-bottom": "2%",
                    },
                ),
       html.Div(id = 'today-score-cards'),
       dbc.Tabs(
            [
                dbc.Tab(tab1_content, label="Standings"),
                dbc.Tab(tab2_content, label="Upcoming Predictions"),
                dbc.Tab(tab3_content, label="Results and Fixtures"),
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

    ]),
    fluid=True,
    )


# Multiple components can update everytime interval gets fired.
@app.callback(
              [
              Output('scoring-table', 'children'),
              Output('score-cards', 'children'),
              Output('today-score-cards', 'children'),
              ],
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

    score_cards = get_score_cards(tournament.actual.matches)
    live_score_cards = get_score_cards(tournament.actual.matches, tdy=True)

    return (dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True), 
            score_cards,
            live_score_cards,
           )


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
