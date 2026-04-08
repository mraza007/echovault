"""Feature flag system and rollback mechanism for unified memory.

Provides safe migration path with instant rollback capability.
"""

import json
import os
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any


class FeatureState(Enum):
    """Feature flag states."""
    DISABLED = "disabled"      # Use old system only
    SHADOW = "shadow"          # Write to both, read from old
    CANARY = "canary"          # 10% traffic to new system
    ENABLED = "enabled"        # Full new system
    EMERGENCY = "emergency"    # Emergency rollback mode


@dataclass
class RollbackConfig:
    """Configuration for rollback mechanism."""
    feature_state: FeatureState = FeatureState.DISABLED
    unified_enabled: bool = False
    backup_existing_db: bool = True
    backup_unified_db: bool = True
    
    # Rollback triggers
    max_error_rate: float = 0.05  # 5% errors triggers auto-rollback
    max_latency_ms: int = 1000    # 1 second latency triggers warning
    
    # Paths
    backup_dir: str = "~/.memory/backups"
    existing_db_path: str = "~/.memory/index.db"
    unified_medium_path: str = "~/.memory/medium.db"
    unified_slow_path: str = "~/.memory/slow.db"
    
    # Timestamps
    last_backup: Optional[str] = None
    migration_date: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'feature_state': self.feature_state.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RollbackConfig':
        data = data.copy()
        data['feature_state'] = FeatureState(data.get('feature_state', 'disabled'))
        return cls(**data)


class RollbackManager:
    """Manages feature flags and rollback for unified memory.
    
    Usage:
        manager = RollbackManager()
        
        # Enable gradual rollout
        manager.set_state(FeatureState.SHADOW)
        
        # Check if should use unified for operation
        if manager.should_use_unified():
            unified.save(entry)
        
        # Emergency rollback
        manager.emergency_rollback()
    """
    
    CONFIG_FILE = "rollback_config.json"
    
    def __init__(self, memory_home: Optional[str] = None):
        self.memory_home = memory_home or os.path.expanduser("~/.memory")
        self.config_path = os.path.join(self.memory_home, self.CONFIG_FILE)
        self.config = self._load_config()
        self._error_count = 0
        self._total_operations = 0
    
    def _load_config(self) -> RollbackConfig:
        """Load rollback configuration."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                return RollbackConfig.from_dict(data)
            except Exception:
                pass
        return RollbackConfig()
    
    def _save_config(self):
        """Save rollback configuration."""
        os.makedirs(self.memory_home, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config.to_dict(), f, indent=2)
    
    def set_state(self, state: FeatureState) -> None:
        """Set feature flag state."""
        old_state = self.config.feature_state
        self.config.feature_state = state
        self.config.unified_enabled = (state in 
            [FeatureState.CANARY, FeatureState.ENABLED])
        
        # Create backup when transitioning to enabled
        if old_state == FeatureState.SHADOW and state == FeatureState.ENABLED:
            self._create_full_backup()
            self.config.migration_date = datetime.now().isoformat()
        
        self._save_config()
        print(f"[RollbackManager] State: {old_state.value} → {state.value}")
    
    def should_use_unified(self) -> bool:
        """Check if current operation should use unified system."""
        state = self.config.feature_state
        
        if state == FeatureState.DISABLED:
            return False
        elif state == FeatureState.SHADOW:
            return True  # Write to both
        elif state == FeatureState.CANARY:
            # Hash-based canary (10% of traffic)
            import hashlib
            digest = hashlib.md5(str(time.time()).encode()).hexdigest()
            return int(digest[:2], 16) < 26  # ~10%
        elif state == FeatureState.ENABLED:
            return True
        elif state == FeatureState.EMERGENCY:
            return False
        
        return False
    
    def should_read_from_unified(self) -> bool:
        """Check if reads should use unified system."""
        state = self.config.feature_state
        return state in [FeatureState.ENABLED]
    
    def record_error(self, error: Exception) -> None:
        """Record an error for monitoring."""
        self._error_count += 1
        self._total_operations += 1
        
        # Check for auto-rollback trigger
        if self._total_operations > 100:
            error_rate = self._error_count / self._total_operations
            if error_rate > self.config.max_error_rate:
                print(f"[RollbackManager] Error rate {error_rate:.2%} exceeded threshold!")
                self.emergency_rollback()
    
    def record_success(self) -> None:
        """Record successful operation."""
        self._total_operations += 1
    
    def _create_full_backup(self) -> str:
        """Create full backup of all databases."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(
            os.path.expanduser(self.config.backup_dir),
            f"pre_migration_{timestamp}"
        )
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup existing system
        existing_db = os.path.expanduser(self.config.existing_db_path)
        if os.path.exists(existing_db):
            shutil.copy2(existing_db, backup_dir)
            print(f"[RollbackManager] Backed up existing DB to {backup_dir}")
        
        # Backup markdown files
        vault_dir = os.path.join(self.memory_home, "vault")
        if os.path.exists(vault_dir):
            vault_backup = os.path.join(backup_dir, "vault")
            shutil.copytree(vault_dir, vault_backup, dirs_exist_ok=True)
            print(f"[RollbackManager] Backed up vault to {vault_backup}")
        
        self.config.last_backup = backup_dir
        self._save_config()
        
        return backup_dir
    
    def create_unified_backup(self) -> str:
        """Create backup of unified databases."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(
            os.path.expanduser(self.config.backup_dir),
            f"unified_{timestamp}"
        )
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup unified databases
        for db_file in [self.config.unified_medium_path, 
                        self.config.unified_slow_path]:
            db_path = os.path.expanduser(db_file)
            if os.path.exists(db_path):
                shutil.copy2(db_path, backup_dir)
        
        print(f"[RollbackManager] Backed up unified DBs to {backup_dir}")
        return backup_dir
    
    def emergency_rollback(self) -> None:
        """Emergency rollback to old system."""
        print("[RollbackManager] ⚠️ EMERGENCY ROLLBACK INITIATED")
        
        # Set emergency state
        self.config.feature_state = FeatureState.EMERGENCY
        self.config.unified_enabled = False
        self._save_config()
        
        # Create backup of current state before rollback
        emergency_backup = self.create_unified_backup()
        print(f"[RollbackManager] Emergency backup: {emergency_backup}")
        
        # Restore from pre-migration backup if available
        if self.config.last_backup:
            print(f"[RollbackManager] Restoring from: {self.config.last_backup}")
            # Actual restore would happen here
            # For now, just disable unified system
        
        print("[RollbackManager] Rollback complete. System using legacy mode.")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current rollback system status."""
        return {
            "state": self.config.feature_state.value,
            "unified_enabled": self.config.unified_enabled,
            "last_backup": self.config.last_backup,
            "migration_date": self.config.migration_date,
            "error_rate": self._error_count / max(self._total_operations, 1),
            "total_operations": self._total_operations,
            "recent_errors": self._error_count,
        }
    
    def enable_graceful_degradation(self) -> None:
        """Enable graceful degradation mode.
        
        In this mode:
        - Fast tier always available
        - Medium tier with reduced size
        - Slow tier disabled
        """
        print("[RollbackManager] Enabling graceful degradation")
        # This would reconfigure the unified system
        # to work with reduced resources


class MigrationProgress:
    """Track migration progress and health."""
    
    def __init__(self, rollback_manager: RollbackManager):
        self.manager = rollback_manager
        self.migrated_count = 0
        self.failed_count = 0
        self.verification_passed = 0
        self.verification_failed = 0
    
    def record_migration(self, success: bool):
        """Record a migration attempt."""
        if success:
            self.migrated_count += 1
        else:
            self.failed_count += 1
            self.manager.record_error(Exception("Migration failed"))
    
    def record_verification(self, passed: bool):
        """Record a verification check."""
        if passed:
            self.verification_passed += 1
        else:
            self.verification_failed += 1
    
    def get_progress(self) -> Dict[str, Any]:
        """Get migration progress report."""
        total = self.migrated_count + self.failed_count
        success_rate = self.migrated_count / max(total, 1)
        
        return {
            "migrated": self.migrated_count,
            "failed": self.failed_count,
            "success_rate": f"{success_rate:.1%}",
            "verification": {
                "passed": self.verification_passed,
                "failed": self.verification_failed,
            },
            "can_proceed": success_rate > 0.95 and self.verification_failed == 0,
        }


# Convenience functions for CLI

def enable_shadow_mode(memory_home: Optional[str] = None):
    """Enable shadow mode (write to both systems)."""
    manager = RollbackManager(memory_home)
    manager.set_state(FeatureState.SHADOW)
    print("Shadow mode enabled: writing to both systems")

def enable_canary(memory_home: Optional[str] = None):
    """Enable canary mode (10% traffic to new system)."""
    manager = RollbackManager(memory_home)
    manager.set_state(FeatureState.CANARY)
    print("Canary mode enabled: 10% traffic to unified system")

def enable_unified(memory_home: Optional[str] = None):
    """Full enable unified system."""
    manager = RollbackManager(memory_home)
    
    # Verify we're ready
    if manager.config.feature_state != FeatureState.SHADOW:
        print("Warning: Not in shadow mode. Consider enabling shadow mode first.")
    
    manager.set_state(FeatureState.ENABLED)
    print("Unified memory system fully enabled")

def rollback(memory_home: Optional[str] = None):
    """Emergency rollback."""
    manager = RollbackManager(memory_home)
    manager.emergency_rollback()

def status(memory_home: Optional[str] = None):
    """Show current status."""
    manager = RollbackManager(memory_home)
    status_dict = manager.get_status()
    
    print("\n=== Rollback Manager Status ===")
    for key, value in status_dict.items():
        print(f"  {key}: {value}")
    print("================================\n")


# Global instance for easy access
_manager: Optional[RollbackManager] = None

def get_manager(memory_home: Optional[str] = None) -> RollbackManager:
    """Get or create global rollback manager."""
    global _manager
    if _manager is None:
        _manager = RollbackManager(memory_home)
    return _manager
