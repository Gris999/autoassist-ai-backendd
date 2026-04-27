import asyncio
import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

import anyio
import httpx
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
    DispositivoPushRegisterRequest,
    DispositivoPushResponse,
    EstadoServicioDetalleResponse,
    HistorialIncidenteEventoResponse,
    IncidenteTecnicoLlegadaListResponse,
    IncidenteHistorialDetailResponse,
    IncidenteHistorialListResponse,
    IntencionPagoResponse,
    MarcarLlegadaIncidenteRequest,
    MarcarLlegadaIncidenteResponse,
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
    get_asignacion_llegada_by_incidente_and_tecnico_id_for_update,
    get_asignaciones_llegada_by_tecnico_id,
    get_cliente_by_id,
    get_estado_servicio_by_nombre,
    get_incidente_asignacion_by_id_and_cliente,
    get_incidente_historial_by_id,
    get_incidente_pago_context_by_id_and_cliente,
    get_incidentes_by_cliente_id,
    get_incidentes_historial_all,
    get_incidentes_historial_by_taller_id,
    get_incidentes_historial_by_tecnico_id,
    get_incidente_by_id,
    get_dispositivos_push_by_usuario_id,
    get_dispositivo_push_by_token,
    get_notificacion_by_id_and_usuario,
    get_notificaciones_by_usuario_id,
    get_pago_servicio_by_id,
    get_pago_servicio_by_incidente_id,
    get_pago_servicio_by_referencia_transaccion,
    get_roles_by_usuario_id,
    get_usuario_by_id,
    upsert_metrica_incidente_llegada,
    update_pago_servicio,
    update_notificacion_leido,
    update_dispositivo_push_activo,
    update_notificacion_push_result,
    upsert_dispositivo_push,
    upsert_comision_plataforma,
)
from app.modules.gestion_incidentes_atencion.repository import (
    create_historial_incidente,
    get_incidente_by_id_and_cliente,
    update_asignacion_servicio_estado,
    update_incidente_estado_servicio_actual,
)


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
PUSH_STATE_PENDING = "PENDIENTE"
PUSH_STATE_SENT = "ENVIADA"
PUSH_STATE_FAILED = "FALLIDA"
PUSH_STATE_NO_TOKEN = "SIN_TOKEN"
PUSH_STATE_DISABLED = "DESHABILITADA"
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
ESTADO_APTO_MARCAR_LLEGADA = "EN_CAMINO"
ESTADO_SERVICIO_TECNICO_EN_SITIO = "EN_ATENCION"
TIPO_NOTIFICACION_TECNICO_EN_SITIO = "TECNICO_EN_SITIO"


class PaymentConfigurationError(ValueError):
    pass


class PaymentNotEnabledError(ValueError):
    pass


class PaymentAlreadyCompletedError(ValueError):
    pass


class PaymentRecordNotFoundError(ValueError):
    pass


class TrackingIncidentNotFoundError(ValueError):
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


def _to_incidente_tecnico_llegada_list_response(
    asignacion,
) -> IncidenteTecnicoLlegadaListResponse:
    incidente = asignacion.incidente
    return IncidenteTecnicoLlegadaListResponse(
        id_incidente=incidente.id_incidente,
        id_asignacion=asignacion.id_asignacion,
        titulo=incidente.titulo,
        descripcion_texto=incidente.descripcion_texto,
        direccion_referencia=incidente.direccion_referencia,
        latitud=incidente.latitud,
        longitud=incidente.longitud,
        fecha_reporte=incidente.fecha_reporte,
        tipo_incidente=incidente.tipo_incidente.nombre,
        prioridad=incidente.prioridad.nombre,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
        estado_asignacion=asignacion.estado_asignacion,
        tiempo_estimado_min=asignacion.tiempo_estimado_min,
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
        push_estado=notificacion.push_estado,
        push_error=notificacion.push_error,
        fecha_envio_push=notificacion.fecha_envio_push,
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
        push_estado=notificacion.push_estado,
        push_error=notificacion.push_error,
        fecha_envio_push=notificacion.fecha_envio_push,
        fecha_envio=notificacion.fecha_envio,
    )


def _to_dispositivo_push_response(dispositivo) -> DispositivoPushResponse:
    return DispositivoPushResponse(
        id_dispositivo_push=dispositivo.id_dispositivo_push,
        token_push=dispositivo.token_push,
        plataforma=dispositivo.plataforma,
        proveedor=dispositivo.proveedor,
        activo=dispositivo.activo,
        fecha_registro=dispositivo.fecha_registro,
        fecha_actualizacion=dispositivo.fecha_actualizacion,
    )


def _normalize_push_provider(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {"EXPO", "FCM"}:
        raise ValueError("Proveedor push no soportado. Use FCM o EXPO.")
    return normalized


def _normalize_push_platform(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {"ANDROID", "IOS", "WEB"}:
        raise ValueError("Plataforma no soportada. Use ANDROID, IOS o WEB.")
    return normalized


def _build_push_payload(notificacion: Notificacion, token: str) -> dict:
    data = {
        "id_notificacion": notificacion.id_notificacion,
        "id_incidente": notificacion.id_incidente,
        "tipo_notificacion": notificacion.tipo_notificacion,
    }
    return {
        "to": token,
        "title": notificacion.titulo,
        "body": notificacion.mensaje,
        "data": data,
        "sound": "default",
    }


def _send_expo_push_notifications(notificacion: Notificacion, tokens: list[str]) -> tuple[bool, str | None]:
    payload = [_build_push_payload(notificacion, token) for token in tokens]
    response = httpx.post(
        settings.EXPO_PUSH_URL,
        json=payload,
        timeout=settings.PUSH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    response_payload = response.json()
    tickets = response_payload.get("data", [])
    errors = []
    if isinstance(tickets, list):
        for ticket in tickets:
            if ticket.get("status") == "error":
                details = ticket.get("details") or {}
                error_code = details.get("error") or ticket.get("message") or "error"
                errors.append(str(error_code))
    if errors:
        return False, "; ".join(errors[:5])
    return True, None


def _get_firebase_credentials():
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise ValueError(
            "Las dependencias de Firebase no estan instaladas. "
            "Instale google-auth y requests desde requirements.txt."
        ) from exc

    scopes = ["https://www.googleapis.com/auth/firebase.messaging"]
    if settings.FIREBASE_SERVICE_ACCOUNT_JSON:
        service_account_info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=scopes,
        )
    elif settings.FIREBASE_SERVICE_ACCOUNT_FILE:
        credentials = service_account.Credentials.from_service_account_file(
            settings.FIREBASE_SERVICE_ACCOUNT_FILE,
            scopes=scopes,
        )
    else:
        raise ValueError(
            "Configure FIREBASE_SERVICE_ACCOUNT_FILE o FIREBASE_SERVICE_ACCOUNT_JSON."
        )

    credentials.refresh(Request())
    return credentials


def _resolve_firebase_project_id(credentials) -> str:
    project_id = settings.FIREBASE_PROJECT_ID or getattr(credentials, "project_id", None)
    if not project_id:
        raise ValueError("Configure FIREBASE_PROJECT_ID o use un service account con project_id.")
    return project_id


def _build_fcm_payload(notificacion: Notificacion, token: str) -> dict:
    data = {
        "id_notificacion": str(notificacion.id_notificacion),
        "id_incidente": str(notificacion.id_incidente or ""),
        "tipo_notificacion": notificacion.tipo_notificacion,
    }
    return {
        "message": {
            "token": token,
            "notification": {
                "title": notificacion.titulo,
                "body": notificacion.mensaje,
            },
            "data": data,
        }
    }


def _send_fcm_push_notifications(notificacion: Notificacion, tokens: list[str]) -> tuple[bool, str | None]:
    credentials = _get_firebase_credentials()
    project_id = _resolve_firebase_project_id(credentials)
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }

    errors = []
    for token in tokens:
        response = httpx.post(
            url,
            headers=headers,
            json=_build_fcm_payload(notificacion, token),
            timeout=settings.PUSH_TIMEOUT_SECONDS,
        )
        if response.is_success:
            continue

        try:
            error_payload = response.json()
        except ValueError:
            error_payload = {"error": {"message": response.text}}
        message = (
            error_payload.get("error", {}).get("message")
            or f"FCM HTTP {response.status_code}"
        )
        status_name = error_payload.get("error", {}).get("status")
        errors.append(str(status_name or message))

    if errors:
        return False, "; ".join(errors[:5])
    return True, None


def dispatch_push_notification_service(
    db: Session,
    notificacion: Notificacion,
) -> Notificacion:
    provider = settings.PUSH_PROVIDER.strip().lower()
    if provider in {"", "disabled", "none"}:
        return update_notificacion_push_result(
            db,
            notificacion,
            push_estado=PUSH_STATE_DISABLED,
            push_error="El proveedor push no esta habilitado.",
        )

    dispositivos = [
        dispositivo
        for dispositivo in get_dispositivos_push_by_usuario_id(
            db,
            notificacion.id_usuario,
            solo_activos=True,
        )
        if dispositivo.proveedor.strip().lower() == provider
    ]
    if not dispositivos:
        return update_notificacion_push_result(
            db,
            notificacion,
            push_estado=PUSH_STATE_NO_TOKEN,
            push_error=f"El usuario no tiene token push activo para {provider.upper()}.",
        )

    tokens = [dispositivo.token_push for dispositivo in dispositivos]
    try:
        if provider == "expo":
            sent, error = _send_expo_push_notifications(notificacion, tokens)
        elif provider == "fcm":
            sent, error = _send_fcm_push_notifications(notificacion, tokens)
        else:
            sent = False
            error = "Proveedor push no soportado por el backend."

        if error and any(code in error for code in ("DeviceNotRegistered", "UNREGISTERED")):
            for dispositivo in dispositivos:
                update_dispositivo_push_activo(db, dispositivo, activo=False)

        return update_notificacion_push_result(
            db,
            notificacion,
            push_estado=PUSH_STATE_SENT if sent else PUSH_STATE_FAILED,
            push_error=error,
            fecha_envio_push=datetime.utcnow() if sent else None,
        )
    except Exception as exc:
        return update_notificacion_push_result(
            db,
            notificacion,
            push_estado=PUSH_STATE_FAILED,
            push_error=str(exc)[:1000],
        )


def registrar_dispositivo_push_service(
    db: Session,
    current_user,
    payload: DispositivoPushRegisterRequest,
) -> DispositivoPushResponse:
    dispositivo = upsert_dispositivo_push(
        db,
        id_usuario=current_user.id_usuario,
        token_push=payload.token_push.strip(),
        plataforma=_normalize_push_platform(payload.plataforma),
        proveedor=_normalize_push_provider(payload.proveedor),
    )
    db.commit()
    db.refresh(dispositivo)
    return _to_dispositivo_push_response(dispositivo)


def listar_dispositivos_push_service(
    db: Session,
    current_user,
) -> list[DispositivoPushResponse]:
    dispositivos = get_dispositivos_push_by_usuario_id(db, current_user.id_usuario)
    return [_to_dispositivo_push_response(dispositivo) for dispositivo in dispositivos]


def desactivar_dispositivo_push_service(
    db: Session,
    current_user,
    token_push: str,
) -> DispositivoPushResponse:
    dispositivo = get_dispositivo_push_by_token(db, token_push)
    if not dispositivo or dispositivo.id_usuario != current_user.id_usuario:
        raise ValueError("El token push no existe o no pertenece al usuario autenticado.")
    dispositivo = update_dispositivo_push_activo(db, dispositivo, activo=False)
    db.commit()
    db.refresh(dispositivo)
    return _to_dispositivo_push_response(dispositivo)


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
    dispatch_push_notification_service(db, notificacion)
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
    db.commit()
    db.refresh(notificacion)
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


def _validar_incidente_apto_para_marcar_llegada(incidente) -> None:
    if not incidente.estado_servicio_actual:
        raise ValueError("El incidente no tiene un estado de servicio actual definido.")

    if incidente.estado_servicio_actual.nombre != ESTADO_APTO_MARCAR_LLEGADA:
        raise ValueError(
            "El incidente no se encuentra en un estado apto para marcar llegada. "
            f"Debe estar en {ESTADO_APTO_MARCAR_LLEGADA}."
        )


def _registrar_notificaciones_llegada_tecnico(
    db: Session,
    *,
    incidente,
    asignacion,
    current_user,
    fecha_llegada: datetime,
) -> int:
    destinatarios: list[int] = []

    cliente = get_cliente_by_id(db, incidente.id_cliente)
    if cliente and cliente.id_usuario != current_user.id_usuario:
        destinatarios.append(cliente.id_usuario)

    if (
        asignacion.taller
        and asignacion.taller.id_usuario != current_user.id_usuario
        and asignacion.taller.id_usuario not in destinatarios
    ):
        destinatarios.append(asignacion.taller.id_usuario)

    if not destinatarios:
        return 0

    mensaje = (
        "El tecnico asignado ha llegado al lugar del incidente "
        f"'{incidente.titulo}' el {fecha_llegada.strftime('%Y-%m-%d %H:%M:%S')}."
    )
    total = 0
    for id_usuario_destino in destinatarios:
        notificacion = create_notificacion(
            db,
            id_usuario=id_usuario_destino,
            id_incidente=incidente.id_incidente,
            titulo="Tecnico en sitio",
            mensaje=mensaje,
            tipo_notificacion=TIPO_NOTIFICACION_TECNICO_EN_SITIO,
        )
        dispatch_push_notification_service(db, notificacion)
        total += 1

    return total


def listar_incidentes_asignados_para_llegada_service(
    db: Session,
    current_user,
) -> list[IncidenteTecnicoLlegadaListResponse]:
    tecnico = _get_tecnico_autenticado(db, current_user)
    asignaciones = get_asignaciones_llegada_by_tecnico_id(db, tecnico.id_tecnico)
    return [
        _to_incidente_tecnico_llegada_list_response(asignacion)
        for asignacion in asignaciones
        if asignacion.incidente and asignacion.incidente.estado_servicio_actual
    ]


def marcar_llegada_incidente_service(
    db: Session,
    current_user,
    id_incidente: int,
    payload: MarcarLlegadaIncidenteRequest,
) -> MarcarLlegadaIncidenteResponse:
    tecnico = _get_tecnico_autenticado(db, current_user)
    incidente = get_incidente_by_id(db, id_incidente)
    if not incidente:
        raise TrackingIncidentNotFoundError("El incidente especificado no existe.")

    asignacion = get_asignacion_llegada_by_incidente_and_tecnico_id_for_update(
        db,
        id_incidente=id_incidente,
        id_tecnico=tecnico.id_tecnico,
    )
    if not asignacion:
        raise ValueError("El incidente no esta asignado al tecnico autenticado.")

    incidente_asignado = asignacion.incidente
    _validar_incidente_apto_para_marcar_llegada(incidente_asignado)

    nuevo_estado = get_estado_servicio_by_nombre(db, ESTADO_SERVICIO_TECNICO_EN_SITIO)
    if not nuevo_estado:
        raise ValueError(
            f"No existe el estado {ESTADO_SERVICIO_TECNICO_EN_SITIO} en la base de datos."
        )
    if nuevo_estado.id_estado_servicio == incidente_asignado.id_estado_servicio_actual:
        raise ValueError("El incidente ya se encuentra en el estado de atencion en sitio.")
    if nuevo_estado.orden_flujo != incidente_asignado.estado_servicio_actual.orden_flujo + 1:
        raise ValueError("La transicion de estado para marcar llegada no es valida.")

    fecha_llegada = datetime.utcnow()
    tiempo_llegada_seg = None
    if asignacion.fecha_asignacion is not None:
        tiempo_llegada_seg = max(
            int((fecha_llegada - asignacion.fecha_asignacion).total_seconds()),
            0,
        )

    detalle_historial = (
        payload.detalle.strip()
        if payload.detalle and payload.detalle.strip()
        else "El tecnico marco su llegada al lugar del incidente."
    )
    estado_anterior = incidente_asignado.estado_servicio_actual

    try:
        update_incidente_estado_servicio_actual(
            db,
            incidente_asignado,
            id_estado_servicio_actual=nuevo_estado.id_estado_servicio,
        )
        update_asignacion_servicio_estado(
            db,
            asignacion,
            estado_asignacion=nuevo_estado.nombre,
        )
        historial = create_historial_incidente(
            db,
            id_incidente=incidente_asignado.id_incidente,
            id_estado_anterior=estado_anterior.id_estado_servicio,
            id_estado_nuevo=nuevo_estado.id_estado_servicio,
            id_usuario_actor=current_user.id_usuario,
            detalle=detalle_historial,
        )
        upsert_metrica_incidente_llegada(
            db,
            id_incidente=incidente_asignado.id_incidente,
            tiempo_llegada_seg=tiempo_llegada_seg,
        )
        total_notificaciones = _registrar_notificaciones_llegada_tecnico(
            db,
            incidente=incidente_asignado,
            asignacion=asignacion,
            current_user=current_user,
            fecha_llegada=historial.fecha_hora,
        )

        db.commit()
        response = MarcarLlegadaIncidenteResponse(
            id_incidente=incidente_asignado.id_incidente,
            id_asignacion=asignacion.id_asignacion,
            id_tecnico=tecnico.id_tecnico,
            fecha_llegada=historial.fecha_hora,
            id_estado_anterior=estado_anterior.id_estado_servicio,
            estado_anterior=estado_anterior.nombre,
            id_estado_nuevo=nuevo_estado.id_estado_servicio,
            estado_nuevo=nuevo_estado.nombre,
            estado_asignacion=asignacion.estado_asignacion,
            tiempo_llegada_seg=tiempo_llegada_seg,
            historial_registrado=True,
            notificaciones_emitidas=total_notificaciones,
            validacion_geografica_aplicada=False,
            mensaje="Llegada al incidente registrada correctamente.",
        )
        _emitir_actualizacion_tiempo_real(
            incidente_asignado.id_incidente,
            {
                "type": "tecnico_en_sitio",
                "payload": response.model_dump(mode="json"),
            },
        )
        return response
    except Exception:
        db.rollback()
        raise


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
