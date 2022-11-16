import requests
import random
import dateutil.parser
from bs4 import BeautifulSoup
from urllib import parse
from datetime import datetime
from collections import namedtuple

gen_score = lambda : f'{random.randint(0,3)} - {random.randint(0,3)}'
parse_min = lambda x: int(x.strip().replace("'",""))

Score = namedtuple('Score', 'id home_score away_score home_team away_team dt stage')
Stage = namedtuple('Stage', 'name scores')

def from_livescore(x):
    if x.endswith('finals'):
        x = x.title()
    else:
        x = x.replace('-',' ').title()
    x = x.replace('Of','of')
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


def extract_scores(url, gen=False):

    parsed_markup = fetch_beautiful_markup(url)
    # dictionary to contain score
    scores = {}
    # scrape needed data from the parsed markup
    for element in parsed_markup.select_one('[data-testid="match_rows-root"]').children:
        if (date_markup:= element.select_one('[data-testid^="category_header-date"]')):
            match_date = date_markup.get_text() + f' {datetime.now().year}'
        if not ( element.get('data-testid','').startswith('football_match_row')):
            continue
        match_path = element.select_one('a').get('href')
        match_stage, matchup, mid = match_path.split('/')[-4:-1]
        match_stage = from_livescore(match_stage)
        if match_stage not in scores: scores[match_stage] = {}
        home_team = from_livescore(matchup.split('-vs-')[0].strip())
        away_team = from_livescore(matchup.split('-vs-')[1].strip())
        match_dt = None


        minute = element.select_one('[data-testid^="match_row_time-status_or_time"]').get_text()
        home_score = element.select_one('[data-testid^="football_match_row-home_score"]').get_text()
        if gen: home_score = random.randint(0,4)
        if home_score == '?': home_score = None
        away_score = element.select_one('[data-testid^="football_match_row-away_score"]').get_text()
        if gen: away_score = random.randint(0,4)
        if away_score == '?': away_score = None
        match_path = parse.urljoin(url, match_path)
        if minute in ('AET', 'AP'):
            home_score, away_score = fulltime_match_score(match_path)
        elif ':' in minute:
            # game has not started
            match_dt = dateutil.parser.parse(match_date + ' ' + minute)
        elif minute != 'FT':
            try:
                minute = parse_min(minute)
                if minute > 90:
                    home_score, away_score = fulltime_match_score(match_path)
            except ValueError:
                pass
        # add our data to our dictionary
        scores[match_stage][mid] = Score(mid, home_score, away_score, home_team, away_team, match_dt, match_stage)

    return scores

def extract_competition_stages(markup):
    stages = {}
    stage_markup = markup.select_one('#leftMenu [data-active="true"]').parent.select('ul li')
    for s in stage_markup:
        s_url = s.find('a').get('href')
        s_name = s.find('span').get_text()
        stages[s_name] = s_url
    return stages
    
def fulltime_match_score(match_url):
    """
    if a match goes to extra-time we want to get only
    the score after 90 minutes.
    """
    match = fetch_beautiful_markup(match_url)
    ft_score = match.select_one('[data-testid="full_time_scores"]')
    if ft_score:
        home_score = ft_score.select_one('[data-testid="match_detail-home_score"]').get_text()
        away_score = ft_score.select_one('[data-testid="match_detail-home_score"]').get_text()
        return home_score, away_score
    else:
        return None, None


def scrape_competition_from_livescore(comp_url, gen=False):
    """
    scrape an entire compatition from livescore

    config - dict contaiing livescore config for a given tourney
    """
    comp_scores = {}
    comp_markup = fetch_beautiful_markup(comp_url)
    #comp_scores = extract_scores(comp_markup, comp_url)
    comp_stages = extract_competition_stages(comp_markup)
    
    for g_name, g_url in comp_stages.items():
        g_path = parse.urljoin(comp_url, g_url)
        g_path = parse.urljoin(g_path, '?tz=1&page=1')
        g_what = extract_scores(g_path, gen=gen)
        for stage, stage_scores in g_what.items():
            if stage not in comp_scores:
                comp_scores[stage] = stage_scores
            else:
                for mid, score in stage_scores.items():
                    if mid not in comp_scores:
                        comp_scores[stage][mid] = score

    return comp_scores

def populate_from_livescore(url, db):
    '''
    This is used to populate fixtures and scoers on an empty database
    '''
    comp_fixtures = scrape_competition_from_livescore(url)
    fixture_query = """INSERT INTO fixtures (home_team , away_team , kickoff , livescore_id, stage ) 
            VALUES (%s,%s,%s,%s,%s)"""

    for stage in comp_fixtures.values():
        for fixture in stage.values():
            # update fixtures table
            entry = (fixture.home_team, fixture.away_team, fixture.dt.strftime('%Y-%m-%d %H:%M:%S'), fixture.id, fixture.stage)
            db.query(fixture_query, entry)



def update_from_livescore(url, db, scores=True, fixtures=False):
    """
    populate the score and/or fixtures sql tables from livescore 

    for fixtures table we always want to update rows in the table
    for score table we always want to replace the current row in its entirety
    """

    comp_results = scrape_competition_from_livescore(url, gen=True)
    score_query = """REPLACE INTO score (home_score , away_score , match_id , source ) 
            VALUES (%s,%s,%s,%s)"""
    fixture_query = """UPDATE fixtures 
            SET home_team=%s, away_team=%s, 
            WHERE livescore_id=%s"""

    for stage in comp_results.values():
        for fixture in stage.values():
            match_id = db.get("fixtures","id", livescore_id=fixture.id)
            if scores:
                entry = (fixture.home_score, fixture.away_score, match_id, 'livescore')
                print(entry)
                if fixture.home_score is not None and fixture.home_score != '?':
                    db.query(score_query, entry)
            if fixtures:
                entry = (fixture.home_team, fixture.away_team, fixture.id)
                print(entry)
                db.query(fixture_query, entry)

    
code_url = 'http://www.rsssf.com/miscellaneous/fifa-codes.html'
codes = fetch_beautiful_markup(code_url)
codes = codes.pre.get_text().splitlines()
codes = [l.replace('\t', '').replace('-----','---') for l in codes if '\t' in l]
fifa_codes = {l[:-6]:l[-6:-3] for l in codes}
fifa_codes['North Macedonia'] = fifa_codes.pop('Macedonia FYR')
fifa_codes['Netherlands'] = fifa_codes.pop('Holland')
# two way mapping
fifa_codes.update({v:k for k,v in fifa_codes.items()})

if __name__ == "__main__":
    url = "https://www.livescores.com/football/world-cup/?tz=1"
    res = scrape_competition_from_livescore(url)
    print(res)