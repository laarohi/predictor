import os.path
import base64
import MySQLdb
import yaml


from email_validator import validate_email
from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


metadata_path = os.environ.get("METADATA_YML", './tournaments/worldcup2022/metadata.yml')
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
    competition = db.get('competition', 'name', competition_id)[0][0]

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
            v = [v]
        data.append({'range':c, 'values':[v]})

    body = {'valueInputOption': value_input_option, 'data':data}

    res = service.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id, body=body).execute()

    return res

def protect_sheet(service, sheet_id, ranges, sheet, warning=False):
    requests = []

    for r in ranges:
        if sheet:
            r = sheet + '!' + r
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

    res = service.spreadsheets().values.batchUpdate(
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


def send_email_invite(service, email, sheet_url, subject):

        try:
            message = EmailMessage()
            res = "Welcome to the World Cup 2022 Prection Game. Please use the following link to fill in your predictions:\n\n"
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
    def query(self, query, args=()):
        res = None
        c = self.conn.cursor()
        exists = c.execute(query, args)
        if exists:
            res = c.fetchall()
        c.close()
        return res
    
    def get(self, table, what, id=None):
        query = f"SELECT {what} from {table}"
        if id:
            query += f" WHERE id={id}"
        res = self.query(query)
        return res
    
        
    

if 1 and __name__ == '__main__':
    import MySQLdb
    import os
    db = DB(config['sql'])
    creds = get_creds()
    tid = '1EKQnM9qsdpfEkUdCMX1SkzUUXSiul4rExZ7xa1ksk-s'
    fid = '1wTnX3wApK8Mpe7LkptJSDPCIHhuOuxyR'
    gen_entry(creds, 'Vinay','Aarohi','vinay.aarohi@atlas.com.mt',1, db, tid, fid, 'World Cup 2022 Predictor')
