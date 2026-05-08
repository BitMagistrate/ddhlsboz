"""Тесты 152-ФЗ контракта: согласие, экспорт, право на забвение."""

from __future__ import annotations

import pytest

from app import privacy


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    privacy.get_store().reset()
    yield
    privacy.get_store().reset()


def test_consent_set_and_query() -> None:
    store = privacy.get_store()
    rec = store.set_consent("u1", "personalization", granted=True)
    assert rec.user_id == "u1"
    assert rec.granted is True
    assert store.has_consent("u1", "personalization") is True
    assert store.has_consent("u1", "marketing") is False


def test_consent_revoke_overrides_prior() -> None:
    store = privacy.get_store()
    store.set_consent("u1", "marketing", granted=True)
    assert store.has_consent("u1", "marketing") is True
    store.set_consent("u1", "marketing", granted=False)
    assert store.has_consent("u1", "marketing") is False


def test_unknown_purpose_rejected() -> None:
    with pytest.raises(ValueError):
        privacy.get_store().set_consent("u1", "definitely_unknown", granted=True)


def test_history_appended_until_forget() -> None:
    store = privacy.get_store()
    store.append_history("u1", {"event": "route_built", "query": "Пушкин"})
    out = store.export("u1")
    assert out["found"] is True
    assert out["data"]["history"]


def test_forget_removes_user_data() -> None:
    store = privacy.get_store()
    store.append_history("u1", {"event": "x"})
    res = store.forget("u1")
    assert res["deleted"] is True
    assert res["audit_stub"].startswith("deleted-")
    out = store.export("u1")
    assert out["found"] is False


def test_forget_unknown_user_safe() -> None:
    res = privacy.get_store().forget("nope")
    assert res["deleted"] is False
    assert res["reason"] == "not_found"


def test_export_contains_consents() -> None:
    store = privacy.get_store()
    store.set_consent("u1", "service_delivery", granted=True)
    out = store.export("u1")
    assert out["found"] is True
    consents = out["data"]["consents"]
    assert any(c["purpose"] == "service_delivery" and c["granted"] for c in consents)


def test_policy_summary_machine_readable() -> None:
    pol = privacy.policy_summary()
    assert pol["law"].startswith("152-ФЗ")
    assert pol["data_localization"].startswith("Все данные")
    assert pol["international_transfer"] is False
    purposes = {p["id"] for p in pol["purposes"]}
    assert "service_delivery" in purposes


def test_history_capped_at_500() -> None:
    store = privacy.get_store()
    for i in range(600):
        store.append_history("u1", {"event": str(i)})
    out = store.export("u1")
    assert len(out["data"]["history"]) == 500
