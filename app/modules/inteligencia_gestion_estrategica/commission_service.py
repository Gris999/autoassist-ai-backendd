from datetime import datetime
from decimal import Decimal

from app.core.config.settings import settings
from app.modules.inteligencia_gestion_estrategica.repository import (
    create_bitacora_comision,
    upsert_comision_plataforma_inteligencia,
)

COMMISSION_STATE_PENDING_SETTLEMENT = "PENDIENTE_LIQUIDACION"
PAYMENT_STATE_PAID = "PAGADO"


class CommissionNotFoundError(LookupError):
    pass


class CommissionAlreadyExistsError(ValueError):
    pass


class PaymentNotEligibleForCommissionError(ValueError):
    pass


class CommissionConfigurationError(ValueError):
    pass


class NoCommissionEligiblePaymentsError(LookupError):
    pass


def decimal_amount(value) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    return Decimal(str(value)).quantize(Decimal("0.01"))


def get_platform_commission_percentage() -> Decimal:
    percentage = Decimal(str(settings.PLATFORM_COMMISSION_PERCENTAGE)).quantize(
        Decimal("0.01")
    )
    if percentage < Decimal("0.00") or percentage > Decimal("100.00"):
        raise CommissionConfigurationError(
            "La politica de comision configurada es invalida. Debe estar entre 0 y 100."
        )
    return percentage


def resolve_pago_taller(pago_servicio):
    incidente = pago_servicio.incidente
    if not incidente or not incidente.asignacion_servicio or not incidente.asignacion_servicio.taller:
        raise PaymentNotEligibleForCommissionError(
            "El pago no tiene un taller asignado valido para generar comision."
        )
    return incidente.asignacion_servicio.taller


def validate_pago_eligible_for_commission(pago_servicio) -> None:
    if not pago_servicio:
        raise PaymentNotEligibleForCommissionError(
            "El pago especificado no existe o no se encuentra disponible."
        )
    if pago_servicio.estado_pago != PAYMENT_STATE_PAID:
        raise PaymentNotEligibleForCommissionError(
            "El pago no es elegible para comision. Debe encontrarse en estado PAGADO."
        )
    resolve_pago_taller(pago_servicio)


def generate_platform_commission_for_payment(
    db,
    *,
    pago_servicio,
    recalcular: bool,
    id_usuario_actor: int | None = None,
):
    validate_pago_eligible_for_commission(pago_servicio)

    existing_comision = pago_servicio.comision_plataforma
    if existing_comision is not None and not recalcular:
        raise CommissionAlreadyExistsError(
            "Ya existe una comision registrada para el pago especificado."
        )

    taller = resolve_pago_taller(pago_servicio)
    porcentaje = get_platform_commission_percentage()
    monto_total = decimal_amount(pago_servicio.monto_total)
    monto_comision = (
        monto_total * porcentaje / Decimal("100")
    ).quantize(Decimal("0.01"))
    estado_comision = (
        existing_comision.estado
        if existing_comision is not None and existing_comision.estado
        else COMMISSION_STATE_PENDING_SETTLEMENT
    )

    comision = upsert_comision_plataforma_inteligencia(
        db,
        pago_servicio=pago_servicio,
        id_taller=taller.id_taller,
        porcentaje=porcentaje,
        monto_comision=monto_comision,
        estado=estado_comision,
    )
    if existing_comision is not None:
        comision.fecha_calculo = datetime.utcnow()
        db.flush()
        db.refresh(comision)

    if id_usuario_actor is not None:
        accion = "RECALCULAR_COMISION" if existing_comision is not None else "GENERAR_COMISION"
        create_bitacora_comision(
            db,
            id_usuario=id_usuario_actor,
            accion=accion,
            descripcion=(
                f"{accion} sobre pago {pago_servicio.id_pago_servicio}, "
                f"incidente {pago_servicio.id_incidente}, taller {taller.id_taller}, "
                f"porcentaje {porcentaje}, monto {monto_comision}."
            ),
        )

    return comision, existing_comision is None
