from datetime import datetime
from types import SimpleNamespace

import pytest

from app.modules.inteligencia_gestion_estrategica import service as ia_service
from app.modules.inteligencia_gestion_estrategica.commission_service import (
    COMMISSION_STATE_CANCELED,
    COMMISSION_STATE_OBSERVED,
    COMMISSION_STATE_PENDING_SETTLEMENT,
    COMMISSION_STATE_SETTLED,
    CommissionInvalidTransitionError,
    CommissionNotFoundError,
)


class DummyDB:
    def __init__(self):
        self.commit_called = 0
        self.rollback_called = 0

    def commit(self):
        self.commit_called += 1

    def rollback(self):
        self.rollback_called += 1


def _user(user_id: int):
    return SimpleNamespace(id_usuario=user_id)


def _commission(state: str, *, referencia_liquidacion=None, id_comision: int = 1):
    return SimpleNamespace(
        id_comision=id_comision,
        estado=state,
        referencia_liquidacion=referencia_liquidacion,
    )


def test_liquidar_comision_desde_pendiente_usa_misma_fecha_y_crea_historial(monkeypatch):
    db = DummyDB()
    current_user = _user(99)
    comision = _commission(COMMISSION_STATE_PENDING_SETTLEMENT)
    fixed_now = datetime(2026, 6, 6, 15, 0, 0)
    calls: dict[str, object] = {}

    class FixedDateTime:
        @staticmethod
        def utcnow():
            return fixed_now

    monkeypatch.setattr(ia_service, "datetime", FixedDateTime)
    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["ADMIN"])
    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_for_update",
        lambda db, id_comision: comision,
    )

    def fake_update(db, commission_obj, **kwargs):
        calls["update"] = kwargs
        commission_obj.estado = kwargs["estado_nuevo"]
        commission_obj.fecha_liquidacion = kwargs["fecha_liquidacion"]
        return commission_obj

    def fake_history(db, **kwargs):
        calls["history"] = kwargs
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(ia_service, "update_comision_plataforma_estado_operativo", fake_update)
    monkeypatch.setattr(ia_service, "create_historial_comision_plataforma", fake_history)
    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_with_history",
        lambda db, id_comision: comision,
    )
    monkeypatch.setattr(
        ia_service,
        "_to_comision_detail_response",
        lambda commission_obj: SimpleNamespace(
            id_comision=commission_obj.id_comision,
            estado=commission_obj.estado,
        ),
    )

    result = ia_service.liquidar_comision_plataforma_service(
        db,
        id_comision=1,
        current_user=current_user,
        referencia_liquidacion="LQ-001",
        observacion="Liquidada por admin",
    )

    assert result.estado == COMMISSION_STATE_SETTLED
    assert result.id_comision == comision.id_comision
    assert calls["update"]["estado_nuevo"] == COMMISSION_STATE_SETTLED
    assert calls["update"]["id_usuario_actor"] == 99
    assert calls["update"]["referencia"] == "LQ-001"
    assert calls["update"]["observacion"] == "Liquidada por admin"
    assert calls["update"]["fecha_accion"] == fixed_now
    assert calls["update"]["fecha_liquidacion"] == fixed_now
    assert calls["history"]["estado_anterior"] == COMMISSION_STATE_PENDING_SETTLEMENT
    assert calls["history"]["estado_nuevo"] == COMMISSION_STATE_SETTLED
    assert calls["history"]["id_usuario_actor"] == 99
    assert calls["history"]["fecha_hora"] == fixed_now
    assert calls["history"]["referencia"] == "LQ-001"
    assert db.commit_called == 1
    assert db.rollback_called == 0


def test_observar_comision_desde_pendiente_hace_strip_y_no_envia_fecha_liquidacion(monkeypatch):
    db = DummyDB()
    comision = _commission(COMMISSION_STATE_PENDING_SETTLEMENT, referencia_liquidacion="REF-OLD")
    calls: dict[str, object] = {}
    fixed_now = datetime(2026, 6, 6, 16, 0, 0)

    class FixedDateTime:
        @staticmethod
        def utcnow():
            return fixed_now

    monkeypatch.setattr(ia_service, "datetime", FixedDateTime)
    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["ADMIN"])
    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_for_update",
        lambda db, id_comision: comision,
    )

    def fake_update(db, commission_obj, **kwargs):
        calls["update"] = kwargs
        return commission_obj

    def fake_history(db, **kwargs):
        calls["history"] = kwargs
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(
        ia_service,
        "update_comision_plataforma_estado_operativo",
        fake_update,
    )
    monkeypatch.setattr(
        ia_service,
        "create_historial_comision_plataforma",
        fake_history,
    )
    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_with_history",
        lambda db, id_comision: comision,
    )
    monkeypatch.setattr(
        ia_service,
        "_to_comision_detail_response",
        lambda commission_obj: SimpleNamespace(
            id_comision=commission_obj.id_comision,
            estado=commission_obj.estado,
        ),
    )

    ia_service.observar_comision_plataforma_service(
        db,
        id_comision=1,
        current_user=_user(50),
        observacion="  Revisar monto  ",
    )

    assert calls["update"]["estado_nuevo"] == COMMISSION_STATE_OBSERVED
    assert calls["update"]["observacion"] == "Revisar monto"
    assert calls["update"]["referencia"] == "REF-OLD"
    assert "fecha_liquidacion" not in calls["update"]
    assert calls["history"]["estado_nuevo"] == COMMISSION_STATE_OBSERVED
    assert calls["history"]["observacion"] == "Revisar monto"
    assert calls["history"]["referencia"] == "REF-OLD"
    assert calls["history"]["fecha_hora"] == fixed_now


def test_cancelar_comision_desde_pendiente_hace_strip_y_no_limpia_referencia(monkeypatch):
    db = DummyDB()
    comision = _commission(COMMISSION_STATE_PENDING_SETTLEMENT, referencia_liquidacion="REF-CAN")
    calls: dict[str, object] = {}
    fixed_now = datetime(2026, 6, 6, 17, 0, 0)

    class FixedDateTime:
        @staticmethod
        def utcnow():
            return fixed_now

    monkeypatch.setattr(ia_service, "datetime", FixedDateTime)
    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["ADMIN"])
    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_for_update",
        lambda db, id_comision: comision,
    )

    def fake_update(db, commission_obj, **kwargs):
        calls["update"] = kwargs
        return commission_obj

    def fake_history(db, **kwargs):
        calls["history"] = kwargs
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(
        ia_service,
        "update_comision_plataforma_estado_operativo",
        fake_update,
    )
    monkeypatch.setattr(
        ia_service,
        "create_historial_comision_plataforma",
        fake_history,
    )
    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_with_history",
        lambda db, id_comision: comision,
    )
    monkeypatch.setattr(
        ia_service,
        "_to_comision_detail_response",
        lambda commission_obj: SimpleNamespace(
            id_comision=commission_obj.id_comision,
            estado=commission_obj.estado,
        ),
    )

    ia_service.cancelar_comision_plataforma_service(
        db,
        id_comision=1,
        current_user=_user(51),
        observacion="  Dato inconsistente  ",
    )

    assert calls["update"]["estado_nuevo"] == COMMISSION_STATE_CANCELED
    assert calls["update"]["observacion"] == "Dato inconsistente"
    assert calls["update"]["referencia"] == "REF-CAN"
    assert "fecha_liquidacion" not in calls["update"]
    assert calls["history"]["estado_nuevo"] == COMMISSION_STATE_CANCELED
    assert calls["history"]["observacion"] == "Dato inconsistente"
    assert calls["history"]["referencia"] == "REF-CAN"
    assert calls["history"]["fecha_hora"] == fixed_now


def test_liquidar_comision_desde_observada_permitido(monkeypatch):
    db = DummyDB()
    comision = _commission(COMMISSION_STATE_OBSERVED, id_comision=2)

    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["ADMIN"])
    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_for_update",
        lambda db, id_comision: comision,
    )
    monkeypatch.setattr(
        ia_service,
        "update_comision_plataforma_estado_operativo",
        lambda db, commission_obj, **kwargs: SimpleNamespace(
            **{**commission_obj.__dict__, "estado": kwargs["estado_nuevo"]}
        ),
    )
    monkeypatch.setattr(
        ia_service,
        "create_historial_comision_plataforma",
        lambda db, **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_with_history",
        lambda db, id_comision: SimpleNamespace(id_comision=id_comision, estado=COMMISSION_STATE_SETTLED),
    )
    monkeypatch.setattr(
        ia_service,
        "_to_comision_detail_response",
        lambda commission_obj: SimpleNamespace(
            id_comision=commission_obj.id_comision,
            estado=commission_obj.estado,
        ),
    )

    result = ia_service.liquidar_comision_plataforma_service(
        db,
        id_comision=2,
        current_user=_user(88),
    )

    assert result.estado == COMMISSION_STATE_SETTLED


def test_invalid_transitions_fail(monkeypatch):
    db = DummyDB()
    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["ADMIN"])
    monkeypatch.setattr(
        ia_service,
        "update_comision_plataforma_estado_operativo",
        lambda *args, **kwargs: pytest.fail("No debe actualizar en transicion invalida."),
    )
    monkeypatch.setattr(
        ia_service,
        "create_historial_comision_plataforma",
        lambda *args, **kwargs: pytest.fail("No debe crear historial en transicion invalida."),
    )

    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_for_update",
        lambda db, id_comision: _commission(COMMISSION_STATE_SETTLED),
    )
    with pytest.raises(CommissionInvalidTransitionError):
        ia_service.cancelar_comision_plataforma_service(
            db,
            id_comision=1,
            current_user=_user(1),
            observacion="Intento invalido",
        )

    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_for_update",
        lambda db, id_comision: _commission(COMMISSION_STATE_CANCELED),
    )
    with pytest.raises(CommissionInvalidTransitionError):
        ia_service.liquidar_comision_plataforma_service(
            db,
            id_comision=1,
            current_user=_user(1),
        )


@pytest.mark.parametrize(
    "service_name, kwargs",
    [
        ("liquidar_comision_plataforma_service", {"referencia_liquidacion": "R1"}),
        ("observar_comision_plataforma_service", {"observacion": "Obs"}),
        ("cancelar_comision_plataforma_service", {"observacion": "Obs"}),
    ],
)
def test_non_admin_cannot_manage_commission(monkeypatch, service_name, kwargs):
    db = DummyDB()
    called = {"get": 0}

    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["TALLER"])
    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_for_update",
        lambda db, id_comision: called.__setitem__("get", called["get"] + 1),
    )

    with pytest.raises(PermissionError):
        getattr(ia_service, service_name)(
            db,
            id_comision=1,
            current_user=_user(2),
            **kwargs,
        )

    assert called["get"] == 0


@pytest.mark.parametrize("observacion", [None, "", "   "])
def test_observar_requires_valid_observacion_before_repository(monkeypatch, observacion):
    db = DummyDB()
    called = {"get": 0}

    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["ADMIN"])
    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_for_update",
        lambda db, id_comision: called.__setitem__("get", called["get"] + 1),
    )

    with pytest.raises(ValueError):
        ia_service.observar_comision_plataforma_service(
            db,
            id_comision=1,
            current_user=_user(1),
            observacion=observacion,
        )

    assert called["get"] == 0


@pytest.mark.parametrize("observacion", [None, "", "   "])
def test_cancelar_requires_valid_observacion_before_repository(monkeypatch, observacion):
    db = DummyDB()
    called = {"get": 0}

    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["ADMIN"])
    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_for_update",
        lambda db, id_comision: called.__setitem__("get", called["get"] + 1),
    )

    with pytest.raises(ValueError):
        ia_service.cancelar_comision_plataforma_service(
            db,
            id_comision=1,
            current_user=_user(1),
            observacion=observacion,
        )

    assert called["get"] == 0


@pytest.mark.parametrize(
    "service_name, kwargs",
    [
        ("liquidar_comision_plataforma_service", {"referencia_liquidacion": None, "observacion": None}),
        ("observar_comision_plataforma_service", {"observacion": "Observada"}),
        ("cancelar_comision_plataforma_service", {"observacion": "Cancelada"}),
    ],
)
def test_commission_not_found_raises(monkeypatch, service_name, kwargs):
    db = DummyDB()

    monkeypatch.setattr(ia_service, "get_roles_by_usuario_id", lambda db, user_id: ["ADMIN"])
    monkeypatch.setattr(
        ia_service,
        "get_comision_plataforma_by_id_for_update",
        lambda db, id_comision: None,
    )

    with pytest.raises(CommissionNotFoundError):
        getattr(ia_service, service_name)(
            db,
            id_comision=404,
            current_user=_user(10),
            **kwargs,
        )
