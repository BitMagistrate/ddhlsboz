"""Тесты конфигурации GigaChat-провайдера.

Защищаем главное: `verify_ssl` теперь читается из окружения, а не зашит в `False`.
В демо/CI можно оставить `False`, но в production-конфиге Yandex Cloud мы
сможем подложить сертификат Минцифры через `GIGACHAT_CA_BUNDLE`, не правя код.
"""

from __future__ import annotations

import pytest

from app.llm.gigachat import GigaChatProvider


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch) -> None:
    monkeypatch.delenv("GIGACHAT_VERIFY_SSL", raising=False)
    monkeypatch.delenv("GIGACHAT_CA_BUNDLE", raising=False)
    yield


def test_verify_ssl_defaults_to_false() -> None:
    """Обратная совместимость: без env-переменных поведение прежнее (verify=False)."""
    provider = GigaChatProvider(authorization_key="x", scope="GIGACHAT_API_PERS")
    assert provider.verify_ssl is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_verify_ssl_env_truthy(value: str, monkeypatch) -> None:
    monkeypatch.setenv("GIGACHAT_VERIFY_SSL", value)
    provider = GigaChatProvider(authorization_key="x", scope="GIGACHAT_API_PERS")
    assert provider.verify_ssl is True


@pytest.mark.parametrize("value", ["0", "false", "no", "", "garbage"])
def test_verify_ssl_env_falsy(value: str, monkeypatch) -> None:
    monkeypatch.setenv("GIGACHAT_VERIFY_SSL", value)
    provider = GigaChatProvider(authorization_key="x", scope="GIGACHAT_API_PERS")
    assert provider.verify_ssl is False


def test_ca_bundle_path_takes_precedence(monkeypatch) -> None:
    monkeypatch.setenv("GIGACHAT_CA_BUNDLE", "/etc/ssl/certs/min_digital.pem")
    monkeypatch.setenv("GIGACHAT_VERIFY_SSL", "false")  # bundle перевешивает
    provider = GigaChatProvider(authorization_key="x", scope="GIGACHAT_API_PERS")
    assert provider.verify_ssl == "/etc/ssl/certs/min_digital.pem"


def test_explicit_argument_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("GIGACHAT_VERIFY_SSL", "true")
    monkeypatch.setenv("GIGACHAT_CA_BUNDLE", "/some/path.pem")
    provider = GigaChatProvider(
        authorization_key="x",
        scope="GIGACHAT_API_PERS",
        verify_ssl=False,
    )
    assert provider.verify_ssl is False
