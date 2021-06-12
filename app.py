import datetime

import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import plotly
from dash.dependencies import Input, Output
from euro_prediction import Tournament

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app  = dash.Dash(__name__) , external_stylesheets=external_stylesheets)
app.layout = html.Div(
    html.Div([
        html.H4('CxF Euro 2020 Pools'),
        html.Div(id='live-update-text'),
        dash_table.DataTable(
            id='scoring-table',
        ),
        dcc.Interval(
            id='interval-component',
            interval=5*60*1*1000, # in milliseconds
            n_intervals=0
        )
    ])
    )

tournament = Tournament('./euro2020/', 'https://www.livescores.com/soccer/euro-2020/')
#tournament = Tournament('/Users/lukeaarohi/pyfiles/EURO2020/', 'https://www.livescores.com/soccer/euro-2020/')


# Multiple components can update everytime interval gets fired.
@app.callback([
              Output('scoring-table', 'data'),
              Output('scoring-table', 'columns'),
              #Output('pred-table', 'data'),
              #Output('pred-table', 'columns'),
              ],
              Input('interval-component', 'n_intervals'))
def update_scoring_live(n):
    tournament.reload()
    df = tournament.standings
    df.index.name = 'Name'
    df = df.loc[:, (df.sum() > 0)]
    df = df.reset_index(col_fill=None)
    df.columns = df.columns.droplevel(0)
    df['Total'] = df.sum(axis=1)
    df = df.sort_index().sort_values('Total', ascending=False)
    data = df.to_dict('records')
    columns=[{'name': x, 'id': x} for x in df.columns]
    return data, columns


if __name__ == '__main__':
    app.run_server(debug=True)
