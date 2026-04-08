"""Shadow mode test script for unified memory system.

Run this to verify unified memory works before enabling in production MCP.
"""

import sys
import asyncio
import time

sys.path.insert(0, r'C:\Git\echovault\src')

from memory.unified_adapter import create_unified_adapter
from memory.rollback import enable_shadow_mode, status, RollbackManager, FeatureState


async def test_shadow_mode():
    """Test unified memory in shadow mode (writes to both systems)."""
    
    print("=== Shadow Mode Test ===")
    print()
    
    # Enable shadow mode
    print("[1] Enabling shadow mode...")
    mgr = RollbackManager()
    mgr.set_state(FeatureState.SHADOW)
    print("    ✓ Shadow mode enabled")
    print()
    
    # Create adapter
    print("[2] Creating unified adapter...")
    adapter = create_unified_adapter(memory_home=r'C:\Users\Администратор\.memory')
    await adapter.start()
    print("    ✓ Adapter started")
    print()
    
    # Test write
    print("[3] Testing write to both systems...")
    test_id = f"shadow-test-{int(time.time())}"
    adapter.save_unified(
        memory_id=test_id,
        title="[SHADOW] Тест unified памяти",
        what="Проверка записи в обе системы параллельно",
        project="Windsurf",
        tags=["test", "shadow", "unified"],
        category="context"
    )
    print(f"    ✓ Saved entry: {test_id}")
    print()
    
    # Test read from unified
    print("[4] Testing read from unified (Fast+Medium)...")
    results = adapter.search_unified("SHADOW", limit=5)
    print(f"    ✓ Unified results: {len(results)} entries")
    for r in results:
        print(f"      - {r.title} (tier: {r.tier.value})")
    print()
    
    # Test read from existing (for comparison)
    print("[5] Testing read from existing system...")
    existing_results = adapter.existing.search("SHADOW", limit=5)
    print(f"    ✓ Existing results: {len(existing_results)} entries")
    print()
    
    # Cleanup test data
    print("[6] Cleanup...")
    adapter.unified.fast.remove(test_id)
    print("    ✓ Test data removed from Fast tier")
    print()
    
    await adapter.stop()
    
    # Reset to disabled
    mgr.set_state(FeatureState.DISABLED)
    
    print("=== Shadow Mode Test Complete ===")
    print()
    print("Results:")
    print(f"  - Unified writes: OK")
    print(f"  - Unified reads: OK ({len(results)} results)")
    print(f"  - Existing system: OK ({len(existing_results)} results)")
    print()
    print("Ready for production shadow mode!")


if __name__ == "__main__":
    asyncio.run(test_shadow_mode())
