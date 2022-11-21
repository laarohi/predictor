#!/usr/bin/env python

import re
import time
from collections import Counter
from datetime import datetime

import yaml
import pandas as pd

from livescore import fifa_codes

def get_predictions_db(db, pid, stage, phase):
    match_query = '''
        SELECT p.match_id, p.home_score, p.away_score, f.home_team, f.away_team, f.kickoff
        FROM match_prediction as p
        LEFT JOIN fixtures as f
        ON p.match_id=f.id
        WHERE p.participant_id=%s AND f.stage LIKE %s AND p.phase=%s
    '''
    team_query = '''
        SELECT team, group_order
        FROM team_prediction
        WHERE participant_id=%s AND stage=%s AND phase=%s
    '''

    if stage == 'Group Stage': stage = 'Group%'

    match_preds = db.query(match_query, (pid, stage, phase) )
    matches = {}
    if match_preds:
        if not isinstance(match_preds[0], tuple):
            match_preds = (match_preds,)
        for mid, home_score, away_score, home_team, away_team, kickoff in match_preds:
            score = (home_score, away_score)
            m_teams = (home_team, away_team)
            matches[mid] = Score(mid, score, m_teams, dt=kickoff, stage=stage)

    team_preds = db.query(team_query, (pid, stage, phase))
    teams = []
    if team_preds:
        if not isinstance(team_preds[0], tuple):
            team_preds = (team_preds,)
        for team, group_order in team_preds:
            if group_order:
                teams.append((team, group_order))
            else:
                teams.append(team)

    return matches, teams

def get_results_db(db):
    results_query = '''
        SELECT f.id, s.home_score, s.away_score, f.home_team, f.away_team, f.kickoff, f.stage
        FROM fixtures as f
        LEFT JOIN score as s
        ON s.match_id=f.id
    '''
    results = db.query(results_query)
    stage_scores = {}
    if results:
        if not isinstance(results[0], tuple):
            results = (results,)
        for mid, home_score, away_score, home_team, away_team, kickoff, stage in results:
            if stage and stage.startswith('Group'):
                stage = 'Group Stage'
            if stage not in stage_scores:
                stage_scores[stage] = {}
            score = (home_score, away_score)
            m_teams = (home_team, away_team)
            stage_scores[stage][mid] = Score(mid, score, m_teams, dt=kickoff, stage=stage)
    
    stages = {}
    for stage, scores in stage_scores.items():
        stages[stage] = Stage(stage, scores)

    return stages

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
            if (score[0] is None) or (score[1] is None):
                return
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
                return f'{teams[0]} - {teams[1]}'
            else:
                return f'{self.mid}: ? - ?'
    
    def __repr__(self):
        return self.__str__()
    
    
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
        self.teams = set()
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
                if other_match and (-1 <= (other_match.dt.date() - datetime.now().date()).days <= 2):
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
    
    def __init__(self, name, pid, db, scoring=None, phase=1):
        '''
        load bracket from excel or pkl
        
        maybe specify name and dir or something along those lines
        '''
        self.name = name
        self.dat = {}
        self.phase = phase
        self.scoring = scoring.get(f'Phase {self.phase}', None)
        self.db = db
        self.pid = pid
        for stage, scor in self.scoring.items():
            matches, teams = get_predictions_db(db, self.pid, stage, phase)
            self.dat[stage] = Stage(name=stage,matches=matches, teams=teams, **scor)
        
    @classmethod
    def load_dual_phase(cls, participant, pid, db, scoring):
        phase1 = cls(participant, pid, db, scoring, phase=1)
        phase2 = cls(participant, pid, db, scoring, phase=2)
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
            if key == 'Bonus GS':
                bonus = other.dat['Group Stage'].matches.values()
                if sum([v.outcome is not None for v in bonus]) < len(bonus):
                    pts = 0
            points[(self.phase, key)] = pts
            
        return points
    
    def get_upcoming_scores(self, other):
        matches = {}
        for stage, dat in self.dat.items():
            if dat.matches:
                matches.update(dat.get_upcoming_scores(other.dat[stage]))
        return matches

    @property
    def teams(self):
        teams = {}
        for key, stage in self.dat.items():
            if stage.get_teams():
                teams[(self.phase, key)] = stage.get_teams()
        return teams

    @property
    def matches(self):
        matches = {}
        for stage in self.dat.values():
            if hasattr(stage, 'matches') and stage.matches:
                matches.update(stage.matches)

        return matches
    

class ActualBracket(Bracket):

    def __init__(self, db):
        self.name = 'actual'
        self.phase = 0
        self.db = db
        self.stages = ['Group Stage','Round of 16','Quarter-Finals','Semi-Finals','Finals','Winner','Bonus GS','Bonus KO']
        self.update()

    def update(self):
        self.dat = get_results_db(self.db)
        winner = list(self.dat['Final'].matches.values())[0].winner
        if winner: winner = [winner]
        self.dat['Winner'] = Stage('Winner', teams=winner)
        self.dat['Bonus GS'] = Stage('Bonus GS')
        self.dat['Bonus KO'] = Stage('Bonus KO')

            
class Tournament():

    def __init__(self, name, db, config, update=60, load=3600*24):
        self.name = name
        self.db = db
        self.participants = {}
        self.brackets = {}
        self.scoring = config['scoring']

        competitions = self.db.get('competition', 'id, description')
        self.competitions = {cid:comp for cid, comp in competitions}
        for cid, comp in self.competitions.items():
            participants = self.db.get('participant','id, name', competition_id=cid)
            self.participants[cid] = {p_name.title(): pid for pid, p_name in participants}

            self.brackets[cid] = {}
            for participant, pid in self.participants[cid].items():
                self.brackets[cid][participant] = Bracket.load_dual_phase(participant, pid, db, scoring=self.scoring)
                print('loaded bracket for:', comp, participant)

        self.load_time = 0
        self.load_interval = load 
        self.update_time = time.time()
        self.update_interval = update 
        self.reload()

    
    def reload(self):
        current_time = time.time()
        if current_time - self.load_time > self.load_interval:
            self.actual = ActualBracket(self.db)
            self.teams = self.actual.dat['Group Stage'].teams
            self.load_time = current_time
        elif current_time - self.update_time > self.update_interval:
            self.actual.update()
            self.update_time = current_time
        

    @property
    def standings(self):
        res = {}
        for cid, comp in self.competitions.items():
            points = {}
            for name, (phase1, phase2) in self.brackets[cid].items():
                name = re.sub(r"(\w)([A-Z])", r"\1 \2", name)
                points[name] = {}
                points[name].update(phase1.compute(self.actual))
                points[name].update(phase2.compute(self.actual))

            points = pd.DataFrame.from_dict(points, orient='index')
            res[comp] = points
        
        return res
    
    @property
    def predicted_scores(self):
        res = {}
        for cid, comp in self.competitions.items():
            scores = {}
            for name, (phase1, phase2) in self.brackets[cid].items():
                name = re.sub(r"(\w)([A-Z])", r"\1 \2", name)
                scores[name] = phase1.get_upcoming_scores(self.actual)
                scores[name].update(phase2.get_upcoming_scores(self.actual))
            scores = pd.DataFrame.from_dict(scores).T.sort_index()
            res[comp] = scores
        
        return res

    @property
    def predicted_teams(self):
        res = {}
        for cid, comp in self.competitions.items():
            teams = {}
            for name, (phase1, phase2) in self.brackets[cid].items():
                name = re.sub(r"(\w)([A-Z])", r"\1 \2", name)
                teams[name] = {}
                if phase1.teams:
                    teams[name].update(phase1.teams)
                if phase2.teams:
                    teams[name].update(phase2.teams)
            teams = pd.DataFrame.from_dict(teams, orient='index').sort_index()
            res[comp] = teams

        return res