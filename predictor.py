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


import os
import re
import time
from collections import Counter
from datetime import datetime

import yaml
import pandas as pd

from livescore import fifa_codes, scrape_competition_from_livescore

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

            
        


