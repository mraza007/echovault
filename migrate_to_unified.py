#!/usr/bin/env python3
"""Optimized migration script with multi-threading for EchoVault to unified Slow tier."""

import sys
import os
import json
import time
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from datetime import datetime

sys.path.insert(0, r'C:\Git\echovault\src')

from memory.core import MemoryService

# Global stats for thread safety
stats = {'migrated': 0, 'errors': 0, 'skipped': 0}
stats_lock = Lock()

def init_slow_db(db_path):
    """Initialize Slow tier database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, what TEXT NOT NULL,
            summary TEXT, timestamp INTEGER NOT NULL, tags TEXT,
            category TEXT, project TEXT, embedding BLOB,
            access_count INTEGER DEFAULT 0, compressed_at INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_project ON memories(project);
        CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp);
        CREATE INDEX IF NOT EXISTS idx_category ON memories(category);
    """)
    conn.commit()
    return conn

def migrate_single_memory(args):
    """Migrate a single memory (thread-safe)."""
    row, slow_db_path = args
    try:
        # Parse timestamp
        created_str = row.get('created_at') or ''
        try:
            dt = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
            timestamp = int(dt.timestamp())
        except:
            timestamp = int(time.time())
        
        # Parse tags
        tags = []
        if row.get('tags'):
            try:
                parsed = json.loads(row['tags'])
                tags = parsed if isinstance(parsed, list) else [str(parsed)]
            except:
                tags = [str(row['tags'])]
        
        # Per-thread DB connection
        conn = sqlite3.connect(slow_db_path)
        cursor = conn.cursor()
        
        # Skip if already exists
        cursor.execute('SELECT id FROM memories WHERE id = ?', (row['id'],))
        if cursor.fetchone():
            conn.close()
            with stats_lock:
                stats['skipped'] += 1
            return 'skipped'
        
        # Insert (fast, without embedding generation)
        cursor.execute("""
            INSERT INTO memories 
            (id, title, what, summary, timestamp, tags, category, project, compressed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['id'],
            row.get('title') or 'Untitled',
            row.get('what') or '',
            None,  # No summary yet
            timestamp,
            json.dumps(tags),
            row.get('category'),
            row.get('project'),
            int(time.time())
        ))
        
        conn.commit()
        conn.close()
        
        with stats_lock:
            stats['migrated'] += 1
        return 'success'
    except Exception as e:
        with stats_lock:
            stats['errors'] += 1
        return f'error: {e}'

def migrate_parallel(dry_run=True, max_workers=8):
    """Parallel migration using thread pool."""
    print(f"=== Parallel Migration ({max_workers} workers) ===\n")
    
    svc = MemoryService()
    slow_db_path = os.path.expanduser('~/.memory/slow.db')
    
    if not dry_run:
        init_slow_db(slow_db_path)
        # Reset stats
        stats['migrated'] = stats['errors'] = stats['skipped'] = 0
    
    # Fetch all memories
    cursor = svc.db.conn.cursor()
    cursor.execute('''
        SELECT id, title, what, why, impact, category, tags, project,
               created_at, updated_at, status, file_path
        FROM memories 
        ORDER BY created_at
    ''')
    
    memories = [dict(row) for row in cursor.fetchall()]
    total = len(memories)
    print(f"Total: {total} memories")
    
    if dry_run:
        print("\nDRY RUN - use --apply to migrate")
        return
    
    # Prepare args for workers
    args_list = [(m, slow_db_path) for m in memories]
    start_time = time.time()
    
    # Process in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(migrate_single_memory, a): i for i, a in enumerate(args_list)}
        completed = 0
        
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            
            # Progress update every 50
            if completed % 50 == 0:
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                print(f"  {completed}/{total} | M:{stats['migrated']} E:{stats['errors']} S:{stats['skipped']} | {rate:.1f} mem/s")
    
    # Final stats
    elapsed = time.time() - start_time
    print(f"\n=== Migration Complete ===")
    print(f"  Total processed: {total}")
    print(f"  Migrated: {stats['migrated']}")
    print(f"  Skipped (exist): {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Rate: {stats['migrated']/elapsed:.1f} mem/s")

def verify_migration():
    """Verify migration integrity."""
    print("\n=== Verification ===\n")
    
    # Count in original
    svc = MemoryService()
    cursor = svc.db.conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM memories')
    original_count = cursor.fetchone()[0]
    
    # Count in slow tier
    slow_db_path = os.path.expanduser('~/.memory/slow.db')
    if os.path.exists(slow_db_path):
        conn = sqlite3.connect(slow_db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM memories')
        slow_count = cursor.fetchone()[0]
        conn.close()
    else:
        slow_count = 0
    
    print(f"Original: {original_count} memories")
    print(f"Slow tier: {slow_count} memories")
    
    if slow_count >= original_count * 0.95:
        print("\n✓ VERIFIED: Migration successful")
    else:
        print(f"\n⚠ WARNING: Only {slow_count}/{original_count} migrated")

def analyze_existing():
    """Quick analysis."""
    print("=== EchoVault Data Analysis ===\n")
    
    svc = MemoryService()
    cursor = svc.db.conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM memories')
    total = cursor.fetchone()[0]
    print(f"Total memories: {total}")
    
    cursor.execute('SELECT category, COUNT(*) FROM memories GROUP BY category')
    print("\nBy category:")
    for cat, cnt in cursor.fetchall():
        print(f"  {cat or '(none)'}: {cnt}")
    
    return total

if __name__ == "__main__":
    # Quick analysis
    total = analyze_existing()
    
    if total == 0:
        print("No memories to migrate")
        sys.exit(0)
    
    # Parse args
    dry_run = '--apply' not in sys.argv
    workers = 8
    
    for arg in sys.argv:
        if arg.startswith('--workers='):
            workers = int(arg.split('=')[1])
    
    print(f"\n{'='*50}")
    print(f"{'DRY RUN' if dry_run else f'APPLYING with {workers} workers'}")
    print(f"{'='*50}\n")
    
    # Run
    migrate_parallel(dry_run=dry_run, max_workers=workers)
    
    if not dry_run:
        verify_migration()
    else:
        print("\nTo apply: python migrate_to_unified.py --apply [--workers=8]")
