from datetime import datetime, UTC
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modules.inteligencia_gestion_estrategica import commission_service


class DummyDB:
    def flush(self):
        return None

    def refresh(self, obj):
        return obj


@pytest.mark.parametrize(
    ("current_state", "target_state"),
    [
        (
            commission_service.COMMISSION_STATE_PENDING_SETTLEMENT,
            commission_service.COMMISSION_STATE_SETTLED,
        ),
        (
            commission_service.COMMISSION_STATE_PENDING_SETTLEMENT,
            commission_service.COMMISSION_STATE_OBSERVED,
        ),
        (
            commission_service.COMMISSION_STATE_PENDING_SETTLEMENT,
            commission_service.COMMISSION_STATE_CANCELED,
        ),
        (
            commission_service.COMMISSION_STATE_OBSERVED,
            commission_service.COMMISSION_STATE_SETTLED,
        ),
        (
            commission_service.COMMISSION_STATE_OBSERVED,
            commission_service.COMMISSION_STATE_CANCELED,
        ),
    ],
)
def test_valid_commission_transitions(current_state, target_state):
    current, target = commission_service._validate_commission_transition(
        current_state,
        target_state,
    )

    assert current == current_state
    assert target == target_state


@pytest.mark.parametrize(
    ("current_state", "target_state"),
    [
        (
            commission_service.COMMISSION_STATE_SETTLED,
            commission_service.COMMISSION_STATE_CANCELED,
        ),
        (
            commission_service.COMMISSION_STATE_CANCELED,
            commission_service.COMMISSION_STATE_SETTLED,
        ),
        (
            commission_service.COMMISSION_STATE_OBSERVED,
            commission_service.COMMISSION_STATE_PENDING_SETTLEMENT,
        ),
        (
            commission_service.COMMISSION_STATE_PENDING_SETTLEMENT,
            commission_service.COMMISSION_STATE_PENDING_SETTLEMENT,
        ),
        (
            commission_service.COMMISSION_STATE_SETTLED,
            commission_service.COMMISSION_STATE_SETTLED,
        ),
        ("DESCONOCIDO", commission_service.COMMISSION_STATE_SETTLED),
        (commission_service.COMMISSION_STATE_PENDING_SETTLEMENT, "DESCONOCIDO"),
        ("", commission_service.COMMISSION_STATE_SETTLED),
        (None, commission_service.COMMISSION_STATE_SETTLED),
        (commission_service.COMMISSION_STATE_PENDING_SETTLEMENT, ""),
        (commission_service.COMMISSION_STATE_PENDING_SETTLEMENT, None),
    ],
)
def test_invalid_commission_transitions(current_state, target_state):
    with pytest.raises(commission_service.CommissionInvalidTransitionError):
        commission_service._validate_commission_transition(
            current_state,
            target_state,
        )


@pytest.mark.parametrize(
    "state",
    [commission_service.COMMISSION_STATE_PENDING_SETTLEMENT],
)
def test_pending_commission_is_recalculable(state):
    assert commission_service._validate_commission_recalculation_allowed(state) == state


@pytest.mark.parametrize(
    "state",
    [
        commission_service.COMMISSION_STATE_OBSERVED,
        commission_service.COMMISSION_STATE_SETTLED,
        commission_service.COMMISSION_STATE_CANCELED,
    ],
)
def test_closed_or_observed_commissions_are_not_recalculable(state):
    with pytest.raises(commission_service.CommissionClosedStateError):
        commission_service._validate_commission_recalculation_allowed(state)


def test_generate_platform_commission_blocks_recalculation_for_liquidada(monkeypatch):
    db = DummyDB()
    existing_comision = SimpleNamespace(
        estado=commission_service.COMMISSION_STATE_SETTLED,
        fecha_calculo=datetime.now(UTC),
    )
    pago_servicio = SimpleNamespace(
        id_pago_servicio=1,
        id_incidente=10,
        monto_total=Decimal("100.00"),
        estado_pago="PAGADO",
        comision_plataforma=existing_comision,
        incidente=SimpleNamespace(
            asignacion_servicio=SimpleNamespace(
                taller=SimpleNamespace(id_taller=7)
            )
        ),
    )

    monkeypatch.setattr(commission_service, "validate_pago_eligible_for_commission", lambda pago: None)
    monkeypatch.setattr(
        commission_service,
        "resolve_pago_taller",
        lambda pago: SimpleNamespace(id_taller=7),
    )
    monkeypatch.setattr(
        commission_service,
        "upsert_comision_plataforma_inteligencia",
        lambda **kwargs: pytest.fail("No debe intentar recalcular una comision cerrada."),
    )

    with pytest.raises(commission_service.CommissionClosedStateError):
        commission_service.generate_platform_commission_for_payment(
            db,
            pago_servicio=pago_servicio,
            recalcular=True,
        )


def test_generate_platform_commission_blocks_recalculation_for_cancelada(monkeypatch):
    db = DummyDB()
    existing_comision = SimpleNamespace(
        estado=commission_service.COMMISSION_STATE_CANCELED,
        fecha_calculo=datetime.now(UTC),
    )
    pago_servicio = SimpleNamespace(
        id_pago_servicio=2,
        id_incidente=11,
        monto_total=Decimal("120.00"),
        estado_pago="PAGADO",
        comision_plataforma=existing_comision,
        incidente=SimpleNamespace(
            asignacion_servicio=SimpleNamespace(
                taller=SimpleNamespace(id_taller=8)
            )
        ),
    )

    monkeypatch.setattr(commission_service, "validate_pago_eligible_for_commission", lambda pago: None)
    monkeypatch.setattr(
        commission_service,
        "resolve_pago_taller",
        lambda pago: SimpleNamespace(id_taller=8),
    )
    monkeypatch.setattr(
        commission_service,
        "upsert_comision_plataforma_inteligencia",
        lambda **kwargs: pytest.fail("No debe intentar recalcular una comision cancelada."),
    )

    with pytest.raises(commission_service.CommissionClosedStateError):
        commission_service.generate_platform_commission_for_payment(
            db,
            pago_servicio=pago_servicio,
            recalcular=True,
        )
