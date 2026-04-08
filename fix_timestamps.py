#!/usr/bin/env python3
"""Fix timestamps in Slow tier - set earliest timestamp for records with invalid/missing timestamps."""

import sqlite3
import os
import time

slow_db = os.path.expanduser('~/.memory/slow.db')
conn = sqlite3.connect(slow_db)
cursor = conn.cursor()

current_ts = int(time.time())

# Find records with recent timestamps (parsing failures)
cursor.execute('''
    SELECT id, title, timestamp, project 
    FROM memories 
    WHERE timestamp > ?
    ORDER BY timestamp ASC
''', (current_ts - 3600,))
recent = cursor.fetchall()
print(f'Records with recent timestamps (parsing failures): {len(recent)}')
for row in recent:
    print(f'  {row[0]}: "{row[1]}" | ts={row[2]} | proj={row[3]}')

if not recent:
    print('No records need fixing.')
    conn.close()
    exit(0)

# Get earliest valid timestamp
cursor.execute('SELECT MIN(timestamp) FROM memories WHERE timestamp < ?', (current_ts - 3600,))
earliest_ts = cursor.fetchone()[0]
print(f'\nEarliest valid timestamp: {earliest_ts} ({time.ctime(earliest_ts)})')

# Update these records to earliest timestamp
print(f'\nUpdating {len(recent)} records to earliest timestamp...')
cursor.executemany(
    'UPDATE memories SET timestamp = ? WHERE id = ?',
    [(earliest_ts, row[0]) for row in recent]
)
conn.commit()

# Verify
cursor.execute('SELECT COUNT(*) FROM memories WHERE timestamp > ?', (current_ts - 3600,))
remaining = cursor.fetchone()[0]
print(f'Remaining records with recent timestamps: {remaining}')

# Show updated records
cursor.execute('''
    SELECT id, title, timestamp FROM memories 
    WHERE id IN ({})'''.format(','.join('?'*len(recent))),
    [row[0] for row in recent]
)
print('\nUpdated records:')
for row in cursor.fetchall():
    print(f'  {row[0]}: "{row[1]}" -> {time.ctime(row[2])}')

conn.close()
print('\nDone!')
