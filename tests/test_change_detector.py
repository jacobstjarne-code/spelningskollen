"""Tester för change_detector."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from collector.change_detector import detect_changes


def test_detect_no_changes():
    existing = {"date": "2026-05-01", "time": "20:00", "venue_id": 1, "ticket_status": "on_sale"}
    incoming = {"date": "2026-05-01", "time": "20:00", "venue_id": 1, "ticket_status": "on_sale"}
    assert detect_changes(existing, incoming) == []


def test_detect_date_change():
    existing = {"date": "2026-05-01", "venue_id": 1, "ticket_status": "on_sale"}
    incoming = {"date": "2026-05-15", "venue_id": 1, "ticket_status": "on_sale"}
    changes = detect_changes(existing, incoming)
    assert len(changes) == 1
    assert changes[0]["field"] == "date"
    assert changes[0]["old_value"] == "2026-05-01"
    assert changes[0]["new_value"] == "2026-05-15"


def test_detect_status_change():
    existing = {"date": "2026-05-01", "ticket_status": "on_sale"}
    incoming = {"date": "2026-05-01", "ticket_status": "sold_out"}
    changes = detect_changes(existing, incoming)
    assert any(c["field"] == "ticket_status" for c in changes)


def test_detect_venue_change():
    existing = {"date": "2026-05-01", "venue_id": 1, "ticket_status": "on_sale"}
    incoming = {"date": "2026-05-01", "venue_id": 2, "ticket_status": "on_sale"}
    changes = detect_changes(existing, incoming)
    assert any(c["field"] == "venue_id" for c in changes)


def test_detect_multiple_changes():
    existing = {"date": "2026-05-01", "time": "20:00", "ticket_status": "on_sale"}
    incoming = {"date": "2026-05-02", "time": "19:00", "ticket_status": "sold_out"}
    changes = detect_changes(existing, incoming)
    assert len(changes) == 3


def test_ignore_empty_incoming():
    """Tom ny data ska inte trigga change."""
    existing = {"date": "2026-05-01", "ticket_status": "on_sale"}
    incoming = {"date": "2026-05-01", "ticket_status": ""}
    changes = detect_changes(existing, incoming)
    assert not any(c["field"] == "ticket_status" for c in changes)
