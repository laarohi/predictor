import os.path
import base64
import MySQLdb
import yaml

from time import sleep

USE_GOOGLE = int(os.environ.get("USE_GOOGLE", 1))

from email_validator import validate_email
from email.message import EmailMessage
if USE_GOOGLE:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError


metadata_path = os.environ.get("METADATA_YML", './tournaments/euro2024/metadata.yml')
with open(metadata_path, 'r') as f:
    config = yaml.load(f, Loader=yaml.Loader)

# If modifying these scopes, delete the file token.json.
SCOPES = [
          'https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive',
          'https://mail.google.com/',
         ]


def get_creds(token='token.json', creds_file='credentials.json'):
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token):
        creds = Credentials.from_authorized_user_file(token, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                creds_file, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token, 'w') as token:
            token.write(creds.to_json())
    return creds

def build_services(creds):
    res = {}
    res['drive'] = build('drive', 'v3', credentials=creds)
    res['sheets'] = build('sheets', 'v4', credentials=creds)
    res['gmail'] = build('gmail', 'v1', credentials=creds)
    return res


def gen_entry(services, full_name, email, competition_id, db, template_id, folder_id=None, 
                tournament='predictor'):
    ''''
    Generate a competition_id entry as follows:
    0. check that email doesnt exist in db
    1. duplicate template sheet
    2. edit name to include participant name and group
    4. invite participant to edit sheet (add option to send email)
    5. update the database
    6. return sheet link
    '''

    # check if email is valid
    try:
        r = validate_email(email)
    except:
        r = False
    if not r:
        # email is invalid
        error_msg = "The email address you have entered does not appear to be valid, please try again."
        raise ValueError(error_msg)
    
    is_google_account = "google.com" in r.spf

    # check if participant already exists in db
    query = f"SELECT sheet_id from participant WHERE {email=} and {competition_id=}"
    existing_sheet = db.query(query)
    if existing_sheet:
        # email competition_id combo already registered return it
        error_msg = f"A sign up for the selected competition with the email address {email} already exists."
        raise KeyError(error_msg)
    
    # get competition name from db
    competition = db.get('competition', 'name', id=competition_id)

    # duplicating template sheet
    file_name = ' '.join([tournament, full_name, competition])
    sheet_id = copy_template(services['drive'], template_id, file_name, folder_id)

    # update user info in sheet
    update_sheet(services['sheets'], sheet_id, {"G4":competition,"R3":full_name,"R4":email})

    # copy protected ranges
    #copy_protected_ranges(sheets, template_id, sheet_id, sheet, warning=False):

    # invite participant
    invite_participant(services['drive'], sheet_id, email, is_google_account)

    # add participant to database
    query = """INSERT INTO participant (name , email , competition_id , sheet_id ) 
            VALUES (%s,%s,%s,%s)"""
    db.query(query, (full_name, email, competition_id, sheet_id))

    sheet_url = 'https://docs.google.com/spreadsheets/d/' + sheet_id + '/edit'

    if not is_google_account:
        send_email_invite(services['gmail'], email, sheet_url, file_name)

    return sheet_url

# ----------------------------- GOOGLE DRIVE FUNCTIONS ---------------------------------- #

def copy_template(service, template_id, file_name, folder_id=None):
    body = {}
    body['name'] = file_name
    if folder_id:
        body['parents'] = [folder_id]

    res = service.files().copy(fileId=template_id, body=body).execute()
    print(res)
    sheet_id = res['id']
    return sheet_id

def invite_participant(service, sheet_id, email, is_google_account=True):
    if is_google_account:
        body = {
            'type': 'user',
            'role': 'writer',
            'emailAddress': email,
        }
    else:
        body = {
            'type': 'anyone',
            'role': 'writer',
        }
    res = service.permissions().create(fileId=sheet_id, body=body).execute()
    return res

# ----------------------------- GOOGLE SHEETS FUNCTIONS ---------------------------------- #

def update_sheet(service, sheet_id, to_update, sheet=None, value_input_option='RAW'):
    data = []
    for c, v in to_update.items():
        if sheet:
            c = sheet + '!' + c
        if not isinstance(v, list): 
            v = [[v]]
        data.append({'range':c, 'values':v})

    body = {'valueInputOption': value_input_option, 'data':data}

    res = service.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id, body=body).execute()

    return res

def protect_sheet(service, sheet_id, ranges, warning=False):
    requests = []

    for r in ranges:
        req = {
            "addProtectedRange": {
                "ProtectedRange": {
                    "range": r,
                    "warningOnly": warning,
                }
            }
        }
        requests.append(req)

    body = {'requests': requests}

    res = service.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id, body=body).execute()

    return res

def copy_protected_ranges(service, old_sheet, new_sheet, warning=False):
    requests = []

    old_spreadsheet_info = service.spreadsheets().get(
        spreadsheetId=old_sheet).execute()

    new_spreadsheet_info = service.spreadsheets().get(
        spreadsheetId=new_sheet).execute()

    for i in range(len(old_spreadsheet_info['sheets'])):
        new_sheet_id = new_spreadsheet_info['sheets'][i]['properties']['sheetId']
        old_sheet_protected_ranges = old_spreadsheet_info['sheets'][i]['protectedRanges']
        for pr in old_sheet_protected_ranges:
            r = {}
            r['range'] = pr['range']
            r['range']['sheetId'] = new_sheet_id
            r['warningOnly'] = warning
            r['editors'] = pr['editors']
            requests.append(r)

    body = {'requests': requests}

    res = service.spreadsheets().values.batchUpdate(
        spreadsheetId=new_sheet_id, body=body).execute()
    
    return res

def update_protected_ranges(service, old_sheet, new_sheet, protected_range, warning=False):
    requests = []

    old_spreadsheet_info = service.spreadsheets().get(
        spreadsheetId=old_sheet).execute()

    new_spreadsheet_info = service.spreadsheets().get(
        spreadsheetId=new_sheet).execute()

    for i in range(len(old_spreadsheet_info['sheets'])):
        new_sheet_id = new_spreadsheet_info['sheets'][i]['properties']['sheetId']
        old_sheet_protected_ranges = old_spreadsheet_info['sheets'][i]['protectedRanges']
        for pr in old_sheet_protected_ranges:
            r = {}
            r['range'] = pr['range']
            r['range']['sheetId'] = new_sheet_id
            r['warningOnly'] = warning
            r['editors'] = pr['editors']
            requests.append(r)

    body = {'requests': requests}

    res = service.spreadsheets().values.batchUpdate(
        spreadsheetId=new_sheet_id, body=body).execute()
    
    return res

def send_email_invite(service, email, sheet_url, subject):

        try:
            message = EmailMessage()
            res = "Welcome to the Euro 2024 Prediction Game. Please use the following link to fill in your predictions:\n\n"
            res += sheet_url + '\n\nThe link is a public link so do not share it with anyone.\n\nGood luck, \nLuke Aarohi'
            message.set_content(res)
            message['To'] = email
            message['From'] = 'aarohiluke@gmail.com'
            message['Subject'] = subject

            # encoded message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()) \
                .decode()

            create_message = {
                'raw': encoded_message
            }
            # pylint: disable=E1101
            send_message = (service.users().messages().send
                            (userId="me", body=create_message).execute())
            print(F'Message Id: {send_message["id"]}')
        except HttpError as error:
            print(F'An error occurred: {error}')
            send_message = None
        return send_message

def get_sheet_data(service, sheet_id, ranges, value_render_option='FORMATTED_VALUE'):
    range_keys = list(ranges.keys())
    range_values = list(ranges.values())
    data = service.spreadsheets().values().batchGet(
        spreadsheetId=sheet_id, ranges=range_values, valueRenderOption=value_render_option).execute()
    data = data.get('valueRanges', [])

    res = {}
    for k, v in zip(range_keys, data):
        res[k] = v['values']
    return res

def lock_sheet_phase_1(service, sheet_id):
    body = {
        "requests": [
            {
            "updateProtectedRange": {
                "protectedRange": {
                    'protectedRangeId': 1883711663,
                        'unprotectedRanges': [
                            {'sheetId': 517157059,
                            'startRowIndex': 108,
                            'endRowIndex': 123,
                            'startColumnIndex': 10,
                            'endColumnIndex': 12}
                        ] 
                    },
                "fields": "unprotectedRanges"
            }
            }
        ]
    }
    response = service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body=body).execute()
    print(response)
    return 




# ----------------------------- SQL FUNCTIONS ---------------------------------- #

class DB:
    
    def __init__(self, config):
        host = config['host']
        user = config['user']
        passwd = config['passwd']
        db = config['db']
        self.host = os.environ.get(host, host)
        self.user = os.environ.get(user, user)
        self.passwd = os.environ.get(passwd, passwd)
        self.db = os.environ.get(db, db)
        self.conn = None

    def _reconnect(func):
        def wrapper(self, *args, **kwargs):
            try:
                self.conn.commit()
            except (AttributeError, MySQLdb.OperationalError):
                self.connect()
            res = func(self, *args, **kwargs)
            self.conn.commit()
            return res
        return wrapper
            
    def connect(self):
        self.conn = MySQLdb.connect(host=self.host, passwd=self.passwd, user=self.user, db=self.db)
    
    @_reconnect
    def query(self, query, args=None):
        res = None
        c = self.conn.cursor()
        exists = c.execute(query, args)
        if exists:
            res = c.fetchall()
        c.close()
        while isinstance(res, tuple) and len(res)==1:
            res = res[0]
        return res
    
    def get(self, table, what="*", order_by=None, asc=True, **kwargs):
        query = f"SELECT {what} from {table}"
        if kwargs: query += " WHERE"
        for i,(k,v) in enumerate(kwargs.items()):
            if i: query += " AND"
            query += f" {k}='{v}'"
        if order_by:
            query += f" ORDER BY {order_by}"
            if asc:
                query += " ASC"
            else:
                query += " DESC"
        print(query)
        res = self.query(query)
        return res
    
# ------------------------ GET SHEET DATA --------------------------------------

def update_predictions_db(sheets, db, phase):

    match_query = """REPLACE INTO match_prediction (home_score , away_score , match_id , match_result , phase, participant_id ) 
            VALUES (%s,%s,%s,%s,%s,%s)"""
    delete_team_query = """DELETE FROM team_prediction WHERE stage=%s AND phase=%s AND participant_id=%s"""
    insert_team_query = """INSERT INTO team_prediction (team , stage , group_order , phase , participant_id ) 
            VALUES (%s,%s,%s,%s,%s)"""
    
    participant_sheets = db.get('participant', 'id, sheet_id')
    if not isinstance(participant_sheets[0], tuple):
        participant_sheets = [participant_sheets]
    
    if phase == 1:
        template_id = config['google_api']['template_id']
        gs_row_map = group_stage_row_map(sheets, template_id, db)
        sheet_ranges = config['sheet_ranges']['Phase 1'] 

        for pid, sheet_id in participant_sheets:
            data = get_sheet_data(sheets, sheet_id, sheet_ranges)
            gs = data.pop('Group Stage')
            for i, score in enumerate(gs):
                if isinstance(score, list): score = score[0]
                match_id, is_reversed = gs_row_map[i]
                home_score, away_score = list(map(lambda x: int(x.strip()), score.split('-')))
                if is_reversed:
                    home_score, away_score = away_score, home_score
                match_result = None
                entry = (home_score, away_score, match_id, match_result, phase, pid)
                db.query(match_query, entry)
            
            ro16 = data.pop('Round of 16')
            db.query(delete_team_query, ('Round of 16', phase, pid))
            for row in ro16:
                team_a_order = int(row[0][0])
                team_a = row[1]
                entry = (team_a, 'Round of 16', team_a_order, phase, pid)
                db.query(insert_team_query, entry)
                team_b_order = int(row[2][0])
                team_b = row[3]
                entry = (team_b, 'Round of 16', team_b_order, phase, pid)
                db.query(insert_team_query, entry)
            
                
            for stage, dat in data.items():
                db.query(delete_team_query, (stage, phase, pid))
                for team in dat:
                    if isinstance(team, list): team = team[0]
                    entry = (team, stage, None, phase, pid)
                    db.query(insert_team_query, entry)
    
    if phase == 2:

        # TODO Test this before actually using it 
        sheet_ranges = config['sheet_ranges']['Phase 2'] 
        for pid, sheet_id in participant_sheets:
            data = get_sheet_data(sheets, sheet_id, sheet_ranges)
            for stage, dat in data.items():
                db.query(delete_team_query, (stage, phase, pid))
                match_ids = db.get("fixtures", "id", order_by="kickoff", stage=stage)
                if not isinstance(match_ids, (list, tuple)):
                    match_ids = [match_ids]
                for match_id, (home_team, home_score, away_team, away_score) in zip(match_ids, dat):
                    score = f'{home_score}-{away_score}'
                    if '*' in score:
                        o = score.find('*') - score.find('-')
                        if o > 0:
                            match_result = 2
                        elif o < 0:
                            match_result = 1
                        home_score = home_score.replace('*', '')
                        away_score = away_score.replace('*', '')
                    else:
                        match_result = None
                    match_entry = (home_score, away_score, match_id, match_result, phase, pid)
                    db.query(match_query, match_entry)
                    home_team_entry = (home_team, stage, None, phase, pid)
                    away_team_entry = (away_team, stage, None, phase, pid)
                    db.query(insert_team_query, home_team_entry)
                    db.query(insert_team_query, away_team_entry)
            print(f'{pid} done!')


def check_status_sheet(sheets, db, phase):
    participant_sheets = db.get('participant', 'name, paid, competition_id, sheet_id')

    ranges = {
        'phase I': 'Euros!E92',
        'phase II': 'Euros!Q117',
    }

    res = {}

    for name, paid, cid, sheet_id in participant_sheets:
        if not cid in res:
            res[cid] = {'Complete':[], 'Missing Predictions':[], 'Pending Payment':[]}
        checks = get_sheet_data(sheets, sheet_id, ranges)
        if phase == 1:
            check = checks['phase I'][0][0]
        elif phase == 2:
            check = checks['phase II'][0][0]
        print(name, cid, check)
        complete = (check == 'COMPLETE POOL:')
        if not paid:
            res[cid]['Pending Payment'].append(name)
        if not complete:
            res[cid]['Missing Predictions'].append(name)
        if paid and complete:
            res[cid]['Complete'].append(name)
        
        sleep(3)

    return res

def update_bracket_sheet(sheets, template, db):
    b_ranges = config['sheet_ranges']['bracket']
    b_data = get_sheet_data(sheets, template, b_ranges, value_render_option="FORMULA")
    to_update = {b_ranges[k]:v for k,v in b_data.items()}
    sheet_ids = db.get('participant','sheet_id')
    for sheet_id in sheet_ids:
        if isinstance(sheet_id, tuple) and len(sheet_id) == 1:
            sheet_id = sheet_id[0]
        update_sheet(sheets, sheet_id, to_update, value_input_option="USER_ENTERED")


def lock_prediction_sheet(sheets, db, phase):

    sheet_ids = db.get('participant','sheet_id')

    if phase == 1:
        uprs = [
                {'sheetId': 517157059,
                'startRowIndex': 103,
                'endRowIndex': 118,
                'startColumnIndex': 10,
                'endColumnIndex': 12}
                ] 
    elif phase == 2:
        uprs = []


    body = {
        "requests": [
            {
            "updateProtectedRange": {
                "protectedRange": {
                    'protectedRangeId': 1883711663,
                        'unprotectedRanges': uprs
                    },
                "fields": "unprotectedRanges"
            }
            }
        ]
    }

    for sheet_id in sheet_ids:
        if isinstance(sheet_id, tuple) and len(sheet_id) == 1:
            sheet_id = sheet_id[0]
        response = sheets.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body=body).execute()
        print(response)

def bug_fix_sheet(sheets, db):

    sheet_ids = db.get('participant','sheet_id')

    body = {
        "requests": [
            {
            "setDataValidation": {
                "range": {
                "sheetId": 517157059,
                "startRowIndex": 67,
                "endRowIndex": 68,
                "startColumnIndex": 10,
                "endColumnIndex": 11,
                },
                "rule": {
                'condition': {
                    'type': 'ONE_OF_RANGE', 
                    'values': [{'userEnteredValue': '=QF_B'}]},
                'strict': True,
                'showCustomUi': True
                }
                }
            },
            {
            "setDataValidation": {
                "range": {
                "sheetId": 517157059,
                "startRowIndex": 68,
                "endRowIndex": 69,
                "startColumnIndex": 4,
                "endColumnIndex": 5,
                },
                "rule": {
                'condition': {
                    'type': 'ONE_OF_RANGE', 
                    'values': [{'userEnteredValue': '=QF_C'}]},
                'strict': True,
                'showCustomUi': True
                }
                }
            },
        ]
        }

    to_update = {'M4':'=Euros!BA69','M8':'=Euros!BA71'}
    for sheet_id in sheet_ids:
        if isinstance(sheet_id, tuple) and len(sheet_id) == 1:
            sheet_id = sheet_id[0]
        response = sheets.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body=body).execute()
        print(response)
        update_sheet(sheets, sheet_id, to_update, sheet='Teams', value_input_option='USER_ENTERED')
    

def group_stage_row_map(sheets, sheet_id, db):
    '''
    this function is just a placeholder for now, to be used as part of larger script
    
    idea is to create a map from row to fixture.id table in sql for data entry
    '''
    rows = get_sheet_data(sheets, sheet_id, {'data':'Euros!I19:N64'})
    i = 0
    res = {}
    for row in rows['data']:
        reversed = False
        if len(row) == 0 or row[0] == 'Home':
            continue
        home_team = row[0]
        away_team = row[5]
        mid = db.get('fixtures','id', home_team=home_team, away_team=away_team)
        if mid is None:
            reversed = True
            mid = db.get('fixtures','id', home_team=away_team, away_team=home_team)
        print(mid, home_team, away_team, reversed)
        res[i] = (mid, reversed)
        i += 1
    return res
    

if 1 and __name__ == '__main__':
    creds = get_creds('google_token.json','google_credentials.json')
    services = build_services(creds)
    tid = '192NYpfnQj6e8zhwN_a21Mi_uYfj8epel_X5x4oBd_rA'
    sheet_id = '1fYceYMnyjwWbUN8UhiJ-_MDSKQJ_KL4rmWWKKsQUvvI'
    db = DB(config['sql'])
    # res = check_status_sheet(services['sheets'], db, phase=2)
    # lock_prediction_sheet(services['sheets'],db,2)
    update_predictions_db(services['sheets'],db,2)


