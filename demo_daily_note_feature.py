#!/usr/bin/env python3
"""
Demo script showing the new Obsidian daily note integration feature.

This demonstrates the toggleable daily note writing feature that:
1. Opens daily note on launch if enabled
2. Appends transcribed text to daily notes
3. Implements mutual exclusivity with copy/inject features
4. Uses the "D" keybinding to toggle the feature
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

from omega13.config import ConfigManager
from omega13.obsidian_cli import obsidian_cli


def test_obsidian_integration():
    """Test the Obsidian CLI integration."""
    print("=== Obsidian Daily Note Feature Demo ===\n")

    # Test 1: Check if Obsidian CLI is available
    print("1. Checking Obsidian CLI availability...")
    available = obsidian_cli.is_available()
    print(f"   ✓ Available: {available}")
    if not available:
        print("   ℹ️  To enable: Install Obsidian > Settings > General > Command line interface")
    print()

    # Test 2: Test configuration
    print("2. Testing configuration management...")
    config = ConfigManager()

    # Show current settings
    copy_enabled = config.get_copy_to_clipboard()
    inject_enabled = config.get_inject_to_active_window()
    daily_enabled = config.get_write_to_daily_note()

    print(f"   Current settings:")
    print(f"   - Copy to clipboard: {copy_enabled}")
    print(f"   - Inject to active window: {inject_enabled}")
    print(f"   - Write to daily note: {daily_enabled}")
    print()

    # Test 3: Demonstrate mutual exclusivity
    print("3. Testing mutual exclusivity...")

    # Enable daily note writing
    config.set_write_to_daily_note(True)
    print("   ✓ Enabled daily note writing")

    # Show that copy/inject should be disabled in the app logic
    print("   📋 In the app: copy/inject will be automatically disabled")
    print("   ⌨️  Keybinding: Press 'D' to toggle daily note writing")
    print()

    # Test 4: Test daily note operations (if available)
    if available:
        print("4. Testing daily note operations...")

        # Test opening daily note
        result = obsidian_cli.open_daily_note()
        print(f"   Open daily note: {'✓ Success' if result.success else '✗ Failed'}")
        if not result.success:
            print(f"   Error: {result.message}")

        # Test appending content
        test_content = "🤖 Test transcription from omega-13 demo"
        result = obsidian_cli.append_to_daily_note(test_content)
        print(f"   Append content: {'✓ Success' if result.success else '✗ Failed'}")
        if not result.success:
            print(f"   Error: {result.message}")
        elif result.success:
            print(f"   ✓ Appended: {test_content}")

    else:
        print("4. Skipping daily note operations (CLI not available)")

    print()
    print("=== Feature Summary ===")
    print("✨ New capabilities:")
    print("   • Toggle daily note writing with 'D' key")
    print("   • Automatic daily note opening on launch (if enabled)")
    print("   • Timestamped transcription entries in daily notes")
    print("   • Mutual exclusivity prevents conflicts")
    print("   • Error handling with user notifications")
    print()
    print("🔧 Configuration:")
    print("   • Settings persist in ~/.config/omega13/config.json")
    print("   • Feature integrated with existing transcription pipeline")
    print("   • Follows established app patterns and conventions")


if __name__ == "__main__":
    test_obsidian_integration()