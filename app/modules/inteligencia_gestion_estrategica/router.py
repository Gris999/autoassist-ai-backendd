import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db.session import get_db
from app.modules.inteligencia_gestion_estrategica.schemas import (
    AnalisisImagenRoboflowResponse,
    AnalizarImagenIncidenteRequest,
    AnalisisIncidenteManualRequest,
    AnalisisIncidenteResponse,
    AsignacionInteligenteResponse,
    EvidenciaProcesadaResponse,
    RegistrarEvidenciaProcesadaRequest,
    SolicitudMasInformacionResponse,
)
from app.modules.inteligencia_gestion_estrategica.service import (
    IncidentClassificationInsufficientError,
    IncidentClientNotFoundError,
    IncidentDoesNotRequireMoreInformationError,
    IncidentLocationInvalidError,
    IncidentNotFoundError,
    IncidentNotAnalyzedError,
    IncidentUserNotFoundError,
    IncidentVehicleNotFoundError,
    ImageEvidenceNotFoundError,
    NoCandidateTallerFoundError,
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
