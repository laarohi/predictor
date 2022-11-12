import re
import os
from datetime import datetime
from dateutil.tz import gettz

import MySQLdb
import yaml
import dash
from dash import dcc, ctx, html
import dash_bootstrap_components as dbc
from pandas import DataFrame
from dash.dependencies import Input, Output, State
#from predictor import Tournament
from sheet import gen_entry, build_services, get_creds

utc = gettz('UTC')
mlt = gettz('Europe/Malta')

#------------------------------ HELPER FUNCTIONS ------------------------------- #

col_ordering = ['Ranking','Name', 'Group Stage', 'Round of 16', 'Quarter-Finals', 'Semi-Finals', 
                'Final', 'Winner', 'Bonus', 'Total']

def to_local(dt):
    dt = dt.astimezone(utc)
    return dt.astimezone(mlt)

def prep_standings(df):
    df['Total'] = df.sum(axis=1)
    df = df.sort_index().sort_values('Total', ascending=False)
    df['Ranking'] = df.Total.rank(method='min', ascending=False)
    df = df.reset_index()
    cols = [col for col in col_ordering if col in df.columns]
    df = df[cols]
    tbl = dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True)
    return tbl
#------------------------------ LOAD DATA ------------------------------- #

with open('./tournaments/worldcup2022/metadata.yml', 'r') as f:
    config = yaml.load(f)

#tournament = Tournament('./', 'https://www.livescores.com/soccer/euro-2020/')

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
app.title = config['tournament']
app.config.suppress_callback_exceptions = True
user = config['sql']['user']
passwd = config['sql']['passwd']
db = config['sql']['db']
user = os.environ.get(user, user)
passwd = os.environ.get(passwd, passwd)
db = os.environ.get(db, db)
db = MySQLdb.connect(passwd=passwd, user=user, db='wc2022')
creds = get_creds()
services = build_services(creds)
template_id = config['google_api']['template_id']
folder_id = config['google_api']['folder_id']

def get_score_cards(matches, tdy=None):
    cards = []
    row = []
    match_list = sorted(list(matches.values()), key=lambda x: x.dt)
    if tdy:
        match_list = [m for m in match_list if m.dt.date() == datetime.utcnow().date()]
    if not match_list:
        return cards
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
            body = []
            if False: #match.live:
                body.append(dbc.Col(dbc.Spinner(color='success', type='grow'), width=1))
            body.append(dbc.Col(html.H5(title, className="card-title"))),
            card_content = [
            dbc.CardHeader(header, style={'textAlign': 'center'}),
            dbc.CardBody(
                    dbc.Row(body),
                    style={'textAlign': 'center'}
                    ),
                ] 
            row.append(dbc.Col(dbc.Card(card_content, color=col, inverse=True, 
                className="mb-4"), width=3))

    cards.append(dbc.Row(row, className="mb-4", justify='center'))
    return cards


# -------------------------- PROJECT DASHBOARD ---------------------------- #
rules_tab_content = dbc.Card(
    dbc.CardBody(
        [
            dbc.Row(className='', children=[
                dbc.Col([
                    html.H2(
                        "Rules and Point System",
                        style={
                            "width": "100%",
                            "text-align": "center",
                            "padding-bottom": "2%",
                        },
                    ),
            ], lg='12')
            ]),
            dbc.Row( children=[
                dbc.Col(
                    [
                        dbc.Card([
                            dbc.CardBody(className='card-text', children=[
                                html.H4('Phase I', className='card-title'),
                                html.P('Deadline: 3pm on Sunday 20th November 2022',className='card-text'),
                                html.Hr(),
                                html.P("These predictions will be made before the start of the competition."
                                "One must predict the results of all the group stage games as well as their "
                                "competition Semi-Finalists, Finalists and Winners."
                                 " There are a number of bonus questions for extra points."),
                                html.Hr(),
                                html.H5("Point System"),
                                html.Ul(children=[
                                    html.Li("5 pts for correct result: 1-X-2 OR 15 pts for correct score (Group Stage Only)"),
                                    html.Li("10 pts for each correct Round of 16 team"),
                                    html.Li("5 pts for each correct group stage position of qualified teams"),
                                    html.Li("30 pts for each correct Semi Finalist",),
                                    html.Li("50 pts for each correct Finalist",),
                                    html.Li("75 pts for the correct Winner",),
                                    html.Li("15 pts for each correct group stage bonus question",),
                                    html.Li("20 pts for each correct knockout stage bonus question",),
                                ])
                            ]),
                        ], style={'width': ''})
                    ], lg='6'),
                dbc.Col(
                    [
                        dbc.Card([
                            dbc.CardBody(className='card-text', children=[
                                html.H4('Phase II', className='card-title'),
                                html.P('Deadline: 2pm on Saturday 3rd December 2022',className='card-text'),
                                html.Hr(),
                                html.P("These predictions will be made between the end of the group stage and the start of the knockout stage."
                                "One must fill out their knockout bracket for the rest of the tournament."
                                 "Points for the correct score are only given if both teams are predicted correctly."),
                                html.Hr(),
                                html.H5("Point System"),
                                html.Ul(children=[
                                    html.Li("10 pts for correct score (only if teams are predicted correctly)"),
                                    html.Li("10 pts for each correct Quarter Finalist",),
                                    html.Li("20 pts for each correct Semi Finalist",),
                                    html.Li("30 pts for each correct Finalist",),
                                    html.Li("50 pts for the correct Winner",),
                                ])
                            ]),
                        ], style={'width': ''})

                    ], lg='6'),
            ],
            class_name='row gy-2'),
            dbc.Row( children=[
                dbc.Col([
                        dbc.Card([
                            dbc.CardBody(className='card-text', children=[
                                html.H4('Prize Split', className='card-title'),
                                html.P("The actual prize split will be updated once the price pool is known but the prize split will be as follows:"),
                                html.Ul(children=[
                                    html.Li("60/% to Overall Winner"),
                                    html.Li("20/% to Overall Runner Up"),
                                    html.Li("10/% to Group Stage Winner"),
                                    html.Li("10/% to Phase II Winner"),
                                ])
                            ]),
                        ], style={'width': ''})
                    ], lg='12'),
            ],
            class_name='row gy-2'),
       ],
    ),
    className="mt-3",
)

name_input = html.Div(
    [
        dbc.Label("Name", html_for="name-form"),
        dbc.Input(type="name", id="name-form", placeholder="Enter name"),
    ],
    className="mb-3",
)
surname_input = html.Div(
    [
        dbc.Label("Surname", html_for="surname-form"),
        dbc.Input(type="surname", id="surname-form", placeholder="Enter surname"),
    ],
    className="mb-3",
)
email_input = html.Div(
    [
        dbc.Label("Email", html_for="email-form"),
        dbc.Input(type="email", id="email-form", placeholder="Enter email"),
        dbc.FormText(
            "A google adress is preferable but any email will work.",
            color="secondary",
        ),
        dbc.FormFeedback(
            "Please enter a valid email address...",
            type="invalid",
        ),
    ],
    className="mb-3",
)

# eventually the options should come from sql
competition_input = html.Div(
    [
        dbc.Label("Competition", html_for="competition-form"),
        dbc.Select(
                    options=[
                        {"label": "Main Competition (€25)", "value": 1},
                        {"label": "Ta' Giorni Wanderers (€10)", "value": 2},
                    ],
                    id="competition-form"
        ),
    ],
    className="mb-3",
)

form_button = html.Div(id='div-submit-form', className="d-grid gap-2", children=[ 
       dbc.Button("Submit", id='submit-button', color="primary", n_clicks=0),
       html.Br(),
       dcc.Loading(
           [
            dbc.Alert(
                [
                    html.H4("Sign up successful!", className="alert-heading"),
                    html.P(
                        "The next step is to check your email for an invitation link"
                        " to your google sheet which must be completed by Sunday 20th November @ 3pm."
                    ),
                    html.Hr(),
                    html.P(
                        [
                            "Lastly to confirm your entry you must send me your entry fee via Revolut.",
                            html.Br(),
                            "If you are on mobile ",
                            html.A(
                                "click here.", 
                                href="https://revolut.me/laarohi", 
                                className="alert-link",
                                target="_blank",
                            ),
                            " Otherwise my number is +356 99290197.",
                        ],
                        className="mb-0",
                    ),
                ],
                id='submit-success-alert',
                is_open=False,
                color='success',
            ),
            dbc.Alert(
                [
                    html.H4("Sign up Error!", className="alert-heading"),
                    html.P(
                        id="alert-error-text"
                    ),
                ],
                id='submit-fail-alert',
                is_open=False,
                color='danger',
            ),
           ]
       ),
   ]
)

form = dbc.Form([
    dbc.Row([
        dbc.Col([name_input], lg='6'),
        dbc.Col([surname_input], lg='6'),
    ]),
    email_input, 
    competition_input, 
    form_button], 
    id='signup-form')

form = dbc.Row(
    [
        dbc.Col([form], lg='4', md='8', sm='12'),
    ],
    align="center",
    justify="center",
    )

@app.callback(
    Output("submit-success-alert", "is_open"),
    Output("submit-fail-alert", "is_open"),
    Output("alert-error-text", "children"),
    Input("submit-button", "n_clicks"),
    Input("name-form", "value"),
    Input("surname-form", "value"),
    Input("email-form", "value"),
    Input("competition-form", "value"),
    Input("email-form", "valid"),
    State("submit-success-alert", "is_open"),
)
def handle_form(n_clicks, name, surname, email, competition, valid_email, is_success):
    """
    submit entry to db and generate link
    """
    tid = ctx.triggered_id
    if not tid or tid != "submit-button" or not n_clicks:
        return False, False, ""
    elif is_success:
        return True, False, ""
    else:
        # attempt to submit
        if not all([name, surname, email, competition, valid_email]):
            error_msg = 'Missing input, please fill in all your details and try again.'
            return False, True, error_msg
        full_name = name.strip().capitalize() + ' ' + surname.strip().capitalize()
        email = email.strip().lower()

        try:
            gen_entry(services, full_name, email, competition, db, 
                    template_id, folder_id, config['tournament'])
            return True, False, ""
        except Exception as e:
            return False, True, str(e)



    
signup_tab_content = dbc.Card(
    dbc.CardBody(
        [
            html.H2(
                "Sign Up",
                style={
                    "width": "100%",
                    "text-align": "center",
                    "padding-bottom": "2%",
                },
            ),
            form, 
        ]
    ),
    className="mt-3",
)

standings_tab_content = dbc.Card(
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

score_pred_tab_content = dbc.Card(
    dbc.CardBody(
        [
            html.H2(
                "Upcoming Predicted Scores",
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

team_pred_tab_content = dbc.Card(
    dbc.CardBody(
        [
            html.H2(
                "Predicted Teams",
                style={
                    "width": "100%",
                    "text-align": "center",
                    "padding-bottom": "2%",
                },
            ),
            html.Div(id='pred-team-table'),		
        ]
    ),
    className="mt-3",
)

result_tab_content = dbc.Card(
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
        html.H1(config['tournament'],
                style={
                    "width": "100%",
                    "text-align": "center",
                    "padding-top": "2%",
                    "padding-bottom": "2%",
                    },
                ),
        #html.H2('Today\'s Matches',
        #        style={
        #            "width": "100%",
        #            "text-align": "center",
        #            "padding-top": "2%",
        #            "padding-bottom": "2%",
        #            },
        #        ),
       #html.Div(id = 'today-score-cards'),
       dbc.Tabs(
            [
                dbc.Tab(rules_tab_content, label="Rules and Point System"),
                dbc.Tab(signup_tab_content, label="Sign Up"),
                #dbc.Tab(standings_tab_content, label="Standings"),
                #dbc.Tab(score_pred_tab_content, label="Upcoming Predicted Scores"),
                #dbc.Tab(team_pred_tab_content, label="Predicted Teams"),
                #dbc.Tab(result_tab_content, label="Results and Fixtures"),
                # add a tab with the rules and points system
            ]
                ),
        #dcc.Interval(
        #    id='scoring-interval-component',
        #    interval=1*60*1*1000, # in milliseconds
        #    n_intervals=0
        #),
        #dcc.Interval(
        #    id='pred-interval-component',
        #    interval=24*60*60*1*1000, # in milliseconds
        #    n_intervals=0
        #),

    ]),
    fluid=True,
    )

# --- Callbacks --- #
@app.callback(
    [Output("email-form", "valid"), Output("email-form", "invalid")],
    [Input("email-form", "value")],
)
def check_validity(email):
    if email:
        regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        is_valid = bool(re.fullmatch(regex, email))
        return is_valid, not is_valid
    return False, False

'''
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
    p_tabs = []
    # Compute overall standings
    o_df = df.groupby(level=1, axis=1).sum()
    o_tbl = prep_standings(o_df)
    tab = dbc.Tab(dbc.Card(dbc.CardBody([o_tbl]),className="mt-3"),
                            label='Overall')
    p_tabs.append(tab)
    for phase in df.columns.get_level_values(0).unique():
        p_tbl = prep_standings(df[phase].copy())
        tab = dbc.Tab(dbc.Card(dbc.CardBody([p_tbl]),className="mt-3"),
                                label=phase)
        p_tabs.append(tab)

    score_cards = get_score_cards(tournament.actual.matches)
    live_score_cards = get_score_cards(tournament.actual.matches, tdy=True)

    return (dbc.Tabs(p_tabs), 
            score_cards,
            live_score_cards,
           )


# Multiple components can update everytime interval gets fired.
@app.callback(
              Output('pred-table', 'children'),
              Input('pred-interval-component', 'n_intervals'))
def update_pred_scores_live(n):
    df = tournament.predicted_scores
    df.index.name = 'Name'
    df = df.reset_index()
    return dbc.Table.from_dataframe(df, dark=True, striped=True, bordered=True, hover=True)

@app.callback(
              Output('pred-team-table', 'children'),
              Input('pred-interval-component', 'n_intervals'))
def update_pred_teams_live(n):
    df = tournament.predicted_teams
    p_tabs = []
    for phase in df.columns.get_level_values(0).unique():
        pdf = df[phase]
        s_tabs = []
        for stage in pdf.columns:
            if stage == 'Round of 16': continue
            stage_s = pdf[stage]
            cols = [stage + ' ' + str(i) for i in range(1, len(stage_s[0])+1)]
            sdf = DataFrame.from_dict(dict(zip(df.index, stage_s.values)), orient='index', columns=cols)
            sdf.index.name = 'Name'
            sdf = sdf.reset_index()
            s_table = dbc.Table.from_dataframe(sdf,
                        dark=True, striped=True, bordered=True, hover=True)
            tab = dbc.Tab(dbc.Card(dbc.CardBody([s_table]),className="mt-3"),
                            label=stage)
            s_tabs.append(tab)

        stage_tabs = dbc.Tabs(s_tabs)
        tab = dbc.Tab(dbc.Card(dbc.CardBody([stage_tabs]),className="mt-3"),
                            label=phase)
        p_tabs.append(tab)
    phase_tabs = dbc.Tabs(p_tabs)
    return phase_tabs 
'''


if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=True,) # use_reloader=False)
