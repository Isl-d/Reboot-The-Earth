"""The hash-chained decision log (CLAUDE.md section 7.6)."""
from backend.audit import GENESIS, AuditLog, digest


def test_an_empty_chain_is_valid():
    log = AuditLog()
    assert log.verify() == (True, None)
    assert log.head == GENESIS


def test_each_record_points_at_the_one_before_it():
    log = AuditLog()
    first = log.append("decision", {"truck": "TRK-07"})
    second = log.append("approve", {"truck": "TRK-07", "chosen": "C"})
    assert first.prev_hash == GENESIS
    assert second.prev_hash == first.hash
    assert log.verify() == (True, None)


def test_editing_history_breaks_the_chain():
    log = AuditLog()
    log.append("decision", {"chosen": "C"})
    log.append("approve", {"chosen": "C"})
    log.records[0].payload["chosen"] = "A"
    ok, broken_at = log.verify()
    assert not ok and broken_at == 1


def test_deleting_a_record_breaks_the_chain():
    log = AuditLog()
    for i in range(3):
        log.append("decision", {"i": i})
    del log.records[1]
    assert log.verify()[0] is False


def test_the_same_content_always_hashes_the_same():
    a = digest(GENESIS, 1, 1.0, "decision", {"b": 2, "a": 1})
    b = digest(GENESIS, 1, 1.0, "decision", {"a": 1, "b": 2})
    assert a == b                                   # key order must not matter


def test_evidence_is_stored_with_the_decision():
    log = AuditLog()
    rec = log.append("approve", {"chosen": "C", "evidence": {"air_c": 28.0}})
    assert rec.payload["evidence"]["air_c"] == 28.0


def test_reset_clears_the_chain():
    log = AuditLog()
    log.append("decision", {})
    log.reset()
    assert log.records == [] and log.head == GENESIS
