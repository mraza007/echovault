"""Tests for graph relations in memory system."""

import pytest
import tempfile
import os
from memory.graph_relations import (
    GraphRelationsStore,
    MemoryRelation,
    RelationType,
)


class TestGraphRelations:
    """Tests for graph relations functionality."""
    
    def test_add_relation(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            graph = GraphRelationsStore(db_path)
            
            rel = MemoryRelation(
                source_id="entry-1",
                target_id="entry-2",
                relation_type=RelationType.DEPENDS_ON,
                strength=0.9,
                notes="Depends on config"
            )
            
            assert graph.add_relation(rel) is True
            
            # Verify it was added
            relations = graph.get_relations_from("entry-1")
            assert len(relations) == 1
            assert relations[0].target_id == "entry-2"
            assert relations[0].relation_type == RelationType.DEPENDS_ON
            
        finally:
            os.unlink(db_path)
    
    def test_remove_relation(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            graph = GraphRelationsStore(db_path)
            
            # Add relation
            rel = MemoryRelation(
                source_id="a",
                target_id="b",
                relation_type=RelationType.RELATED_TO
            )
            graph.add_relation(rel)
            
            # Remove it
            assert graph.remove_relation("a", "b", RelationType.RELATED_TO) is True
            
            # Verify removed
            relations = graph.get_relations_from("a")
            assert len(relations) == 0
            
        finally:
            os.unlink(db_path)
    
    def test_get_relations_from(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            graph = GraphRelationsStore(db_path)
            
            # Add multiple relations from same source
            graph.add_relation(MemoryRelation("x", "a", RelationType.DEPENDS_ON))
            graph.add_relation(MemoryRelation("x", "b", RelationType.DEPENDS_ON))
            graph.add_relation(MemoryRelation("x", "c", RelationType.RELATED_TO))
            
            # Get all
            all_rels = graph.get_relations_from("x")
            assert len(all_rels) == 3
            
            # Filter by type
            deps = graph.get_relations_from("x", RelationType.DEPENDS_ON)
            assert len(deps) == 2
            
        finally:
            os.unlink(db_path)
    
    def test_get_relations_to(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            graph = GraphRelationsStore(db_path)
            
            # Add relations pointing to same target
            graph.add_relation(MemoryRelation("a", "target", RelationType.DEPENDS_ON))
            graph.add_relation(MemoryRelation("b", "target", RelationType.RELATED_TO))
            
            # Get incoming relations
            incoming = graph.get_relations_to("target")
            assert len(incoming) == 2
            
        finally:
            os.unlink(db_path)
    
    def test_get_all_related(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            graph = GraphRelationsStore(db_path)
            
            # Add bidirectional relations
            graph.add_relation(MemoryRelation("center", "out", RelationType.DEPENDS_ON))
            graph.add_relation(MemoryRelation("in", "center", RelationType.DEPENDS_ON))
            
            # Get all related (both directions)
            related = graph.get_all_related("center")
            assert len(related) == 2
            
        finally:
            os.unlink(db_path)
    
    def test_get_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            graph = GraphRelationsStore(db_path)
            
            # Create a chain: A -> B -> C -> D
            graph.add_relation(MemoryRelation("A", "B", RelationType.RELATED_TO))
            graph.add_relation(MemoryRelation("B", "C", RelationType.RELATED_TO))
            graph.add_relation(MemoryRelation("C", "D", RelationType.RELATED_TO))
            
            # Find path A to D
            path = graph.get_path("A", "D")
            assert len(path) == 3
            assert path[0].target_id == "B"
            assert path[1].target_id == "C"
            assert path[2].target_id == "D"
            
        finally:
            os.unlink(db_path)
    
    def test_get_dependencies(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            graph = GraphRelationsStore(db_path)
            
            # Create dependency tree
            graph.add_relation(MemoryRelation("app", "config", RelationType.DEPENDS_ON))
            graph.add_relation(MemoryRelation("config", "env", RelationType.DEPENDS_ON))
            graph.add_relation(MemoryRelation("app", "utils", RelationType.DEPENDS_ON))
            
            # Get transitive dependencies
            deps = graph.get_dependencies("app")
            assert "config" in deps
            assert "env" in deps  # Transitive
            assert "utils" in deps
            
        finally:
            os.unlink(db_path)
    
    def test_find_cycles(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            graph = GraphRelationsStore(db_path)
            
            # Create cycle: A -> B -> C -> A
            graph.add_relation(MemoryRelation("A", "B", RelationType.DEPENDS_ON))
            graph.add_relation(MemoryRelation("B", "C", RelationType.DEPENDS_ON))
            graph.add_relation(MemoryRelation("C", "A", RelationType.DEPENDS_ON))
            
            cycles = graph.find_cycles("A")
            assert len(cycles) > 0
            
        finally:
            os.unlink(db_path)
    
    def test_delete_entry_relations(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            graph = GraphRelationsStore(db_path)
            
            # Add relations
            graph.add_relation(MemoryRelation("x", "y", RelationType.RELATED_TO))
            graph.add_relation(MemoryRelation("z", "x", RelationType.DEPENDS_ON))
            
            # Delete all for entry
            deleted = graph.delete_entry_relations("x")
            assert deleted == 2
            
            # Verify
            assert len(graph.get_all_related("x")) == 0
            
        finally:
            os.unlink(db_path)
    
    def test_get_stats(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            graph = GraphRelationsStore(db_path)
            
            # Add various relations
            graph.add_relation(MemoryRelation("a", "b", RelationType.DEPENDS_ON))
            graph.add_relation(MemoryRelation("b", "c", RelationType.RELATED_TO))
            graph.add_relation(MemoryRelation("c", "d", RelationType.DEPENDS_ON))
            
            stats = graph.get_stats()
            assert stats["total_relations"] == 3
            assert stats["by_type"]["depends_on"] == 2
            assert stats["by_type"]["related_to"] == 1
            assert stats["unique_entries"] == 4  # a, b, c, d
            
        finally:
            os.unlink(db_path)


class TestGraphWithUnifiedMemory:
    """Integration tests with UnifiedMemoryService."""
    
    def test_graph_available_in_service(self):
        import tempfile
        from memory.unified import UnifiedMemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = UnifiedMemoryService(
                slow_db_path=os.path.join(tmpdir, "slow.db"),
            )
            
            # Graph store should be available
            assert memory.graph is not None
            
            # Can add relations
            rel = MemoryRelation(
                source_id="mem-1",
                target_id="mem-2",
                relation_type=RelationType.RELATED_TO
            )
            assert memory.graph.add_relation(rel) is True
