# SPDX-License-Identifier: MPL-2.0

import sqlite3

from solaris.services.review import ReviewService


def test_run_review_retries_transient_locked_error(monkeypatch):
    calls = {"count": 0}

    class _Tx:
        def __enter__(self):
            calls["count"] += 1
            if calls["count"] == 1:
                raise sqlite3.OperationalError("database is locked")
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Db:
        def transaction(self):
            return _Tx()

    service = ReviewService(db=_Db(), editorial_repo=None, engine=None)
    monkeypatch.setattr(service, "_load_review_items", lambda *args, **kwargs: [{"artifact_type": "claim", "artifact_id": "cl_1"}])
    service.engine = type(
        "_Engine",
        (),
        {"review": staticmethod(lambda connection, *, scope, items, policy_profile: {"ok": True, "count": len(items)})},
    )()
    monkeypatch.setattr("solaris.services.review.time.sleep", lambda _seconds: None)

    result = service.run_review(scope=type("_Scope", (), {"key": lambda self: "s"})(), session_id=None, policy_profile="p")

    assert result["ok"] is True
    assert result["count"] == 1
    assert calls["count"] == 2


def test_run_review_does_not_retry_non_lock_operational_error(monkeypatch):
    class _Tx:
        def __enter__(self):
            raise sqlite3.OperationalError("no such table: review_queue")

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Db:
        def transaction(self):
            return _Tx()

    service = ReviewService(db=_Db(), editorial_repo=None, engine=None)
    monkeypatch.setattr("solaris.services.review.time.sleep", lambda _seconds: None)

    try:
        service.run_review(scope=type("_Scope", (), {"key": lambda self: "s"})(), session_id=None, policy_profile="p")
    except sqlite3.OperationalError as exc:
        assert "no such table" in str(exc)
    else:
        raise AssertionError("expected OperationalError")
