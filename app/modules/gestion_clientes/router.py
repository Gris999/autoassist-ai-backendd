from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db.session import get_db
from app.modules.autenticacion_seguridad.models import Usuario
from app.modules.autenticacion_seguridad.permissions import require_roles
from app.modules.gestion_clientes.schemas import (
    CalificacionServicioCreateRequest,
    CalificacionServicioResponse,
    ServicioPendienteCalificacionResponse,
    TipoVehiculoResponse,
    VehiculoCreateRequest,
    VehiculoResponse,
)
from app.modules.gestion_clientes.service import (
    get_mis_vehiculos_service,
    listar_tipos_vehiculo_service,
    listar_servicios_pendientes_calificacion_service,
    register_vehiculo_service,
    registrar_calificacion_service,
)

router = APIRouter(prefix="/clientes", tags=["Gestion Clientes"])


@router.get(
    "/tipos-vehiculo",
    response_model=list[TipoVehiculoResponse],
    status_code=status.HTTP_200_OK,
)
def listar_tipos_vehiculo(
    db: Session = Depends(get_db),
):
    try:
        return listar_tipos_vehiculo_service(db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/vehiculos",
    response_model=VehiculoResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_vehiculo(
    payload: VehiculoCreateRequest,
    current_user: Usuario = Depends(require_roles("CLIENTE")),
    db: Session = Depends(get_db),
):
    try:
        return register_vehiculo_service(db, current_user, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/vehiculos",
    response_model=list[VehiculoResponse],
    status_code=status.HTTP_200_OK,
)
def get_mis_vehiculos(
    current_user: Usuario = Depends(require_roles("CLIENTE")),
    db: Session = Depends(get_db),
):
    try:
        return get_mis_vehiculos_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/servicios/finalizados/pendientes-calificacion",
    response_model=list[ServicioPendienteCalificacionResponse],
    status_code=status.HTTP_200_OK,
)
def listar_servicios_pendientes_calificacion(
    current_user: Usuario = Depends(require_roles("CLIENTE")),
    db: Session = Depends(get_db),
):
    try:
        return listar_servicios_pendientes_calificacion_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/calificaciones",
    response_model=CalificacionServicioResponse,
    status_code=status.HTTP_201_CREATED,
)
def registrar_calificacion(
    payload: CalificacionServicioCreateRequest,
    current_user: Usuario = Depends(require_roles("CLIENTE")),
    db: Session = Depends(get_db),
):
    try:
        return registrar_calificacion_service(db, current_user, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
