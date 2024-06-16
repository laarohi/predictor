import requests
import os
import dateutil.parser
from bs4 import BeautifulSoup
from time import time, sleep
import datetime
from collections import namedtuple
from util import config

API_KEY = os.environ["FOOTBALL_API_KEY"]
api_url = 'https://apiv3.apifootball.com'

parse_min = lambda x: int(x.strip().replace("'",""))

Score = namedtuple('Score', 'id home_score away_score home_team away_team dt stage')
Stage = namedtuple('Stage', 'name scores')

def from_fapi(x):
    if x.endswith('finals'):
        x = x.title()
    else:
        x = x.replace('-',' ').title()
    x = x.replace('Of','of')
    if x == 'Czechia':
        return 'Czech Republic'
    if x == 'Türkiye':
        return 'Turkey'
    return x


def fetch_beautiful_markup(url):
    print('fetching markup from ' + url)
    
    # try catching all possible http errors
    try :
        livescore_html = requests.get(url)
    except Exception as e :
        return print('An error occured as: ', e)

    parsed_markup = BeautifulSoup(livescore_html.text, 'html.parser')
    
    return parsed_markup

code_url = 'http://www.rsssf.com/miscellaneous/fifa-codes.html'
codes = fetch_beautiful_markup(code_url)
codes = codes.pre.get_text().splitlines()
codes = [l.replace('\t', '').replace('-----','---') for l in codes if '\t' in l]
fifa_codes = {l[:-6]:l[-6:-3] for l in codes}
fifa_codes['North Macedonia'] = fifa_codes.pop('Macedonia FYR')
fifa_codes['Netherlands'] = fifa_codes.pop('Holland')
fifa_codes['Usa'] = fifa_codes.pop('United States of America')
fifa_codes['South Korea'] = fifa_codes.pop('Korea Republic')
fifa_codes['Australia'] = 'AUS'
# two way mapping
fifa_codes.update({v:k for k,v in fifa_codes.items()})

group_map = {t:k for k,v in config['groups'].items() for t in v}

def get_scores(league_id, stage=None, start='2024-06-14', stop='2024-07-15', live=False):
    
    scores = {}
    params = {
        'action':'get_events',
        'from':start,
        'to':stop,
        'league_id': league_id,
        'APIkey': API_KEY,
        'match_live':int(live)
    }
    r = requests.get(api_url, params)
    for match in r.json():
        mid = match['match_id']
        home_team = from_fapi(match['match_hometeam_name'])
        away_team = from_fapi(match['match_awayteam_name'])
        match_stage = from_fapi(match['stage_name'])
        if stage and stage != match_stage:
            continue
        if match_stage == 'Group Stage':
            match_stage = 'Group ' + group_map[home_team]
            print(match_stage)
        if match_stage not in scores: scores[match_stage] = {}
        match_date = match['match_date']
        match_time = match['match_time']
        match_dt = dateutil.parser.parse(match_date + ' ' + match_time)
        if match.get('match_live'):
            home_score = match['match_hometeam_score'] or None
            away_score = match['match_awayteam_score'] or None
        else:
            home_score = match['match_hometeam_ft_score'] or None
            away_score = match['match_awayteam_ft_score'] or None
        scores[match_stage][mid] = Score(mid, home_score, away_score, home_team, away_team, match_dt, match_stage)
    return scores


def populate_from_fapi(league_id, db):
    '''
    This is used to populate fixtures and scores on an empty database
    '''
    comp_fixtures = get_scores(league_id)
    fixture_query = """INSERT INTO fixtures (home_team , away_team , kickoff , livescore_id, stage ) 
            VALUES (%s,%s,%s,%s,%s)"""

    for stage in comp_fixtures.values():
        for fixture in stage.values():
            # update fixtures table
            print(fixture)
            entry = (fixture.home_team, fixture.away_team, fixture.dt.strftime('%Y-%m-%d %H:%M:%S'), fixture.id, fixture.stage)
            db.query(fixture_query, entry)



def update_from_fapi(league_id, db, live=False, scores=True, fixtures=False):
    """
    populate the score and/or fixtures sql tables from footballapi

    for fixtures table we always want to update rows in the table
    for score table we always want to replace the current row in its entirety
    """

    comp_results = get_scores(league_id, live=live)

    score_query = """REPLACE INTO score (home_score , away_score , match_id , source ) 
            VALUES (%s,%s,%s,%s)"""
    fixture_query = """UPDATE fixtures 
            SET home_team=%s, away_team=%s
            WHERE livescore_id=%s"""

    print(comp_results)
    for stage in comp_results.values():
        for fixture in stage.values():
            if not fixtures and (fixture.home_score is None or fixture.home_score == '?'):
                continue
            match_id = db.get("fixtures","id", livescore_id=fixture.id)
            if scores:
                entry = (fixture.home_score, fixture.away_score, match_id, 'footballapi')
                print(entry)
                if fixture.home_score is not None and fixture.home_score != '?':
                    db.query(score_query, entry)
            if fixtures:
                entry = (fixture.home_team, fixture.away_team, fixture.id)
                db.query(fixture_query, entry)


def main(league_id, db, update_interval, rescrape_interval, phase2_deadline):
    last_update = time()
    last_rescrape = time()
    # phase2_locked = time() > phase2_deadline
    while True:
        if not (datetime.time(16) < datetime.datetime.now().time() < datetime.time(23,30)):
            pass
        elif (time() - last_rescrape) > rescrape_interval:
            print('Rescraping entire competition from livescore')
            last_rescrape = time()
            update_from_fapi(league_id, db, scores=True, fixtures=True)
        elif (time() - last_update) > update_interval:
            print('Updating scores from livescore')
            last_update = time()
            update_from_fapi(league_id, db, live=True, scores=True, fixtures=False)

        print('sleeping for ',update_interval)
        sleep(update_interval)
        
        # if not phase2_locked and (time() > phase2_deadline):
        #     from util import build_services, get_creds, lock_prediction_sheet, update_predictions_db
        #     token = os.environ.get("GOOGLE_APP_TOKEN", "google_token.json")
        #     creds_file = os.environ.get("GOOGLE_APP_CREDENTIALS", "google_credentials.json")
        #     creds = get_creds(token, creds_file)
        #     services = build_services(creds)
        #     sheets = services['sheets']
        #     try:
        #         lock_prediction_sheet(sheets, db, 2)
        #     except:
        #         pass
        #     try:
        #         update_predictions_db(sheets, db, 2)
        #     except:
        #         pass
        
if __name__ == "__main__":
    from util import DB, config
    league_id = config['footballapi']['league_id']
    update_interval = config['footballapi']['interval']['update']
    rescrape_interval = config['footballapi']['interval'].get('rescrape', 1e12)
    phase2_deadline = config['deadline']['Phase 2'].timestamp()
    db = DB(config['sql'])
    # update_from_fapi(league_id, db, True, True)
    main(league_id, db, update_interval, rescrape_interval, phase2_deadline)
