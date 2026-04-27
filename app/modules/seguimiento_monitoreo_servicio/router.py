from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.db.session import SessionLocal, get_db
from app.modules.autenticacion_seguridad.models import Usuario
from app.modules.autenticacion_seguridad.permissions import require_roles
from app.modules.seguimiento_monitoreo_servicio.realtime import incident_location_manager
from app.shared.dependencies.auth import get_current_user_from_token
from app.modules.seguimiento_monitoreo_servicio.schemas import (
    ActualizarUbicacionActualRequest,
    AsignacionAuxilioDetalleResponse,
    ClienteIncidenteListResponse,
    ConfirmacionPagoDemoResponse,
    ConfirmarPagoDemoRequest,
    ComprobantePagoResponse,
    CrearIntencionPagoRequest,
    EstadoServicioDetalleResponse,
    IncidenteHistorialDetailResponse,
    IncidenteHistorialListResponse,
    IntencionPagoResponse,
    NotificacionDetailResponse,
    NotificacionLeidaResponse,
    NotificacionListResponse,
    PagoIncidenteDetalleResponse,
    UbicacionActualTecnicoResponse,
    WebhookStripeResponse,
)
from app.modules.seguimiento_monitoreo_servicio.service import (
    PaymentAlreadyCompletedError,
    PaymentConfigurationError,
    PaymentNotEnabledError,
    PaymentRecordNotFoundError,
    actualizar_ubicacion_actual_tecnico_service,
    confirmar_pago_demo_service,
    consultar_asignacion_auxilio_service,
    crear_intencion_pago_service,
    get_estado_servicio_service,
    listar_incidentes_historial_service,
    listar_incidentes_cliente_service,
    listar_notificaciones_service,
    marcar_notificacion_leida_service,
    obtener_comprobante_pago_service,
    obtener_detalle_pago_incidente_service,
    obtener_historial_incidente_service,
    obtener_notificacion_service,
    procesar_webhook_stripe_service,
    validar_acceso_incidente_seguimiento_service,
)

router = APIRouter(
    prefix="/seguimiento",
    tags=["Seguimiento y Monitoreo del Servicio"],
)


@router.websocket("/ws/incidentes/{id_incidente}")
async def websocket_seguimiento_incidente(
    websocket: WebSocket,
    id_incidente: int,
    token: str = Query(...),
):
    db = SessionLocal()
    try:
        current_user = get_current_user_from_token(token, db)
        incidente = validar_acceso_incidente_seguimiento_service(db, current_user, id_incidente)
    except HTTPException:
        await websocket.close(code=1008)
        db.close()
        return
    except ValueError:
        await websocket.close(code=1008)
        db.close()
        return

    await incident_location_manager.connect(id_incidente, websocket)
    try:
        await incident_location_manager.send_personal_message(
            websocket,
            {
                "type": "conexion_establecida",
                "payload": {
                    "id_incidente": incidente.id_incidente,
                    "estado_servicio_actual": incidente.estado_servicio_actual.nombre,
                    "latitud": float(incidente.latitud) if incidente.latitud is not None else None,
                    "longitud": float(incidente.longitud) if incidente.longitud is not None else None,
                },
            },
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        incident_location_manager.disconnect(id_incidente, websocket)
    finally:
        db.close()


@router.get(
    "/pagos/incidentes/{id_incidente}",
    response_model=PagoIncidenteDetalleResponse,
    status_code=status.HTTP_200_OK,
)
def obtener_detalle_pago_incidente(
    id_incidente: int,
    current_user: Usuario = Depends(require_roles("CLIENTE")),
    db: Session = Depends(get_db),
):
    try:
        return obtener_detalle_pago_incidente_service(db, current_user, id_incidente)
    except (PaymentNotEnabledError, PaymentAlreadyCompletedError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/pagos/incidentes/{id_incidente}/intencion",
    response_model=IntencionPagoResponse,
    status_code=status.HTTP_201_CREATED,
)
def crear_intencion_pago(
    id_incidente: int,
    payload: CrearIntencionPagoRequest,
    current_user: Usuario = Depends(require_roles("CLIENTE")),
    db: Session = Depends(get_db),
):
    try:
        return crear_intencion_pago_service(db, current_user, id_incidente, payload)
    except (PaymentConfigurationError, PaymentNotEnabledError, PaymentAlreadyCompletedError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/pagos/incidentes/{id_incidente}/confirmar-demo",
    response_model=ConfirmacionPagoDemoResponse,
    status_code=status.HTTP_200_OK,
)
def confirmar_pago_demo(
    id_incidente: int,
    payload: ConfirmarPagoDemoRequest,
    current_user: Usuario = Depends(require_roles("CLIENTE")),
    db: Session = Depends(get_db),
):
    try:
        return confirmar_pago_demo_service(db, current_user, id_incidente, payload)
    except (PaymentNotEnabledError, PaymentAlreadyCompletedError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/pagos/{id_pago_servicio}/comprobante",
    response_model=ComprobantePagoResponse,
    status_code=status.HTTP_200_OK,
)
def obtener_comprobante_pago(
    id_pago_servicio: int,
    current_user: Usuario = Depends(require_roles("CLIENTE")),
    db: Session = Depends(get_db),
):
    try:
        return obtener_comprobante_pago_service(db, current_user, id_pago_servicio)
    except (PaymentConfigurationError, PaymentRecordNotFoundError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/pagos/webhook",
    response_model=WebhookStripeResponse,
    status_code=status.HTTP_200_OK,
)
async def procesar_webhook_pago(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    try:
        raw_payload = await request.body()
        return procesar_webhook_stripe_service(
            db,
            raw_payload=raw_payload,
            stripe_signature=stripe_signature,
        )
    except (PaymentConfigurationError, PaymentRecordNotFoundError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/incidentes/historial",
    response_model=list[IncidenteHistorialListResponse],
    status_code=status.HTTP_200_OK,
)
def listar_incidentes_historial(
    current_user: Usuario = Depends(
        require_roles("CLIENTE", "TECNICO", "TALLER", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    try:
        return listar_incidentes_historial_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.patch(
    "/incidentes/{id_incidente}/ubicacion-actual",
    response_model=UbicacionActualTecnicoResponse,
    status_code=status.HTTP_200_OK,
)
def actualizar_ubicacion_actual_tecnico(
    id_incidente: int,
    payload: ActualizarUbicacionActualRequest,
    current_user: Usuario = Depends(require_roles("TECNICO")),
    db: Session = Depends(get_db),
):
    try:
        return actualizar_ubicacion_actual_tecnico_service(
            db,
            current_user,
            id_incidente,
            payload,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/incidentes/{id_incidente}/historial",
    response_model=IncidenteHistorialDetailResponse,
    status_code=status.HTTP_200_OK,
)
def obtener_historial_incidente(
    id_incidente: int,
    current_user: Usuario = Depends(
        require_roles("CLIENTE", "TECNICO", "TALLER", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    try:
        return obtener_historial_incidente_service(db, current_user, id_incidente)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/notificaciones",
    response_model=list[NotificacionListResponse],
    status_code=status.HTTP_200_OK,
)
def listar_notificaciones(
    current_user: Usuario = Depends(require_roles("CLIENTE", "TALLER", "TECNICO")),
    db: Session = Depends(get_db),
):
    try:
        return listar_notificaciones_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/notificaciones/{id_notificacion}",
    response_model=NotificacionDetailResponse,
    status_code=status.HTTP_200_OK,
)
def obtener_notificacion(
    id_notificacion: int,
    current_user: Usuario = Depends(require_roles("CLIENTE", "TALLER", "TECNICO")),
    db: Session = Depends(get_db),
):
    try:
        return obtener_notificacion_service(db, current_user, id_notificacion)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.patch(
    "/notificaciones/{id_notificacion}/leer",
    response_model=NotificacionLeidaResponse,
    status_code=status.HTTP_200_OK,
)
def marcar_notificacion_leida(
    id_notificacion: int,
    current_user: Usuario = Depends(require_roles("CLIENTE", "TALLER", "TECNICO")),
    db: Session = Depends(get_db),
):
    try:
        return marcar_notificacion_leida_service(db, current_user, id_notificacion)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/cliente/incidentes",
    response_model=list[ClienteIncidenteListResponse],
    status_code=status.HTTP_200_OK,
)
def listar_incidentes_cliente(
    current_user: Usuario = Depends(require_roles("CLIENTE")),
    db: Session = Depends(get_db),
):
    try:
        return listar_incidentes_cliente_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/cliente/incidentes/{id_incidente}/asignacion",
    response_model=AsignacionAuxilioDetalleResponse,
    status_code=status.HTTP_200_OK,
)
def consultar_asignacion_auxilio(
    id_incidente: int,
    current_user: Usuario = Depends(require_roles("CLIENTE")),
    db: Session = Depends(get_db),
):
    try:
        return consultar_asignacion_auxilio_service(db, current_user, id_incidente)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/estado/{id_incidente}",
    response_model=EstadoServicioDetalleResponse,
    status_code=status.HTTP_200_OK,
)
def get_estado_servicio(
    id_incidente: int,
    current_user: Usuario = Depends(require_roles("CLIENTE")),
    db: Session = Depends(get_db),
):
    try:
        return get_estado_servicio_service(db, current_user, id_incidente)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
