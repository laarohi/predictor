#!/usr/bin/env python
# coding: utf-8

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
# - rewrite of excel parser to parse directly from first sheet
# - fix astericks scoring for knockout phase in excel and python
# - set then unordered tuple then ordered for teams
# - 
# 

# In[197]:


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

def from_livescore(x):
    x = x.replace('-',' ').title()
    if x.startswith('Group'):
        return 'Group Stage'
    return x


euro_url = 'https://www.livescores.com/soccer/euro-2020/'

ls_id_map = {80596: 1,
             80595: 2,
             80737: 3,
             80736: 4,
             80742: 5,
             81035: 6,
             81036: 7,
             80743: 8,
             80748: 9,
             80749: 10,
             80612: 11,
             80611: 12,
             80738: 13,
             80598: 14,
             80597: 15,
             81037: 16,
             80739: 17,
             81038: 18,
             80750: 19,
             80745: 20,
             80744: 21,
             80613: 22,
             80614: 23,
             80751: 24,
             80599: 25,
             80600: 26,
             81039: 27,
             81040: 28,
             80741: 29,
             80740: 30,
             80747: 31,
             80746: 32,
             80753: 33,
             80752: 34,
             80615: 35,
             80616: 36}

ls_order_map = {
             80042: (2, 2),
             80043: (1, 2),
             80046: (1, 3),
             80044: (1, 3),
             80045: (2, 2),
             80047: (1, 3),
             80048: (1, 2),
             80049: (1, 3)
             }


def fetch_beautiful_markup(url):
    print('fetching markup from ' + url)
    
    # try catching all possible http errors
    try :
        livescore_html = requests.get(url)
    except Exception as e :
        return print('An error occured as: ', e)

    parsed_markup = BeautifulSoup(livescore_html.text, 'html.parser')
    
    return parsed_markup

def extract_scores(parsed_markup, stage=None):
    # dictionary to contain score
    scores = {}

    # scrape needed data from the parsed markup
    for element in parsed_markup.find_all("div", "row-gray") :
        
        match_name_element = element.find(attrs={"class": "scorelink"})
        ls_id = int(element.get('data-eid'))
        match_dt = element.get('data-esd')
        if match_dt:
            match_dt = datetime.strptime(match_dt, '%Y%m%d%H%M%S')
        mid = ls_id_map.get(ls_id, ls_id)
        order = ls_order_map.get(ls_id, None)

        if match_name_element is not None :
            # this means the match is about to be played
            match_stage, matchup = match_name_element.get('href').split('/')[3:5]
            match_stage = from_livescore(match_stage)
            if match_stage not in scores: scores[match_stage] = {}
            home_team = from_livescore(matchup.split('-vs-')[0].strip())
            away_team = from_livescore(matchup.split('-vs-')[1].strip())
            teams = (home_team, away_team)
            if order:
                teams = tuple(zip(teams, order))
            score = element.find("div", "sco").get_text().strip()
            #score = gen_score()

            # add our data to our dictionary
            scores[match_stage][mid] = Score(mid, score, teams, match_dt)
        elif stage:
            if stage not in scores: scores[stage] = {}
            # we need to use a different method to get our data
            home_team = '-'.join(element.find("div", "tright").get_text().strip().split(" "))
            away_team = '-'.join(element.find(attrs={"class": "ply name"}).get_text().strip().split(" "))

            score = element.find("div", "sco").get_text().strip()
            #score = gen_score()

            teams = (home_team, away_team)
            if order:
                teams = tuple(zip(teams, order))

            # add our data to our dictionary
            scores[stage][mid] = Score(mid, score, teams, match_dt)

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
    

def scrape_scores_from_livescore(url, stage) :
    
    parsed_markup = fetch_beautiful_markup(url)
    scores = extract_scores(parsed_markup, stage)
    return scores


def scrape_competition_from_livescore(comp_url):
    res = {}
    comp = parse.urlparse(comp_url).path
    comp_markup = fetch_beautiful_markup(comp_url)
    comp_scores = extract_scores(comp_markup)
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

def update_scrape_from_livescore(comp_scores, comp_url):
    comp_markup = fetch_beautiful_markup(comp_url)
    new_scores = extract_scores(comp_markup)
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
# two way mapping
fifa_codes = {l[:-6]:l[-6:-3] for l in codes}
fifa_codes['North Macedonia'] = fifa_codes.pop('Macedonia FYR')
fifa_codes['Netherlands'] = fifa_codes.pop('Holland')


class Score():
    def __init__(self, mid, score, teams=None, dt=None):
        self.mid = mid
        self.home = None
        self.away = None
        self.score = None
        self.teams = None
        self.outcome = None
        self.dt = None
        
        if teams:
            self.teams = tuple(teams)
            try:
                self.teams = tuple([fifa_codes[team] for team in self.teams])
            except KeyError:
                pass
        if dt:
            self.dt = dt
        if isinstance(score, str):
            if '?' in score:
                # handling livescore future game score
                #print(f'No score yet for {self.teams}')
                return
            else:
                score = score.replace(' ','').split('-')
                
        if isinstance(score, (list, tuple)) and len(score)==2:
            self.score = tuple(score)
            self.home = int(score[0])
            self.away = int(score[1])
        else:
            raise TypeError('unknown score format')
            
        # 1 - home_win; 0 - draw; 2 - away_win
        self.outcome = (self.home != self.away) + (self.away>self.home)
        return 

        
    
    def __str__(self):
        if self.score:
            if self.teams:
                if isinstance(self.teams[0], tuple):
                    teams = [t[0] for t in self.teams]
                else:
                    teams = self.teams
                return f"{teams[0]} {'-'.join(self.score)} {teams[1]}"
            else:
                return f"{'-'.join(self.score)}"
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
            return f'{self.teams[0]} vs {self.teams[1]}'
    
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
        if self.teams and other.teams and (self.teams != other.teams):
            return 0
        if self.score == other.score:
            return result
        elif self.outcome == other.outcome:
            return outcome
        else:
            return 0


def score_compare(a, b, outcome=5, result=15):
    '''
    compare scores a & b
    '''
    b.score = tuple([s.strip() for s in b.score])
    if a.teams and b.teams and (a.teams != b.teams):
        return 0
    if a.score == b.score:
        return result
    elif a.outcome == b.outcome:
        return outcome
    else:
        return 0

def team_compare(a, b, qualified=10, ordering=0):
    '''
    compare teams in a to teams in b and score points accordingly
    
    a and b must be sets of teams
    '''
    pts = 0
    correct_qualified = len(a.intersection(b))
    
    if ordering and a and isinstance(a, tuple):
        correct_ordering = correct_qualified
        a_teams = set([t[0] for t in a])
        b_teams = set([t[0] for t in b])
        correct_qualified = len(a_teams.intersection(b_teams))
        pts += correct_ordering * ordering
        
    pts += correct_qualified * qualified
    
    return pts
        
        
class Stage():
    def __init__(self, name, matches=None, teams=None, outcome=None, result=None, qualified=None, ordering=None):
        '''
        matches - a dict of matches and the corresponding scores scores could be in string or Score format
        teams - a list of teams who qualified for this stage
        '''
        self.name = name
        self.matches = None
        self.teams = None
        if matches:
            test_match = list(matches.values())[0]
            if isinstance(test_match, str):
                self.matches = {k:Score(k, v) for k,v in matches.items()}
            elif isinstance(test_match, Score):
                self.matches = matches
            else:
                raise TypeError('Unrecognised matches format')
            self.outcome = outcome or 0
            self.result = result or 0
            if not teams:
                match_teams = []
                for match in self.matches.values():
                    if match.teams:
                        match_teams += list(match.teams)
                self.teams = set(match_teams) or None
        if teams:
            self.teams = set(teams)
            self.qualified = qualified or 0
            self.ordering = ordering or 0
        
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
            
            
    def compute(self, other):
        points = 0
        if self.matches:
            missing_matches = set(self.matches.keys()) - set(other.matches.keys())
            if missing_matches:
                print(f'Warning missing matches! {missing_matches}')
            for mid, match in self.matches.items():
                points += match.compute(other.matches[mid], self.outcome, self.result)
        
        if self.teams:
            points += team_compare(self.teams, other.teams, self.qualified, self.ordering)
            
        return points
    
    def get_upcoming_scores(self, other):
        matches = {}
        if self.matches:
            missing_matches = set(self.matches.keys()) - set(other.matches.keys())
            if missing_matches:
                print(f'Warning missing matches! {missing_matches}')
            for mid, match in self.matches.items():
                other_match = other.matches.get(mid)
                if other_match and (0 <= (other_match.dt.date() - datetime.now().date()).days <= 2):
                    matches[other_match.matchup] = match.__str__()
        
        return matches

            
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
                self.dat['Round of 16'] = Stage(name='Round of 16', teams=list(zip(dat[38:54], [1,2]*4 + [3]*4)), **self.scoring['Round of 16'])
                self.dat['Semi-finals']= Stage(name='Semi-final', teams=list(dat[55:59]), **self.scoring['Semi-finals'])
                self.dat['Final'] = Stage(name='Final', teams=list(dat[60:62]), **self.scoring['Final'])
                self.dat['Winner'] = Stage(name='Winner', teams=list(dat[63:64]), **self.scoring['Winner'])
                self.dat['Bonus'] = Stage(name='Bonus', teams=list(dat[65:68]), **self.scoring['Bonus'])
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
                dat = pd.read_excel(xlsx_file_2, sheet_name='INTERNAL_USE_ONLY').iloc[:,0].values
                # TODO add phase 2 once sheet is complete
            else:
                #print(f'No valid Phase 2 file found for {name}')
                return None
        
    
    
    @classmethod
    def load_dual_phase(cls, participant, workdir, scoring):
        phase1 = cls(participant, workdir, scoring, phase=1)
        phase2 = cls(participant, workdir, scoring, phase=2)
        return phase1, phase2
        
    
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
        if 'Group Stage' in self.dat:
            return self.dat['Group Stage'].get_upcoming_scores(other.dat['Group Stage'])
    
class ActualBracket(Bracket):
    def __init__(self, comp_url):
        self.name = 'actual'
        self.phase = 0
        self.dat = scrape_competition_from_livescore(comp_url)
        self.comp_url = comp_url
        self.dat['Winner'] = Stage(name='Winner', teams = self.dat['Final'].winners)
        bonus_1 = self.dat['Group Stage'].highest_scoring_team
        bonus_2 = None
        bonus_3 = None
        #load bonus 2 and 3 from metadata.yml
        self.dat['Bonus'] = Stage(name='Bonus', teams=[bonus_1, bonus_2, bonus_3])

    def update(self):
        self.dat = update_scrape_from_livescore(self.dat, self.comp_url)
        self.dat['Winner'] = Stage(name='Winner', teams = self.dat['Final'].winners)
        bonus_1 = self.dat['Group Stage'].highest_scoring_team
        bonus_2 = None
        bonus_3 = None
        #load bonus 2 and 3 from metadata.yml
        self.dat['Bonus'] = Stage(name='Bonus', teams=[bonus_1, bonus_2, bonus_3])

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
        #points['Total'] = points.sum(axis=1)
        #points = points.sort_index().sort_values('Total', ascending=False)
        return points
    
    @property
    def predicted_scores(self):
        scores = {}
        for name, (phase1, phase2) in self.brackets.items():
            name = re.sub(r"(\w)([A-Z])", r"\1 \2", name)
            scores[name] = phase1.get_upcoming_scores(self.actual)
        scores = pd.DataFrame.from_dict(scores).T.sort_index()
        return scores
        


