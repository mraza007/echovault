#!/usr/bin/env python3
"""Process STATIC_IP and SETUP files from minisforum/docs."""

import sys
import os
import re
import json
import sqlite3
from datetime import datetime
from pathlib import Path

sys.path.insert(0, r'C:\Git\echovault\src')

PATTERNS = [r'STATIC_IP', r'STATIC', r'SETUP', r'ROAMING_SETUP']

def parse_file(filepath):
    """Parse a documentation file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return None
    
    filename = os.path.basename(filepath)
    
    # Extract title
    title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else filename.replace('.md', '')
    
    # Summary
    summary_match = re.search(r'^# .+\n\n(.+?)(?:\n\n|\n##)', content, re.DOTALL)
    summary = summary_match.group(1).strip()[:400] if summary_match else content[:400]
    
    # Extract sections
    sections = []
    section_matches = re.findall(r'##? (.+)\n\n(.+?)(?=\n##? |\Z)', content, re.DOTALL)
    for section_title, section_content in section_matches[:2]:
        sections.append(f"**{section_title}**: {section_content[:200]}...")
    
    # Category
    category = 'setup'
    if 'FIX' in filename.upper():
        category = 'bug'
    elif 'SOLUTION' in filename.upper():
        category = 'decision'
    elif 'ROAMING' in filename.upper():
        category = 'setup'
    
    # Tags
    tags = ['minisforum', 'documentation']
    if 'STATIC' in filename.upper():
        tags.append('static-ip')
    if 'SETUP' in filename.upper():
        tags.append('setup')
    if 'BRIDGE' in filename.upper():
        tags.append('bridge-ap')
    if 'ROAMING' in filename.upper():
        tags.append('roaming')
    if 'DOH' in filename.upper() or 'DOT' in filename.upper():
        tags.append('dns-over-https')
    if 'NETWORK' in filename.upper():
        tags.append('network')
    
    # Timestamp
    try:
        mtime = os.path.getmtime(filepath)
        timestamp = int(mtime)
    except:
        timestamp = int(datetime.now().timestamp())
    
    return {
        'id': f"doc-{filename.replace('.md', '').lower()[:45]}",
        'title': title[:100],
        'what': summary,
        'details': f"Documentation: {title}\n\nFile: {filename}\n\nSummary:\n{summary}\n\nSections:\n{chr(10).join(sections)}",
        'category': category,
        'tags': tags,
        'project': 'minisforum',
        'timestamp': timestamp,
        'source_file': filename
    }

def load_to_slow_tier(memory_data):
    """Load into Slow tier."""
    slow_db_path = os.path.expanduser('~/.memory/slow.db')
    conn = sqlite3.connect(slow_db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM memories WHERE id = ?', (memory_data['id'],))
    if cursor.fetchone():
        conn.close()
        return 'skipped'
    
    cursor.execute("""
        INSERT INTO memories 
        (id, title, what, summary, timestamp, tags, category, project, compressed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        memory_data['id'], memory_data['title'], memory_data['what'], memory_data['details'],
        memory_data['timestamp'], json.dumps(memory_data['tags']), memory_data['category'],
        memory_data['project'], int(datetime.now().timestamp())
    ))
    conn.commit()
    conn.close()
    return 'loaded'

def main():
    docs_dir = r'C:\Git\Backup\minisforum\docs'
    if not os.path.exists(docs_dir):
        print(f"Directory not found: {docs_dir}")
        return
    
    # Find matching files
    md_files = list(Path(docs_dir).glob('*.md'))
    matched_files = []
    for f in md_files:
        if any(re.search(p, f.name, re.IGNORECASE) for p in PATTERNS):
            matched_files.append(f)
    
    print(f"Found {len(matched_files)} files matching patterns\n")
    
    loaded = skipped = errors = deleted = 0
    
    for filepath in sorted(matched_files):
        print(f"Processing: {filepath.name}")
        
        memory_data = parse_file(str(filepath))
        if not memory_data:
            errors += 1
            continue
        
        result = load_to_slow_tier(memory_data)
        
        if result == 'loaded':
            loaded += 1
            print(f"  ✓ Loaded: {memory_data['title'][:70]}")
            try:
                os.remove(filepath)
                deleted += 1
                print(f"  ✓ Deleted")
            except Exception as e:
                print(f"  ⚠ Could not delete: {e}")
        else:
            skipped += 1
            print(f"  ⊘ Skipped")
    
    print(f"\n=== Summary ===")
    print(f"  Found: {len(matched_files)}")
    print(f"  Loaded: {loaded}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Deleted: {deleted}")

if __name__ == "__main__":
    main()
