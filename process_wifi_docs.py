#!/usr/bin/env python3
"""Process all WiFi-related files from minisforum/docs and load into Slow tier memory."""

import sys
import os
import re
import json
import sqlite3
from datetime import datetime
from pathlib import Path

sys.path.insert(0, r'C:\Git\echovault\src')

def parse_wifi_file(filepath):
    """Parse a WiFi documentation file and extract structured data."""
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
    
    # Extract summary (first paragraph after title or first 300 chars)
    summary_match = re.search(r'^# .+\n\n(.+?)(?:\n\n|\n##)', content, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else content[:400]
    
    # Extract key sections
    sections = []
    section_matches = re.findall(r'##? (.+)\n\n(.+?)(?=\n##? |\Z)', content, re.DOTALL)
    for section_title, section_content in section_matches[:3]:  # Limit to 3 sections
        sections.append(f"**{section_title}**: {section_content[:250]}...")
    
    # Build what
    what = summary[:400]
    
    # Build details
    details = f"""WiFi Documentation: {title}

File: {filename}

Summary:
{summary}

Key Sections:
{chr(10).join(sections) if sections else 'Documentation file'}

Full content available in original file.
"""
    
    # Determine category
    category = 'context'
    if 'setup' in filename.lower() or 'install' in filename.lower() or 'guide' in filename.lower():
        category = 'setup'
    elif 'analysis' in filename.lower():
        category = 'learning'
    elif 'optimization' in filename.lower():
        category = 'decision'
    
    # Extract tags from filename and content
    tags = ['minisforum', 'wifi', 'documentation']
    
    if 'debian' in content.lower():
        tags.append('debian')
    if 'openwrt' in content.lower():
        tags.append('openwrt')
    if 'vht' in filename.lower() or 'ht40' in filename.lower():
        tags.append('vht40')
    if 'roaming' in filename.lower():
        tags.append('roaming')
    if 'power' in filename.lower():
        tags.append('power-management')
    if 'config' in filename.lower():
        tags.append('configuration')
    if 'client' in filename.lower():
        tags.append('clients')
    if 'firmware' in filename.lower():
        tags.append('firmware')
    
    # Timestamp based on file modification time
    try:
        mtime = os.path.getmtime(filepath)
        timestamp = int(mtime)
    except:
        timestamp = int(datetime.now().timestamp())
    
    return {
        'id': f"wifi-doc-{filename.replace('.md', '').lower()[:40]}",
        'title': title[:100],
        'what': what,
        'details': details,
        'category': category,
        'tags': tags,
        'project': 'minisforum',
        'timestamp': timestamp,
        'source_file': filename
    }

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
    
    # Find all WiFi-related files (case insensitive)
    md_files = list(Path(docs_dir).glob('*.md'))
    wifi_files = [f for f in md_files if re.search(r'wifi', f.name, re.IGNORECASE)]
    
    print(f"Found {len(wifi_files)} WiFi-related files\n")
    
    loaded = 0
    skipped = 0
    errors = 0
    deleted = 0
    
    for filepath in sorted(wifi_files):
        print(f"Processing: {filepath.name}")
        
        # Parse
        memory_data = parse_wifi_file(str(filepath))
        if not memory_data:
            errors += 1
            continue
        
        # Load to Slow tier
        result = load_to_slow_tier(memory_data)
        
        if result == 'loaded':
            loaded += 1
            print(f"  ✓ Loaded: {memory_data['title'][:70]}")
            
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
    print(f"  Found WiFi files: {len(wifi_files)}")
    print(f"  Loaded: {loaded}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Files deleted: {deleted}")

if __name__ == "__main__":
    main()
