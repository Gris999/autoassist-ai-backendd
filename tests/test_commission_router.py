from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.db.session import get_db
from app.modules.inteligencia_gestion_estrategica import router as ia_router
from app.modules.inteligencia_gestion_estrategica import service as ia_service
from app.modules.inteligencia_gestion_estrategica.commission_service import (
    CommissionInvalidTransitionError,
    CommissionNotFoundError,
)
from app.shared.dependencies.auth import get_current_user


class DummyRoleResult:
    def scalars(self):
        return self

    def all(self):
        return ["ADMIN"]


class DummyDB:
    def execute(self, statement):
        return DummyRoleResult()


@pytest.fixture
def admin_client(fastapi_app):
    def override_current_user():
        return SimpleNamespace(id_usuario=99)

    def override_db():
        return DummyDB()

    fastapi_app.dependency_overrides[get_current_user] = override_current_user
    fastapi_app.dependency_overrides[get_db] = override_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


def _detail_response_payload():
    return {
        "id_comision": 1,
        "id_pago_servicio": 10,
        "id_incidente": 20,
        "titulo_incidente": "Incidente de prueba",
        "id_taller": 30,
        "nombre_taller": "Taller Central",
        "monto_total_pago": Decimal("100.00"),
        "porcentaje": Decimal("10.00"),
        "monto_comision": Decimal("10.00"),
        "estado": "PENDIENTE_LIQUIDACION",
        "estado_pago": "PAGADO",
        "fecha_pago": datetime(2026, 6, 6, 12, 0, 0).isoformat(),
        "fecha_calculo": datetime(2026, 6, 6, 12, 5, 0).isoformat(),
        "referencia_transaccion": "TRX-001",
        "fecha_liquidacion": datetime(2026, 6, 6, 13, 0, 0).isoformat(),
        "observacion_estado": "Liquidada por admin",
        "referencia_liquidacion": "LQ-001",
        "id_usuario_ultima_accion": 99,
        "fecha_ultima_accion": datetime(2026, 6, 6, 13, 0, 0).isoformat(),
        "metodo_pago": "TARJETA",
        "detalles_pago": [],
        "historial": [
            {
                "id_historial_comision": 1,
                "id_comision": 1,
                "estado_anterior": "PENDIENTE_LIQUIDACION",
                "estado_nuevo": "LIQUIDADA",
                "observacion": "Liquidada por admin",
                "referencia": "LQ-001",
                "id_usuario_actor": 99,
                "fecha_hora": datetime(2026, 6, 6, 13, 0, 0).isoformat(),
            }
        ],
    }


def _build_commission_with_operational_metadata():
    detalle = SimpleNamespace(
        id_detalle_pago=1,
        descripcion="Servicio",
        cantidad=1,
        precio_unitario=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        id_taller_auxilio=200,
        taller_auxilio=SimpleNamespace(
            tipo_auxilio=SimpleNamespace(nombre="REMOLQUE")
        ),
    )
    pago = SimpleNamespace(
        id_incidente=20,
        monto_total=Decimal("100.00"),
        estado_pago="PAGADO",
        fecha_pago=datetime(2026, 6, 6, 12, 0, 0),
        referencia_transaccion="TRX-001",
        metodo_pago="TARJETA",
        detalles_pago=[detalle],
        incidente=SimpleNamespace(titulo="Incidente de prueba"),
    )
    historial = SimpleNamespace(
        id_historial_comision=1,
        id_comision=1,
        estado_anterior="PENDIENTE_LIQUIDACION",
        estado_nuevo="LIQUIDADA",
        observacion="Liquidada por admin",
        referencia="LQ-001",
        id_usuario_actor=99,
        fecha_hora=datetime(2026, 6, 6, 13, 0, 0),
    )
    return SimpleNamespace(
        id_comision=1,
        id_pago_servicio=10,
        id_taller=30,
        porcentaje=Decimal("10.00"),
        monto_comision=Decimal("10.00"),
        estado="LIQUIDADA",
        fecha_calculo=datetime(2026, 6, 6, 12, 5, 0),
        fecha_liquidacion=datetime(2026, 6, 6, 13, 0, 0),
        observacion_estado="Liquidada por admin",
        referencia_liquidacion="LQ-001",
        id_usuario_ultima_accion=99,
        fecha_ultima_accion=datetime(2026, 6, 6, 13, 0, 0),
        pago_servicio=pago,
        taller=SimpleNamespace(nombre_taller="Taller Central"),
        historial=[historial],
    )


def test_commission_admin_routes_are_registered(fastapi_app):
    route_index = {
        (route.path, tuple(sorted(route.methods)))
        for route in fastapi_app.routes
        if hasattr(route, "methods")
    }

    assert ("/api/v1/inteligencia/comisiones/{id_comision}/liquidar", ("POST",)) in route_index
    assert ("/api/v1/inteligencia/comisiones/{id_comision}/observar", ("POST",)) in route_index
    assert ("/api/v1/inteligencia/comisiones/{id_comision}/cancelar", ("POST",)) in route_index


def test_liquidar_endpoint_calls_service_and_passes_body(admin_client, monkeypatch):
    captured = {}

    def fake_service(db, id_comision, current_user, referencia_liquidacion=None, observacion=None):
        captured["db"] = db
        captured["id_comision"] = id_comision
        captured["current_user"] = current_user
        captured["referencia_liquidacion"] = referencia_liquidacion
        captured["observacion"] = observacion
        return _detail_response_payload()

    monkeypatch.setattr(ia_router, "liquidar_comision_plataforma_service", fake_service)

    response = admin_client.post(
        "/api/v1/inteligencia/comisiones/15/liquidar",
        json={
            "referencia_liquidacion": "  LQ-009  ",
            "observacion": "  Liquidada por admin  ",
        },
    )

    assert response.status_code == 200
    assert captured["id_comision"] == 15
    assert captured["current_user"].id_usuario == 99
    assert captured["referencia_liquidacion"] == "LQ-009"
    assert captured["observacion"] == "Liquidada por admin"


def test_observar_endpoint_calls_service_and_passes_body(admin_client, monkeypatch):
    captured = {}

    def fake_service(db, id_comision, current_user, observacion):
        captured["id_comision"] = id_comision
        captured["current_user"] = current_user
        captured["observacion"] = observacion
        return _detail_response_payload() | {"estado": "OBSERVADA"}

    monkeypatch.setattr(ia_router, "observar_comision_plataforma_service", fake_service)

    response = admin_client.post(
        "/api/v1/inteligencia/comisiones/16/observar",
        json={"observacion": "  Revisar monto  "},
    )

    assert response.status_code == 200
    assert captured["id_comision"] == 16
    assert captured["current_user"].id_usuario == 99
    assert captured["observacion"] == "Revisar monto"


def test_cancelar_endpoint_calls_service_and_passes_body(admin_client, monkeypatch):
    captured = {}

    def fake_service(db, id_comision, current_user, observacion):
        captured["id_comision"] = id_comision
        captured["current_user"] = current_user
        captured["observacion"] = observacion
        return _detail_response_payload() | {"estado": "CANCELADA"}

    monkeypatch.setattr(ia_router, "cancelar_comision_plataforma_service", fake_service)

    response = admin_client.post(
        "/api/v1/inteligencia/comisiones/17/cancelar",
        json={"observacion": "  Dato inconsistente  "},
    )

    assert response.status_code == 200
    assert captured["id_comision"] == 17
    assert captured["current_user"].id_usuario == 99
    assert captured["observacion"] == "Dato inconsistente"


@pytest.mark.parametrize(
    ("route", "exception", "expected_status"),
    [
        ("liquidar", CommissionNotFoundError("No existe"), 404),
        ("liquidar", CommissionInvalidTransitionError("Invalida"), 400),
        ("liquidar", PermissionError("Sin permiso"), 403),
        ("liquidar", ValueError("Dato invalido"), 400),
        ("observar", CommissionNotFoundError("No existe"), 404),
        ("observar", CommissionInvalidTransitionError("Invalida"), 400),
        ("observar", PermissionError("Sin permiso"), 403),
        ("observar", ValueError("Dato invalido"), 400),
        ("cancelar", CommissionNotFoundError("No existe"), 404),
        ("cancelar", CommissionInvalidTransitionError("Invalida"), 400),
        ("cancelar", PermissionError("Sin permiso"), 403),
        ("cancelar", ValueError("Dato invalido"), 400),
    ],
)
def test_commission_admin_routes_translate_errors(
    admin_client,
    monkeypatch,
    route,
    exception,
    expected_status,
):
    service_name = f"{route}_comision_plataforma_service"

    def fake_service(*args, **kwargs):
        raise exception

    monkeypatch.setattr(ia_router, service_name, fake_service)

    body = {"observacion": "Motivo"}
    if route == "liquidar":
        body = {"referencia_liquidacion": "LQ-001", "observacion": "Motivo"}

    response = admin_client.post(f"/api/v1/inteligencia/comisiones/5/{route}", json=body)

    assert response.status_code == expected_status
    assert response.json()["detail"] == str(exception)


def test_to_comision_list_response_includes_operational_metadata():
    comision = _build_commission_with_operational_metadata()

    response = ia_service._to_comision_list_response(comision)

    assert response.fecha_liquidacion == comision.fecha_liquidacion
    assert response.observacion_estado == "Liquidada por admin"
    assert response.referencia_liquidacion == "LQ-001"
    assert response.id_usuario_ultima_accion == 99
    assert response.fecha_ultima_accion == comision.fecha_ultima_accion
    assert "historial" not in response.model_dump()


def test_to_comision_detail_response_includes_operational_metadata_and_history():
    comision = _build_commission_with_operational_metadata()

    response = ia_service._to_comision_detail_response(comision)

    assert response.fecha_liquidacion == comision.fecha_liquidacion
    assert response.observacion_estado == "Liquidada por admin"
    assert response.referencia_liquidacion == "LQ-001"
    assert response.id_usuario_ultima_accion == 99
    assert response.fecha_ultima_accion == comision.fecha_ultima_accion
    assert len(response.historial) == 1
    assert response.historial[0].estado_nuevo == "LIQUIDADA"
