import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db.session import get_db
from app.modules.autenticacion_seguridad.models import Usuario
from app.modules.autenticacion_seguridad.permissions import require_roles
from app.modules.inteligencia_gestion_estrategica.schemas import (
    AnalisisImagenRoboflowResponse,
    AnalizarImagenIncidenteRequest,
    AnalisisIncidenteManualRequest,
    AnalisisIncidenteResponse,
    AsignacionInteligenteResponse,
    ComisionPlataformaDetailResponse,
    ComisionPlataformaGenerateRequest,
    ComisionPlataformaGenerateResponse,
    ComisionPlataformaListResponse,
    EvidenciaProcesadaResponse,
    MetricaIncidenteDetailResponse,
    MetricaIncidenteListResponse,
    RegistrarEvidenciaProcesadaRequest,
    SolicitudMasInformacionResponse,
)
from app.modules.inteligencia_gestion_estrategica.service import (
    IncidentClassificationInsufficientError,
    IncidentClientNotFoundError,
    CommissionAlreadyExistsError,
    CommissionConfigurationError,
    CommissionNotFoundError,
    IncidentDoesNotRequireMoreInformationError,
    IncidentLocationInvalidError,
    IncidentNotFoundError,
    IncidentNotAnalyzedError,
    IncidentUserNotFoundError,
    IncidentVehicleNotFoundError,
    ImageEvidenceNotFoundError,
    listar_metricas_incidentes_service,
    listar_comisiones_plataforma_service,
    NoCandidateTallerFoundError,
    NoCommissionEligiblePaymentsError,
    obtener_metrica_incidente_service,
    obtener_comision_plataforma_service,
    generar_comisiones_plataforma_service,
    PaymentNotEligibleForCommissionError,
    RoboflowConfigurationError,
    analizar_imagen_incidente_roboflow_service,
    asignar_taller_inteligentemente_service,
    analizar_incidente_manual_service,
    analizar_incidente_por_id_service,
    listar_evidencias_procesadas_incidente_service,
    registrar_evidencia_procesada_service,
    solicitar_mas_informacion_incidente_service,
)

router = APIRouter(
    prefix="/inteligencia",
    tags=["Inteligencia y Gesti\u00f3n Estrat\u00e9gica"],
)


@router.post(
    "/incidentes/analizar",
    response_model=AnalisisIncidenteResponse,
    status_code=status.HTTP_200_OK,
)
def analizar_incidente_manual(
    payload: AnalisisIncidenteManualRequest,
):
    try:
        return analizar_incidente_manual_service(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error inesperado durante el analisis del incidente.",
        ) from exc


@router.post(
    "/incidentes/{id_incidente}/analizar",
    response_model=AnalisisIncidenteResponse,
    status_code=status.HTTP_200_OK,
)
def analizar_incidente_por_id(
    id_incidente: int,
    db: Session = Depends(get_db),
):
    try:
        return analizar_incidente_por_id_service(db, id_incidente)
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error inesperado durante el analisis o guardado del incidente.",
        ) from exc


@router.post(
    "/incidentes/{id_incidente}/solicitar-mas-informacion",
    response_model=SolicitudMasInformacionResponse,
    status_code=status.HTTP_200_OK,
)
def solicitar_mas_informacion_incidente(
    id_incidente: int,
    db: Session = Depends(get_db),
):
    try:
        return solicitar_mas_informacion_incidente_service(db, id_incidente)
    except (
        IncidentNotFoundError,
        IncidentClientNotFoundError,
        IncidentUserNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except IncidentDoesNotRequireMoreInformationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error inesperado al emitir la solicitud de mas informacion.",
        ) from exc


@router.post(
    "/incidentes/{id_incidente}/evidencias/procesada",
    response_model=EvidenciaProcesadaResponse,
    status_code=status.HTTP_201_CREATED,
)
def registrar_evidencia_procesada(
    id_incidente: int,
    payload: RegistrarEvidenciaProcesadaRequest,
    db: Session = Depends(get_db),
):
    try:
        return registrar_evidencia_procesada_service(db, id_incidente, payload)
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error inesperado al guardar la evidencia procesada.",
        ) from exc


@router.get(
    "/incidentes/{id_incidente}/evidencias",
    response_model=list[EvidenciaProcesadaResponse],
    status_code=status.HTTP_200_OK,
)
def listar_evidencias_procesadas_incidente(
    id_incidente: int,
    db: Session = Depends(get_db),
):
    try:
        return listar_evidencias_procesadas_incidente_service(db, id_incidente)
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error inesperado al listar las evidencias del incidente.",
        ) from exc


@router.post(
    "/incidentes/{id_incidente}/analizar-imagen",
    response_model=AnalisisImagenRoboflowResponse,
    status_code=status.HTTP_200_OK,
)
def analizar_imagen_incidente_roboflow(
    id_incidente: int,
    payload: AnalizarImagenIncidenteRequest,
    db: Session = Depends(get_db),
):
    try:
        return analizar_imagen_incidente_roboflow_service(db, id_incidente, payload)
    except (IncidentNotFoundError, ImageEvidenceNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (RoboflowConfigurationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Roboflow respondio con error durante el analisis de imagen: "
                f"{exc.response.status_code}."
            ),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible comunicarse con Roboflow para analizar la imagen.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error inesperado al analizar la imagen con Roboflow.",
        ) from exc


@router.post(
    "/incidentes/{id_incidente}/asignar-taller-inteligente",
    response_model=AsignacionInteligenteResponse,
    status_code=status.HTTP_200_OK,
)
def asignar_taller_inteligente(
    id_incidente: int,
    db: Session = Depends(get_db),
):
    try:
        return asignar_taller_inteligentemente_service(db, id_incidente)
    except (IncidentNotFoundError, NoCandidateTallerFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        IncidentNotAnalyzedError,
        IncidentDoesNotRequireMoreInformationError,
        IncidentClassificationInsufficientError,
        IncidentLocationInvalidError,
        IncidentVehicleNotFoundError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error inesperado al calcular la asignacion inteligente de taller.",
        ) from exc


@router.get(
    "/metricas/incidentes",
    response_model=list[MetricaIncidenteListResponse],
    status_code=status.HTTP_200_OK,
)
def listar_metricas_incidentes(
    current_user: Usuario = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    try:
        return listar_metricas_incidentes_service(db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error inesperado al generar las metricas de incidentes.",
        ) from exc


@router.get(
    "/metricas/incidentes/{id_incidente}",
    response_model=MetricaIncidenteDetailResponse,
    status_code=status.HTTP_200_OK,
)
def obtener_metrica_incidente(
    id_incidente: int,
    current_user: Usuario = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    try:
        return obtener_metrica_incidente_service(db, id_incidente)
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error inesperado al generar la metrica del incidente.",
        ) from exc


@router.get(
    "/comisiones",
    response_model=list[ComisionPlataformaListResponse],
    status_code=status.HTTP_200_OK,
)
def listar_comisiones_plataforma(
    current_user: Usuario = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
    id_taller: int | None = Query(default=None, ge=1),
    estado: str | None = Query(default=None, min_length=1, max_length=50),
    id_pago_servicio: int | None = Query(default=None, ge=1),
    id_incidente: int | None = Query(default=None, ge=1),
):
    try:
        return listar_comisiones_plataforma_service(
            db,
            id_taller=id_taller,
            estado=estado.strip() if estado else None,
            id_pago_servicio=id_pago_servicio,
            id_incidente=id_incidente,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error inesperado al listar las comisiones de la plataforma.",
        ) from exc


@router.get(
    "/comisiones/{id_comision}",
    response_model=ComisionPlataformaDetailResponse,
    status_code=status.HTTP_200_OK,
)
def obtener_comision_plataforma(
    id_comision: int,
    current_user: Usuario = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    try:
        return obtener_comision_plataforma_service(db, id_comision)
    except CommissionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error inesperado al consultar el detalle de la comision.",
        ) from exc


@router.post(
    "/comisiones/generar",
    response_model=ComisionPlataformaGenerateResponse,
    status_code=status.HTTP_200_OK,
)
def generar_comisiones_plataforma(
    payload: ComisionPlataformaGenerateRequest,
    current_user: Usuario = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    try:
        return generar_comisiones_plataforma_service(db, current_user, payload)
    except (NoCommissionEligiblePaymentsError, CommissionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        CommissionAlreadyExistsError,
        CommissionConfigurationError,
        PaymentNotEligibleForCommissionError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error inesperado al generar las comisiones de la plataforma.",
        ) from exc
