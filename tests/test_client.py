import pytest
from onion_routing.client import weighted_path_selection

def test_weighted_path_selection_sizes_and_flags():
    """Verify that path selection honors minimum hop length and always ends with an explicit exit."""
    mock_relays = [
        {"relay_id": "r1", "host": "127.0.0.1", "port": 9001, "capacity": 10, "is_exit": False},
        {"relay_id": "r2", "host": "127.0.0.1", "port": 9002, "capacity": 5, "is_exit": False},
        {"relay_id": "r3", "host": "127.0.0.1", "port": 9003, "capacity": 2, "is_exit": True},
        {"relay_id": "r4", "host": "127.0.0.1", "port": 9004, "capacity": 100, "is_exit": True},
    ]

    selected = weighted_path_selection(mock_relays, hops=3)
    
    assert len(selected) == 3, "Selected path must be exactly 3 hops long"
    
    selected_ids = [r["relay_id"] for r in selected]
    assert len(set(selected_ids)) == 3, "Relay entries must be distinct (no looped paths)"
    
    # Must enforce the final node is exit-enabled
    assert selected[-1]["is_exit"] is True, "The strict final hop must be an exit node"

def test_insufficient_relays():
    """Guarantee an error is raised if the client requires more hops than live relays."""
    mock_relays = [
        {"relay_id": "r1", "host": "127.0.0.1", "port": 9001, "capacity": 10, "is_exit": True},
    ]
    with pytest.raises(RuntimeError) as exc:
        weighted_path_selection(mock_relays, hops=3)
    assert "Need at least 3 active relays" in str(exc.value)

def test_fallback_no_explicit_exit_capabilities():
    """If no relays strictly declare `is_exit=True`, it should fallback securely to the generic pool using the same rules."""
    mock_relays = [
        {"relay_id": "r1", "host": "127.0.0.1", "port": 9001, "capacity": 10, "is_exit": False},
        {"relay_id": "r2", "host": "127.0.0.1", "port": 9002, "capacity": 5, "is_exit": False},
        {"relay_id": "r3", "host": "127.0.0.1", "port": 9003, "capacity": 2, "is_exit": False},
    ]

    selected = weighted_path_selection(mock_relays, hops=3)
    assert len(selected) == 3
    # No crash implies graceful simulation generic networking applied
