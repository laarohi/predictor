"""
populate any required metadata in the database.
"""
import yaml
from util import db_setup, db_insert


with open('./tournaments/worldcup2022/metadata.yml', 'r') as f:
    config = yaml.load(f, Loader=yaml.Loader)

db = db_setup(config['sql'])

query = """INSERT INTO competition (name, description, entry_fee) 
        VALUES (%s, %s, %s)"""

for k,v in config['competitions'].items():
    name = k
    desc = v['desc']
    entry_fee = v['entry_fee']
    db_insert(db, query, (name, desc, entry_fee))

