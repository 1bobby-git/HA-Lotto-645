"""Focused tests for automatic managed connection and preserved journals."""
import asyncio
import ast
import copy
import hashlib
import json
import re
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from custom_components.lotto_645.managed_connection import (
    ManagedConnection,
    connection_values,
    without_user_connection,
)
from custom_components.lotto_645.const import (
    CONF_SERVICE_URL as URL,
    CONF_SERVICE_TOKEN as TOKEN,
    CONF_SERVICE_CERT as CERT,
)

R = Path(__file__).resolve().parents[1] / "custom_components/lotto_645"
OLD_ORIGIN = "https://lottolab.toiss.kr"
NEW_ORIGIN = "https://lotto.formulab.kr"


class MemoryStore:
    def __init__(self, value=None, fail=False):
        self.value = value
        self.fail = fail
        self.writes = 0

    async def async_load(self):
        return copy.deepcopy(self.value)

    async def async_save(self, value):
        if self.fail:
            raise OSError("disk unavailable")
        self.value = copy.deepcopy(value)
        self.writes += 1


class Response:
    content_type = "application/json"

    def __init__(self, iid, status=201):
        self.iid = iid
        self.status = status
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def iter_chunked(self, _):
        yield json.dumps({
            "contract_version": 1,
            "installation_id": self.iid,
            "device_id": "ha-" + self.iid,
            "enrolled": True,
            "expires_at": time.time() + 90 * 86400,
        }).encode()


class Session:
    def __init__(self, status=201):
        self.calls = []
        self.status = status

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(kwargs["json"]["installation_id"], self.status)


LEGACY = {URL: "https://example.com", TOKEN: "x" * 43, CERT: "ab" * 32}


def test_migrate_operator_credential_without_network_or_identity_change():
    async def case():
        store = MemoryStore()
        manager = ManagedConnection(store)
        session = Session()
        await manager.load(LEGACY)
        await manager.ensure_enrolled(session)
        assert manager.values == LEGACY
        assert not session.calls
        second = ManagedConnection(store)
        await second.load()
        assert second.values == LEGACY
    asyncio.run(case())


def test_new_installation_enrolls_directly_without_account():
    async def case():
        store = MemoryStore()
        manager = ManagedConnection(store)
        await manager.load()
        initial = copy.deepcopy(store.value)
        session = Session()
        await manager.ensure_enrolled(session)
        assert len(session.calls) == 1
        url, request = session.calls[0]
        assert url == NEW_ORIGIN + "/v1/ha/installations"
        assert request["json"]["installation_id"] == initial["installation_id"]
        assert request["json"]["credential"] == initial["credentials"][TOKEN]
        assert manager.state["source"] == "automatic"
        assert manager.state["enrolled"] is True
        assert manager.state["expires_at"] > time.time() + 86400
        assert manager.values[TOKEN] == initial["credentials"][TOKEN]
        assert manager.values[URL] == NEW_ORIGIN
    asyncio.run(case())


def test_concurrent_setup_shares_one_enrollment():
    async def case():
        store = MemoryStore()
        manager = ManagedConnection(store)
        await manager.load()
        session = Session()
        await asyncio.gather(
            manager.ensure_enrolled(session),
            manager.ensure_enrolled(session),
        )
        assert len(session.calls) == 1
    asyncio.run(case())


def test_member_connection_is_preserved_for_server_side_membership_tier():
    async def case():
        old = {
            "version": 1,
            "source": "member",
            "credentials": {URL: OLD_ORIGIN, TOKEN: "t" * 43, CERT: ""},
            "enrolled": True,
            "device_id": "d" * 32,
            "refresh_token": "r" * 64,
            "access_expires_at": time.time() + 600,
            "context_secret": "context-secret",
        }
        old_scope = hashlib.sha256(
            (OLD_ORIGIN + "\0" + "t" * 43).encode()
        ).hexdigest()[:24]
        store = MemoryStore(old)
        manager = ManagedConnection(store)
        await manager.load()
        assert manager.state["source"] == "member"
        assert manager.state["device_id"] == "d" * 32
        assert manager.values[URL] == NEW_ORIGIN
        assert manager.values[TOKEN] == "t" * 43
        assert manager.journal_scope == old_scope
        assert manager.context_secret == "context-secret"
        assert manager.state["refresh_token"] == "r" * 64
        assert manager.needs_refresh is False
    asyncio.run(case())


def test_failed_private_save_does_not_mark_new_identity_done():
    async def case():
        manager = ManagedConnection(MemoryStore(fail=True))
        with pytest.raises(OSError):
            await manager.load()
        assert manager.state is None
    asyncio.run(case())


def test_corrupt_store_is_not_replaced_by_new_identity():
    async def case():
        store = MemoryStore({"version": 9})
        manager = ManagedConnection(store)
        with pytest.raises(ValueError):
            await manager.load(LEGACY)
        assert store.value == {"version": 9}
        assert store.writes == 0
    asyncio.run(case())


def test_clean_options_preserves_user_settings_and_removes_transport():
    raw = {
        **LEGACY,
        "_member_link": {"source": "member"},
        "generation_rules": {"fixed": [1]},
        "formula_options": {"x": 1},
        "selected_methods": ["uniform_floyd"],
        "saju_remote_consent": True,
    }
    cleaned = without_user_connection(raw)
    assert cleaned == {
        "selected_methods": ["uniform_floyd"],
        "saju_remote_consent": True,
    }


def test_config_flow_keeps_automatic_setup_and_optional_member_link():
    tree = ast.parse((R / "config_flow.py").read_text(encoding="utf-8"))
    names = {
        n.name
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "async_step_account" in names
    assert not names & {
        "async_step_service",
        "async_step_formula_options",
        "async_step_generation_rules",
        "async_step_reauth_confirm",
    }
    menus = [
        ast.literal_eval(k.value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        for k in n.keywords
        if k.arg == "menu_options"
    ]
    assert menus == [["account", "recommendations", "saju", "purchases"]]
    user = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_step_user"
    )
    source = ast.unparse(user)
    assert "async_create_entry" in source
    assert "member_link" not in source


def test_retired_automatic_origin_is_rewritten_without_identity_change():
    async def case():
        iid = "a" * 32
        token = "t" * 43
        old = {
            "version": 1,
            "source": "automatic",
            "installation_id": iid,
            "credentials": {URL: OLD_ORIGIN, TOKEN: token, CERT: ""},
            "enrolled": True,
            "expires_at": time.time() + 30 * 86400,
        }
        old_scope = hashlib.sha256(
            (OLD_ORIGIN + "\0" + token).encode()
        ).hexdigest()[:24]
        store = MemoryStore(old)
        manager = ManagedConnection(store)
        await manager.load()
        assert manager.values[URL] == NEW_ORIGIN
        assert manager.values[TOKEN] == token
        assert manager.state["installation_id"] == iid
        assert manager.journal_scope == old_scope
    asyncio.run(case())


def test_removed_values_are_never_sent_to_generation():
    source = (R / "service_runtime.py").read_text(encoding="utf-8")
    assert "options.update(self.entry.options.get('formula_options'" not in source
    assert "options['generation_rules']" not in source
    assert "async_start_reauth" not in source


def test_connection_client_can_update_token_without_replacing_journals():
    tree = ast.parse((R / "service_runtime.py").read_text(encoding="utf-8"))
    method = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_configure_connection"
    )

    class Client:
        def __init__(self, session, url, token, **kwargs):
            self.token = token

        def set_access_token(self, value):
            self.token = value

    namespace = {
        "DOMAIN": "lotto_645",
        "CONF_SERVICE_URL": URL,
        "CONF_SERVICE_TOKEN": TOKEN,
        "CONF_SERVICE_CERT": CERT,
        "LottoLabClient": Client,
        "async_get_clientsession": lambda _: None,
        "Store": lambda h, v, key: key,
        "RemoteGeneration": lambda client, store: SimpleNamespace(
            client=client, store=store
        ),
    }
    exec(
        compile(ast.Module(body=[method], type_ignores=[]), "<runtime>", "exec"),
        namespace,
    )
    owner = SimpleNamespace(
        client=None,
        connection={},
        hass=None,
        entry=SimpleNamespace(entry_id="entry"),
        connection_manager=SimpleNamespace(journal_scope="fixed-journal"),
    )
    apply = namespace["_configure_connection"]
    apply(owner, LEGACY)
    before = owner.client
    pending = owner.generator
    ai = owner.ai_generator
    apply(owner, {**LEGACY, TOKEN: "rotated-access-token-1234567890"})
    assert owner.client is before
    assert owner.generator is pending
    assert owner.ai_generator is ai
    assert owner.connection[TOKEN] == "rotated-access-token-1234567890"


def test_config_entry_migration_targets_automatic_connection_schema_v5():
    source = (R / "__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    migrate = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_migrate_entry"
    )
    text = ast.unparse(migrate)
    assert "entry.version > 5" in text
    assert "version=5" in text
    assert "member_connection_pending" not in source
    assert "member_service_unavailable" not in source


def test_panel_upgrade_accepts_recent_release_tags():
    source = (R / "ticket_panel.py").read_text(encoding="utf-8")
    for tag in (
        "lotto-ticket-panel-v2-1-0",
        "lotto-ticket-panel-v2-1-1",
        "lotto-ticket-panel-v2-1-2",
        "lotto-ticket-panel-v2-2-0",
    ):
        assert repr(tag) in source
    assert "PANEL_TAG = 'lotto-ticket-panel-v2-2-1'" in source


def test_member_refresh_preserves_identity_and_uses_one_rotation(monkeypatch):
    from custom_components.lotto_645.member_link import state_from_tokens
    import custom_components.lotto_645.member_link as link

    async def case():
        tokens = {
            "access_token": "a" * 43,
            "refresh_token": "b" * 64,
            "device_id": "c" * 32,
            "expires_in": 900,
        }
        saved = state_from_tokens(tokens)
        saved["access_expires_at"] = 0
        store = MemoryStore(saved)
        manager = ManagedConnection(store)
        await manager.load()
        original_scope = manager.journal_scope
        calls = []

        async def exchange(session, path, body):
            calls.append(dict(body))
            return {
                **tokens,
                "token_type": "Bearer",
                "access_token": "d" * 43,
                "refresh_token": "e" * 64,
            }

        monkeypatch.setattr(link, "request", exchange)
        await asyncio.gather(
            manager.ensure_enrolled(None),
            manager.ensure_enrolled(None),
        )
        assert len(calls) == 1
        assert manager.state["source"] == "member"
        assert manager.values[TOKEN] == "d" * 43
        assert manager.journal_scope == original_scope
        assert "pending_rotation" not in store.value

    asyncio.run(case())
