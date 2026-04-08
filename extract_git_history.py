#!/usr/bin/env python3
"""Extract ALL markdown files from git history including deleted ones."""

import sys
import os
import re
import json
import sqlite3
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

sys.path.insert(0, r'C:\Git\echovault\src')

REPO_PATH = r'C:\Git\openwrt-captive-monitor'

def run_git(cmd, cwd=None):
    """Run git command with proper error handling."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd or REPO_PATH, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='ignore'
        )
        return result.stdout if result.returncode == 0 else None
    except Exception as e:
        print(f"  Git error: {e}")
        return None

def get_all_md_files_with_commits():
    """Get all markdown files ever committed with their last commit hash."""
    print("Scanning git history for all markdown files...")
    
    # Get all commits that touched md files with file list
    cmd = ['git', 'log', '--all', '--full-history', '--name-only', '--pretty=format:%H', '--', '*.md']
    stdout = run_git(cmd)
    
    if not stdout:
        return {}
    
    # Parse: commit hash followed by files
    files_commits = {}
    current_commit = None
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        if len(line) == 40 and all(c in '0123456789abcdef' for c in line.lower()):
            # This is a commit hash
            current_commit = line
        elif line.endswith('.md') and not line.startswith('package/'):
            # This is a file - store the most recent commit
            if line not in files_commits:
                files_commits[line] = current_commit
    
    return files_commits

def extract_file_content(filepath, commit_hash):
    """Extract file content using git cat-file or show."""
    # Try git show first
    content = run_git(['git', 'show', f'{commit_hash}:{filepath}'])
    if content:
        return content
    
    # If that fails, try to get blob hash and then content
    ls_tree = run_git(['git', 'ls-tree', '-r', commit_hash, filepath])
    if ls_tree:
        parts = ls_tree.split()
        if len(parts) >= 3:
            blob_hash = parts[2]
            content = run_git(['git', 'cat-file', '-p', blob_hash])
            return content
    
    return None

def get_commit_timestamp(commit_hash):
    """Get timestamp from commit."""
    result = run_git(['git', 'show', '-s', '--format=%ct', commit_hash])
    try:
        return int(result.strip().split('\n')[0]) if result else int(datetime.now().timestamp())
    except:
        return int(datetime.now().timestamp())

def parse_md_content(content, filename, filepath, timestamp):
    """Parse markdown content into structured memory."""
    if not content:
        return None
    
    # Extract title
    title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else filename.replace('.md', '')
    
    # Summary - first paragraph after title
    summary_match = re.search(r'^# .+\n\n(.+?)(?:\n\n|\n##)', content, re.DOTALL)
    summary = summary_match.group(1).strip()[:500] if summary_match else content[:500]
    
    # Category based on filename
    category = 'context'
    upper_name = filename.upper()
    if 'README' in upper_name:
        category = 'setup'
    elif 'REPORT' in upper_name or 'ANALYSIS' in upper_name:
        category = 'learning'
    elif 'SECURITY' in upper_name or 'AUDIT' in upper_name:
        category = 'bug'
    elif 'WORKFLOW' in upper_name or 'REFACTOR' in upper_name or 'FIX' in upper_name:
        category = 'decision'
    elif 'TEST' in upper_name:
        category = 'learning'
    
    # Tags
    tags = ['openwrt-captive-monitor', 'git-history']
    if 'README' in upper_name:
        tags.append('readme')
    if 'REPORT' in upper_name:
        tags.append('report')
    if 'SECURITY' in upper_name:
        tags.append('security')
    if 'AUDIT' in upper_name:
        tags.append('audit')
    if 'WORKFLOW' in upper_name:
        tags.append('workflow')
    if 'TEST' in upper_name:
        tags.append('testing')
    if 'RELEASE' in upper_name:
        tags.append('release')
    if 'RU' in upper_name:
        tags.append('russian')
    if 'DE' in upper_name:
        tags.append('german')
    if 'ARCHIVE' in filepath.upper():
        tags.append('archive')
    
    return {
        'id': f"ocm-{filename.replace('.md', '').lower()[:50]}",
        'title': title[:100],
        'what': summary,
        'details': f"Git History: {filename}\n\nPath: {filepath}\n\nContent:\n{content[:2500]}",
        'category': category,
        'tags': tags,
        'project': 'openwrt-captive-monitor',
        'timestamp': timestamp,
        'source_file': filepath
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
    # Get all files with their commits
    files_commits = get_all_md_files_with_commits()
    print(f"Found {len(files_commits)} unique markdown files\n")
    
    if not files_commits:
        print("No files found!")
        return
    
    loaded = skipped = errors = 0
    
    for i, (filepath, commit_hash) in enumerate(sorted(files_commits.items()), 1):
        filename = os.path.basename(filepath)
        print(f"[{i}/{len(files_commits)}] {filepath[:60]}...", end=' ')
        
        # Extract content
        content = extract_file_content(filepath, commit_hash)
        if not content:
            errors += 1
            print("EXTRACT FAIL")
            continue
        
        # Get timestamp
        timestamp = get_commit_timestamp(commit_hash)
        
        # Parse
        memory_data = parse_md_content(content, filename, filepath, timestamp)
        if not memory_data:
            errors += 1
            print("PARSE FAIL")
            continue
        
        # Load
        result = load_to_slow_tier(memory_data)
        
        if result == 'loaded':
            loaded += 1
            print("LOADED")
        else:
            skipped += 1
            print("SKIPPED")
    
    print(f"\n=== Summary ===")
    print(f"  Total: {len(files_commits)}")
    print(f"  Loaded: {loaded}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")

if __name__ == "__main__":
    main()
