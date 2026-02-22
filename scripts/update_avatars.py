import sqlite3
import os

updates = [
    (15, 'thorne'), (17, 'senpai'), (19, 'detective_x'), (20, 'echo_ai'),
    (21, 'k_traveler'), (22, 'nuannuan'), (23, 'kai'), (24, 'npc_girl'),
    (25, 'gl1tch'), (28, 'room404'), (29, 'mimi'), (30, 'pixel'),
    (31, 'hina'), (32, 'eve'), (33, 'shiori'), (34, 'nana'),
    (35, 'mio'), (36, 'reina'), (37, 'mei'), (38, 'mistress_v'),
    (39, 'naughty_nurse'), (40, 'captive_elf'), (41, 'succubus_maid'),
    (42, 'ms_sato'), (43, 'rina'), (44, 'mai'),
]

db_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'synclub.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

for db_id, file_id in updates:
    avatar_url = f'/avatars/{file_id}.png'
    c.execute('UPDATE characters SET avatar_url=? WHERE id=?', (avatar_url, db_id))
    print(f'  id={db_id} ({file_id}) -> {avatar_url}')

conn.commit()
conn.close()
print('Done!')
