"""
Real-time safety tests for JACK callback allocation tracking.

This module provides allocation tracking infrastructure to detect memory
allocations in real-time audio callbacks that must never allocate memory.
"""

import gc
import sys
import tracemalloc
import threading
import time
from contextlib import contextmanager
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import pytest
import numpy as np

# Add src to path for standalone execution
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from omega13.audio import AudioEngine
from omega13.config import ConfigManager


class AllocationTracker:
    """
    Tracks memory allocations during function execution using tracemalloc.

    This class provides infrastructure to detect allocations in real-time
    callbacks that must be allocation-free for audio thread safety.
    """

    def __init__(self, track_freed=True):
        """
        Initialize allocation tracker.

        Args:
            track_freed: Whether to track freed memory as well as allocated
        """
        self.track_freed = track_freed
        self.start_snapshot = None
        self.end_snapshot = None
        self.allocations = []
        self.total_allocated = 0
        self.total_freed = 0

    def start_tracking(self):
        """Start tracking allocations."""
        # Clear any existing allocations
        gc.collect()

        if not tracemalloc.is_tracing():
            tracemalloc.start()

        self.start_snapshot = tracemalloc.take_snapshot()

    def stop_tracking(self):
        """Stop tracking and analyze allocations."""
        if not tracemalloc.is_tracing():
            raise RuntimeError("tracemalloc not started")
        if self.start_snapshot is None:
            raise RuntimeError("start_tracking not called")
            
        self.end_snapshot = tracemalloc.take_snapshot()

        # Calculate differences
        top_stats = self.end_snapshot.compare_to(self.start_snapshot, "lineno")

        self.allocations = []
        self.total_allocated = 0
        self.total_freed = 0

        for stat in top_stats:
            self.total_allocated += max(0, stat.size_diff)
            self.total_freed += max(0, -stat.size_diff)

            if stat.size_diff > 0:  # New allocation
                self.allocations.append(
                    {
                        "size": stat.size_diff,
                        "count": stat.count_diff,
                        "filename": stat.traceback.format()[0]
                        if stat.traceback
                        else "unknown",
                        "traceback": stat.traceback,
                    }
                )

    def get_allocation_count(self):
        """Get number of allocation events."""
        return len(self.allocations)

    def get_total_allocated(self):
        """Get total bytes allocated."""
        return self.total_allocated

    def format_report(self):
        """Format a human-readable allocation report."""
        if not self.allocations:
            return "No allocations detected"

        report = [
            f"Total allocations: {len(self.allocations)}",
            f"Total bytes allocated: {self.total_allocated}",
            f"Total bytes freed: {self.total_freed}",
            "",
            "Top allocations:",
        ]

        # Sort by size, show top 10
        sorted_allocs = sorted(self.allocations, key=lambda x: x["size"], reverse=True)
        for i, alloc in enumerate(sorted_allocs[:10]):
            report.append(f"  {i + 1}. {alloc['size']} bytes, {alloc['count']} objects")
            report.append(f"      {alloc['filename']}")

        return "\n".join(report)


@contextmanager
def gc_disabled_allocation_tracking():
    """
    Context manager for allocation tracking with garbage collection disabled.

    This simulates the real-time environment where GC should not run.
    Returns an AllocationTracker instance.

    Usage:
        with gc_disabled_allocation_tracking() as tracker:
            # Code to test
            pass
        print(f"Allocations: {tracker.get_allocation_count()}")
    """
    tracker = AllocationTracker()

    # Disable garbage collection to simulate real-time environment
    gc_was_enabled = gc.isenabled()
    gc.disable()

    try:
        tracker.start_tracking()
        yield tracker
    finally:
        tracker.stop_tracking()

        # Restore original GC state
        if gc_was_enabled:
            gc.enable()


def create_mock_jack_client():
    """Create a mock JACK client for testing."""
    mock_client = Mock()
    mock_client.samplerate = 48000
    mock_client.inports = Mock()

    # Create mock input ports - make it reusable for multiple test runs
    def create_mock_port(port_name):
        mock_port = Mock()
        mock_port.get_array.return_value = np.zeros(512, dtype="float32")
        return mock_port
    
    # Return a fresh mock port on each call
    mock_client.inports.register.side_effect = create_mock_port
    mock_client.set_process_callback = Mock()
    mock_client.status = True
    mock_client.activate = Mock()
    mock_client.deactivate = Mock()
    mock_client.close = Mock()

    return mock_client, []  # Return empty list since ports are created on demand


class TestAllocationTracking:
    """Test the allocation tracking framework itself."""

    def test_tracker_detects_allocations(self):
        """Test that the tracker can detect simple allocations."""
        with gc_disabled_allocation_tracking() as tracker:
            # Make some allocations
            data = [1, 2, 3, 4, 5]  # Should allocate
            data2 = np.array([1, 2, 3, 4])  # Should allocate

        # Should detect allocations
        assert tracker.get_allocation_count() > 0
        assert tracker.get_total_allocated() > 0
        print(f"Detected {tracker.get_allocation_count()} allocations")
        print(tracker.format_report())

    def test_tracker_detects_no_allocations(self):
        """Test that tracker reports zero for allocation-free code."""
        # Pre-allocate variables to avoid allocations during test
        x = 5
        y = 10

        with gc_disabled_allocation_tracking() as tracker:
            # No allocations - just arithmetic
            z = x + y
            result = z * 2

        # Should detect no allocations
        allocations = tracker.get_allocation_count()
        print(f"Clean function allocations: {allocations}")
        print(tracker.format_report())

        # Note: May not be exactly 0 due to Python internals and tracemalloc overhead,
        # but should be very small (<= 5)
        assert allocations <= 5, f"Expected <= 5 allocations, got {allocations}"


class TestJACKCallbackAllocations:
    """Test allocation tracking for JACK audio callback methods."""

    def setup_method(self):
        """Set up test environment."""
        # Mock JACK entirely to avoid audio system dependency
        self.jack_patcher = patch("omega13.audio.jack")
        self.mock_jack = self.jack_patcher.start()

        # Configure mock JACK client
        self.mock_client, self.mock_ports = create_mock_jack_client()
        self.mock_jack.Client.return_value = self.mock_client

    def teardown_method(self):
        """Clean up test environment."""
        self.jack_patcher.stop()

    def test_baseline_process_callback_allocations(self):
        """
        BASELINE TEST: Document current allocation violations in process callback.

        This test establishes the baseline of ~15 allocations that need to be
        fixed in Task 17. It should PASS and document violations, not fail.
        """
        # Create AudioEngine with mocked JACK
        config = ConfigManager()
        engine = AudioEngine(config_manager=config, num_channels=2)

        # Prepare test data - realistic JACK callback with 512 frames
        frames = 512

        # Pre-warm the callback to avoid first-call allocations
        for _ in range(3):
            engine.process(frames)

        # Now measure allocations in a realistic callback scenario
        with gc_disabled_allocation_tracking() as tracker:
            engine.process(frames)

        allocation_count = tracker.get_allocation_count()
        total_bytes = tracker.get_total_allocated()

        print(f"\n=== BASELINE JACK CALLBACK ALLOCATIONS ===")
        print(f"Allocation events: {allocation_count}")
        print(f"Total bytes allocated: {total_bytes}")
        print("\nDetailed report:")
        print(tracker.format_report())
        print("=" * 50)

        # Document that we expect violations (this is a baseline)
        # The goal is to track current state, not enforce zero allocations yet
        assert allocation_count >= 0, "Sanity check: should measure some number >= 0"

        # Log the result for Task 17 reference
        baseline_info = {
            "allocations": allocation_count,
            "bytes": total_bytes,
            "frames": frames,
            "timestamp": time.time(),
        }

        print(f"TASK 17 BASELINE: {baseline_info}")

        # This test should always pass - it's documenting current violations
        return allocation_count, total_bytes

    def test_ring_buffer_write_allocations(self):
        """Test allocations in ring buffer write operations."""
        config = ConfigManager()
        engine = AudioEngine(config_manager=config, num_channels=2)

        # Create test data
        frames = 512
        test_data = np.random.random((frames, 2)).astype("float32")

        # Pre-warm
        engine._write_to_ring_buffer(test_data, frames)

        with gc_disabled_allocation_tracking() as tracker:
            engine._write_to_ring_buffer(test_data, frames)

        allocation_count = tracker.get_allocation_count()
        print(f"Ring buffer write allocations: {allocation_count}")
        print(tracker.format_report())

        # Ring buffer should ideally not allocate
        # But may have some due to NumPy indexing
        assert allocation_count >= 0  # Baseline measurement

    def test_signal_detection_allocations(self):
        """Test allocations in signal detection during callback."""
        config = ConfigManager()
        engine = AudioEngine(config_manager=config, num_channels=2)

        # Create test data with audio signal
        frames = 512
        test_data = np.random.random((frames, 2)).astype("float32") * 0.1

        # Pre-warm signal detector
        engine.signal_detector.update(test_data)

        with gc_disabled_allocation_tracking() as tracker:
            metrics = engine.signal_detector.update(test_data)

        allocation_count = tracker.get_allocation_count()
        print(f"Signal detection allocations: {allocation_count}")
        print(tracker.format_report())

        assert allocation_count >= 0  # Baseline measurement


def test_framework_demonstration():
    """
    Demonstrate the allocation tracking framework with clear pass/fail examples.

    This test shows that the framework correctly identifies both allocation-free
    and allocation-heavy code.
    """
    print("\n=== ALLOCATION TRACKING DEMONSTRATION ===")

    # Test 1: Clean function should have minimal/zero allocations
    print("\n1. Testing allocation-free code...")
    x, y = 10, 20  # Pre-allocate

    with gc_disabled_allocation_tracking() as clean_tracker:
        z = x + y
        result = z * 2

    clean_count = clean_tracker.get_allocation_count()
    print(f"Clean code allocations: {clean_count}")

    # Test 2: Allocation-heavy function should detect many allocations
    print("\n2. Testing allocation-heavy code...")

    with gc_disabled_allocation_tracking() as heavy_tracker:
        # Deliberately allocate memory
        lists = []
        for i in range(10):
            lists.append([i] * 100)  # Many allocations
        arrays = [np.array(lst) for lst in lists]  # More allocations

    heavy_count = heavy_tracker.get_allocation_count()
    print(f"Heavy allocation code allocations: {heavy_count}")
    print(heavy_tracker.format_report())

    # Verify framework works correctly - allow for tracemalloc overhead
    assert clean_count <= 5, (
        f"Clean code should have minimal allocations, got {clean_count}"
    )
    assert heavy_count > 5, (
        f"Heavy code should have many allocations, got {heavy_count}"
    )

    print(f"\n✅ Framework verification passed!")
    print(f"   Clean: {clean_count} allocations")
    print(f"   Heavy: {heavy_count} allocations")


if __name__ == "__main__":
    # Standalone runner following project patterns
    import os

    # Ensure src is in Python path
    sys.path.insert(0, os.path.abspath("./src"))

    print("=== REAL-TIME SAFETY ALLOCATION TESTING ===")
    print("Testing allocation tracking framework...")

    # Run framework demonstration
    test_framework_demonstration()

    # Run tracker self-tests
    tracker_test = TestAllocationTracking()
    print("\n=== TRACKER SELF-TESTS ===")
    tracker_test.test_tracker_detects_allocations()
    tracker_test.test_tracker_detects_no_allocations()

    # Run JACK callback tests
    callback_test = TestJACKCallbackAllocations()
    callback_test.setup_method()

    try:
        print("\n=== JACK CALLBACK BASELINE TESTING ===")
        allocation_count, total_bytes = (
            callback_test.test_baseline_process_callback_allocations()
        )

        print("\n=== INDIVIDUAL COMPONENT TESTING ===")
        callback_test.test_ring_buffer_write_allocations()
        callback_test.test_signal_detection_allocations()

        print(f"\n=== SUMMARY ===")
        print(f"✅ Allocation tracking framework is functional")
        print(
            f"📊 Baseline JACK callback: {allocation_count} allocations, {total_bytes} bytes"
        )
        print(f"🎯 Ready for Task 17 zero-allocation implementation")

    finally:
        callback_test.teardown_method()
