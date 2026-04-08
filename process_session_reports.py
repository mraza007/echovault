#!/usr/bin/env python3
"""Process session report files from minisforum/docs and load into Slow tier memory."""

import sys
import os
import re
import json
import sqlite3
from datetime import datetime
from pathlib import Path

sys.path.insert(0, r'C:\Git\echovault\src')
from memory.core import MemoryService

def extract_date_from_filename(filename):
    """Extract date from filename patterns like 2026-02-25, 20250402, etc."""
    # Pattern: YYYY-MM-DD
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    # Pattern: YYYYMMDD
    match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None

def parse_session_file(filepath):
    """Parse a session report file and extract structured data."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"  ERROR reading {filepath}: {e}")
        return None
    
    filename = os.path.basename(filepath)
    
    # Extract title from first heading
    title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else filename.replace('.md', '')
    
    # Extract date from filename or content
    date = extract_date_from_filename(filename)
    if not date:
        # Try to find date in content
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', content)
        if date_match:
            date = date_match.group(1)
    
    # Convert date to timestamp
    if date:
        try:
            dt = datetime.strptime(date, '%Y-%m-%d')
            timestamp = int(dt.timestamp())
        except:
            timestamp = int(datetime.now().timestamp())
    else:
        timestamp = int(datetime.now().timestamp())
    
    # Extract summary (first paragraph after title)
    summary_match = re.search(r'^# .+\n\n(.+?)(?:\n\n|\n##)', content, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else content[:500]
    
    # Extract key sections
    sections = []
    section_matches = re.findall(r'## (.+)\n\n(.+?)(?=\n## |\Z)', content, re.DOTALL)
    for section_title, section_content in section_matches[:5]:  # Limit to 5 sections
        sections.append(f"**{section_title}**: {section_content[:300]}...")
    
    # Build structured content
    what = summary[:300]
    details = f"""Session Report: {title}

Date: {date or 'unknown'}
File: {filename}

Summary:
{summary}

Key Sections:
{chr(10).join(sections)}

Full content available in backup.
"""
    
    # Determine category based on content
    category = 'context'
    if 'recovery' in content.lower() or 'restore' in content.lower():
        category = 'bug' if 'error' in content.lower() or 'fail' in content.lower() else 'context'
    elif 'optimization' in content.lower() or 'improve' in content.lower():
        category = 'decision'
    elif 'analysis' in content.lower():
        category = 'learning'
    
    # Extract tags
    tags = ['minisforum', 'session-report']
    if 'wifi' in content.lower():
        tags.append('wifi')
    if 'network' in content.lower():
        tags.append('network')
    if 'debian' in content.lower():
        tags.append('debian')
    if 'openwrt' in content.lower():
        tags.append('openwrt')
    
    return {
        'id': f"session-{filename.replace('.md', '').lower()[:40]}",
        'title': title[:100],
        'what': what,
        'details': details,
        'category': category,
        'tags': tags,
        'project': 'minisforum',
        'timestamp': timestamp,
        'source_file': filename
    }

def is_session_report(filename):
    """Check if file is a session report based on patterns."""
    patterns = [
        r'SESSION', r'session',
        r'RECOVERY.*\d{4}',
        r'FINAL.*\d{4}',
        r'\d{4}-\d{2}-\d{2}',
        r'\d{8}',
        r'report.*\d{4}',
        r'analysis.*\d{4}',
        r'REPORT.*\d{4}',
        r'ANALYSIS.*\d{4}',
    ]
    return any(re.search(p, filename, re.IGNORECASE) for p in patterns)

def load_to_slow_tier(memory_data):
    """Load structured memory into Slow tier."""
    slow_db_path = os.path.expanduser('~/.memory/slow.db')
    
    conn = sqlite3.connect(slow_db_path)
    cursor = conn.cursor()
    
    # Check if already exists
    cursor.execute('SELECT id FROM memories WHERE id = ?', (memory_data['id'],))
    if cursor.fetchone():
        conn.close()
        return 'skipped'
    
    # Insert
    cursor.execute("""
        INSERT INTO memories 
        (id, title, what, summary, timestamp, tags, category, project, compressed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        memory_data['id'],
        memory_data['title'],
        memory_data['what'],
        memory_data['details'],
        memory_data['timestamp'],
        json.dumps(memory_data['tags']),
        memory_data['category'],
        memory_data['project'],
        int(datetime.now().timestamp())
    ))
    
    conn.commit()
    conn.close()
    return 'loaded'

def main():
    docs_dir = r'C:\Git\Backup\minisforum\docs'
    
    if not os.path.exists(docs_dir):
        print(f"Directory not found: {docs_dir}")
        return
    
    # Find all markdown files
    md_files = list(Path(docs_dir).glob('*.md'))
    
    # Filter session reports
    session_files = [f for f in md_files if is_session_report(f.name)]
    
    print(f"Found {len(session_files)} session report files\n")
    
    loaded = 0
    skipped = 0
    errors = 0
    deleted = 0
    
    for filepath in session_files:
        print(f"Processing: {filepath.name}")
        
        # Parse
        memory_data = parse_session_file(str(filepath))
        if not memory_data:
            errors += 1
            continue
        
        # Load to Slow tier
        result = load_to_slow_tier(memory_data)
        
        if result == 'loaded':
            loaded += 1
            print(f"  ✓ Loaded: {memory_data['title'][:60]}")
            
            # Delete file after successful load
            try:
                os.remove(filepath)
                deleted += 1
                print(f"  ✓ Deleted file")
            except Exception as e:
                print(f"  ⚠ Could not delete: {e}")
        else:
            skipped += 1
            print(f"  ⊘ Already exists, skipped")
    
    print(f"\n=== Summary ===")
    print(f"  Processed: {len(session_files)}")
    print(f"  Loaded: {loaded}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Files deleted: {deleted}")

if __name__ == "__main__":
    main()
