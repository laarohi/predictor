"""
populate any required metadata in the database.
"""
import yaml
import os
from util import DB

metadata_path = os.environ.get("METADATA_YML", './tournaments/worldcup2022/metadata.yml')

with open(metadata_path, 'r') as f:
    config = yaml.load(f, Loader=yaml.Loader)

db = DB(config['sql'])

query = """INSERT INTO competition (name, description, entry_fee) 
        VALUES (%s, %s, %s)"""

for k,v in config['competitions'].items():
    name = k
    desc = v['desc']
    entry_fee = v['entry_fee']
    db.query(query, (name, desc, entry_fee))

