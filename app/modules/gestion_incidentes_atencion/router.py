from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db.session import get_db
from app.modules.autenticacion_seguridad.models import Usuario
from app.modules.autenticacion_seguridad.permissions import require_roles
from app.modules.gestion_incidentes_atencion.schemas import (
    ActualizacionEstadoServicioResponse,
    ActualizarEstadoServicioRequest,
    AsignacionIncidenteRequest,
    AsignacionIncidenteResponse,
    EstadoServicioIncidenteResponse,
    IncidenteAsignadoDetailResponse,
    IncidenteAsignadoListResponse,
    IncidenteCreateRequest,
    IncidenteDisponibleResponse,
    IncidenteResponse,
    ResponderSolicitudAtencionRequest,
    RespuestaSolicitudAtencionResponse,
    SolicitudAtencionDetalleResponse,
    TecnicoDisponibleAsignacionResponse,
    TipoIncidenteResponse,
    UnidadMovilDisponibleAsignacionResponse,
)
from app.modules.gestion_incidentes_atencion.service import (
    actualizar_estado_servicio_incidente_service,
    asignar_tecnico_unidad_incidente_service,
    get_estado_servicio_incidente_service,
    get_incidentes_disponibles_service,
    get_mis_incidentes_service,
    get_solicitud_atencion_detalle_service,
    listar_incidentes_asignados_tecnico_service,
    listar_tecnicos_disponibles_para_incidente_service,
    listar_tipos_incidente_service,
    listar_unidades_moviles_disponibles_para_incidente_service,
    obtener_incidente_asignado_tecnico_service,
    report_incidente_service,
    responder_solicitud_atencion_service,
)

router = APIRouter(prefix="/incidentes", tags=["Gestion Incidentes y Atencion"])


@router.get(
    "/tipos-incidente",
    response_model=list[TipoIncidenteResponse],
    status_code=status.HTTP_200_OK,
)
def listar_tipos_incidente(
    db: Session = Depends(get_db),
):
    try:
        return listar_tipos_incidente_service(db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "",
    response_model=IncidenteResponse,
    status_code=status.HTTP_201_CREATED,
)
def report_incidente(
    payload: IncidenteCreateRequest,
    current_user: Usuario = Depends(require_roles("CLIENTE")),
    db: Session = Depends(get_db),
):
    try:
        return report_incidente_service(db, current_user, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/mis",
    response_model=list[IncidenteResponse],
    status_code=status.HTTP_200_OK,
)
def get_mis_incidentes(
    current_user: Usuario = Depends(require_roles("CLIENTE")),
    db: Session = Depends(get_db),
):
    try:
        return get_mis_incidentes_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/disponibles",
    response_model=list[IncidenteDisponibleResponse],
    status_code=status.HTTP_200_OK,
)
def get_incidentes_disponibles(
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return get_incidentes_disponibles_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/taller/solicitudes-atencion/{id_solicitud_taller}",
    response_model=SolicitudAtencionDetalleResponse,
    status_code=status.HTTP_200_OK,
)
def get_solicitud_atencion_detalle(
    id_solicitud_taller: int,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return get_solicitud_atencion_detalle_service(db, current_user, id_solicitud_taller)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/taller/solicitudes-atencion/{id_solicitud_taller}/respuesta",
    response_model=RespuestaSolicitudAtencionResponse,
    status_code=status.HTTP_200_OK,
)
def responder_solicitud_atencion(
    id_solicitud_taller: int,
    payload: ResponderSolicitudAtencionRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return responder_solicitud_atencion_service(
            db,
            current_user,
            id_solicitud_taller,
            payload,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/taller/incidentes/{id_incidente}/tecnicos-disponibles",
    response_model=list[TecnicoDisponibleAsignacionResponse],
    status_code=status.HTTP_200_OK,
)
def listar_tecnicos_disponibles_para_incidente(
    id_incidente: int,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return listar_tecnicos_disponibles_para_incidente_service(db, current_user, id_incidente)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/taller/incidentes/{id_incidente}/unidades-moviles-disponibles",
    response_model=list[UnidadMovilDisponibleAsignacionResponse],
    status_code=status.HTTP_200_OK,
)
def listar_unidades_moviles_disponibles_para_incidente(
    id_incidente: int,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return listar_unidades_moviles_disponibles_para_incidente_service(
            db,
            current_user,
            id_incidente,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/taller/incidentes/{id_incidente}/asignacion",
    response_model=AsignacionIncidenteResponse,
    status_code=status.HTTP_201_CREATED,
)
def asignar_tecnico_unidad_incidente(
    id_incidente: int,
    payload: AsignacionIncidenteRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return asignar_tecnico_unidad_incidente_service(
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
    "/taller/incidentes/{id_incidente}/estado",
    response_model=EstadoServicioIncidenteResponse,
    status_code=status.HTTP_200_OK,
)
def get_estado_servicio_incidente(
    id_incidente: int,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return get_estado_servicio_incidente_service(db, current_user, id_incidente)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/taller/incidentes/{id_incidente}/estado",
    response_model=ActualizacionEstadoServicioResponse,
    status_code=status.HTTP_200_OK,
)
def actualizar_estado_servicio_incidente(
    id_incidente: int,
    payload: ActualizarEstadoServicioRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return actualizar_estado_servicio_incidente_service(
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
    "/tecnico/incidentes-asignados",
    response_model=list[IncidenteAsignadoListResponse],
    status_code=status.HTTP_200_OK,
)
def listar_incidentes_asignados_tecnico(
    current_user: Usuario = Depends(require_roles("TECNICO")),
    db: Session = Depends(get_db),
):
    try:
        return listar_incidentes_asignados_tecnico_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/tecnico/incidentes-asignados/{id_incidente}",
    response_model=IncidenteAsignadoDetailResponse,
    status_code=status.HTTP_200_OK,
)
def obtener_incidente_asignado_tecnico(
    id_incidente: int,
    current_user: Usuario = Depends(require_roles("TECNICO")),
    db: Session = Depends(get_db),
):
    try:
        return obtener_incidente_asignado_tecnico_service(db, current_user, id_incidente)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
