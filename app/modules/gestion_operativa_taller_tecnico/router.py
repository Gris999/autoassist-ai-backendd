from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db.session import get_db
from app.modules.autenticacion_seguridad.models import Usuario
from app.modules.autenticacion_seguridad.permissions import require_roles
from app.modules.gestion_operativa_taller_tecnico.schemas import (
    ActualizarDisponibilidadTecnicoRequest,
    ActualizarDisponibilidadTallerRequest,
    DisponibilidadTecnicoResponse,
    DisponibilidadTallerResponse,
    EspecialidadResponse,
    TecnicoCreateRequest,
    TecnicoDetailResponse,
    TecnicoEstadoResponse,
    TecnicoEspecialidadesAssignRequest,
    TecnicoEspecialidadesResponse,
    TecnicoEspecialidadesUpdateRequest,
    TecnicoListResponse,
    TecnicoUpdateRequest,
    TallerTiposVehiculoConfigRequest,
    TallerTiposVehiculoConfigResponse,
    TallerAuxilioCreateRequest,
    TipoAuxilioCatalogResponse,
    TallerAuxilioResponse,
    TallerAuxilioUpdateRequest,
    TallerInfoResponse,
    TipoVehiculoResponse,
    UnidadMovilCreateRequest,
    UnidadMovilDetailResponse,
    UnidadMovilEstadoDisponibilidadRequest,
    UnidadMovilListResponse,
    UnidadMovilUpdateRequest,
)
from app.modules.gestion_operativa_taller_tecnico.service import (
    actualizar_disponibilidad_tecnico_service,
    actualizar_disponibilidad_taller_service,
    actualizar_especialidades_tecnico_service,
    actualizar_estado_disponibilidad_unidad_movil_service,
    actualizar_tecnico_service,
    actualizar_unidad_movil_service,
    configurar_tipos_vehiculo_taller_service,
    deshabilitar_servicio_auxilio_service,
    deshabilitar_tecnico_service,
    habilitar_tecnico_service,
    asignar_especialidades_tecnico_service,
    listar_servicios_auxilio_service,
    listar_tipos_auxilio_disponibles_service,
    listar_especialidades_disponibles_service,
    listar_especialidades_tecnico_service,
    listar_tecnicos_service,
    listar_tipos_vehiculo_disponibles_service,
    listar_unidades_moviles_service,
    obtener_configuracion_tipos_vehiculo_taller_service,
    obtener_tecnico_service,
    obtener_disponibilidad_tecnico_service,
    obtener_disponibilidad_taller_service,
    obtener_informacion_taller_service,
    obtener_unidad_movil_service,
    obtener_talleres_disponibles_service,
    quitar_especialidad_tecnico_service,
    registrar_unidad_movil_service,
    registrar_tecnico_service,
    registrar_servicio_auxilio_service,
    actualizar_servicio_auxilio_service,
)

router = APIRouter(prefix="/operativo/taller", tags=["Gestión Operativa Taller"])


@router.get(
    "/me",
    response_model=TallerInfoResponse,
    status_code=status.HTTP_200_OK,
)
def obtener_informacion_taller(
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return obtener_informacion_taller_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/disponibilidad",
    response_model=DisponibilidadTallerResponse,
    status_code=status.HTTP_200_OK,
)
def obtener_disponibilidad(
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return obtener_disponibilidad_taller_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/disponibilidad",
    response_model=DisponibilidadTallerResponse,
    status_code=status.HTTP_200_OK,
)
def actualizar_disponibilidad(
    payload: ActualizarDisponibilidadTallerRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return actualizar_disponibilidad_taller_service(db, current_user, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/tipos-vehiculo",
    response_model=list[TipoVehiculoResponse],
    status_code=status.HTTP_200_OK,
)
def listar_tipos_vehiculo_disponibles(
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return listar_tipos_vehiculo_disponibles_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/configuracion/tipos-vehiculo",
    response_model=TallerTiposVehiculoConfigResponse,
    status_code=status.HTTP_200_OK,
)
def obtener_configuracion_tipos_vehiculo_taller(
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return obtener_configuracion_tipos_vehiculo_taller_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/configuracion/tipos-vehiculo",
    response_model=TallerTiposVehiculoConfigResponse,
    status_code=status.HTTP_200_OK,
)
def configurar_tipos_vehiculo_taller(
    payload: TallerTiposVehiculoConfigRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return configurar_tipos_vehiculo_taller_service(db, current_user, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/unidades-moviles",
    response_model=list[UnidadMovilListResponse],
    status_code=status.HTTP_200_OK,
)
def listar_unidades_moviles(
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return listar_unidades_moviles_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/unidades-moviles/{id_unidad_movil}",
    response_model=UnidadMovilDetailResponse,
    status_code=status.HTTP_200_OK,
)
def obtener_unidad_movil(
    id_unidad_movil: int,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return obtener_unidad_movil_service(db, current_user, id_unidad_movil)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/unidades-moviles",
    response_model=UnidadMovilDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def registrar_unidad_movil(
    payload: UnidadMovilCreateRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return registrar_unidad_movil_service(db, current_user, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/unidades-moviles/{id_unidad_movil}",
    response_model=UnidadMovilDetailResponse,
    status_code=status.HTTP_200_OK,
)
def actualizar_unidad_movil(
    id_unidad_movil: int,
    payload: UnidadMovilUpdateRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return actualizar_unidad_movil_service(db, current_user, id_unidad_movil, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/unidades-moviles/{id_unidad_movil}/disponibilidad",
    response_model=UnidadMovilDetailResponse,
    status_code=status.HTTP_200_OK,
)
def actualizar_estado_disponibilidad_unidad_movil(
    id_unidad_movil: int,
    payload: UnidadMovilEstadoDisponibilidadRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return actualizar_estado_disponibilidad_unidad_movil_service(
            db,
            current_user,
            id_unidad_movil,
            payload,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/tecnicos",
    response_model=list[TecnicoListResponse],
    status_code=status.HTTP_200_OK,
)
def listar_tecnicos(
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return listar_tecnicos_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/tecnicos/{id_tecnico}",
    response_model=TecnicoDetailResponse,
    status_code=status.HTTP_200_OK,
)
def obtener_tecnico(
    id_tecnico: int,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return obtener_tecnico_service(db, current_user, id_tecnico)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/tecnicos",
    response_model=TecnicoDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def registrar_tecnico(
    payload: TecnicoCreateRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return registrar_tecnico_service(db, current_user, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/tecnicos/{id_tecnico}",
    response_model=TecnicoDetailResponse,
    status_code=status.HTTP_200_OK,
)
def actualizar_tecnico(
    id_tecnico: int,
    payload: TecnicoUpdateRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return actualizar_tecnico_service(db, current_user, id_tecnico, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/tecnicos/{id_tecnico}/habilitar",
    response_model=TecnicoEstadoResponse,
    status_code=status.HTTP_200_OK,
)
def habilitar_tecnico(
    id_tecnico: int,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return habilitar_tecnico_service(db, current_user, id_tecnico)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/tecnicos/{id_tecnico}/deshabilitar",
    response_model=TecnicoEstadoResponse,
    status_code=status.HTTP_200_OK,
)
def deshabilitar_tecnico(
    id_tecnico: int,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return deshabilitar_tecnico_service(db, current_user, id_tecnico)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/especialidades",
    response_model=list[EspecialidadResponse],
    status_code=status.HTTP_200_OK,
)
def listar_especialidades_disponibles(
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return listar_especialidades_disponibles_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/tecnicos/{id_tecnico}/especialidades",
    response_model=TecnicoEspecialidadesResponse,
    status_code=status.HTTP_200_OK,
)
def listar_especialidades_tecnico(
    id_tecnico: int,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return listar_especialidades_tecnico_service(db, current_user, id_tecnico)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/tecnicos/{id_tecnico}/especialidades",
    response_model=TecnicoEspecialidadesResponse,
    status_code=status.HTTP_200_OK,
)
def asignar_especialidades_tecnico(
    id_tecnico: int,
    payload: TecnicoEspecialidadesAssignRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return asignar_especialidades_tecnico_service(db, current_user, id_tecnico, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/tecnicos/{id_tecnico}/especialidades",
    response_model=TecnicoEspecialidadesResponse,
    status_code=status.HTTP_200_OK,
)
def actualizar_especialidades_tecnico(
    id_tecnico: int,
    payload: TecnicoEspecialidadesUpdateRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return actualizar_especialidades_tecnico_service(db, current_user, id_tecnico, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/tecnicos/{id_tecnico}/especialidades/{id_especialidad}",
    response_model=TecnicoEspecialidadesResponse,
    status_code=status.HTTP_200_OK,
)
def quitar_especialidad_tecnico(
    id_tecnico: int,
    id_especialidad: int,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return quitar_especialidad_tecnico_service(
            db,
            current_user,
            id_tecnico,
            id_especialidad,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/tecnico/disponibilidad",
    response_model=DisponibilidadTecnicoResponse,
    status_code=status.HTTP_200_OK,
)
def obtener_disponibilidad_tecnico(
    current_user: Usuario = Depends(require_roles("TECNICO")),
    db: Session = Depends(get_db),
):
    try:
        return obtener_disponibilidad_tecnico_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/tecnico/disponibilidad",
    response_model=DisponibilidadTecnicoResponse,
    status_code=status.HTTP_200_OK,
)
def actualizar_disponibilidad_tecnico(
    payload: ActualizarDisponibilidadTecnicoRequest,
    current_user: Usuario = Depends(require_roles("TECNICO")),
    db: Session = Depends(get_db),
):
    try:
        return actualizar_disponibilidad_tecnico_service(db, current_user, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/tipos-auxilio",
    response_model=list[TipoAuxilioCatalogResponse],
    status_code=status.HTTP_200_OK,
)
def listar_tipos_auxilio_disponibles(
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return listar_tipos_auxilio_disponibles_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/servicios-auxilio",
    response_model=list[TallerAuxilioResponse],
    status_code=status.HTTP_200_OK,
)
def listar_servicios_auxilio(
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return listar_servicios_auxilio_service(db, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/servicios-auxilio",
    response_model=TallerAuxilioResponse,
    status_code=status.HTTP_201_CREATED,
)
def registrar_servicio_auxilio(
    payload: TallerAuxilioCreateRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return registrar_servicio_auxilio_service(db, current_user, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/servicios-auxilio/{id_taller_auxilio}",
    response_model=TallerAuxilioResponse,
    status_code=status.HTTP_200_OK,
)
def actualizar_servicio_auxilio(
    id_taller_auxilio: int,
    payload: TallerAuxilioUpdateRequest,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return actualizar_servicio_auxilio_service(db, current_user, id_taller_auxilio, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/servicios-auxilio/{id_taller_auxilio}/deshabilitar",
    response_model=TallerAuxilioResponse,
    status_code=status.HTTP_200_OK,
)
def deshabilitar_servicio_auxilio(
    id_taller_auxilio: int,
    current_user: Usuario = Depends(require_roles("TALLER")),
    db: Session = Depends(get_db),
):
    try:
        return deshabilitar_servicio_auxilio_service(db, current_user, id_taller_auxilio)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/disponibles",
    response_model=list[TallerInfoResponse],
    status_code=status.HTTP_200_OK,
)
def listar_talleres_disponibles(
    db: Session = Depends(get_db),
):
    try:
        return obtener_talleres_disponibles_service(db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
