"""Graph relations for EchoVault memory system.

Models relationships between memory entries:
- depends_on: Entry A depends on Entry B
- related_to: Entry A is related to Entry B  
- part_of: Entry A is part of Entry B
- supersedes: Entry A supersedes/replaces Entry B
"""

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class RelationType(Enum):
    """Types of relations between memory entries."""
    DEPENDS_ON = "depends_on"    # A depends on B
    RELATED_TO = "related_to"    # A is related to B
    PART_OF = "part_of"          # A is part of B
    SUPERSEDES = "supersedes"   # A supersedes/replaces B


@dataclass
class MemoryRelation:
    """A relation between two memory entries."""
    source_id: str       # The entry that has the relation
    target_id: str       # The entry being related to
    relation_type: RelationType
    strength: float = 1.0  # 0.0 to 1.0
    timestamp: int = 0
    notes: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = int(time.time())


class GraphRelationsStore:
    """Store for graph relations between memory entries.
    
    Stored in Slow tier database for persistence.
    """
    
    def __init__(self, db_path: str):
        """Initialize graph relations store.
        
        Args:
            db_path: Path to SQLite database (typically slow.db)
        """
        self.db_path = db_path
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self._init_schema()
    
    def _init_schema(self):
        """Initialize graph relations schema."""
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS memory_relations (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                strength REAL DEFAULT 1.0,
                timestamp INTEGER NOT NULL,
                notes TEXT,
                PRIMARY KEY (source_id, target_id, relation_type)
            );
            
            CREATE INDEX IF NOT EXISTS idx_source ON memory_relations(source_id);
            CREATE INDEX IF NOT EXISTS idx_target ON memory_relations(target_id);
            CREATE INDEX IF NOT EXISTS idx_type ON memory_relations(relation_type);
        """)
        self.db.commit()
    
    def add_relation(self, relation: MemoryRelation) -> bool:
        """Add a relation between two memory entries.
        
        Args:
            relation: The relation to add
            
        Returns:
            True if added successfully
        """
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO memory_relations
                (source_id, target_id, relation_type, strength, timestamp, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                relation.source_id,
                relation.target_id,
                relation.relation_type.value,
                relation.strength,
                relation.timestamp,
                relation.notes
            ))
            self.db.commit()
            return True
        except sqlite3.Error as e:
            print(f"[GraphRelations] Failed to add relation: {e}")
            return False
    
    def remove_relation(self, source_id: str, target_id: str, 
                        relation_type: RelationType) -> bool:
        """Remove a specific relation.
        
        Args:
            source_id: Source entry ID
            target_id: Target entry ID
            relation_type: Type of relation
            
        Returns:
            True if removed successfully
        """
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                DELETE FROM memory_relations
                WHERE source_id = ? AND target_id = ? AND relation_type = ?
            """, (source_id, target_id, relation_type.value))
            self.db.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"[GraphRelations] Failed to remove relation: {e}")
            return False
    
    def get_relations_from(self, source_id: str,
                           relation_type: Optional[RelationType] = None
                           ) -> list[MemoryRelation]:
        """Get all relations from a source entry.
        
        Args:
            source_id: The source entry ID
            relation_type: Optional filter by relation type
            
        Returns:
            List of relations
        """
        cursor = self.db.cursor()
        
        if relation_type:
            cursor.execute("""
                SELECT * FROM memory_relations
                WHERE source_id = ? AND relation_type = ?
                ORDER BY strength DESC
            """, (source_id, relation_type.value))
        else:
            cursor.execute("""
                SELECT * FROM memory_relations
                WHERE source_id = ?
                ORDER BY strength DESC
            """, (source_id,))
        
        return [self._row_to_relation(row) for row in cursor.fetchall()]
    
    def get_relations_to(self, target_id: str,
                         relation_type: Optional[RelationType] = None
                         ) -> list[MemoryRelation]:
        """Get all relations pointing to a target entry.
        
        Args:
            target_id: The target entry ID
            relation_type: Optional filter by relation type
            
        Returns:
            List of relations
        """
        cursor = self.db.cursor()
        
        if relation_type:
            cursor.execute("""
                SELECT * FROM memory_relations
                WHERE target_id = ? AND relation_type = ?
                ORDER BY strength DESC
            """, (target_id, relation_type.value))
        else:
            cursor.execute("""
                SELECT * FROM memory_relations
                WHERE target_id = ?
                ORDER BY strength DESC
            """, (target_id,))
        
        return [self._row_to_relation(row) for row in cursor.fetchall()]
    
    def get_all_related(self, entry_id: str,
                        relation_type: Optional[RelationType] = None
                        ) -> list[MemoryRelation]:
        """Get all relations to/from an entry (bidirectional).
        
        Args:
            entry_id: The entry ID
            relation_type: Optional filter by relation type
            
        Returns:
            List of relations (both incoming and outgoing)
        """
        cursor = self.db.cursor()
        
        if relation_type:
            cursor.execute("""
                SELECT * FROM memory_relations
                WHERE (source_id = ? OR target_id = ?) AND relation_type = ?
                ORDER BY strength DESC
            """, (entry_id, entry_id, relation_type.value))
        else:
            cursor.execute("""
                SELECT * FROM memory_relations
                WHERE source_id = ? OR target_id = ?
                ORDER BY strength DESC
            """, (entry_id, entry_id))
        
        return [self._row_to_relation(row) for row in cursor.fetchall()]
    
    def get_path(self, start_id: str, end_id: str,
                 max_depth: int = 3) -> list[MemoryRelation]:
        """Find a path between two entries using BFS.
        
        Args:
            start_id: Starting entry ID
            end_id: Target entry ID
            max_depth: Maximum path length
            
        Returns:
            List of relations forming the path, or empty if no path
        """
        # BFS to find shortest path
        from collections import deque
        
        queue = deque([(start_id, [])])
        visited = {start_id}
        
        while queue:
            current_id, path = queue.popleft()
            
            if len(path) >= max_depth:
                continue
            
            # Get outgoing relations
            relations = self.get_relations_from(current_id)
            
            for rel in relations:
                if rel.target_id == end_id:
                    return path + [rel]
                
                if rel.target_id not in visited:
                    visited.add(rel.target_id)
                    queue.append((rel.target_id, path + [rel]))
        
        return []  # No path found
    
    def get_dependencies(self, entry_id: str) -> list[str]:
        """Get all transitive dependencies of an entry.
        
        Args:
            entry_id: The entry to find dependencies for
            
        Returns:
            List of entry IDs this entry depends on (transitively)
        """
        deps = set()
        to_process = [entry_id]
        visited = {entry_id}
        
        while to_process:
            current = to_process.pop(0)
            
            # Get direct dependencies
            relations = self.get_relations_from(current, RelationType.DEPENDS_ON)
            
            for rel in relations:
                if rel.target_id not in visited:
                    deps.add(rel.target_id)
                    visited.add(rel.target_id)
                    to_process.append(rel.target_id)
        
        return list(deps)
    
    def find_cycles(self, entry_id: str) -> list[list[str]]:
        """Find dependency cycles involving an entry.
        
        Args:
            entry_id: Entry to check for cycles
            
        Returns:
            List of cycles (each cycle is a list of entry IDs)
        """
        cycles = []
        
        def dfs(current: str, path: list[str], visited: set):
            if current == entry_id and len(path) > 0:
                cycles.append(path + [entry_id])
                return
            
            if current in visited or len(path) > 10:  # Limit depth
                return
            
            visited.add(current)
            
            relations = self.get_relations_from(current, RelationType.DEPENDS_ON)
            for rel in relations:
                dfs(rel.target_id, path + [current], visited.copy())
        
        dfs(entry_id, [], set())
        return cycles
    
    def delete_entry_relations(self, entry_id: str) -> int:
        """Delete all relations involving an entry.
        
        Args:
            entry_id: Entry ID to remove relations for
            
        Returns:
            Number of relations deleted
        """
        cursor = self.db.cursor()
        cursor.execute("""
            DELETE FROM memory_relations
            WHERE source_id = ? OR target_id = ?
        """, (entry_id, entry_id))
        self.db.commit()
        return cursor.rowcount
    
    def get_stats(self) -> dict:
        """Get statistics about stored relations."""
        cursor = self.db.cursor()
        
        # Total relations
        cursor.execute("SELECT COUNT(*) FROM memory_relations")
        total = cursor.fetchone()[0]
        
        # By type
        cursor.execute("""
            SELECT relation_type, COUNT(*) 
            FROM memory_relations 
            GROUP BY relation_type
        """)
        by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Unique entries
        cursor.execute("""
            SELECT COUNT(DISTINCT source_id) + COUNT(DISTINCT target_id) 
            FROM memory_relations
        """)
        entries = cursor.fetchone()[0]
        
        return {
            "total_relations": total,
            "by_type": by_type,
            "unique_entries": entries
        }
    
    def _row_to_relation(self, row) -> MemoryRelation:
        """Convert DB row to MemoryRelation."""
        return MemoryRelation(
            source_id=row["source_id"],
            target_id=row["target_id"],
            relation_type=RelationType(row["relation_type"]),
            strength=row["strength"],
            timestamp=row["timestamp"],
            notes=row["notes"]
        )
