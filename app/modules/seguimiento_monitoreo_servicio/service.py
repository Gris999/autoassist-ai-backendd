import asyncio
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

import anyio
from sqlalchemy.orm import Session
from app.core.config.settings import settings

from app.modules.gestion_clientes.repository import get_cliente_by_usuario_id
from app.modules.gestion_operativa_taller_tecnico.repository import (
    get_asignacion_activa_by_tecnico_id,
    get_taller_by_usuario_id,
    get_tecnico_by_usuario_id,
    update_tecnico,
    update_unidad_movil,
)
from app.modules.seguimiento_monitoreo_servicio.models import Notificacion
from app.modules.seguimiento_monitoreo_servicio.realtime import incident_location_manager
from app.modules.seguimiento_monitoreo_servicio.schemas import (
    ActualizarUbicacionActualRequest,
    AsignacionAuxilioDetalleResponse,
    ClienteIncidenteListResponse,
    ConfirmacionPagoDemoResponse,
    ConfirmarPagoDemoRequest,
    ComisionPlataformaResponse,
    ComprobantePagoResponse,
    CrearIntencionPagoRequest,
    DetalleCobroAuxilioResponse,
    EstadoServicioDetalleResponse,
    HistorialIncidenteEventoResponse,
    IncidenteHistorialDetailResponse,
    IncidenteHistorialListResponse,
    IntencionPagoResponse,
    MetodoPagoDisponibleResponse,
    NotificacionCreateRequest,
    NotificacionDetailResponse,
    NotificacionLeidaResponse,
    NotificacionListResponse,
    PagoIncidenteDetalleResponse,
    TallerAsignadoResponse,
    TecnicoAsignadoResponse,
    UnidadMovilAsignadaResponse,
    UbicacionActualTecnicoResponse,
    WebhookStripeResponse,
)
from app.modules.seguimiento_monitoreo_servicio.repository import (
    clear_detalles_pago,
    create_detalle_pago,
    create_notificacion,
    create_pago_servicio,
    get_incidente_asignacion_by_id_and_cliente,
    get_incidente_historial_by_id,
    get_incidente_pago_context_by_id_and_cliente,
    get_incidentes_by_cliente_id,
    get_incidentes_historial_all,
    get_incidentes_historial_by_taller_id,
    get_incidentes_historial_by_tecnico_id,
    get_incidente_by_id,
    get_notificacion_by_id_and_usuario,
    get_notificaciones_by_usuario_id,
    get_pago_servicio_by_id,
    get_pago_servicio_by_incidente_id,
    get_pago_servicio_by_referencia_transaccion,
    get_roles_by_usuario_id,
    get_usuario_by_id,
    update_pago_servicio,
    update_notificacion_leido,
    upsert_comision_plataforma,
)
from app.modules.gestion_incidentes_atencion.repository import get_incidente_by_id_and_cliente


def _get_cliente_autenticado(db: Session, current_user):
    cliente = get_cliente_by_usuario_id(db, current_user.id_usuario)
    if not cliente:
        raise ValueError("El usuario autenticado no tiene perfil de cliente.")
    return cliente


def _get_taller_autenticado(db: Session, current_user):
    taller = get_taller_by_usuario_id(db, current_user.id_usuario)
    if not taller:
        raise ValueError("El usuario autenticado no tiene perfil de taller.")
    return taller


def _get_tecnico_autenticado(db: Session, current_user):
    tecnico = get_tecnico_by_usuario_id(db, current_user.id_usuario)
    if not tecnico:
        raise ValueError("El usuario autenticado no tiene perfil de tecnico.")
    if not tecnico.estado:
        raise ValueError("El tecnico no se encuentra habilitado en la plataforma.")
    return tecnico


SUPPORTED_PAYMENT_METHODS = (
    MetodoPagoDisponibleResponse(
        codigo="STRIPE_CARD",
        nombre="Tarjeta",
        descripcion="Pago seguro con Stripe mediante tarjeta o wallet compatible.",
    ),
)
PAYMENT_STATE_PENDING = "PENDIENTE"
PAYMENT_STATE_REQUIRES_ACTION = "REQUIERE_ACCION"
PAYMENT_STATE_PAID = "PAGADO"
PAYMENT_STATE_REJECTED = "RECHAZADO"
PAYMENT_STATE_CANCELED = "CANCELADO"
PAYABLE_SERVICE_STATES = {"FINALIZADO"}
INCIDENT_TYPE_TO_AUXILIO = {
    "BATERIA_DESCARGADA": "AUXILIO_ELECTRICO",
    "PINCHAZO_LLANTA": "CAMBIO_DE_LLANTA",
    "SIN_COMBUSTIBLE": "SUMINISTRO_COMBUSTIBLE",
    "LLAVES_DENTRO": "APERTURA_VEHICULO",
    "FALLA_MECANICA": "AUXILIO_MECANICO_BASICO",
    "ACCIDENTE_MENOR": "REMOLQUE",
}
CLASSIFICATION_TO_AUXILIO = {
    "bateria": "AUXILIO_ELECTRICO",
    "llanta": "CAMBIO_DE_LLANTA",
    "combustible": "SUMINISTRO_COMBUSTIBLE",
    "llave": "APERTURA_VEHICULO",
    "motor": "AUXILIO_MECANICO_BASICO",
    "choque": "REMOLQUE",
}


class PaymentConfigurationError(ValueError):
    pass


class PaymentNotEnabledError(ValueError):
    pass


class PaymentAlreadyCompletedError(ValueError):
    pass


class PaymentRecordNotFoundError(ValueError):
    pass


def _get_stripe_client():
    if not settings.STRIPE_SECRET_KEY:
        raise PaymentConfigurationError("STRIPE_SECRET_KEY no esta configurada.")
    try:
        import stripe
    except ImportError as exc:
        raise PaymentConfigurationError(
            "La libreria stripe no esta instalada en el entorno."
        ) from exc

    stripe.api_key = settings.STRIPE_SECRET_KEY
    requests_client_cls = getattr(stripe, "RequestsClient", None)
    if requests_client_cls is not None:
        stripe.default_http_client = requests_client_cls(
            timeout=settings.STRIPE_TIMEOUT_SECONDS
        )
    return stripe


def _require_stripe_webhook_secret() -> str:
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise PaymentConfigurationError("STRIPE_WEBHOOK_SECRET no esta configurada.")
    return settings.STRIPE_WEBHOOK_SECRET


def _decimal_amount(value) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _decimal_to_minor_units(amount: Decimal) -> int:
    normalized = _decimal_amount(amount)
    return int((normalized * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))


def _normalize_payment_method(method: str) -> str:
    normalized = method.strip().upper()
    if normalized != "STRIPE_CARD":
        raise ValueError("Metodo de pago no soportado. Use STRIPE_CARD.")
    return normalized


def _normalize_demo_payment_method(method: str) -> str:
    normalized = method.strip().upper()
    if normalized not in {"DEMO_CARD", "TARJETA", "TARJETA_DEMO"}:
        raise ValueError(
            "Metodo de pago demo no soportado. Use DEMO_CARD, TARJETA o TARJETA_DEMO."
        )
    return "DEMO_CARD"


def _resolve_incident_auxilio(incidente):
    asignacion = incidente.asignacion_servicio
    if not asignacion or not asignacion.taller:
        raise PaymentNotEnabledError(
            "El servicio aun no tiene una asignacion valida para calcular el cobro."
        )

    tipo_incidente_nombre = incidente.tipo_incidente.nombre if incidente.tipo_incidente else ""
    tipo_auxilio_nombre = INCIDENT_TYPE_TO_AUXILIO.get(tipo_incidente_nombre)
    if tipo_auxilio_nombre is None and incidente.clasificacion_ia:
        tipo_auxilio_nombre = CLASSIFICATION_TO_AUXILIO.get(incidente.clasificacion_ia.strip().lower())

    if tipo_auxilio_nombre is None:
        raise PaymentNotEnabledError(
            "No se pudo determinar el tipo de auxilio asociado al incidente para calcular el pago."
        )

    taller_auxilio = next(
        (
            item
            for item in asignacion.taller.talleres_auxilio
            if item.tipo_auxilio and item.tipo_auxilio.nombre == tipo_auxilio_nombre
        ),
        None,
    )
    if not taller_auxilio:
        raise PaymentNotEnabledError(
            "El taller asignado no tiene configurado el servicio de auxilio a cobrar."
        )
    return taller_auxilio


def _build_detalles_cobro(incidente) -> list[DetalleCobroAuxilioResponse]:
    taller_auxilio = _resolve_incident_auxilio(incidente)
    precio = _decimal_amount(taller_auxilio.precio_referencial)
    return [
        DetalleCobroAuxilioResponse(
            descripcion=taller_auxilio.tipo_auxilio.descripcion or taller_auxilio.tipo_auxilio.nombre,
            cantidad=1,
            precio_unitario=precio,
            subtotal=precio,
            id_taller_auxilio=taller_auxilio.id_taller_auxilio,
            tipo_auxilio=taller_auxilio.tipo_auxilio.nombre,
        )
    ]


def _assert_incidente_payable(incidente, pago_existente=None) -> None:
    estado_actual = incidente.estado_servicio_actual.nombre if incidente.estado_servicio_actual else ""
    if estado_actual not in PAYABLE_SERVICE_STATES:
        raise PaymentNotEnabledError(
            "El servicio aun no esta habilitado para pago. Debe encontrarse finalizado."
        )
    if pago_existente and pago_existente.estado_pago == PAYMENT_STATE_PAID:
        raise PaymentAlreadyCompletedError("El servicio ya fue pagado.")


def _build_pago_detalle_response(incidente, pago_existente=None) -> PagoIncidenteDetalleResponse:
    detalles = _build_detalles_cobro(incidente)
    monto_total = sum((detalle.subtotal for detalle in detalles), Decimal("0.00"))
    asignacion = incidente.asignacion_servicio
    return PagoIncidenteDetalleResponse(
        id_incidente=incidente.id_incidente,
        titulo=incidente.titulo,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
        id_estado_servicio_actual=incidente.id_estado_servicio_actual,
        tipo_incidente=incidente.tipo_incidente.nombre,
        nombre_taller=asignacion.taller.nombre_taller,
        id_taller=asignacion.id_taller,
        moneda=settings.STRIPE_CURRENCY.upper(),
        monto_total=_decimal_amount(monto_total),
        habilitado_para_pago=True,
        mensaje=None,
        metodos_pago_disponibles=list(SUPPORTED_PAYMENT_METHODS),
        detalles_cobro=detalles,
        pago_existente=pago_existente is not None,
        estado_pago=pago_existente.estado_pago if pago_existente else None,
        referencia_transaccion=pago_existente.referencia_transaccion if pago_existente else None,
    )


def _build_demo_reference(id_incidente: int) -> str:
    return f"SIM-{id_incidente}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


def _extract_payment_receipt_url(stripe_payment_intent) -> str | None:
    latest_charge = getattr(stripe_payment_intent, "latest_charge", None)
    if latest_charge and getattr(latest_charge, "receipt_url", None):
        return latest_charge.receipt_url
    return None


def _resolve_pago_method_from_stripe(stripe_payment_intent) -> str:
    latest_charge = getattr(stripe_payment_intent, "latest_charge", None)
    payment_method_details = getattr(latest_charge, "payment_method_details", None)
    pm_type = getattr(payment_method_details, "type", None)
    return (pm_type or "STRIPE_CARD").upper()


def _stripe_object_get(obj, key: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    value = getattr(obj, key, None)
    if value is not None:
        return value
    try:
        return obj[key]
    except Exception:
        return default


def _to_ubicacion_actual_tecnico_response(
    *,
    incidente,
    asignacion,
    tecnico,
) -> UbicacionActualTecnicoResponse:
    return UbicacionActualTecnicoResponse(
        id_incidente=incidente.id_incidente,
        id_tecnico=tecnico.id_tecnico,
        id_unidad_movil=asignacion.id_unidad_movil,
        latitud_actual=tecnico.latitud_actual,
        longitud_actual=tecnico.longitud_actual,
        fecha_actualizacion=datetime.utcnow(),
        estado_asignacion=asignacion.estado_asignacion,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
        mensaje="Ubicacion actualizada correctamente.",
    )


def _emitir_actualizacion_tiempo_real(id_incidente: int, payload: dict) -> None:
    try:
        anyio.from_thread.run(
            incident_location_manager.broadcast_incident_update,
            id_incidente,
            payload,
        )
    except RuntimeError:
        asyncio.run(
            incident_location_manager.broadcast_incident_update(
                id_incidente,
                payload,
            )
        )


def _resolver_rol_historial_service(db: Session, current_user) -> str:
    roles = set(get_roles_by_usuario_id(db, current_user.id_usuario))
    if "ADMIN" in roles:
        return "ADMIN"
    if "TALLER" in roles:
        return "TALLER"
    if "TECNICO" in roles:
        return "TECNICO"
    if "CLIENTE" in roles:
        return "CLIENTE"
    raise ValueError("El usuario autenticado no tiene un rol valido para consultar historial.")


def validar_acceso_incidente_seguimiento_service(
    db: Session,
    current_user,
    id_incidente: int,
):
    incidente = get_incidente_historial_by_id(db, id_incidente)
    if not incidente:
        raise ValueError("El incidente especificado no existe.")
    _validar_acceso_historial_incidente(db, current_user, incidente)
    return incidente


def _to_notificacion_list_response(notificacion: Notificacion) -> NotificacionListResponse:
    return NotificacionListResponse(
        id_notificacion=notificacion.id_notificacion,
        id_incidente=notificacion.id_incidente,
        titulo=notificacion.titulo,
        mensaje=notificacion.mensaje,
        tipo_notificacion=notificacion.tipo_notificacion,
        leido=notificacion.leido,
        fecha_envio=notificacion.fecha_envio,
    )


def _to_notificacion_detail_response(notificacion: Notificacion) -> NotificacionDetailResponse:
    return NotificacionDetailResponse(
        id_notificacion=notificacion.id_notificacion,
        id_usuario=notificacion.id_usuario,
        id_incidente=notificacion.id_incidente,
        titulo=notificacion.titulo,
        mensaje=notificacion.mensaje,
        tipo_notificacion=notificacion.tipo_notificacion,
        leido=notificacion.leido,
        fecha_envio=notificacion.fecha_envio,
    )


def crear_notificacion_service(
    db: Session,
    payload: NotificacionCreateRequest,
) -> NotificacionDetailResponse:
    usuario = get_usuario_by_id(db, payload.id_usuario)
    if not usuario:
        raise ValueError("El destinatario de la notificacion no existe.")

    if payload.id_incidente is not None:
        incidente = get_incidente_by_id(db, payload.id_incidente)
        if not incidente:
            raise ValueError("El incidente asociado a la notificacion no existe.")

    notificacion = create_notificacion(
        db,
        id_usuario=payload.id_usuario,
        id_incidente=payload.id_incidente,
        titulo=payload.titulo,
        mensaje=payload.mensaje,
        tipo_notificacion=payload.tipo_notificacion,
    )
    return _to_notificacion_detail_response(notificacion)


def listar_notificaciones_service(
    db: Session,
    current_user,
) -> list[NotificacionListResponse]:
    notificaciones = get_notificaciones_by_usuario_id(db, current_user.id_usuario)
    return [_to_notificacion_list_response(notificacion) for notificacion in notificaciones]


def obtener_notificacion_service(
    db: Session,
    current_user,
    id_notificacion: int,
) -> NotificacionDetailResponse:
    notificacion = get_notificacion_by_id_and_usuario(
        db,
        id_notificacion=id_notificacion,
        id_usuario=current_user.id_usuario,
    )
    if not notificacion:
        raise ValueError("La notificacion no existe o no pertenece al usuario autenticado.")
    return _to_notificacion_detail_response(notificacion)


def marcar_notificacion_leida_service(
    db: Session,
    current_user,
    id_notificacion: int,
) -> NotificacionLeidaResponse:
    notificacion = get_notificacion_by_id_and_usuario(
        db,
        id_notificacion=id_notificacion,
        id_usuario=current_user.id_usuario,
    )
    if not notificacion:
        raise ValueError("La notificacion no existe o no pertenece al usuario autenticado.")

    update_notificacion_leido(db, notificacion, leido=True)
    return NotificacionLeidaResponse(
        id_notificacion=notificacion.id_notificacion,
        leido=notificacion.leido,
        mensaje="Notificacion marcada como leida.",
    )


def _to_incidente_historial_list_response(incidente) -> IncidenteHistorialListResponse:
    return IncidenteHistorialListResponse(
        id_incidente=incidente.id_incidente,
        titulo=incidente.titulo,
        fecha_reporte=incidente.fecha_reporte,
        tipo_incidente=incidente.tipo_incidente.nombre,
        id_estado_servicio_actual=incidente.id_estado_servicio_actual,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
    )


def _to_actor_nombre(usuario_actor) -> str | None:
    if not usuario_actor:
        return None
    return f"{usuario_actor.nombres} {usuario_actor.apellidos}"


def _construir_eventos_historial(incidente) -> list[HistorialIncidenteEventoResponse]:
    eventos: list[HistorialIncidenteEventoResponse] = []

    solicitud_aceptada = next(
        (
            solicitud
            for solicitud in incidente.solicitudes_taller
            if solicitud.estado_solicitud == "ACEPTADA"
        ),
        None,
    )
    if solicitud_aceptada and solicitud_aceptada.taller:
        eventos.append(
            HistorialIncidenteEventoResponse(
                fecha_hora=solicitud_aceptada.fecha_respuesta or solicitud_aceptada.fecha_envio,
                tipo_evento="SOLICITUD_TALLER",
                detalle="Solicitud de atencion aceptada por el taller.",
                estado_solicitud=solicitud_aceptada.estado_solicitud,
                id_taller=solicitud_aceptada.id_taller,
                nombre_taller=solicitud_aceptada.taller.nombre_taller,
            )
        )

    asignacion = incidente.asignacion_servicio
    if asignacion:
        nombre_tecnico = None
        if asignacion.tecnico and asignacion.tecnico.usuario:
            nombre_tecnico = (
                f"{asignacion.tecnico.usuario.nombres} "
                f"{asignacion.tecnico.usuario.apellidos}"
            )

        eventos.append(
            HistorialIncidenteEventoResponse(
                fecha_hora=asignacion.fecha_asignacion,
                tipo_evento="ASIGNACION_SERVICIO",
                detalle=asignacion.observaciones,
                id_taller=asignacion.id_taller,
                nombre_taller=asignacion.taller.nombre_taller if asignacion.taller else None,
                id_tecnico=asignacion.id_tecnico,
                nombre_tecnico=nombre_tecnico,
                id_unidad_movil=asignacion.id_unidad_movil,
                placa_unidad_movil=(
                    asignacion.unidad_movil.placa if asignacion.unidad_movil else None
                ),
            )
        )

    for historial in incidente.historial:
        eventos.append(
            HistorialIncidenteEventoResponse(
                fecha_hora=historial.fecha_hora,
                tipo_evento="CAMBIO_ESTADO",
                actor=_to_actor_nombre(historial.usuario_actor),
                detalle=historial.detalle,
                estado_anterior=(
                    historial.estado_anterior.nombre if historial.estado_anterior else None
                ),
                estado_nuevo=historial.estado_nuevo.nombre,
            )
        )

    eventos.sort(key=lambda evento: evento.fecha_hora)
    return eventos


def _validar_acceso_historial_incidente(db: Session, current_user, incidente) -> None:
    rol = _resolver_rol_historial_service(db, current_user)
    if rol == "ADMIN":
        return

    if rol == "CLIENTE":
        cliente = _get_cliente_autenticado(db, current_user)
        if incidente.id_cliente != cliente.id_cliente:
            raise ValueError("El incidente no esta disponible para el cliente autenticado.")
        return

    if rol == "TECNICO":
        tecnico = _get_tecnico_autenticado(db, current_user)
        if not incidente.asignacion_servicio or incidente.asignacion_servicio.id_tecnico != tecnico.id_tecnico:
            raise ValueError("El incidente no esta disponible para el tecnico autenticado.")
        return

    taller = _get_taller_autenticado(db, current_user)
    asignacion = incidente.asignacion_servicio
    if asignacion and asignacion.id_taller == taller.id_taller:
        return

    solicitud_aceptada = next(
        (
            solicitud
            for solicitud in incidente.solicitudes_taller
            if solicitud.id_taller == taller.id_taller and solicitud.estado_solicitud == "ACEPTADA"
        ),
        None,
    )
    if not solicitud_aceptada:
        raise ValueError("El incidente no esta disponible para el taller autenticado.")


def listar_incidentes_historial_service(
    db: Session,
    current_user,
) -> list[IncidenteHistorialListResponse]:
    rol = _resolver_rol_historial_service(db, current_user)

    if rol == "ADMIN":
        incidentes = get_incidentes_historial_all(db)
    elif rol == "CLIENTE":
        cliente = _get_cliente_autenticado(db, current_user)
        incidentes = get_incidentes_by_cliente_id(db, cliente.id_cliente)
    elif rol == "TECNICO":
        tecnico = _get_tecnico_autenticado(db, current_user)
        incidentes = get_incidentes_historial_by_tecnico_id(db, tecnico.id_tecnico)
    else:
        taller = _get_taller_autenticado(db, current_user)
        incidentes = get_incidentes_historial_by_taller_id(db, taller.id_taller)

    return [_to_incidente_historial_list_response(incidente) for incidente in incidentes]


def obtener_historial_incidente_service(
    db: Session,
    current_user,
    id_incidente: int,
) -> IncidenteHistorialDetailResponse:
    incidente = get_incidente_historial_by_id(db, id_incidente)
    if not incidente:
        raise ValueError("El incidente especificado no existe.")

    _validar_acceso_historial_incidente(db, current_user, incidente)
    eventos = _construir_eventos_historial(incidente)

    return IncidenteHistorialDetailResponse(
        id_incidente=incidente.id_incidente,
        titulo=incidente.titulo,
        fecha_reporte=incidente.fecha_reporte,
        tipo_incidente=incidente.tipo_incidente.nombre,
        prioridad=incidente.prioridad.nombre,
        id_estado_servicio_actual=incidente.id_estado_servicio_actual,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
        descripcion_texto=incidente.descripcion_texto,
        direccion_referencia=incidente.direccion_referencia,
        latitud=incidente.latitud,
        longitud=incidente.longitud,
        historial=eventos,
        mensaje=(
            "No existen registros adicionales de historial para el incidente."
            if not eventos
            else None
        ),
    )


def listar_incidentes_cliente_service(
    db: Session,
    current_user,
) -> list[ClienteIncidenteListResponse]:
    cliente = _get_cliente_autenticado(db, current_user)
    incidentes = get_incidentes_by_cliente_id(db, cliente.id_cliente)

    return [
        ClienteIncidenteListResponse(
            id_incidente=incidente.id_incidente,
            titulo=incidente.titulo,
            fecha_reporte=incidente.fecha_reporte,
            id_estado_servicio_actual=incidente.id_estado_servicio_actual,
            estado_servicio_actual=incidente.estado_servicio_actual.nombre,
            tiene_asignacion=incidente.asignacion_servicio is not None,
        )
        for incidente in incidentes
    ]


def obtener_detalle_pago_incidente_service(
    db: Session,
    current_user,
    id_incidente: int,
) -> PagoIncidenteDetalleResponse:
    cliente = _get_cliente_autenticado(db, current_user)
    incidente = get_incidente_pago_context_by_id_and_cliente(
        db,
        id_incidente=id_incidente,
        id_cliente=cliente.id_cliente,
    )
    if not incidente:
        raise ValueError("El incidente no existe o no pertenece al cliente autenticado.")

    pago_existente = get_pago_servicio_by_incidente_id(db, incidente.id_incidente)
    _assert_incidente_payable(incidente, pago_existente)
    return _build_pago_detalle_response(incidente, pago_existente)


def crear_intencion_pago_service(
    db: Session,
    current_user,
    id_incidente: int,
    payload: CrearIntencionPagoRequest,
) -> IntencionPagoResponse:
    stripe = _get_stripe_client()
    cliente = _get_cliente_autenticado(db, current_user)
    incidente = get_incidente_pago_context_by_id_and_cliente(
        db,
        id_incidente=id_incidente,
        id_cliente=cliente.id_cliente,
    )
    if not incidente:
        raise ValueError("El incidente no existe o no pertenece al cliente autenticado.")

    pago_existente = get_pago_servicio_by_incidente_id(db, incidente.id_incidente)
    _assert_incidente_payable(incidente, pago_existente)
    detalle = _build_pago_detalle_response(incidente, pago_existente)
    metodo_pago = _normalize_payment_method(payload.metodo_pago)
    amount_minor = _decimal_to_minor_units(detalle.monto_total)

    payment_intent = stripe.PaymentIntent.create(
        amount=amount_minor,
        currency=settings.STRIPE_CURRENCY.lower(),
        automatic_payment_methods={
            "enabled": True,
            "allow_redirects": "never",
        },
        metadata={
            "id_incidente": str(incidente.id_incidente),
            "id_cliente": str(cliente.id_cliente),
            "id_taller": str(detalle.id_taller),
        },
        description=f"Pago de auxilio AutoAssist AI - Incidente {incidente.id_incidente}",
    )

    try:
        if pago_existente is None:
            pago_servicio = create_pago_servicio(
                db,
                id_incidente=incidente.id_incidente,
                monto_total=detalle.monto_total,
                metodo_pago=metodo_pago,
                estado_pago=PAYMENT_STATE_PENDING,
                referencia_transaccion=payment_intent.id,
            )
        else:
            pago_servicio = update_pago_servicio(
                db,
                pago_existente,
                monto_total=detalle.monto_total,
                metodo_pago=metodo_pago,
                estado_pago=PAYMENT_STATE_PENDING,
                referencia_transaccion=payment_intent.id,
            )
        db.commit()
        db.refresh(pago_servicio)
    except Exception:
        db.rollback()
        raise

    return IntencionPagoResponse(
        id_pago_servicio=pago_servicio.id_pago_servicio,
        id_incidente=incidente.id_incidente,
        monto_total=detalle.monto_total,
        moneda=settings.STRIPE_CURRENCY.upper(),
        estado_pago=pago_servicio.estado_pago,
        client_secret=payment_intent.client_secret,
        payment_intent_id=payment_intent.id,
        publishable_key=settings.STRIPE_PUBLISHABLE_KEY,
        metodo_pago=metodo_pago,
        mensaje="Intencion de pago creada correctamente.",
    )


def _persistir_pago_confirmado_desde_stripe(
    db: Session,
    *,
    pago_servicio,
    stripe_payment_intent,
) -> None:
    incidente = get_incidente_pago_context_by_id_and_cliente(
        db,
        id_incidente=pago_servicio.id_incidente,
        id_cliente=pago_servicio.incidente.id_cliente,
    )
    if not incidente:
        incidente = get_incidente_asignacion_by_id_and_cliente(
            db,
            id_incidente=pago_servicio.id_incidente,
            id_cliente=pago_servicio.incidente.id_cliente,
        )
    if not incidente:
        raise PaymentRecordNotFoundError(
            "No se pudo reconstruir el incidente asociado al pago."
        )

    detalle_pago = _build_pago_detalle_response(incidente, pago_servicio)
    detalles_cobro = detalle_pago.detalles_cobro
    monto_total = detalle_pago.monto_total
    clear_detalles_pago(db, pago_servicio)
    for detalle in detalles_cobro:
        create_detalle_pago(
            db,
            id_pago_servicio=pago_servicio.id_pago_servicio,
            id_taller_auxilio=detalle.id_taller_auxilio,
            descripcion=detalle.descripcion,
            cantidad=detalle.cantidad,
            precio_unitario=detalle.precio_unitario,
            subtotal=detalle.subtotal,
        )

    comision = (
        monto_total * Decimal(str(settings.PLATFORM_COMMISSION_PERCENTAGE)) / Decimal("100")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    update_pago_servicio(
        db,
        pago_servicio,
        monto_total=monto_total,
        metodo_pago=_resolve_pago_method_from_stripe(stripe_payment_intent),
        estado_pago=PAYMENT_STATE_PAID,
        referencia_transaccion=stripe_payment_intent.id,
        fecha_pago=datetime.utcnow(),
    )
    upsert_comision_plataforma(
        db,
        pago_servicio=pago_servicio,
        id_taller=incidente.asignacion_servicio.id_taller,
        porcentaje=Decimal(str(settings.PLATFORM_COMMISSION_PERCENTAGE)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        monto_comision=comision,
        estado="PENDIENTE_LIQUIDACION",
    )


def _persistir_pago_demo_confirmado(
    db: Session,
    *,
    incidente,
    pago_servicio,
    metodo_pago: str,
    referencia_transaccion: str,
) -> None:
    detalle_pago = _build_pago_detalle_response(incidente, pago_servicio)
    detalles_cobro = detalle_pago.detalles_cobro
    monto_total = detalle_pago.monto_total

    clear_detalles_pago(db, pago_servicio)
    for detalle in detalles_cobro:
        create_detalle_pago(
            db,
            id_pago_servicio=pago_servicio.id_pago_servicio,
            id_taller_auxilio=detalle.id_taller_auxilio,
            descripcion=detalle.descripcion,
            cantidad=detalle.cantidad,
            precio_unitario=detalle.precio_unitario,
            subtotal=detalle.subtotal,
        )

    comision = (
        monto_total * Decimal(str(settings.PLATFORM_COMMISSION_PERCENTAGE)) / Decimal("100")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    update_pago_servicio(
        db,
        pago_servicio,
        monto_total=monto_total,
        metodo_pago=metodo_pago,
        estado_pago=PAYMENT_STATE_PAID,
        referencia_transaccion=referencia_transaccion,
        fecha_pago=datetime.utcnow(),
    )
    upsert_comision_plataforma(
        db,
        pago_servicio=pago_servicio,
        id_taller=incidente.asignacion_servicio.id_taller,
        porcentaje=Decimal(str(settings.PLATFORM_COMMISSION_PERCENTAGE)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        monto_comision=comision,
        estado="PENDIENTE_LIQUIDACION",
    )


def procesar_webhook_stripe_service(
    db: Session,
    *,
    raw_payload: bytes,
    stripe_signature: str | None,
) -> WebhookStripeResponse:
    stripe = _get_stripe_client()
    webhook_secret = _require_stripe_webhook_secret()
    if not stripe_signature:
        raise PaymentConfigurationError("Encabezado Stripe-Signature no proporcionado.")

    try:
        event = stripe.Webhook.construct_event(
            payload=raw_payload,
            sig_header=stripe_signature,
            secret=webhook_secret,
        )
    except Exception as exc:
        raise ValueError(f"Firma webhook invalida: {str(exc)}") from exc

    event_type = _stripe_object_get(event, "type")
    data = _stripe_object_get(event, "data", {})
    data_object = _stripe_object_get(data, "object")
    payment_intent_id = _stripe_object_get(data_object, "id")

    if not event_type or not payment_intent_id:
        raise ValueError("El evento Stripe recibido no contiene la informacion minima esperada.")

    if event_type not in {
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "payment_intent.canceled",
    }:
        return WebhookStripeResponse(
            recibido=True,
            evento=event_type,
            mensaje="Evento recibido sin accion requerida.",
        )

    pago_servicio = get_pago_servicio_by_referencia_transaccion(db, payment_intent_id)
    if not pago_servicio:
        raise PaymentRecordNotFoundError(
            "No existe un pago local asociado al PaymentIntent recibido."
        )

    try:
        stripe_payment_intent = stripe.PaymentIntent.retrieve(
            payment_intent_id,
            expand=["latest_charge"],
        )
        if event_type == "payment_intent.succeeded":
            _persistir_pago_confirmado_desde_stripe(
                db,
                pago_servicio=pago_servicio,
                stripe_payment_intent=stripe_payment_intent,
            )
        elif event_type == "payment_intent.payment_failed":
            update_pago_servicio(
                db,
                pago_servicio,
                estado_pago=PAYMENT_STATE_REJECTED,
                metodo_pago=_resolve_pago_method_from_stripe(stripe_payment_intent),
                referencia_transaccion=payment_intent_id,
            )
        elif event_type == "payment_intent.canceled":
            update_pago_servicio(
                db,
                pago_servicio,
                estado_pago=PAYMENT_STATE_CANCELED,
                metodo_pago=_resolve_pago_method_from_stripe(stripe_payment_intent),
                referencia_transaccion=payment_intent_id,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return WebhookStripeResponse(
        recibido=True,
        evento=event_type,
        mensaje="Webhook Stripe procesado correctamente.",
    )


def confirmar_pago_demo_service(
    db: Session,
    current_user,
    id_incidente: int,
    payload: ConfirmarPagoDemoRequest,
) -> ConfirmacionPagoDemoResponse:
    cliente = _get_cliente_autenticado(db, current_user)
    incidente = get_incidente_pago_context_by_id_and_cliente(
        db,
        id_incidente=id_incidente,
        id_cliente=cliente.id_cliente,
    )
    if not incidente:
        raise ValueError("El incidente no existe o no pertenece al cliente autenticado.")

    pago_existente = get_pago_servicio_by_incidente_id(db, incidente.id_incidente)
    _assert_incidente_payable(incidente, pago_existente)
    detalle = _build_pago_detalle_response(incidente, pago_existente)
    metodo_pago = _normalize_demo_payment_method(payload.metodo_pago)
    referencia_transaccion = (
        payload.referencia_demo.strip()
        if payload.referencia_demo and payload.referencia_demo.strip()
        else _build_demo_reference(incidente.id_incidente)
    )

    try:
        if pago_existente is None:
            pago_servicio = create_pago_servicio(
                db,
                id_incidente=incidente.id_incidente,
                monto_total=detalle.monto_total,
                metodo_pago=metodo_pago,
                estado_pago=PAYMENT_STATE_PENDING,
                referencia_transaccion=referencia_transaccion,
            )
        else:
            pago_servicio = update_pago_servicio(
                db,
                pago_existente,
                monto_total=detalle.monto_total,
                metodo_pago=metodo_pago,
                estado_pago=PAYMENT_STATE_PENDING,
                referencia_transaccion=referencia_transaccion,
            )
        _persistir_pago_demo_confirmado(
            db,
            incidente=incidente,
            pago_servicio=pago_servicio,
            metodo_pago=metodo_pago,
            referencia_transaccion=referencia_transaccion,
        )
        db.commit()
        db.refresh(pago_servicio)
    except Exception:
        db.rollback()
        raise

    return ConfirmacionPagoDemoResponse(
        id_pago_servicio=pago_servicio.id_pago_servicio,
        id_incidente=incidente.id_incidente,
        estado_pago=pago_servicio.estado_pago,
        referencia_transaccion=pago_servicio.referencia_transaccion or referencia_transaccion,
        mensaje="Pago demo confirmado correctamente.",
    )


def obtener_comprobante_pago_service(
    db: Session,
    current_user,
    id_pago_servicio: int,
) -> ComprobantePagoResponse:
    stripe = _get_stripe_client()
    cliente = _get_cliente_autenticado(db, current_user)
    pago_servicio = get_pago_servicio_by_id(db, id_pago_servicio)
    if not pago_servicio:
        raise PaymentRecordNotFoundError("El pago solicitado no existe.")
    if pago_servicio.incidente.id_cliente != cliente.id_cliente:
        raise ValueError("El pago no pertenece al cliente autenticado.")

    is_demo_reference = (
        pago_servicio.referencia_transaccion is not None
        and pago_servicio.referencia_transaccion.startswith("SIM-")
    )
    if (
        pago_servicio.estado_pago == PAYMENT_STATE_PAID
        and pago_servicio.referencia_transaccion
        and not is_demo_reference
    ):
        try:
            stripe_payment_intent = stripe.PaymentIntent.retrieve(
                pago_servicio.referencia_transaccion,
                expand=["latest_charge"],
            )
            receipt_url = _extract_payment_receipt_url(stripe_payment_intent)
        except Exception:
            receipt_url = None
    else:
        receipt_url = None

    return ComprobantePagoResponse(
        id_pago_servicio=pago_servicio.id_pago_servicio,
        id_incidente=pago_servicio.id_incidente,
        titulo_incidente=pago_servicio.incidente.titulo,
        nombre_taller=(
            pago_servicio.incidente.asignacion_servicio.taller.nombre_taller
            if pago_servicio.incidente.asignacion_servicio and pago_servicio.incidente.asignacion_servicio.taller
            else ""
        ),
        metodo_pago=pago_servicio.metodo_pago,
        estado_pago=pago_servicio.estado_pago,
        monto_total=_decimal_amount(pago_servicio.monto_total),
        moneda=settings.STRIPE_CURRENCY.upper(),
        fecha_pago=pago_servicio.fecha_pago,
        referencia_transaccion=pago_servicio.referencia_transaccion,
        receipt_url=receipt_url,
        detalles=[
            DetalleCobroAuxilioResponse(
                descripcion=detalle.descripcion,
                cantidad=detalle.cantidad,
                precio_unitario=_decimal_amount(detalle.precio_unitario),
                subtotal=_decimal_amount(detalle.subtotal),
                id_taller_auxilio=detalle.id_taller_auxilio,
                tipo_auxilio=detalle.taller_auxilio.tipo_auxilio.nombre,
            )
            for detalle in pago_servicio.detalles_pago
        ],
        comision_plataforma=(
            ComisionPlataformaResponse(
                porcentaje=_decimal_amount(pago_servicio.comision_plataforma.porcentaje),
                monto_comision=_decimal_amount(pago_servicio.comision_plataforma.monto_comision),
                estado=pago_servicio.comision_plataforma.estado,
                fecha_calculo=pago_servicio.comision_plataforma.fecha_calculo,
            )
            if pago_servicio.comision_plataforma
            else None
        ),
    )


def consultar_asignacion_auxilio_service(
    db: Session,
    current_user,
    id_incidente: int,
) -> AsignacionAuxilioDetalleResponse:
    cliente = _get_cliente_autenticado(db, current_user)
    incidente = get_incidente_asignacion_by_id_and_cliente(
        db,
        id_incidente=id_incidente,
        id_cliente=cliente.id_cliente,
    )
    if not incidente:
        raise ValueError("El incidente no existe o no pertenece al cliente autenticado.")

    asignacion = incidente.asignacion_servicio
    if not asignacion:
        return AsignacionAuxilioDetalleResponse(
            id_incidente=incidente.id_incidente,
            titulo=incidente.titulo,
            fecha_reporte=incidente.fecha_reporte,
            tipo_incidente=incidente.tipo_incidente.nombre,
            descripcion_texto=incidente.descripcion_texto,
            direccion_referencia=incidente.direccion_referencia,
            latitud=incidente.latitud,
            longitud=incidente.longitud,
            id_estado_servicio_actual=incidente.id_estado_servicio_actual,
            estado_servicio_actual=incidente.estado_servicio_actual.nombre,
            asignacion_definida=False,
            mensaje="El incidente aun no tiene una asignacion registrada.",
            placa_vehiculo=incidente.vehiculo.placa if incidente.vehiculo else None,
            marca_vehiculo=incidente.vehiculo.marca if incidente.vehiculo else None,
            modelo_vehiculo=incidente.vehiculo.modelo if incidente.vehiculo else None,
        )

    tecnico = None
    if asignacion.tecnico and asignacion.tecnico.usuario:
        tecnico = TecnicoAsignadoResponse(
            id_tecnico=asignacion.tecnico.id_tecnico,
            nombres=asignacion.tecnico.usuario.nombres,
            apellidos=asignacion.tecnico.usuario.apellidos,
            telefono_contacto=asignacion.tecnico.telefono_contacto,
        )

    unidad_movil = None
    if asignacion.unidad_movil:
        unidad_movil = UnidadMovilAsignadaResponse(
            id_unidad_movil=asignacion.unidad_movil.id_unidad_movil,
            placa=asignacion.unidad_movil.placa,
            tipo_unidad=asignacion.unidad_movil.tipo_unidad,
        )

    return AsignacionAuxilioDetalleResponse(
        id_incidente=incidente.id_incidente,
        titulo=incidente.titulo,
        fecha_reporte=incidente.fecha_reporte,
        tipo_incidente=incidente.tipo_incidente.nombre,
        descripcion_texto=incidente.descripcion_texto,
        direccion_referencia=incidente.direccion_referencia,
        latitud=incidente.latitud,
        longitud=incidente.longitud,
        id_estado_servicio_actual=incidente.id_estado_servicio_actual,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
        estado_asignacion=asignacion.estado_asignacion,
        tiempo_estimado_min=asignacion.tiempo_estimado_min,
        asignacion_definida=True,
        mensaje=(
            None
            if tecnico or unidad_movil
            else "La asignacion fue registrada, pero aun no se definieron todos los recursos."
        ),
        taller=TallerAsignadoResponse(
            id_taller=asignacion.taller.id_taller,
            nombre_taller=asignacion.taller.nombre_taller,
            direccion=asignacion.taller.direccion,
        ),
        tecnico=tecnico,
        unidad_movil=unidad_movil,
        placa_vehiculo=incidente.vehiculo.placa if incidente.vehiculo else None,
        marca_vehiculo=incidente.vehiculo.marca if incidente.vehiculo else None,
        modelo_vehiculo=incidente.vehiculo.modelo if incidente.vehiculo else None,
    )


def get_estado_servicio_service(
    db: Session,
    current_user,
    id_incidente: int,
) -> EstadoServicioDetalleResponse:
    cliente = _get_cliente_autenticado(db, current_user)

    incidente = get_incidente_by_id_and_cliente(db, id_incidente, cliente.id_cliente)
    if not incidente:
        raise ValueError("El incidente no existe o no pertenece al cliente autenticado.")

    return EstadoServicioDetalleResponse(
        id_incidente=incidente.id_incidente,
        titulo=incidente.titulo,
        fecha_reporte=incidente.fecha_reporte,
        id_vehiculo=incidente.id_vehiculo,
        id_tipo_incidente=incidente.id_tipo_incidente,
        tipo_incidente=incidente.tipo_incidente.nombre,
        id_prioridad=incidente.id_prioridad,
        prioridad=incidente.prioridad.nombre,
        id_estado_servicio_actual=incidente.id_estado_servicio_actual,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
        direccion_referencia=incidente.direccion_referencia,
        latitud=incidente.latitud,
        longitud=incidente.longitud,
        clasificacion_ia=incidente.clasificacion_ia,
        confianza_clasificacion=incidente.confianza_clasificacion,
        resumen_ia=incidente.resumen_ia,
        requiere_mas_info=incidente.requiere_mas_info,
    )


def actualizar_ubicacion_actual_tecnico_service(
    db: Session,
    current_user,
    id_incidente: int,
    payload: ActualizarUbicacionActualRequest,
) -> UbicacionActualTecnicoResponse:
    tecnico = _get_tecnico_autenticado(db, current_user)
    asignacion_activa = get_asignacion_activa_by_tecnico_id(db, tecnico.id_tecnico)
    if not asignacion_activa:
        raise ValueError("El tecnico no tiene ningun incidente activo asignado.")
    if asignacion_activa.id_incidente != id_incidente:
        raise ValueError("El incidente indicado no corresponde a la asignacion activa del tecnico.")

    incidente = get_incidente_historial_by_id(db, id_incidente)
    if not incidente:
        raise ValueError("El incidente especificado no existe.")

    try:
        tecnico_actualizado = update_tecnico(
            db,
            tecnico,
            latitud_actual=payload.latitud,
            longitud_actual=payload.longitud,
        )

        if asignacion_activa.unidad_movil is not None:
            update_unidad_movil(
                db,
                asignacion_activa.unidad_movil,
                latitud_actual=payload.latitud,
                longitud_actual=payload.longitud,
            )

        db.commit()
        db.refresh(tecnico_actualizado)
        response = _to_ubicacion_actual_tecnico_response(
            incidente=incidente,
            asignacion=asignacion_activa,
            tecnico=tecnico_actualizado,
        )
        _emitir_actualizacion_tiempo_real(
            incidente.id_incidente,
            {
                "type": "ubicacion_actualizada",
                "payload": response.model_dump(mode="json"),
            },
        )
        return response
    except Exception:
        db.rollback()
        raise
