from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.inteligencia_gestion_estrategica.schemas import (
    CancelarComisionRequest,
    ComisionPlataformaDetailResponse,
    ComisionPlataformaListResponse,
    HistorialComisionPlataformaResponse,
    LiquidarComisionRequest,
    ObservarComisionRequest,
)


def _commission_list_payload():
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
        "fecha_pago": datetime(2026, 6, 6, 12, 0, 0),
        "fecha_calculo": datetime(2026, 6, 6, 12, 5, 0),
        "referencia_transaccion": "TRX-001",
    }


def test_liquidar_comision_request_strips_and_accepts_optionals():
    payload = LiquidarComisionRequest(
        referencia_liquidacion="  REF-001  ",
        observacion="  Liquidada manualmente  ",
    )

    assert payload.referencia_liquidacion == "REF-001"
    assert payload.observacion == "Liquidada manualmente"


@pytest.mark.parametrize(
    ("payload", "expected_reference", "expected_observation"),
    [
        ({}, None, None),
        ({"referencia_liquidacion": "", "observacion": ""}, None, None),
        ({"referencia_liquidacion": "   ", "observacion": "   "}, None, None),
        ({"referencia_liquidacion": None, "observacion": None}, None, None),
    ],
)
def test_liquidar_comision_request_normalizes_empty_strings_to_none(
    payload,
    expected_reference,
    expected_observation,
):
    request = LiquidarComisionRequest(**payload)

    assert request.referencia_liquidacion == expected_reference
    assert request.observacion == expected_observation


def test_liquidar_comision_request_rejects_extra_fields():
    with pytest.raises(ValidationError):
        LiquidarComisionRequest(otro_campo="x")


def test_observar_comision_request_accepts_and_strips_observacion():
    request = ObservarComisionRequest(observacion="  Revisar monto  ")

    assert request.observacion == "Revisar monto"


@pytest.mark.parametrize("observacion", [None, "", "   "])
def test_observar_comision_request_rejects_invalid_observacion(observacion):
    with pytest.raises(ValidationError):
        ObservarComisionRequest(observacion=observacion)


def test_observar_comision_request_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ObservarComisionRequest(observacion="Ok", referencia="X")


def test_cancelar_comision_request_accepts_and_strips_observacion():
    request = CancelarComisionRequest(observacion="  Dato inconsistente  ")

    assert request.observacion == "Dato inconsistente"


@pytest.mark.parametrize("observacion", [None, "", "   "])
def test_cancelar_comision_request_rejects_invalid_observacion(observacion):
    with pytest.raises(ValidationError):
        CancelarComisionRequest(observacion=observacion)


def test_cancelar_comision_request_rejects_extra_fields():
    with pytest.raises(ValidationError):
        CancelarComisionRequest(observacion="Ok", referencia="X")


def test_historial_comision_response_can_be_built():
    response = HistorialComisionPlataformaResponse(
        id_historial_comision=1,
        id_comision=2,
        estado_anterior="PENDIENTE_LIQUIDACION",
        estado_nuevo="OBSERVADA",
        observacion="Monto en revision",
        referencia="OBS-001",
        id_usuario_actor=99,
        fecha_hora=datetime(2026, 6, 6, 13, 0, 0),
    )

    assert response.id_historial_comision == 1
    assert response.id_comision == 2
    assert response.estado_nuevo == "OBSERVADA"


def test_comision_list_response_accepts_optional_operational_metadata():
    payload = _commission_list_payload() | {
        "fecha_liquidacion": datetime(2026, 6, 6, 13, 0, 0),
        "observacion_estado": "Liquidada por admin",
        "referencia_liquidacion": "LQ-001",
        "id_usuario_ultima_accion": 99,
        "fecha_ultima_accion": datetime(2026, 6, 6, 13, 0, 0),
    }

    response = ComisionPlataformaListResponse(**payload)

    assert response.fecha_liquidacion == payload["fecha_liquidacion"]
    assert response.observacion_estado == "Liquidada por admin"
    assert response.referencia_liquidacion == "LQ-001"
    assert response.id_usuario_ultima_accion == 99
    assert response.fecha_ultima_accion == payload["fecha_ultima_accion"]
    assert "historial" not in ComisionPlataformaListResponse.model_fields


def test_comision_detail_response_accepts_operational_metadata_and_historial():
    payload = _commission_list_payload() | {
        "metodo_pago": "TARJETA",
        "fecha_liquidacion": datetime(2026, 6, 6, 13, 0, 0),
        "observacion_estado": "Liquidada por admin",
        "referencia_liquidacion": "LQ-001",
        "id_usuario_ultima_accion": 99,
        "fecha_ultima_accion": datetime(2026, 6, 6, 13, 0, 0),
        "historial": [
            {
                "id_historial_comision": 1,
                "id_comision": 1,
                "estado_anterior": "PENDIENTE_LIQUIDACION",
                "estado_nuevo": "LIQUIDADA",
                "observacion": "Liquidada por admin",
                "referencia": "LQ-001",
                "id_usuario_actor": 99,
                "fecha_hora": datetime(2026, 6, 6, 13, 0, 0),
            }
        ],
    }

    response = ComisionPlataformaDetailResponse(**payload)

    assert response.metodo_pago == "TARJETA"
    assert response.referencia_liquidacion == "LQ-001"
    assert len(response.historial) == 1
    assert response.historial[0].estado_nuevo == "LIQUIDADA"


def test_comision_detail_response_history_uses_default_factory():
    base_payload = _commission_list_payload() | {"metodo_pago": "EFECTIVO"}

    first = ComisionPlataformaDetailResponse(**base_payload)
    second = ComisionPlataformaDetailResponse(**base_payload)
    first.historial.append(
        HistorialComisionPlataformaResponse(
            id_historial_comision=1,
            id_comision=1,
            estado_anterior=None,
            estado_nuevo="OBSERVADA",
            observacion=None,
            referencia=None,
            id_usuario_actor=5,
            fecha_hora=datetime(2026, 6, 6, 14, 0, 0),
        )
    )

    assert first.historial != second.historial
    assert second.historial == []
