import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = [
          'https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive',
         ]

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms'
SAMPLE_RANGE_NAME = 'Class Data!A2:E'

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

def gen_entry(creds, name, surname, email, competition, template_id, folder_id=None, 
                tournament='predictor'):
    ''''
    Generate a competition entry as follows:
    0. check that email doesnt exist in db
    1. duplicate template sheet
    2. edit name to include participant name and group
    4. invite participant to edit sheet (add option to send email)
    5. update the database
    6. return sheet link
    '''

    full_name = name + ' ' + surname

    # TODO check database for existance of key
    #if db_check(email, competition):
        # email competition combo already registered
        # if not registered create entry and return pk
        #return

    # duplicating template sheet
    drive = build('drive', 'v3', credentials=creds)
    file_name = ' '.join([tournament, full_name, competition])
    sheet_id = copy_template(drive, template_id, file_name, folder_id)

    # update user info in sheet
    sheets = build('sheets', 'v4', credentials=creds)
    update_sheet(sheets, sheet_id, ["U3","U4"], [competition, full_name])

    # copy protected ranges
    #copy_protected_ranges(sheets, template_id, sheet_id, sheet, warning=False):

    # invite user
    invite_user(drive, sheet_id, email)

    # TODO update database
    
    sheet_url = 'https://docs.google.com/spreadsheets/d/' + sheet_id + '/edit'

    return sheet_url


def copy_template(service, template_id, file_name, folder_id=None):
    body = {}
    body['name'] = file_name
    if folder_id:
        body['parents'] = [folder_id]

    res = service.files().copy(fileId=template_id, body=body).execute()
    print(res)
    sheet_id = res['id']
    return sheet_id

def invite_user(service, sheet_id, email):
    body = {
        'type': 'user',
        'role': 'writer',
        'emailAddress': email,
    }
    res = service.permissions().create(fileId=sheet_id, body=body).execute()
    return res


def update_sheet(service, sheet_id, cells, values, sheet=None, value_input_option='RAW'):
    data = []
    for c, v in zip(cells, values):
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
        new_sheet_id = new_sheet_info['sheets'][i]['properties']['sheetId']
        old_sheet_protected_ranges = old_sheet_info['sheets'][i]['protectedRanges']
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
        

if 1 and __name__ == '__main__':
    creds = get_creds()
    tid = '1Rd7wrlMI1GRHtwJXfXRP9Am7CWskLFg_orkSzc8w5yI'
    fid = '1wTnX3wApK8Mpe7LkptJSDPCIHhuOuxyR'
    gen_entry(creds,'Luke','Aarohi','lukeinter@gmail.com','cxf',tid, fid)
    











