"""
Example usage of the window aggregation service.

This script demonstrates how to use the aggregator to process frame data.
"""

from aggregator import (
    run_window_aggregator,
    run_window_aggregator_for_session,
    get_active_sessions
)

# Example 1: Run aggregation for all active sessions (processes one window per session)
def example_run_all():
    """Process one window for each active session."""
    processed_count = run_window_aggregator()
    print(f"Processed {processed_count} windows across all sessions")

# Example 2: Run aggregation for a specific session (processes all available windows)
def example_run_session(session_id: str):
    """Process all available windows for a specific session."""
    processed_count = run_window_aggregator_for_session(session_id)
    print(f"Processed {processed_count} windows for session {session_id}")

# Example 3: Get list of active sessions
def example_get_sessions():
    """Get all active session IDs."""
    sessions = get_active_sessions()
    print(f"Active sessions: {sessions}")
    return sessions

# Example 4: Continuous aggregation (for background task)
def example_continuous_aggregation():
    """Run aggregation continuously (for use as background task)."""
    import time
    
    while True:
        try:
            processed = run_window_aggregator()
            if processed > 0:
                print(f"Processed {processed} windows")
            time.sleep(5)  # Wait 5 seconds before next run
        except KeyboardInterrupt:
            print("Stopping aggregation...")
            break
        except Exception as e:
            print(f"Error in aggregation: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Example usage
    print("Window Aggregation Service Examples")
    print("=" * 50)
    
    # Get active sessions
    sessions = example_get_sessions()
    
    if sessions:
        # Process all windows for first session
        example_run_session(sessions[0])
    else:
        print("No active sessions found")

