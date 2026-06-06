from types import SimpleNamespace

import pytest

from app.modules.inteligencia_gestion_estrategica import service as ia_service


def _user(user_id: int):
    return SimpleNamespace(id_usuario=user_id)


def _incident(
    *,
    client_id: int = 100,
    assignment_taller_id: int | None = None,
    tecnico_id: int | None = None,
    solicitud_taller_id: int | None = None,
    solicitud_estado: str | None = None,
):
    asignacion = None
    if assignment_taller_id is not None or tecnico_id is not None:
        asignacion = SimpleNamespace(id_taller=assignment_taller_id, id_tecnico=tecnico_id)

    solicitudes = []
    if solicitud_taller_id is not None and solicitud_estado is not None:
        solicitudes.append(
            SimpleNamespace(
                id_taller=solicitud_taller_id,
                estado_solicitud=solicitud_estado,
            )
        )

    return SimpleNamespace(
        id_cliente=client_id,
        asignacion_servicio=asignacion,
        solicitudes_taller=solicitudes,
    )


def test_admin_can_access_incident(monkeypatch):
    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["ADMIN"])

    roles = ia_service._validate_incidente_ai_access(
        None,
        _user(1),
        _incident(),
        allow_admin=True,
    )

    assert "ADMIN" in roles


def test_cliente_owner_can_access(monkeypatch):
    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["CLIENTE"])
    monkeypatch.setattr(
        ia_service,
        "get_cliente_by_usuario_id",
        lambda db, user_id: SimpleNamespace(id_cliente=100),
    )

    roles = ia_service._validate_incidente_ai_access(
        None,
        _user(2),
        _incident(client_id=100),
        allow_cliente=True,
    )

    assert "CLIENTE" in roles


def test_cliente_non_owner_is_blocked(monkeypatch):
    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["CLIENTE"])
    monkeypatch.setattr(
        ia_service,
        "get_cliente_by_usuario_id",
        lambda db, user_id: SimpleNamespace(id_cliente=999),
    )

    with pytest.raises(PermissionError):
        ia_service._validate_incidente_ai_access(
            None,
            _user(3),
            _incident(client_id=100),
            allow_cliente=True,
        )


def test_tecnico_assigned_can_access(monkeypatch):
    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["TECNICO"])
    monkeypatch.setattr(
        ia_service,
        "get_tecnico_by_usuario_id",
        lambda db, user_id: SimpleNamespace(id_tecnico=77),
    )

    roles = ia_service._validate_incidente_ai_access(
        None,
        _user(4),
        _incident(tecnico_id=77),
        allow_tecnico=True,
    )

    assert "TECNICO" in roles


def test_taller_with_real_assignment_can_access(monkeypatch):
    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["TALLER"])
    monkeypatch.setattr(
        ia_service,
        "get_taller_by_usuario_id",
        lambda db, user_id: SimpleNamespace(id_taller=55),
    )

    roles = ia_service._validate_incidente_ai_access(
        None,
        _user(5),
        _incident(assignment_taller_id=55),
        allow_taller=True,
    )

    assert "TALLER" in roles


def test_taller_with_accepted_request_can_access(monkeypatch):
    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["TALLER"])
    monkeypatch.setattr(
        ia_service,
        "get_taller_by_usuario_id",
        lambda db, user_id: SimpleNamespace(id_taller=55),
    )

    roles = ia_service._validate_incidente_ai_access(
        None,
        _user(6),
        _incident(solicitud_taller_id=55, solicitud_estado="ACEPTADA"),
        allow_taller=True,
    )

    assert "TALLER" in roles


@pytest.mark.parametrize("estado_solicitud", ["PENDIENTE", "RECHAZADA", "CANCELADA"])
def test_taller_with_non_accepted_request_is_blocked(monkeypatch, estado_solicitud):
    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["TALLER"])
    monkeypatch.setattr(
        ia_service,
        "get_taller_by_usuario_id",
        lambda db, user_id: SimpleNamespace(id_taller=55),
    )

    with pytest.raises(PermissionError):
        ia_service._validate_incidente_ai_access(
            None,
            _user(7),
            _incident(solicitud_taller_id=55, solicitud_estado=estado_solicitud),
            allow_taller=True,
        )
