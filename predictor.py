#!/usr/bin/env python

# ### Euro 2020 Prediction Game
# 
# For the euro 2020 prediction game my idea is to do all the score keeping in python. Read the excel data into a python class. The class would contain some nicely organised data structure to store the predictions. 
# 
# 
# Idea:
# 
# - class Bracket:
#     - load from excel; phase I and phase II are two seperate sheets
#     - group_stage dict {mid:score}
#     - knockout_phase:
#         - phase I:
#             - l16: list of tuples ('Team', 'rank')
#             - sf: list
#             - f: list
#             - bonus: list
#         - phase II:
#             - qf: list
#             - sf: list
#             - f: list
# 
# Checklist to get done:
# DONE - make sure that score can be computed correctly from comparison of livescore bracket and player bracket
# DONE - finalise classes
# DONE - pretty print html format for scoring table
# DONE - pretty print html format for player scores
# DONE - figure out flask and how to host
# DONE - make use of metadata.yml for scoring system points
# - prepare phase II excel sheet
# - fix round of 16 scoring in livescore scraper somehow need to know where each team finished in their group. Might be easier to just 
# - fix astericks scoring for knockout phase in excel and python
# - set then unordered tuple then ordered for teams
# - make table sortable by column
# 


import requests
import os
import re
import random
import time
from bs4 import BeautifulSoup
from urllib import parse
from collections import Counter
from datetime import datetime

import yaml
import pandas as pd

gen_score = lambda : f'{random.randint(0,3)} - {random.randint(0,3)}'
parse_min = lambda x: int(x.strip().replace("'",""))


def from_livescore(x):
    if x.endswith('finals'):
        x = x.title()
    else:
        x = x.replace('-',' ').title()
    if x.startswith('Group'):
        return 'Group Stage'
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


def extract_scores(parsed_markup, url, id_map, order_map={}, stage=None):
    # dictionary to contain score
    scores = {}

    # scrape needed data from the parsed markup
    for element in parsed_markup.select('[data-testid|="football_match_row"]') :
        match_path = element.select_one('a').get('href')
        match_stage, matchup, ls_id = match_path.split('/')[-4:-1]
        match_stage = from_livescore(match_stage)
        home_team = from_livescore(matchup.split('-vs-')[0].strip())
        away_team = from_livescore(matchup.split('-vs-')[1].strip())

        # this needs to be linked to sql now
        try:
            mid = id_map[ls_id]
        except KeyError:
            try:
                mid = fifa_codes[home_team] + '.' + fifa_codes[away_team]
            except KeyError:
                mid = ls_id
        minute = element.select_one('[data-testid~="status_or_time"]').get_text()
        home_score = element.select_one('[data-testid^="football_match_row-home_score"]').get_text()
        away_score = element.select_one('[data-testid^="football_match_row-away_score"]').get_text()
        score = home_score + '-' + away_score
        match_path = parse.urljoin(url, match_path)
        if minute in ('AET', 'AP'):
            score = fulltime_match_score(match_path)
        elif minute != 'FT':
            try:
                minute = parse_min(minute)
                if minute > 90:
                    score = fulltime_match_score(match_path)
            except ValueError:
                pass
        # add our data to our dictionary
        scores[match_stage][mid] = Score(mid, score, teams, match_dt, stage=match_stage)

       # ---------------------- OLD WAY ------------------------------ 
        match_name_element = element.find(attrs={"class": "scorelink"})
        ls_id = int(element.get('data-e id'))
        match_dt = element.get('data-esd')
        if match_dt:
            match_dt = datetime.strptime(match_dt, '%Y%m%d%H%M%S')
        order = order_map.get(ls_id, None)

        if match_name_element is not None :
            # this means the match is about to be played
            match_path = match_name_element.get('href')
            match_stage, matchup = match_path.split('/')[3:5]
            match_stage = from_livescore(match_stage)
            if match_stage not in scores: scores[match_stage] = {}
            home_team = from_livescore(matchup.split('-vs-')[0].strip())
            away_team = from_livescore(matchup.split('-vs-')[1].strip())
            try:
                mid = id_map[ls_id]
            except KeyError:
                try:
                    mid = fifa_codes[home_team] + '.' + fifa_codes[away_team]
                except KeyError:
                    mid = ls_id


            teams = (home_team, away_team)
            if order:
                teams = tuple(zip(teams, order))
            score = element.find("div", "sco").get_text().strip()
            minute = element.find("div", "min").get_text().strip()
            match_path = parse.urljoin(url, match_path)
            if minute in ('AET', 'AP'):
                score = fulltime_match_score(match_path)
            elif minute != 'FT':
                try:
                    minute = parse_min(minute)
                    if minute > 90:
                        score = fulltime_match_score(match_path)
                except:
                    pass
            # add our data to our dictionary
            scores[match_stage][mid] = Score(mid, score, teams, match_dt, stage=match_stage)

        elif stage:
            if stage not in scores: scores[stage] = {}
            # we need to use a different method to get our data
            home_team = '-'.join(element.find("div", "tright").get_text().strip().split(" "))
            away_team = '-'.join(element.find(attrs={"class": "ply name"}).get_text().strip().split(" "))
            try:
                mid = id_map[ls_id]
            except KeyError:
                try:
                    mid = fifa_codes[home_team] + '.' + fifa_codes[away_team]
                except KeyError:
                    mid = ls_id

            score = element.find("div", "sco").get_text().strip()
            minute = element.find("div", "min").get_text().strip()

            teams = (home_team, away_team)
            if order:
                teams = tuple(zip(teams, order))

            # add our data to our dictionary
            scores[stage][mid] = Score(mid, score, teams, match_dt, stage=stage)

    return scores

def extract_competition_stages(markup, comp):
    stages = {}
    selected_cat = markup.find('aside', 'left-bar').find('ul','buttons btn-light').find('a',{'class':'selected cat'})
    stage_refs = selected_cat.parent.find_all('a', attrs={'href':re.compile(comp+'.*/')})
    for g in stage_refs:
        g_url = g.get('href')
        g_name = g.get('title')
        stages[g_name] = g_url
    
    return stages
    

def fulltime_match_score(match_url):
    """
    if a match goes to extra-time we want to get only
    the score after 90 minutes.
    """
    match = fetch_beautiful_markup(match_url)
    score = '0 - 0'
    for goal in match.find_all(attrs={'class':'inc goal'}, recursive=True):
        event_elements = goal.parent.parent.parent
        try:
            minute = parse_min(event_elements.find('div','min').get_text().strip())
            if minute <= 90:
                score = event_elements.find('div', 'sco').get_text().strip()
        except:
            pass
    return score


def scrape_scores_from_livescore(config, stage) :
    """
    scores scores for a given stage from livescore
    
    config - dict containing livescore config for given tourney
    """
    comp_url = parse.urljoin(config['url'], config['comp_key'])
    id_map = config['id_map']
    order_map = config['order_map']
    parsed_markup = fetch_beautiful_markup(comp_url)
    scores = extract_scores(parsed_markup, comp_url, id_map, order_map, stage)
    return scores


def scrape_competition_from_livescore(config):
    """
    scrape an entire compatition from livescore

    config - dict contaiing livescore config for a given tourney
    """
    comp_url = parse.urljoin(config['url'], config['comp_key'])
    id_map = config['id_map']
    order_map = config['order_map']
    res = {}
    comp = parse.urlparse(comp_url).path
    comp_markup = fetch_beautiful_markup(comp_url)
    comp_scores = extract_scores(comp_markup, comp_url, order_map, id_map)
    comp_stages = extract_competition_stages(comp_markup, comp)
    
    for g_name, g_url in comp_stages.items():
        g_path = parse.urljoin(comp_url, g_url)
        for what in ['results/all/', 'fixtures/all/']:
            what_path = parse.urljoin(g_path, what)
            g_what = scrape_scores_from_livescore(what_path, g_name)
            for stage, stage_scores in g_what.items():
                if stage not in comp_scores:
                    comp_scores[stage] = stage_scores
                else:
                    for mid, score in stage_scores.items():
                        if mid not in comp_scores:
                            comp_scores[stage][mid] = score
    
    for stage, stage_scores in comp_scores.items():
        res[stage] = Stage(stage, stage_scores)
        
    return res


def update_scrape_from_livescore(comp_scores, config):
    """
    update comp_scores from livescore

    config - dict contaiing livescor4e config for a given tourney
    """
    comp_url = parse.urljoin(config['url'], config['comp_key'])
    id_map = config['id_map']
    order_map = config['order_map']
    comp_markup = fetch_beautiful_markup(comp_url)
    new_scores = extract_scores(comp_markup, comp_url, id_map, order_map)
    for stage, stage_scores in new_scores.items():
        if stage in comp_scores:
            scores = comp_scores[stage].matches
            scores.update(stage_scores)
            comp_scores[stage] = Stage(stage, scores)
    return comp_scores
        
    
code_url = 'http://www.rsssf.com/miscellaneous/fifa-codes.html'
codes = fetch_beautiful_markup(code_url)
codes = codes.pre.get_text().splitlines()
codes = [l.replace('\t', '').replace('-----','---') for l in codes if '\t' in l]
fifa_codes = {l[:-6]:l[-6:-3] for l in codes}
fifa_codes['North Macedonia'] = fifa_codes.pop('Macedonia FYR')
fifa_codes['Netherlands'] = fifa_codes.pop('Holland')
# two way mapping
fifa_codes.update({v:k for k,v in fifa_codes.items()})


class Score():
    def __init__(self, mid, score, teams=None, dt=None, stage=None, live=False, use_code=False):
        self.mid = mid
        self.home = None
        self.away = None
        self.score = None
        self.teams = None
        self.outcome = None
        self.dt = None
        self.stage = stage
        self.live = live
                
        if teams:
            self.teams = tuple(teams)
            try:
                if isinstance(teams[0], tuple):
                    self.teams = tuple([(fifa_codes[team[0]], team[1]) for team in self.teams])
                else:
                    self.teams = tuple([fifa_codes[team] for team in self.teams])
                if use_code:
                    self.mid =  self.teams[0] + '.' + self.teams[1]
            except KeyError:
                pass

        if dt:
            self.dt = dt
        if isinstance(score, str):
            if '?' in score:
                # handling livescore future game score
                #print(f'No score yet for {self.teams}')
                return
            if '*' in score:
                o = score.find('*') - score.find('-')
                if o > 0:
                    self.outcome = 2
                elif o < 0:
                    self.outcome = 1
                score = score.replace('*','')

            score = score.replace(' ','').split('-')

                
        if isinstance(score, (list, tuple)) and len(score)==2:
            self.score = tuple(score)
            self.home = int(float(score[0]))
            self.away = int(float(score[1]))
        else:
            raise TypeError('unknown score format')
            
        # 1 - home_win; 0 - draw; 2 - away_win
        if self.outcome is None:
            self.outcome = (self.home != self.away) + (self.away>self.home)
        return 

        
    def __str__(self):
        if self.score:
            if self.teams:
                if isinstance(self.teams[0], tuple):
                    teams = [t[0] for t in self.teams]
                else:
                    teams = self.teams
                return f"{teams[0]} {self.home}-{self.away} {teams[1]}"
            else:
                return f"{self.home}-{self.away}"
        else:
            if self.teams:
                if isinstance(self.teams[0], tuple):
                    teams = [t[0] for t in self.teams]
                else:
                    teams =  self.teams
                return f'{teams[0]} ? - ? {teams[1]}'
            else:
                return f'{self.mid}: ? - ?'
    
    @property
    def matchup(self):
        if self.teams:
            if isinstance(self.teams[0], tuple):
                teams = [t[0] for t in self.teams]
            else:
                teams = self.teams
            return f'{teams[0]} vs {teams[1]}'
    
    @property
    def winner(self):
        if self.outcome and self.teams:
            return self.teams[self.outcome-1]
        else:
            return None
    
    @property
    def goal_count(self):
        if self.teams and self.score:
            return {team:int(goals) for team, goals in zip(self.teams, self.score)}
        else:
            return None
        
    def compute(self, other, outcome=5, result=15):
        #if self.teams and other.teams and (self.teams != other.teams):
        #    return 0
        if self.score == other.score:
            return result
        elif self.outcome == other.outcome:
            return outcome
        else:
            return 0

        
class Stage():
    def __init__(self, name, matches=None, teams=None, outcome=None, result=None, qualified=None, ordering=None):
        '''
        matches - a dict of matches and the corresponding scores scores could be in string or Score format
        teams - a list of teams who qualified for this stage
        '''
        self.name = name
        self.matches = None
        self.teams = None
        self.outcome = outcome or 0
        self.result = result or 0
        self.qualified = qualified or 0
        self.ordering = ordering or 0
        if matches:
            test_match = list(matches.values())[0]
            if isinstance(test_match, str):
                self.matches = {k:Score(k, v, stage=self.name) for k,v in matches.items()}
            elif isinstance(test_match, Score):
                self.matches = matches
            else:
                raise TypeError('Unrecognised matches format')
            if not teams:
                match_teams = []
                for match in self.matches.values():
                    if match.teams:
                        match_teams += list(match.teams)
                if match_teams and isinstance(match_teams[0], str):
                    match_teams = [fifa_codes.get(team.title(), team) for team in match_teams]
                self.teams = set(match_teams) or None
        if teams:
            if isinstance(teams, tuple):
                if isinstance(teams[0], str):
                    try:
                        teams = tuple([fifa_codes.get(team.title(), team) for team in teams])
                    except KeyError:
                        pass
                elif isinstance(teams[0], tuple):
                    try:
                        teams = tuple([(fifa_codes.get(team[0].title(), team[0]), team[1])
                                        for team in teams])
                    except KeyError:
                        pass
                self.teams = teams
            elif isinstance(teams, (list, set)):
                if isinstance(list(teams)[0], str):
                    try:
                        teams = tuple([fifa_codes.get(team.title(), team) for team in teams])
                    except KeyError:
                        pass
                elif isinstance(list(teams)[0], tuple):
                    try:
                        teams = tuple([(fifa_codes.get(team[0].title(), team[0]), team[1])
                                        for team in teams])
                    except KeyError:
                        pass
                self.teams = set(teams)
        
    @property
    def winners(self):
        if self.matches:
            return set([match.winner for match in self.matches.values()])
        else:
            return None
    
    @property
    def highest_scoring_team(self):
        count = Counter()
        if self.matches:
            for match in self.matches.values():
                count.update(match.goal_count)
        if len(count):
            return count.most_common()[0][0]
        else:
            return None
            

    def team_compare(self, other):
        '''
        compare teams in a to teams in b and score points accordingly
        
        a and b must be sets of teams
        '''
        pts = 0
        if isinstance(self.teams, (list, tuple)):
            correct_qualified = sum([a==b for a,b in zip(self.teams, other.teams)])
        elif isinstance(self.teams, set):
            correct_qualified = len(self.teams.intersection(other.teams))
            
            if self.teams and self.ordering and isinstance(list(self.teams)[0], tuple):
                correct_ordering = correct_qualified
                my_teams = set([t[0] for t in self.teams])
                other_teams = set([t[0] for t in other.teams])
                correct_qualified = len(my_teams.intersection(other_teams))
                pts += correct_ordering * self.ordering
            
        pts += correct_qualified * self.qualified
        
        return pts
        

    def compute(self, other):
        points = 0
        if self.matches:
            missing_matches = set(self.matches.keys()) - set(other.matches.keys())
            #if missing_matches:
            #    print(f'Warning missing matches! {missing_matches}')
            for mid, match in self.matches.items():
                if mid in other.matches:
                    points += match.compute(other.matches[mid], self.outcome, self.result)
        
        if self.teams:
            points += self.team_compare(other)
            
        return points
    
    def get_upcoming_scores(self, other):
        matches = {}
        if self.matches:
            missing_matches = set(self.matches.keys()) - set(other.matches.keys())
            #if missing_matches:
            #    print(f'Warning missing matches! {missing_matches}')
            for mid, match in self.matches.items():
                other_match = other.matches.get(mid)
                if other_match and (-2 <= (other_match.dt.date() - datetime.now().date()).days <= 4):
                    matches[other_match.matchup] = match.__str__()
        return matches
        
    def get_teams(self):
        if self.teams:
            if isinstance(self.teams, set):
                teams = sorted(list(self.teams))
            else:
                teams = list(self.teams)
                if isinstance(teams[0], str):
                    return [t.split()[-1].title() for t in teams]
            return teams
            

            
class Bracket():
    
    def __init__(self, name, workdir, scoring=None, phase=1):
        '''
        load bracket from excel or pkl
        
        maybe specify name and dir or something along those lines
        '''
        self.name = name
        self.dat = {}
        if phase == 1:
            self.phase = 'Phase I'
            self.scoring = scoring.get(self.phase, None)
            pkl_file_1 = os.path.join(workdir,'phase_I', name + '.pkl')
            xlsx_file_1 = os.path.join(workdir,'phase_I','CxFPoolsEuro2020_PhaseI_'+ name + '.xlsx')
            if os.path.exists(pkl_file_1):
                self.dat = pkl_load(pkl_file_1)
            elif os.path.exists(xlsx_file_1):
                dat = pd.read_excel(xlsx_file_1, sheet_name='INTERNAL_USE_ONLY').iloc[:,0].values
                self.dat['Group Stage'] = Stage(name='Group Stage',matches={i+1:m for i,m in enumerate(dat[1:37])}, **self.scoring['Group Stage'])
                self.dat['Round of 16'] = Stage(name='Round of 16', teams=list(zip(dat[38:54], [1,2]*6 + [3]*4)), **self.scoring['Round of 16'])
                self.dat['Semi-Finals']= Stage(name='Semi-Final', teams=list(dat[55:59]), **self.scoring['Semi-Finals'])
                self.dat['Final'] = Stage(name='Final', teams=list(dat[60:62]), **self.scoring['Final'])
                self.dat['Winner'] = Stage(name='Winner', teams=list(dat[63:64]), **self.scoring['Winner'])
                self.dat['Bonus'] = Stage(name='Bonus', teams=tuple(dat[65:68]), **self.scoring['Bonus'])
            else:
                print(f'No valid Phase 1 file found for {name}')
        
        if phase == 2:
            self.phase = 'Phase II'
            self.scoring = scoring.get(self.phase, None)
            pkl_file_2 = os.path.join(workdir,'phase_II', name + '.pkl')
            xlsx_file_2 = os.path.join(workdir,'phase_II', 'CxFPoolsEuro2020_PhaseII_'+ name + '.xlsx')
            if os.path.exists(pkl_file_2):
                self.dat = pkl_load(pkl_file_2)
            elif os.path.exists(xlsx_file_2):
                dat = pd.read_excel(xlsx_file_2, sheet_name='INTERNAL_USE_ONLY').iloc[:,0:2]
                self.dat['Round of 16'] = self.parse_stage('Round of 16', range(37,45),
                        dat.iloc[0:8].values, dat.iloc[8:16].values, use_code=True)
                self.dat['Quarter-Finals'] = self.parse_stage('Quarter-Finals', range(45,49),
                        dat.iloc[17:21].values, dat.iloc[21:25].values, use_code=True)
                self.dat['Semi-Finals'] = self.parse_stage('Semi-Finals', range(49,51),
                        dat.iloc[26:28].values, dat.iloc[28:30].values, use_code=True)
                self.dat['Final'] = self.parse_stage('Final', [51],
                        dat.iloc[31:32].values, dat.iloc[32:33].values, use_code=True)
                self.dat['Winner'] = Stage(name='Winner', teams=[dat.iloc[34,0]], **self.scoring['Winner'])
            else:
                print(f'No valid Phase 2 file found for {name}')
        
    
    
    @classmethod
    def load_dual_phase(cls, participant, workdir, scoring):
        phase1 = cls(participant, workdir, scoring, phase=1)
        phase2 = cls(participant, workdir, scoring, phase=2)
        return phase1, phase2
        
    def parse_stage(self, stage_name, mids, home_dat, away_dat, use_code=False):
        scores = {}
        for i, (home_team, home_score), (away_team, away_score) in zip(mids, home_dat, away_dat):
            s = Score(i,f'{home_score}-{away_score}',  teams=(home_team,away_team), 
                     use_code=use_code)
            scores[s.mid] = s

        return Stage(stage_name, scores, **self.scoring[stage_name])


    def compute(self, other):
        points = {}
        for key, stage in self.dat.items():
            pts = stage.compute(other.dat[key])
            if key == 'Bonus':
                bonus = other.dat['Group Stage'].matches.values()
                if sum([v.outcome is not None for v in bonus]) < len(bonus):
                    pts = 0
            points[(self.phase, key)] = pts
            
        return points
    
    def get_upcoming_scores(self, other):
        matches = {}
        for stage, dat in self.dat.items():
            #import pdb; pdb.set_trace()
            if dat.matches:
                matches.update(dat.get_upcoming_scores(other.dat[stage]))
        return matches
        #if 'Group Stage' in self.dat:
        #    return self.dat['Group Stage'].get_upcoming_scores(other.dat['Group Stage'])

    @property
    def teams(self):
        teams = {}
        for key, stage in self.dat.items():
            if stage.get_teams():
                teams[(self.phase, key)] = stage.get_teams()
        return teams
    
class ActualBracket(Bracket):

    def __init__(self, comp_url):
        self.name = 'actual'
        self.phase = 0
        self.dat = scrape_competition_from_livescore(comp_url)
        self.comp_url = comp_url
        self.dat['Winner'] = Stage(name='Winner', teams = ['Italy'])
        bonus_1 = fifa_codes.get(self.dat['Group Stage'].highest_scoring_team)
        bonus_2 = 'Player'
        bonus_3 = 'Player'
        #load bonus 2 and 3 from metadata.yml
        self.dat['Bonus'] = Stage(name='Bonus', teams=(bonus_1, bonus_2, bonus_3))

    def update(self):
        self.dat = update_scrape_from_livescore(self.dat, self.comp_url)
        self.dat['Winner'] = Stage(name='Winner', teams = ['Italy'])

        bonus_1 = self.dat['Group Stage'].highest_scoring_team
        bonus_2 = 'Player'
        bonus_3 = 'Player'
        #load bonus 2 and 3 from metadata.yml
        self.dat['Bonus'] = Stage(name='Bonus', teams=(bonus_1, bonus_2, bonus_3))

    @property
    def matches(self):
        matches = {}
        for stage in self.dat.values():
            if hasattr(stage, 'matches') and stage.matches:
                matches.update(stage.matches)

        return matches

            
class Tournament():

    def __init__(self, workdir, comp_url, update=60, load=3600*24):
        with open(os.path.join(workdir,'metadata.yml')) as f:
            config = yaml.safe_load(f)
        self.participants = [p.replace(' ','') for p in config['participants']]
        self.scoring = config['scoring']
        self.workdir = workdir
        self.brackets = {}
        for participant in self.participants:
            self.brackets[participant] = Bracket.load_dual_phase(participant, self.workdir, scoring=self.scoring)
        self.comp_url = comp_url
        self.load_time = 0
        self.load_interval = load 
        self.update_time = time.time()
        self.update_interval = update 
        self.reload()

    
    def reload(self):
        current_time = time.time()
        if current_time - self.load_time > self.load_interval:
            self.actual = ActualBracket(self.comp_url)
            self.teams = self.actual.dat['Group Stage'].teams
            self.load_time = current_time
        elif current_time - self.update_time > self.update_interval:
            self.actual.update()
            self.update_time = current_time
        
    @property
    def standings(self):
        points = {}
        for name, (phase1, phase2) in self.brackets.items():
            name = re.sub(r"(\w)([A-Z])", r"\1 \2", name)
            points[name] = {}
            points[name].update(phase1.compute(self.actual))
            points[name].update(phase2.compute(self.actual))

        points = pd.DataFrame.from_dict(points, orient='index')
        #points = points.groupby(level=1, axis=1).sum()
        #cols = [col for col in col_ordering if col in points.columns]
        #points = points[col]
        #points['Total'] = points.sum(axis=1)
        #points = points.sort_index().sort_values('Total', ascending=False)
        return points
    
    @property
    def predicted_scores(self):
        scores = {}
        for name, (phase1, phase2) in self.brackets.items():
            name = re.sub(r"(\w)([A-Z])", r"\1 \2", name)
            scores[name] = phase1.get_upcoming_scores(self.actual)
            scores[name].update(phase2.get_upcoming_scores(self.actual))
        scores = pd.DataFrame.from_dict(scores).T.sort_index()
        return scores

    @property
    def predicted_teams(self):
        teams = {}
        for name, (phase1, phase2) in self.brackets.items():
            name = re.sub(r"(\w)([A-Z])", r"\1 \2", name)
            teams[name] = {}
            if phase1.teams:
                teams[name].update(phase1.teams)
            if phase2.teams:
                teams[name].update(phase2.teams)
        teams = pd.DataFrame.from_dict(teams, orient='index').sort_index()
        return teams

            
        


