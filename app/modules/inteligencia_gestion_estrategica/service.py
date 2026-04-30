import json
import unicodedata
from collections import Counter
from base64 import b64encode
from datetime import datetime
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from app.core.config.settings import settings
from app.modules.inteligencia_gestion_estrategica.commission_service import (
    CommissionAlreadyExistsError,
    CommissionConfigurationError,
    CommissionNotFoundError,
    NoCommissionEligiblePaymentsError,
    PaymentNotEligibleForCommissionError,
    decimal_amount as commission_decimal_amount,
    generate_platform_commission_for_payment,
    resolve_pago_taller,
)
from app.modules.inteligencia_gestion_estrategica.repository import (
    create_solicitud_taller,
    create_processed_evidence,
    create_notification,
    get_cliente_by_id,
    get_comision_plataforma_by_id,
    get_evidencia_by_id_and_incidente_id,
    get_evidencia_textos_by_incidente_id,
    get_estado_servicio_by_nombre,
    get_incidente_by_id,
    get_incidente_metrics_context_by_id,
    get_incidente_with_assignment_context,
    get_latest_image_evidence_by_incidente_id,
    get_metrica_incidente_by_incidente_id,
    get_prioridad_by_nombre,
    get_pending_notification_by_incidente_usuario_tipo,
    get_solicitud_taller_by_incidente_and_taller,
    get_tipo_incidente_by_nombre,
    get_usuario_by_id,
    get_pago_servicio_with_comision_by_id,
    list_comisiones_plataforma,
    list_incidentes_metrics_context,
    list_pagos_servicio_elegibles_para_comision,
    list_available_talleres_with_resources,
    list_evidences_by_incidente_id,
    upsert_metrica_incidente,
    update_evidencia_texto_extraido,
    update_solicitud_taller_candidate_data,
    update_incidente_analysis_result,
)
from app.modules.inteligencia_gestion_estrategica.schemas import (
    AnalisisImagenRoboflowResponse,
    AnalizarImagenIncidenteRequest,
    AnalisisIncidenteManualRequest,
    AnalisisIncidenteLLMResult,
    AnalisisIncidenteResponse,
    AsignacionInteligenteResponse,
    ComisionDetallePagoResponse,
    ComisionPlataformaDetailResponse,
    ComisionPlataformaGenerateItemResponse,
    ComisionPlataformaGenerateRequest,
    ComisionPlataformaGenerateResponse,
    ComisionPlataformaListResponse,
    EntrenarModeloImagenRequest,
    EntrenarModeloImagenResponse,
    EvidenciaProcesadaResponse,
    GeminiTallerRankingResult,
    MetricaIncidenteDetailResponse,
    MetricaIncidenteListResponse,
    RegistrarEvidenciaProcesadaRequest,
    SolicitudMasInformacionResponse,
    TallerCandidatoResponse,
    TallerRecomendadoResponse,
)
from app.modules.seguimiento_monitoreo_servicio.service import (
    dispatch_push_notification_service,
)


INCIDENTE_BATERIA = "bateria"
INCIDENTE_LLANTA = "llanta"
INCIDENTE_CHOQUE = "choque"
INCIDENTE_MOTOR = "motor"
INCIDENTE_COMBUSTIBLE = "combustible"
INCIDENTE_LLAVE = "llave"
INCIDENTE_INCIERTO = "incierto"

AUXILIO_REMOLQUE = "REMOLQUE"
AUXILIO_ELECTRICO = "AUXILIO_ELECTRICO"
AUXILIO_LLANTA = "CAMBIO_DE_LLANTA"
AUXILIO_COMBUSTIBLE = "SUMINISTRO_COMBUSTIBLE"
AUXILIO_APERTURA = "APERTURA_VEHICULO"
AUXILIO_MECANICO = "AUXILIO_MECANICO_BASICO"

NORMALIZED_CLASSIFICATION_MAP: dict[str, str] = {
    INCIDENTE_BATERIA: INCIDENTE_BATERIA,
    "electrico": INCIDENTE_BATERIA,
    INCIDENTE_LLANTA: INCIDENTE_LLANTA,
    INCIDENTE_CHOQUE: INCIDENTE_CHOQUE,
    INCIDENTE_MOTOR: INCIDENTE_MOTOR,
    INCIDENTE_COMBUSTIBLE: INCIDENTE_COMBUSTIBLE,
    INCIDENTE_LLAVE: INCIDENTE_LLAVE,
    INCIDENTE_INCIERTO: INCIDENTE_INCIERTO,
    AUXILIO_ELECTRICO.lower(): INCIDENTE_BATERIA,
    AUXILIO_LLANTA.lower(): INCIDENTE_LLANTA,
    AUXILIO_REMOLQUE.lower(): INCIDENTE_CHOQUE,
    AUXILIO_MECANICO.lower(): INCIDENTE_MOTOR,
    AUXILIO_COMBUSTIBLE.lower(): INCIDENTE_COMBUSTIBLE,
    AUXILIO_APERTURA.lower(): INCIDENTE_LLAVE,
    "apertura_vehiculo": INCIDENTE_LLAVE,
    "auxilio_mecanico_basico": INCIDENTE_MOTOR,
    "suministro_combustible": INCIDENTE_COMBUSTIBLE,
    "cambio_de_llanta": INCIDENTE_LLANTA,
}

CATEGORY_TO_AUXILIO: dict[str, str] = {
    INCIDENTE_BATERIA: AUXILIO_ELECTRICO,
    INCIDENTE_LLANTA: AUXILIO_LLANTA,
    INCIDENTE_CHOQUE: AUXILIO_REMOLQUE,
    INCIDENTE_MOTOR: AUXILIO_MECANICO,
    INCIDENTE_COMBUSTIBLE: AUXILIO_COMBUSTIBLE,
    INCIDENTE_LLAVE: AUXILIO_APERTURA,
}

KEYWORDS_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    INCIDENTE_BATERIA: (
        "no enciende",
        "no arranca",
        "bateria",
        "descargada",
        "corriente",
        "tablero",
        "luces",
        "chispa",
    ),
    INCIDENTE_LLANTA: (
        "llanta",
        "pinchazo",
        "pinchada",
        "rueda",
        "neumatico",
        "desinflada",
        "revento",
    ),
    INCIDENTE_CHOQUE: (
        "choque",
        "colision",
        "accidente",
        "golpe",
        "impacto",
        "abollado",
        "parachoques",
    ),
    INCIDENTE_MOTOR: (
        "motor",
        "humo",
        "sobrecalentamiento",
        "calento",
        "temperatura",
        "aceite",
        "ruido extrano",
        "falla mecanica",
    ),
    INCIDENTE_COMBUSTIBLE: (
        "gasolina",
        "combustible",
        "sin gasolina",
        "sin combustible",
        "tanque vacio",
    ),
    INCIDENTE_LLAVE: (
        "llave",
        "perdi la llave",
        "llave dentro",
        "no puedo abrir",
        "cerradura",
    ),
}

PRIORITY_BY_CATEGORY: dict[str, str] = {
    INCIDENTE_CHOQUE: "alta",
    INCIDENTE_MOTOR: "alta",
    INCIDENTE_BATERIA: "media",
    INCIDENTE_LLANTA: "media",
    INCIDENTE_COMBUSTIBLE: "media",
    INCIDENTE_LLAVE: "baja",
    INCIDENTE_INCIERTO: "baja",
}

INCIDENT_TYPE_BY_CATEGORY: dict[str, str] = {
    INCIDENTE_BATERIA: "BATERIA_DESCARGADA",
    INCIDENTE_LLANTA: "PINCHAZO_LLANTA",
    INCIDENTE_CHOQUE: "ACCIDENTE_MENOR",
    INCIDENTE_MOTOR: "FALLA_MECANICA",
    INCIDENTE_COMBUSTIBLE: "SIN_COMBUSTIBLE",
    INCIDENTE_LLAVE: "LLAVES_DENTRO",
}

QUESTIONS_BY_CATEGORY: dict[str, list[str]] = {
    INCIDENTE_INCIERTO: [
        "\u00bfEl vehiculo enciende?",
        "\u00bfTiene alguna llanta danada?",
        "\u00bfHay humo, fuga o golpe visible?",
        "\u00bfPuede enviar una foto del problema?",
    ],
    INCIDENTE_BATERIA: [
        "\u00bfEl vehiculo intenta arrancar o no hace ningun sonido?",
        "\u00bfSe encienden las luces del tablero?",
        "\u00bfHace cuanto tiempo se cambio la bateria?",
    ],
    INCIDENTE_LLANTA: [
        "\u00bfLa llanta esta desinflada o reventada?",
        "\u00bfTiene llanta de auxilio?",
        "\u00bfEsta en carretera o dentro de la ciudad?",
    ],
    INCIDENTE_CHOQUE: [
        "\u00bfHay personas heridas?",
        "\u00bfEl vehiculo puede moverse?",
        "\u00bfEl dano es frontal, lateral o trasero?",
    ],
    INCIDENTE_MOTOR: [
        "\u00bfSale humo del motor?",
        "\u00bfLa temperatura esta elevada?",
        "\u00bfEscucha algun ruido extrano?",
    ],
    INCIDENTE_COMBUSTIBLE: [
        "\u00bfEl indicador marca reserva o vacio?",
        "\u00bfEl vehiculo se detuvo por falta de combustible?",
        "\u00bfSe encuentra en una zona segura para recibir auxilio?",
    ],
    INCIDENTE_LLAVE: [
        "\u00bfLa llave quedo dentro del vehiculo o se perdio?",
        "\u00bfCuenta con llave de repuesto?",
        "\u00bfLa cerradura responde o esta bloqueada?",
    ],
}

ALLOWED_EVIDENCE_TYPES = {
    "TEXTO",
    "AUDIO_TRANSCRITO",
    "IMAGEN_ANALIZADA",
}

ALLOWED_INCIDENT_CATEGORIES = tuple(KEYWORDS_BY_CATEGORY.keys()) + (INCIDENTE_INCIERTO,)
ALLOWED_PRIORITIES = ("baja", "media", "alta", "critica")

ESTADOS_SOLICITUD_EXCLUIDOS = {"RECHAZADA", "CANCELADA"}
ESTADOS_INCIDENTE_NO_APTOS_PARA_ASIGNACION = {
    "ASIGNADO",
    "EN_CAMINO",
    "EN_ATENCION",
    "FINALIZADO",
    "CANCELADO",
}
ESTADO_SOLICITUD_INTELIGENTE = "PENDIENTE"
ESTADO_INCIDENTE_BUSCANDO_TALLER = "BUSCANDO_TALLER"
ROBOFLOW_IMAGE_EVIDENCE_TYPES = {"IMAGEN", "FOTO", "IMAGE"}
ROBOFLOW_SUPPORTED_TASK_TYPES = {"classification", "object-detection"}
AUDIO_EVIDENCE_TYPES = {"AUDIO", "AUDIO_TRANSCRITO", "VOICE", "MP3", "WAV", "M4A", "OGG"}
AUDIO_MIME_TYPES_BY_EXTENSION = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
}
AUTOASSIST_LOCAL_TZ = ZoneInfo("America/La_Paz")


class IncidentNotFoundError(LookupError):
    pass


class IncidentDoesNotRequireMoreInformationError(ValueError):
    pass


class IncidentClientNotFoundError(LookupError):
    pass


class IncidentUserNotFoundError(LookupError):
    pass


class IncidentNotAnalyzedError(ValueError):
    pass


class IncidentClassificationInsufficientError(ValueError):
    pass


class IncidentLocationInvalidError(ValueError):
    pass


class IncidentVehicleNotFoundError(ValueError):
    pass


class NoCandidateTallerFoundError(LookupError):
    pass


class ImageEvidenceNotFoundError(LookupError):
    pass


class RoboflowConfigurationError(ValueError):
    pass


class MetricsNotAvailableError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _normalize_roboflow_task_type() -> str:
    task_type = settings.ROBOFLOW_TASK_TYPE.strip().lower()
    if task_type not in ROBOFLOW_SUPPORTED_TASK_TYPES:
        raise RoboflowConfigurationError(
            "ROBOFLOW_TASK_TYPE invalido. Use classification u object-detection."
        )
    return task_type


def _is_image_evidence(evidencia) -> bool:
    evidence_type = (evidencia.tipo_evidencia or "").strip().upper()
    return evidence_type in ROBOFLOW_IMAGE_EVIDENCE_TYPES and bool(
        (evidencia.archivo_url or "").strip()
    )


def _extract_image_label_category(raw_label: str) -> str:
    normalized_label = _normalize_text(raw_label)
    if any(keyword in normalized_label for keyword in ("battery", "bateria", "tablero", "electrico", "starter")):
        return "bateria"
    if any(keyword in normalized_label for keyword in ("tire", "tyre", "llanta", "wheel", "neumatico", "puncture", "pinch")):
        return "llanta"
    if any(keyword in normalized_label for keyword in ("crash", "collision", "choque", "bumper", "frontal", "impact", "damage_front")):
        return "choque"
    if any(keyword in normalized_label for keyword in ("engine", "motor", "smoke", "humo", "oil", "overheat", "fuga")):
        return "motor"
    if any(keyword in normalized_label for keyword in ("fuel", "combustible", "gas", "gasolina")):
        return "combustible"
    if any(keyword in normalized_label for keyword in ("key", "llave", "lock", "cerradura", "door")):
        return "llave"
    return INCIDENTE_INCIERTO


def _summarize_roboflow_predictions(
    *,
    task_type: str,
    payload: dict,
) -> tuple[str, float, list[str]]:
    if task_type == "classification":
        raw_predictions = payload.get("predictions", [])
        normalized_predictions: list[tuple[str, float]] = []
        if isinstance(raw_predictions, list):
            for prediction in raw_predictions:
                label = str(prediction.get("class", "")).strip()
                confidence = float(prediction.get("confidence", 0.0) or 0.0)
                if label:
                    normalized_predictions.append((label, confidence))
        elif isinstance(raw_predictions, dict):
            for label, value in raw_predictions.items():
                confidence = float((value or {}).get("confidence", 0.0) or 0.0)
                normalized_predictions.append((str(label).strip(), confidence))

        normalized_predictions.sort(key=lambda item: item[1], reverse=True)
        top_label = str(payload.get("top") or (normalized_predictions[0][0] if normalized_predictions else INCIDENTE_INCIERTO))
        top_confidence = float(payload.get("confidence") or (normalized_predictions[0][1] if normalized_predictions else 0.0))
        detections = [
            f"{label} ({confidence:.2f})"
            for label, confidence in normalized_predictions[:5]
        ]
        return top_label, round(min(max(top_confidence, 0.0), 1.0), 2), detections

    raw_predictions = payload.get("predictions", [])
    normalized_predictions = []
    for prediction in raw_predictions:
        label = str(prediction.get("class", "")).strip()
        confidence = float(prediction.get("confidence", 0.0) or 0.0)
        if label:
            normalized_predictions.append((label, confidence))

    normalized_predictions.sort(key=lambda item: item[1], reverse=True)
    top_label = normalized_predictions[0][0] if normalized_predictions else INCIDENTE_INCIERTO
    top_confidence = normalized_predictions[0][1] if normalized_predictions else 0.0
    detections = [
        f"{label} ({confidence:.2f})"
        for label, confidence in normalized_predictions[:5]
    ]
    return top_label, round(min(max(top_confidence, 0.0), 1.0), 2), detections


def _build_roboflow_visual_summary(
    *,
    task_type: str,
    top_label: str,
    confidence: float,
    detections: list[str],
    categoria_sugerida: str,
) -> str:
    summary_parts = [
        "Analisis visual Roboflow detecta evidencia relacionada con "
        f"'{top_label}' con confianza {confidence:.2f}.",
        f"Categoria sugerida para el incidente: {categoria_sugerida}.",
    ]
    if task_type == "object-detection" and detections:
        summary_parts.append(
            "Detecciones principales: " + ", ".join(detections[:5]) + "."
        )
    elif detections:
        summary_parts.append(
            "Clasificaciones probables: " + ", ".join(detections[:5]) + "."
        )
    return " ".join(summary_parts)


def _run_roboflow_image_analysis(*, image_url: str) -> tuple[str, str, float, str, list[str]]:
    if not settings.ROBOFLOW_API_KEY or not settings.ROBOFLOW_MODEL_ID:
        raise RoboflowConfigurationError(
            "ROBOFLOW_API_KEY y ROBOFLOW_MODEL_ID deben estar configuradas."
        )

    task_type = _normalize_roboflow_task_type()
    api_url = (
        "https://classify.roboflow.com"
        if task_type == "classification"
        else "https://detect.roboflow.com"
    )
    response = httpx.post(
        f"{api_url}/{settings.ROBOFLOW_MODEL_ID}",
        params={
            "api_key": settings.ROBOFLOW_API_KEY,
            "image": image_url,
        },
        timeout=settings.ROBOFLOW_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    payload = response.json()
    top_label, confidence, detections = _summarize_roboflow_predictions(
        task_type=task_type,
        payload=payload,
    )
    categoria_sugerida = _extract_image_label_category(top_label)
    resumen_visual = _build_roboflow_visual_summary(
        task_type=task_type,
        top_label=top_label,
        confidence=confidence,
        detections=detections,
        categoria_sugerida=categoria_sugerida,
    )
    return task_type, top_label, confidence, categoria_sugerida, [resumen_visual, *detections]


def _resolve_roboflow_training_context(dataset_version: int | None = None) -> tuple[str, str, int]:
    workspace = (settings.ROBOFLOW_WORKSPACE or "").strip()
    project = (settings.ROBOFLOW_PROJECT or "").strip()
    version = dataset_version or settings.ROBOFLOW_DATASET_VERSION

    if not settings.ROBOFLOW_API_KEY:
        raise RoboflowConfigurationError("ROBOFLOW_API_KEY debe estar configurada.")
    if not workspace:
        raise RoboflowConfigurationError("ROBOFLOW_WORKSPACE debe estar configurada.")
    if not project:
        raise RoboflowConfigurationError("ROBOFLOW_PROJECT debe estar configurada.")
    if version is None or int(version) < 1:
        raise RoboflowConfigurationError(
            "ROBOFLOW_DATASET_VERSION debe estar configurada con un valor >= 1."
        )

    return workspace, project, int(version)


def entrenar_modelo_imagen_roboflow_service(
    payload: EntrenarModeloImagenRequest,
) -> EntrenarModeloImagenResponse:
    workspace, project, version = _resolve_roboflow_training_context(payload.dataset_version)

    base_url = settings.ROBOFLOW_TRAIN_ENDPOINT.rstrip("/")
    response = httpx.post(
        f"{base_url}/{workspace}/{project}/{version}/train",
        params={"api_key": settings.ROBOFLOW_API_KEY},
        timeout=settings.ROBOFLOW_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()

    estado = str(
        data.get("status")
        or data.get("state")
        or "queued"
    )
    job_id = data.get("job") or data.get("job_id")
    if job_id is not None:
        job_id = str(job_id)

    mensaje = (
        f"Entrenamiento enviado a Roboflow para {workspace}/{project} v{version}."
    )
    if payload.notas:
        mensaje += f" Nota: {payload.notas.strip()}"

    return EntrenarModeloImagenResponse(
        proveedor="roboflow",
        workspace=workspace,
        proyecto=project,
        version_dataset=version,
        job_id=job_id,
        estado=estado,
        mensaje=mensaje,
        detalle=data if isinstance(data, dict) else {"raw": data},
    )


def _clean_texts(texts: list[str | None]) -> list[str]:
    return [text.strip() for text in texts if text and text.strip()]


def _build_text_corpus(
    descripcion_texto: str | None,
    texto_evidencias: list[str],
) -> tuple[list[str], str]:
    text_parts = _clean_texts([descripcion_texto, *texto_evidencias])
    return text_parts, _normalize_text(" ".join(text_parts))


def _match_keywords(text: str) -> dict[str, list[str]]:
    return {
        category: [keyword for keyword in keywords if _normalize_text(keyword) in text]
        for category, keywords in KEYWORDS_BY_CATEGORY.items()
    }


def _classify_incident(
    descripcion_texto: str | None,
    texto_evidencias: list[str],
) -> tuple[str, float, dict[str, list[str]], list[str]]:
    text_parts, normalized_text = _build_text_corpus(descripcion_texto, texto_evidencias)
    if not normalized_text:
        raise ValueError("No hay informacion suficiente para analizar el incidente.")

    matches_by_category = _match_keywords(normalized_text)
    scores = {
        category: len(matches)
        for category, matches in matches_by_category.items()
    }

    max_score = max(scores.values(), default=0)
    if max_score == 0:
        return INCIDENTE_INCIERTO, 0.0, matches_by_category, text_parts

    top_categories = [
        category
        for category, score in scores.items()
        if score == max_score
    ]
    if len(top_categories) > 1:
        return INCIDENTE_INCIERTO, 0.25, matches_by_category, text_parts

    category = top_categories[0]
    total_hits = sum(scores.values())
    dominance = max_score / total_hits if total_hits else 0.0

    confidence = 0.25 + (0.12 * max_score) + (0.18 * dominance)
    if descripcion_texto and descripcion_texto.strip():
        confidence += 0.05
    if texto_evidencias:
        confidence += 0.05

    confidence = round(min(confidence, 0.95), 2)
    return category, confidence, matches_by_category, text_parts


def _estimate_priority(category: str) -> str:
    return PRIORITY_BY_CATEGORY.get(category, "baja")


def _requires_more_information(
    *,
    category: str,
    confidence: float,
    text_parts: list[str],
) -> bool:
    if category == INCIDENTE_INCIERTO:
        return True
    if confidence < 0.55:
        return True
    return sum(len(part.split()) for part in text_parts) < 4


def _build_summary(
    *,
    category: str,
    priority: str,
    confidence: float,
    requires_more_info: bool,
    matches_by_category: dict[str, list[str]],
    evidence_count: int,
    has_location: bool,
) -> str:
    matched_keywords = matches_by_category.get(category, [])
    summary_parts = [
        f"Analisis automatico sugiere un incidente de tipo {category} con prioridad {priority}.",
        f"Confianza estimada: {confidence:.2f}.",
    ]

    if matched_keywords:
        summary_parts.append(
            "Indicadores detectados: " + ", ".join(matched_keywords[:4]) + "."
        )

    if evidence_count:
        summary_parts.append(
            f"Se consideraron {evidence_count} texto(s) extraidos de evidencias."
        )

    if has_location:
        summary_parts.append("La ubicacion del incidente se encuentra disponible.")

    if requires_more_info:
        summary_parts.append(
            "Se requiere mas informacion para confirmar la clasificacion preliminar."
        )

    return " ".join(summary_parts)


def _normalize_llm_category(value: str | None) -> str:
    normalized = _normalize_text((value or "").strip())
    normalized = NORMALIZED_CLASSIFICATION_MAP.get(normalized, normalized)
    if normalized in ALLOWED_INCIDENT_CATEGORIES:
        return normalized
    return INCIDENTE_INCIERTO


def _normalize_llm_priority(value: str | None) -> str:
    normalized = _normalize_text((value or "").strip())
    if normalized in ALLOWED_PRIORITIES:
        return normalized
    return "baja"


def _normalize_llm_questions(questions: list[str] | None, *, requires_more_info: bool) -> list[str]:
    if not requires_more_info:
        return []
    if not questions:
        return []
    cleaned = []
    for question in questions:
        if not question:
            continue
        normalized_question = question.strip()
        if normalized_question:
            cleaned.append(normalized_question[:250])
    return cleaned[:5]


def _build_llm_input_payload(
    *,
    descripcion_texto: str | None,
    texto_evidencias: list[str],
    latitud: Decimal | None,
    longitud: Decimal | None,
) -> str:
    partes = [
        "Analiza el incidente vehicular y responde SOLO JSON valido.",
        "Debes clasificar el incidente, estimar prioridad, resumirlo y decidir si requiere mas informacion.",
        f"Descripcion del incidente: {descripcion_texto or 'Sin descripcion'}",
        f"Latitud: {latitud if latitud is not None else 'No disponible'}",
        f"Longitud: {longitud if longitud is not None else 'No disponible'}",
        "Textos extraidos de evidencias:",
    ]

    if texto_evidencias:
        for index, evidencia in enumerate(texto_evidencias, start=1):
            partes.append(f"{index}. {evidencia}")
    else:
        partes.append("No hay textos extraidos de evidencias.")

    partes.extend(
        [
            "Categorias validas: bateria, llanta, choque, motor, combustible, llave, incierto.",
            "Prioridades validas: baja, media, alta, critica.",
            "Si no hay suficiente informacion, usa clasificacion 'incierto' y requiere_mas_info=true.",
            "Si requiere_mas_info=false, devuelve preguntas_sugeridas vacio.",
        ]
    )
    return "\n".join(partes)


def _get_llm_analysis_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "clasificacion_ia": {
                "type": "string",
                "enum": list(ALLOWED_INCIDENT_CATEGORIES),
            },
            "confianza_clasificacion": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },
            "prioridad": {
                "type": "string",
                "enum": list(ALLOWED_PRIORITIES),
            },
            "resumen_ia": {
                "type": "string",
            },
            "requiere_mas_info": {
                "type": "boolean",
            },
            "preguntas_sugeridas": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "clasificacion_ia",
            "confianza_clasificacion",
            "prioridad",
            "resumen_ia",
            "requiere_mas_info",
            "preguntas_sugeridas",
        ],
    }


def _get_gemini_taller_ranking_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "justificacion_global": {"type": "string"},
            "candidatos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id_taller": {"type": "integer"},
                        "ajuste_puntaje": {
                            "type": "number",
                            "minimum": -15,
                            "maximum": 15,
                        },
                        "justificacion": {"type": "string"},
                    },
                    "required": [
                        "id_taller",
                        "ajuste_puntaje",
                        "justificacion",
                    ],
                },
            },
        },
        "required": ["justificacion_global", "candidatos"],
    }


def _build_gemini_taller_ranking_input_payload(
    *,
    incidente,
    candidatos: list[dict],
) -> str:
    payload = {
        "incidente": {
            "id_incidente": incidente.id_incidente,
            "titulo": incidente.titulo,
            "clasificacion_ia": incidente.clasificacion_ia,
            "prioridad": incidente.prioridad.nombre if incidente.prioridad else None,
            "tipo_incidente": (
                incidente.tipo_incidente.nombre if incidente.tipo_incidente else None
            ),
            "latitud": float(incidente.latitud) if incidente.latitud is not None else None,
            "longitud": float(incidente.longitud) if incidente.longitud is not None else None,
            "requiere_mas_info": incidente.requiere_mas_info,
        },
        "candidatos": candidatos,
        "instrucciones": [
            "Evalua talleres candidatos para atender el incidente.",
            "Usa unicamente los datos entregados en el JSON.",
            "No inventes servicios, distancias ni disponibilidad.",
            "Devuelve un ajuste de puntaje entre -15 y 15 por candidato.",
            "Favorece compatibilidad tecnica y cercania antes que preferencias subjetivas.",
            "Incluye una justificacion corta por candidato y una justificacion global.",
        ],
    }
    return json.dumps(payload, ensure_ascii=True)


def _run_gemini_incident_analysis(
    *,
    descripcion_texto: str | None,
    texto_evidencias: list[str],
    latitud: Decimal | None,
    longitud: Decimal | None,
) -> AnalisisIncidenteLLMResult:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY no configurada.")

    response = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent",
        headers={
            "x-goog-api-key": settings.GEMINI_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "system_instruction": {
                "parts": [
                    {
                        "text": (
                            "Eres un analizador de incidentes vehiculares para AutoAssist AI. "
                            "Debes responder estrictamente en JSON siguiendo el esquema solicitado."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "parts": [
                        {
                            "text": _build_llm_input_payload(
                                descripcion_texto=descripcion_texto,
                                texto_evidencias=texto_evidencias,
                                latitud=latitud,
                                longitud=longitud,
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": _get_llm_analysis_schema(),
            },
        },
        timeout=settings.GEMINI_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    response_payload = response.json()
    text_payload = (
        response_payload.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text")
    )
    if not text_payload:
        raise ValueError("Gemini no devolvio un cuerpo JSON util para el analisis.")

    parsed_result = AnalisisIncidenteLLMResult.model_validate(json.loads(text_payload))
    normalized_category = _normalize_llm_category(parsed_result.clasificacion_ia)
    normalized_priority = _normalize_llm_priority(parsed_result.prioridad)
    requires_more_info = bool(parsed_result.requiere_mas_info)
    confidence = round(min(max(parsed_result.confianza_clasificacion, 0.0), 1.0), 2)

    preguntas_sugeridas = _normalize_llm_questions(
        parsed_result.preguntas_sugeridas,
        requires_more_info=requires_more_info,
    )
    if requires_more_info and not preguntas_sugeridas:
        preguntas_sugeridas = _suggest_questions(normalized_category, True)

    return AnalisisIncidenteLLMResult(
        clasificacion_ia=normalized_category,
        auxilio_sugerido=_resolve_auxilio_name_for_classification(normalized_category),
        confianza_clasificacion=confidence,
        prioridad=normalized_priority,
        resumen_ia=parsed_result.resumen_ia.strip(),
        requiere_mas_info=requires_more_info,
        preguntas_sugeridas=preguntas_sugeridas,
    )


def _run_gemini_taller_ranking_analysis(
    *,
    incidente,
    candidatos: list[dict],
) -> GeminiTallerRankingResult:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY no configurada.")

    response = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent",
        headers={
            "x-goog-api-key": settings.GEMINI_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "system_instruction": {
                "parts": [
                    {
                        "text": (
                            "Eres un evaluador de talleres candidatos para AutoAssist AI. "
                            "Debes responder estrictamente en JSON valido segun el esquema solicitado."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "parts": [
                        {
                            "text": _build_gemini_taller_ranking_input_payload(
                                incidente=incidente,
                                candidatos=candidatos,
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": _get_gemini_taller_ranking_schema(),
            },
        },
        timeout=settings.GEMINI_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    response_payload = response.json()
    text_payload = (
        response_payload.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text")
    )
    if not text_payload:
        raise ValueError("Gemini no devolvio un ranking JSON util para talleres.")

    return GeminiTallerRankingResult.model_validate(json.loads(text_payload))


def _run_openai_incident_analysis(
    *,
    descripcion_texto: str | None,
    texto_evidencias: list[str],
    latitud: Decimal | None,
    longitud: Decimal | None,
) -> AnalisisIncidenteLLMResult:
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY no configurada.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("La libreria openai no esta instalada.") from exc

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
    )

    response = client.responses.create(
        model=settings.OPENAI_MODEL,
        instructions=(
            "Eres un analizador de incidentes vehiculares para AutoAssist AI. "
            "Debes responder estrictamente en JSON siguiendo el esquema solicitado."
        ),
        input=_build_llm_input_payload(
            descripcion_texto=descripcion_texto,
            texto_evidencias=texto_evidencias,
            latitud=latitud,
            longitud=longitud,
        ),
        text={
            "format": {
                "type": "json_schema",
                "name": "analisis_incidente",
                "strict": True,
                "schema": _get_llm_analysis_schema(),
            }
        },
    )

    parsed_result = AnalisisIncidenteLLMResult.model_validate_json(response.output_text)
    normalized_category = _normalize_llm_category(parsed_result.clasificacion_ia)
    normalized_priority = _normalize_llm_priority(parsed_result.prioridad)
    requires_more_info = bool(parsed_result.requiere_mas_info)
    confidence = round(min(max(parsed_result.confianza_clasificacion, 0.0), 1.0), 2)

    preguntas_sugeridas = _normalize_llm_questions(
        parsed_result.preguntas_sugeridas,
        requires_more_info=requires_more_info,
    )
    if requires_more_info and not preguntas_sugeridas:
        preguntas_sugeridas = _suggest_questions(normalized_category, True)

    return AnalisisIncidenteLLMResult(
        clasificacion_ia=normalized_category,
        auxilio_sugerido=_resolve_auxilio_name_for_classification(normalized_category),
        confianza_clasificacion=confidence,
        prioridad=normalized_priority,
        resumen_ia=parsed_result.resumen_ia.strip(),
        requiere_mas_info=requires_more_info,
        preguntas_sugeridas=preguntas_sugeridas,
    )


def _extract_json_from_text(raw_text: str) -> dict:
    content = raw_text.strip()
    if content.startswith("```"):
        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1]
            if content.lower().startswith("json"):
                content = content[4:]
            content = content.strip()
    return json.loads(content)


def _run_openrouter_incident_analysis(
    *,
    descripcion_texto: str | None,
    texto_evidencias: list[str],
    latitud: Decimal | None,
    longitud: Decimal | None,
) -> AnalisisIncidenteLLMResult:
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY no configurada.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("La libreria openai no esta instalada.") from exc

    client = OpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        timeout=settings.OPENROUTER_TIMEOUT_SECONDS,
        default_headers={
            "HTTP-Referer": settings.OPENROUTER_APP_URL,
            "X-Title": settings.OPENROUTER_APP_NAME,
        },
    )

    completion = client.chat.completions.create(
        model=settings.OPENROUTER_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un analizador de incidentes vehiculares para AutoAssist AI. "
                    "Responde unicamente JSON valido con estas claves exactas: "
                    "clasificacion_ia, confianza_clasificacion, prioridad, resumen_ia, "
                    "requiere_mas_info, preguntas_sugeridas."
                ),
            },
            {
                "role": "user",
                "content": _build_llm_input_payload(
                    descripcion_texto=descripcion_texto,
                    texto_evidencias=texto_evidencias,
                    latitud=latitud,
                    longitud=longitud,
                ),
            },
        ],
    )

    raw_text = completion.choices[0].message.content or "{}"
    parsed_result = AnalisisIncidenteLLMResult.model_validate(
        _extract_json_from_text(raw_text)
    )
    normalized_category = _normalize_llm_category(parsed_result.clasificacion_ia)
    normalized_priority = _normalize_llm_priority(parsed_result.prioridad)
    requires_more_info = bool(parsed_result.requiere_mas_info)
    confidence = round(min(max(parsed_result.confianza_clasificacion, 0.0), 1.0), 2)

    preguntas_sugeridas = _normalize_llm_questions(
        parsed_result.preguntas_sugeridas,
        requires_more_info=requires_more_info,
    )
    if requires_more_info and not preguntas_sugeridas:
        preguntas_sugeridas = _suggest_questions(normalized_category, True)

    return AnalisisIncidenteLLMResult(
        clasificacion_ia=normalized_category,
        auxilio_sugerido=_resolve_auxilio_name_for_classification(normalized_category),
        confianza_clasificacion=confidence,
        prioridad=normalized_priority,
        resumen_ia=parsed_result.resumen_ia.strip(),
        requiere_mas_info=requires_more_info,
        preguntas_sugeridas=preguntas_sugeridas,
    )


def _suggest_questions(category: str, requires_more_info: bool) -> list[str]:
    if not requires_more_info:
        return []
    return QUESTIONS_BY_CATEGORY.get(category, QUESTIONS_BY_CATEGORY[INCIDENTE_INCIERTO])


def _get_questions_for_incident_classification(clasificacion_ia: str | None) -> list[str]:
    normalized_category = _normalize_llm_category(clasificacion_ia)
    if not normalized_category or normalized_category not in QUESTIONS_BY_CATEGORY:
        normalized_category = INCIDENTE_INCIERTO
    return QUESTIONS_BY_CATEGORY[normalized_category]


def _serialize_archivo_url(archivo_url: str | None) -> str | None:
    if not archivo_url:
        return None
    return archivo_url


def _is_audio_evidence(evidencia) -> bool:
    return (evidencia.tipo_evidencia or "").strip().upper() in AUDIO_EVIDENCE_TYPES


def _infer_audio_mime_type(archivo_url: str) -> str:
    path = urlparse(archivo_url).path.lower()
    for extension, mime_type in AUDIO_MIME_TYPES_BY_EXTENSION.items():
        if path.endswith(extension):
            return mime_type
    return "audio/mpeg"


def _read_local_media_file_bytes(archivo_url: str) -> bytes | None:
    parsed = urlparse(archivo_url)
    media_prefix = settings.MEDIA_URL_PREFIX.rstrip("/")
    if not parsed.path.startswith(f"{media_prefix}/"):
        return None

    relative_media_path = parsed.path.removeprefix(f"{media_prefix}/").lstrip("/")
    target_path = Path(settings.MEDIA_ROOT) / relative_media_path
    if not target_path.exists() or not target_path.is_file():
        return None
    return target_path.read_bytes()


def _extract_text_from_gemini_response(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = (part.get("text") or "").strip()
            if text:
                return text
    return ""


def _run_gemini_audio_transcription(*, archivo_url: str) -> str:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY no configurada.")

    mime_type = _infer_audio_mime_type(archivo_url)
    local_audio_bytes = _read_local_media_file_bytes(archivo_url)
    if local_audio_bytes is not None:
        audio_bytes = local_audio_bytes
    else:
        audio_response = httpx.get(archivo_url, timeout=settings.GEMINI_TIMEOUT_SECONDS)
        audio_response.raise_for_status()
        audio_bytes = audio_response.content

    inline_audio = b64encode(audio_bytes).decode("ascii")

    response = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent",
        headers={
            "x-goog-api-key": settings.GEMINI_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Transcribe el audio del incidente vehicular de forma literal y breve. "
                                "Devuelve solo la transcripcion en texto plano, sin markdown ni etiquetas."
                            )
                        },
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": inline_audio,
                            }
                        },
                    ]
                }
            ]
        },
        timeout=settings.GEMINI_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    transcript = _extract_text_from_gemini_response(response.json()).strip()
    if not transcript:
        raise ValueError("Gemini no devolvio una transcripcion util para el audio.")
    return transcript


def _to_evidencia_procesada_response(
    evidencia,
    *,
    mensaje: str | None = None,
) -> EvidenciaProcesadaResponse:
    return EvidenciaProcesadaResponse(
        id_evidencia=evidencia.id_evidencia,
        id_incidente=evidencia.id_incidente,
        tipo_evidencia=evidencia.tipo_evidencia,
        archivo_url=_serialize_archivo_url(evidencia.archivo_url),
        texto_extraido=evidencia.texto_extraido,
        descripcion=evidencia.descripcion,
        mensaje=mensaje,
    )


def _normalize_evidence_type(tipo_evidencia: str) -> str:
    normalized_type = tipo_evidencia.strip().upper()
    if normalized_type not in ALLOWED_EVIDENCE_TYPES:
        raise ValueError(
            "tipo_evidencia no permitido. Use TEXTO, AUDIO_TRANSCRITO o IMAGEN_ANALIZADA."
        )
    return normalized_type


def _resolve_image_evidence_for_analysis(
    db: Session,
    *,
    id_incidente: int,
    payload: AnalizarImagenIncidenteRequest,
):
    if payload.id_evidencia is not None:
        evidencia = get_evidencia_by_id_and_incidente_id(
            db,
            id_incidente=id_incidente,
            id_evidencia=payload.id_evidencia,
        )
        if not evidencia or not _is_image_evidence(evidencia):
            raise ImageEvidenceNotFoundError(
                "La evidencia especificada no existe o no corresponde a una imagen valida del incidente."
            )
        return evidencia, _serialize_archivo_url(evidencia.archivo_url)

    if payload.archivo_url and payload.archivo_url.strip():
        return None, payload.archivo_url.strip()

    evidencia = get_latest_image_evidence_by_incidente_id(db, id_incidente)
    if not evidencia:
        raise ImageEvidenceNotFoundError(
            "El incidente no cuenta con una evidencia de imagen disponible para analizar con Roboflow."
        )
    return evidencia, _serialize_archivo_url(evidencia.archivo_url)


def _normalize_service_name(value: str | None) -> str:
    if not value:
        return ""
    return _normalize_text(value)


def _resolve_auxilio_name_for_classification(clasificacion_ia: str | None) -> str | None:
    normalized_category = _normalize_llm_category(clasificacion_ia)
    return CATEGORY_TO_AUXILIO.get(normalized_category)


def _resolve_auxilio_name_for_incidente(incidente) -> str | None:
    if incidente.tipo_incidente and incidente.tipo_incidente.nombre:
        tipo_incidente_nombre = incidente.tipo_incidente.nombre.strip().upper()
        incident_type_to_auxilio = {
            "BATERIA_DESCARGADA": AUXILIO_ELECTRICO,
            "PINCHAZO_LLANTA": AUXILIO_LLANTA,
            "SIN_COMBUSTIBLE": AUXILIO_COMBUSTIBLE,
            "LLAVES_DENTRO": AUXILIO_APERTURA,
            "FALLA_MECANICA": AUXILIO_MECANICO,
            "SOBRECALENTAMIENTO": AUXILIO_MECANICO,
            "ACCIDENTE_MENOR": AUXILIO_REMOLQUE,
        }
        auxilio = incident_type_to_auxilio.get(tipo_incidente_nombre)
        if auxilio:
            return auxilio
    return _resolve_auxilio_name_for_classification(incidente.clasificacion_ia)


def _haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    radius_km = 6371.0
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    a = (
        sin(delta_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(delta_lon / 2) ** 2
    )
    c = 2 * asin(sqrt(a))
    return radius_km * c


def _calculate_distance_score(distance_km: float, coverage_km: float) -> float:
    if distance_km <= 2:
        return 10.0
    if distance_km <= 5:
        return 8.0
    if distance_km <= 10:
        return 5.0
    if distance_km <= coverage_km:
        return 3.0
    return 0.0


def _get_incident_datetime(incidente) -> datetime:
    incident_dt = incidente.fecha_reporte or datetime.utcnow()
    if incident_dt.tzinfo is None:
        incident_dt = incident_dt.replace(tzinfo=ZoneInfo("UTC"))
    return incident_dt.astimezone(AUTOASSIST_LOCAL_TZ)


def _is_taller_schedule_compatible(taller, incidente) -> bool:
    if not taller.horarios_disponibilidad:
        return True

    incident_dt = _get_incident_datetime(incidente)
    day_mapping = {
        "MONDAY": "LUNES",
        "TUESDAY": "MARTES",
        "WEDNESDAY": "MIERCOLES",
        "THURSDAY": "JUEVES",
        "FRIDAY": "VIERNES",
        "SATURDAY": "SABADO",
        "SUNDAY": "DOMINGO",
    }
    dia_semana = day_mapping.get(incident_dt.strftime("%A").upper(), "")
    hora_incidente = incident_dt.time()

    active_horarios = [horario for horario in taller.horarios_disponibilidad if horario.estado]
    if not active_horarios:
        return True

    for horario in active_horarios:
        if horario.dia_semana.strip().upper() != dia_semana:
            continue
        if horario.hora_inicio <= hora_incidente <= horario.hora_fin:
            return True
    return False


def _has_available_tecnico(taller) -> bool:
    return any(tecnico.estado and tecnico.disponible for tecnico in taller.tecnicos)


def _has_available_unidad_movil(taller) -> bool:
    return any(
        unidad_movil.estado and unidad_movil.disponible
        for unidad_movil in taller.unidades_moviles
    )


def _is_vehicle_type_compatible(taller, id_tipo_vehiculo: int) -> bool:
    return any(
        taller_tipo_vehiculo.id_tipo_vehiculo == id_tipo_vehiculo
        for taller_tipo_vehiculo in taller.talleres_tipo_vehiculo
    )


def _get_feasible_auxilio_for_incidente(
    taller,
    *,
    incidente,
    unidad_movil_disponible: bool,
):
    expected_auxilio_name = _resolve_auxilio_name_for_incidente(incidente)
    if not expected_auxilio_name:
        raise IncidentClassificationInsufficientError(
            "La clasificacion del incidente no es suficiente para resolver el auxilio requerido."
        )
    compatible_services = []
    for taller_auxilio in taller.talleres_auxilio:
        tipo_auxilio = taller_auxilio.tipo_auxilio
        if not tipo_auxilio or not tipo_auxilio.estado or not taller_auxilio.disponible:
            continue

        service_name = _normalize_service_name(tipo_auxilio.nombre)
        if service_name == _normalize_service_name(expected_auxilio_name):
            compatible_services.append(taller_auxilio)

    if not compatible_services:
        return None

    feasible_services = [
        service
        for service in compatible_services
        if not service.tipo_auxilio.requiere_unidad_movil or unidad_movil_disponible
    ]
    if not feasible_services:
        return None

    return feasible_services[0]


def _validate_incidente_for_intelligent_assignment(incidente) -> None:
    if not incidente:
        raise IncidentNotFoundError("Incidente no encontrado.")
    if incidente.clasificacion_ia is None:
        raise IncidentNotAnalyzedError(
            "El incidente debe ser analizado primero por CU25."
        )
    if incidente.requiere_mas_info:
        raise IncidentDoesNotRequireMoreInformationError(
            "El incidente aun requiere mas informacion para asignar taller."
        )
    if _normalize_llm_category(incidente.clasificacion_ia) == INCIDENTE_INCIERTO:
        raise IncidentClassificationInsufficientError(
            "La clasificacion del incidente no es suficiente para asignar taller."
        )
    if incidente.latitud is None or incidente.longitud is None:
        raise IncidentLocationInvalidError(
            "El incidente no tiene ubicacion valida para asignar taller."
        )
    if incidente.vehiculo is None or incidente.vehiculo.id_tipo_vehiculo is None:
        raise IncidentVehicleNotFoundError(
            "El incidente no tiene un vehiculo asociado valido."
        )
    if (
        incidente.estado_servicio_actual
        and incidente.estado_servicio_actual.nombre in ESTADOS_INCIDENTE_NO_APTOS_PARA_ASIGNACION
    ):
        raise ValueError("El incidente no se encuentra en un estado apto para asignacion.")
    if incidente.asignacion_servicio is not None:
        raise ValueError("El incidente ya tiene una asignacion operativa registrada.")


def _build_taller_candidate_response(
    *,
    taller,
    distancia_km: float,
    puntaje_asignacion: float,
    taller_disponible: bool,
    tecnico_disponible: bool,
    unidad_movil_disponible: bool,
    estado_solicitud: str,
    justificacion_ranking: str | None = None,
) -> TallerCandidatoResponse:
    return TallerCandidatoResponse(
        id_taller=taller.id_taller,
        nombre_taller=taller.nombre_taller,
        distancia_km=round(distancia_km, 2),
        puntaje_asignacion=round(puntaje_asignacion, 2),
        compatible_servicio=True,
        compatible_tipo_vehiculo=True,
        taller_disponible=taller_disponible,
        tecnico_disponible=tecnico_disponible,
        unidad_movil_disponible=unidad_movil_disponible,
        estado_solicitud=estado_solicitud,
        justificacion_ranking=justificacion_ranking,
    )


def _seconds_between(start, end) -> int | None:
    if start is None or end is None:
        return None
    return max(int((end - start).total_seconds()), 0)


def _find_first_estado_timestamp(incidente, estado_nombre: str):
    matching_dates = [
        historial.fecha_hora
        for historial in incidente.historial
        if historial.estado_nuevo and historial.estado_nuevo.nombre == estado_nombre
    ]
    if not matching_dates:
        return None
    return min(matching_dates)


def _resolve_estado_frecuente(incidente) -> str | None:
    state_names = [
        historial.estado_nuevo.nombre
        for historial in incidente.historial
        if historial.estado_nuevo and historial.estado_nuevo.nombre
    ]
    if incidente.estado_servicio_actual and incidente.estado_servicio_actual.nombre:
        state_names.append(incidente.estado_servicio_actual.nombre)
    if not state_names:
        return None
    return Counter(state_names).most_common(1)[0][0]


def _resolve_incidentes_atendidos(incidente, tiempo_llegada_seg: int | None) -> int:
    if tiempo_llegada_seg is not None:
        return 1
    estado_actual = (
        incidente.estado_servicio_actual.nombre
        if incidente.estado_servicio_actual
        else ""
    )
    return 1 if estado_actual in {"EN_ATENCION", "FINALIZADO"} else 0


def _resolve_rendimiento_operativo(
    *,
    tiempo_asignacion_seg: int | None,
    tiempo_llegada_seg: int | None,
    tiempo_resolucion_seg: int | None,
    incidentes_atendidos: int,
) -> str:
    if tiempo_resolucion_seg is not None:
        if tiempo_resolucion_seg <= 3600:
            return "alto"
        if tiempo_resolucion_seg <= 7200:
            return "medio"
        return "bajo"
    if tiempo_llegada_seg is not None:
        if tiempo_llegada_seg <= 1800:
            return "alto"
        if tiempo_llegada_seg <= 3600:
            return "medio"
        return "bajo"
    if tiempo_asignacion_seg is not None:
        if tiempo_asignacion_seg <= 600:
            return "alto"
        if tiempo_asignacion_seg <= 1800:
            return "medio"
        return "bajo"
    if incidentes_atendidos:
        return "medio"
    return "sin_datos"


def _build_metric_snapshot(db: Session, incidente):
    metrica_existente = get_metrica_incidente_by_incidente_id(db, incidente.id_incidente)
    asignacion = incidente.asignacion_servicio

    tiempo_asignacion_seg = (
        metrica_existente.tiempo_asignacion_seg
        if metrica_existente and metrica_existente.tiempo_asignacion_seg is not None
        else _seconds_between(
            incidente.fecha_reporte,
            asignacion.fecha_asignacion if asignacion else None,
        )
    )

    tiempo_llegada_seg = (
        metrica_existente.tiempo_llegada_seg
        if metrica_existente and metrica_existente.tiempo_llegada_seg is not None
        else _seconds_between(
            asignacion.fecha_asignacion if asignacion else None,
            _find_first_estado_timestamp(incidente, "EN_ATENCION"),
        )
    )

    tiempo_resolucion_seg = (
        metrica_existente.tiempo_resolucion_seg
        if metrica_existente and metrica_existente.tiempo_resolucion_seg is not None
        else _seconds_between(
            incidente.fecha_reporte,
            _find_first_estado_timestamp(incidente, "FINALIZADO"),
        )
    )

    rechazos_calculados = sum(
        1
        for solicitud in incidente.solicitudes_taller
        if solicitud.estado_solicitud == "RECHAZADA"
    )
    cantidad_rechazos = max(
        rechazos_calculados,
        metrica_existente.cantidad_rechazos if metrica_existente else 0,
    )

    talleres_involucrados = {
        solicitud.id_taller
        for solicitud in incidente.solicitudes_taller
        if solicitud.id_taller is not None
    }
    fue_reasignado = bool(
        (metrica_existente.fue_reasignado if metrica_existente else False)
        or cantidad_rechazos > 0
        or len(talleres_involucrados) > 1
    )

    estado_frecuente = _resolve_estado_frecuente(incidente)
    incidentes_atendidos = _resolve_incidentes_atendidos(
        incidente,
        tiempo_llegada_seg,
    )
    rendimiento_operativo = _resolve_rendimiento_operativo(
        tiempo_asignacion_seg=tiempo_asignacion_seg,
        tiempo_llegada_seg=tiempo_llegada_seg,
        tiempo_resolucion_seg=tiempo_resolucion_seg,
        incidentes_atendidos=incidentes_atendidos,
    )

    metrica = upsert_metrica_incidente(
        db,
        incidente=incidente,
        tiempo_asignacion_seg=tiempo_asignacion_seg,
        tiempo_llegada_seg=tiempo_llegada_seg,
        tiempo_resolucion_seg=tiempo_resolucion_seg,
        cantidad_rechazos=cantidad_rechazos,
        fue_reasignado=fue_reasignado,
    )

    return {
        "metrica": metrica,
        "tiempo_respuesta_seg": tiempo_asignacion_seg,
        "incidentes_atendidos": incidentes_atendidos,
        "estado_frecuente": estado_frecuente,
        "rendimiento_operativo": rendimiento_operativo,
    }


def _to_metrica_incidente_list_response(
    incidente,
    snapshot: dict,
) -> MetricaIncidenteListResponse:
    return MetricaIncidenteListResponse(
        id_incidente=incidente.id_incidente,
        titulo=incidente.titulo,
        fecha_reporte=incidente.fecha_reporte,
        estado_actual=(
            incidente.estado_servicio_actual.nombre
            if incidente.estado_servicio_actual
            else "SIN_ESTADO"
        ),
        tiempo_respuesta_seg=snapshot["tiempo_respuesta_seg"],
        incidentes_atendidos=snapshot["incidentes_atendidos"],
        estado_frecuente=snapshot["estado_frecuente"],
        rendimiento_operativo=snapshot["rendimiento_operativo"],
        fecha_generacion=snapshot["metrica"].fecha_registro,
    )


def _to_metrica_incidente_detail_response(
    incidente,
    snapshot: dict,
) -> MetricaIncidenteDetailResponse:
    metrica = snapshot["metrica"]
    return MetricaIncidenteDetailResponse(
        id_incidente=incidente.id_incidente,
        titulo=incidente.titulo,
        fecha_reporte=incidente.fecha_reporte,
        estado_actual=(
            incidente.estado_servicio_actual.nombre
            if incidente.estado_servicio_actual
            else "SIN_ESTADO"
        ),
        tiempo_respuesta_seg=snapshot["tiempo_respuesta_seg"],
        incidentes_atendidos=snapshot["incidentes_atendidos"],
        estado_frecuente=snapshot["estado_frecuente"],
        rendimiento_operativo=snapshot["rendimiento_operativo"],
        fecha_generacion=metrica.fecha_registro,
        clasificacion_ia=incidente.clasificacion_ia,
        prioridad=incidente.prioridad.nombre if incidente.prioridad else None,
        tipo_incidente=incidente.tipo_incidente.nombre if incidente.tipo_incidente else None,
        tiempo_asignacion_seg=metrica.tiempo_asignacion_seg,
        tiempo_llegada_seg=metrica.tiempo_llegada_seg,
        tiempo_resolucion_seg=metrica.tiempo_resolucion_seg,
        cantidad_rechazos=metrica.cantidad_rechazos,
        fue_reasignado=metrica.fue_reasignado,
    )


def _run_rule_based_incident_analysis(
    *,
    id_incidente: int | None,
    descripcion_texto: str | None,
    texto_evidencias: list[str],
    latitud: Decimal | None,
    longitud: Decimal | None,
    fuente_analisis: str = "reglas",
    modelo_analisis: str | None = None,
    fallback_usado: bool = False,
) -> AnalisisIncidenteResponse:
    category, confidence, matches_by_category, text_parts = _classify_incident(
        descripcion_texto,
        texto_evidencias,
    )
    priority = _estimate_priority(category)
    requires_more_info = _requires_more_information(
        category=category,
        confidence=confidence,
        text_parts=text_parts,
    )

    summary = _build_summary(
        category=category,
        priority=priority,
        confidence=confidence,
        requires_more_info=requires_more_info,
        matches_by_category=matches_by_category,
        evidence_count=len(texto_evidencias),
        has_location=latitud is not None and longitud is not None,
    )
    suggested_questions = _suggest_questions(category, requires_more_info)

    return AnalisisIncidenteResponse(
        id_incidente=id_incidente,
        clasificacion_ia=category,
        auxilio_sugerido=_resolve_auxilio_name_for_classification(category),
        confianza_clasificacion=confidence,
        prioridad=priority,
        resumen_ia=summary,
        requiere_mas_info=requires_more_info,
        preguntas_sugeridas=suggested_questions,
        fuente_analisis=fuente_analisis,
        modelo_analisis=modelo_analisis,
        fallback_usado=fallback_usado,
    )


def _run_incident_analysis(
    *,
    id_incidente: int | None,
    descripcion_texto: str | None,
    texto_evidencias: list[str],
    latitud: Decimal | None,
    longitud: Decimal | None,
) -> AnalisisIncidenteResponse:
    cleaned_text_parts = _clean_texts([descripcion_texto, *texto_evidencias])
    has_location = latitud is not None and longitud is not None

    provider = settings.AI_PROVIDER.strip().lower()
    attempted_provider = None
    attempted_model = None
    fallback_used = False

    try:
        if provider == "openrouter" and settings.OPENROUTER_API_KEY:
            attempted_provider = "openrouter"
            attempted_model = settings.OPENROUTER_MODEL
            llm_result = _run_openrouter_incident_analysis(
                descripcion_texto=descripcion_texto,
                texto_evidencias=texto_evidencias,
                latitud=latitud,
                longitud=longitud,
            )
        elif provider == "gemini" and settings.GEMINI_API_KEY:
            attempted_provider = "gemini"
            attempted_model = settings.GEMINI_MODEL
            llm_result = _run_gemini_incident_analysis(
                descripcion_texto=descripcion_texto,
                texto_evidencias=texto_evidencias,
                latitud=latitud,
                longitud=longitud,
            )
        elif provider == "openai" and settings.OPENAI_API_KEY:
            attempted_provider = "openai"
            attempted_model = settings.OPENAI_MODEL
            llm_result = _run_openai_incident_analysis(
                descripcion_texto=descripcion_texto,
                texto_evidencias=texto_evidencias,
                latitud=latitud,
                longitud=longitud,
            )
        else:
            llm_result = None
    except Exception:
        if not settings.AI_USE_FALLBACK:
            raise
        fallback_used = attempted_provider is not None
        llm_result = None

    if llm_result is not None:
        normalized_category = _normalize_llm_category(llm_result.clasificacion_ia)
        requires_more_info = bool(llm_result.requiere_mas_info)
        confidence_value = float(llm_result.confianza_clasificacion)
        if normalized_category != INCIDENTE_INCIERTO:
            if confidence_value >= 0.60 and has_location and cleaned_text_parts:
                requires_more_info = False
        else:
            requires_more_info = True

        return AnalisisIncidenteResponse(
            id_incidente=id_incidente,
            clasificacion_ia=llm_result.clasificacion_ia,
            auxilio_sugerido=llm_result.auxilio_sugerido,
            confianza_clasificacion=llm_result.confianza_clasificacion,
            prioridad=llm_result.prioridad,
            resumen_ia=llm_result.resumen_ia,
            requiere_mas_info=requires_more_info,
            preguntas_sugeridas=llm_result.preguntas_sugeridas,
            fuente_analisis=attempted_provider or "reglas",
            modelo_analisis=attempted_model,
            fallback_usado=False,
        )

    return _run_rule_based_incident_analysis(
        id_incidente=id_incidente,
        descripcion_texto=descripcion_texto,
        texto_evidencias=texto_evidencias,
        latitud=latitud,
        longitud=longitud,
        fuente_analisis="reglas",
        modelo_analisis=attempted_model if fallback_used else None,
        fallback_usado=fallback_used,
    )


def analizar_incidente_manual_service(
    payload: AnalisisIncidenteManualRequest,
) -> AnalisisIncidenteResponse:
    return _run_incident_analysis(
        id_incidente=None,
        descripcion_texto=payload.descripcion_texto,
        texto_evidencias=_clean_texts(payload.texto_evidencias),
        latitud=payload.latitud,
        longitud=payload.longitud,
    )


def analizar_incidente_por_id_service(
    db: Session,
    id_incidente: int,
) -> AnalisisIncidenteResponse:
    incidente = get_incidente_by_id(db, id_incidente)
    if not incidente:
        raise IncidentNotFoundError("El incidente especificado no existe.")

    evidencia_textos = get_evidencia_textos_by_incidente_id(db, id_incidente)
    if not _clean_texts([incidente.descripcion_texto, *evidencia_textos]):
        raise ValueError(
            "El incidente no cuenta con descripcion_texto ni texto_extraido suficiente para analizar."
        )

    try:
        analysis = _run_incident_analysis(
            id_incidente=incidente.id_incidente,
            descripcion_texto=incidente.descripcion_texto,
            texto_evidencias=evidencia_textos,
            latitud=incidente.latitud,
            longitud=incidente.longitud,
        )
        prioridad = get_prioridad_by_nombre(db, analysis.prioridad)
        tipo_incidente = None
        if analysis.clasificacion_ia in INCIDENT_TYPE_BY_CATEGORY:
            tipo_incidente = get_tipo_incidente_by_nombre(
                db,
                INCIDENT_TYPE_BY_CATEGORY[analysis.clasificacion_ia],
            )
        update_incidente_analysis_result(
            db,
            incidente,
            clasificacion_ia=analysis.clasificacion_ia,
            confianza_clasificacion=analysis.confianza_clasificacion,
            resumen_ia=analysis.resumen_ia,
            requiere_mas_info=analysis.requiere_mas_info,
            id_prioridad=prioridad.id_prioridad if prioridad else None,
            id_tipo_incidente=(
                tipo_incidente.id_tipo_incidente if tipo_incidente else None
            ),
        )
        db.commit()
        return analysis
    except Exception:
        db.rollback()
        raise


def solicitar_mas_informacion_incidente_service(
    db: Session,
    id_incidente: int,
) -> SolicitudMasInformacionResponse:
    incidente = get_incidente_by_id(db, id_incidente)
    if not incidente:
        raise IncidentNotFoundError("Incidente no encontrado.")

    if not incidente.requiere_mas_info:
        raise IncidentDoesNotRequireMoreInformationError(
            "El incidente ya cuenta con informacion suficiente."
        )

    cliente = get_cliente_by_id(db, incidente.id_cliente)
    if not cliente:
        raise IncidentClientNotFoundError(
            "No existe cliente asociado al incidente."
        )

    usuario = get_usuario_by_id(db, cliente.id_usuario)
    if not usuario:
        raise IncidentUserNotFoundError(
            "No existe usuario asociado al incidente."
        )

    preguntas_sugeridas = _get_questions_for_incident_classification(
        incidente.clasificacion_ia
    )
    mensaje_base = (
        "Se requiere informacion adicional para analizar correctamente el incidente."
    )
    mensaje_notificacion = (
        mensaje_base
        + " Preguntas sugeridas: "
        + " ".join(preguntas_sugeridas)
    )

    existing_notification = get_pending_notification_by_incidente_usuario_tipo(
        db,
        id_incidente=incidente.id_incidente,
        id_usuario=usuario.id_usuario,
        tipo_notificacion="SOLICITUD_MAS_INFORMACION",
    )
    if existing_notification:
        return SolicitudMasInformacionResponse(
            id_incidente=incidente.id_incidente,
            id_usuario_destino=usuario.id_usuario,
            solicitud_emitida=False,
            mensaje=(
                "Ya existe una solicitud pendiente de mas informacion para este incidente."
            ),
            preguntas_sugeridas=preguntas_sugeridas,
            id_notificacion=existing_notification.id_notificacion,
        )

    try:
        notification = create_notification(
            db,
            id_usuario=usuario.id_usuario,
            id_incidente=incidente.id_incidente,
            titulo="Solicitud de mas informacion del incidente",
            mensaje=mensaje_notificacion,
            tipo_notificacion="SOLICITUD_MAS_INFORMACION",
        )
        dispatch_push_notification_service(db, notification)
        db.commit()
        return SolicitudMasInformacionResponse(
            id_incidente=incidente.id_incidente,
            id_usuario_destino=usuario.id_usuario,
            solicitud_emitida=True,
            mensaje=mensaje_base,
            preguntas_sugeridas=preguntas_sugeridas,
            id_notificacion=notification.id_notificacion,
        )
    except Exception:
        db.rollback()
        raise


def analizar_imagen_incidente_roboflow_service(
    db: Session,
    id_incidente: int,
    payload: AnalizarImagenIncidenteRequest,
) -> AnalisisImagenRoboflowResponse:
    incidente = get_incidente_by_id(db, id_incidente)
    if not incidente:
        raise IncidentNotFoundError("Incidente no encontrado.")

    evidencia_origen, archivo_url = _resolve_image_evidence_for_analysis(
        db,
        id_incidente=id_incidente,
        payload=payload,
    )
    if not archivo_url:
        raise ImageEvidenceNotFoundError(
            "No se encontro una URL valida de imagen para analizar."
        )

    try:
        (
            task_type,
            top_label,
            confidence,
            categoria_sugerida,
            visual_parts,
        ) = _run_roboflow_image_analysis(image_url=archivo_url)
        resumen_visual = visual_parts[0]
        detecciones = visual_parts[1:]
        descripcion = payload.descripcion.strip() if payload.descripcion else None
        if descripcion:
            texto_extraido = f"{resumen_visual} Contexto adicional: {descripcion}."
        else:
            texto_extraido = resumen_visual

        evidencia_procesada = create_processed_evidence(
            db,
            id_incidente=incidente.id_incidente,
            tipo_evidencia="IMAGEN_ANALIZADA",
            archivo_url=archivo_url,
            texto_extraido=texto_extraido,
            descripcion=(
                descripcion
                or f"Analisis visual generado por Roboflow desde evidencia de imagen del incidente."
            ),
        )
        db.commit()
        return AnalisisImagenRoboflowResponse(
            id_incidente=incidente.id_incidente,
            id_evidencia_origen=evidencia_origen.id_evidencia if evidencia_origen else None,
            id_evidencia_procesada=evidencia_procesada.id_evidencia,
            archivo_url=archivo_url,
            proveedor="roboflow",
            tipo_modelo=task_type,
            modelo=settings.ROBOFLOW_MODEL_ID or "",
            clase_principal=top_label,
            confianza=confidence,
            categoria_sugerida=categoria_sugerida,
            resumen_visual=resumen_visual,
            detecciones=detecciones,
            mensaje=(
                "Analisis visual generado correctamente. "
                "Se recomienda volver a ejecutar CU25 para reanalizar el incidente con esta nueva evidencia."
            ),
        )
    except Exception:
        db.rollback()
        raise


def registrar_evidencia_procesada_service(
    db: Session,
    id_incidente: int,
    payload: RegistrarEvidenciaProcesadaRequest,
) -> EvidenciaProcesadaResponse:
    incidente = get_incidente_by_id(db, id_incidente)
    if not incidente:
        raise IncidentNotFoundError("Incidente no encontrado.")

    texto_extraido = payload.texto_extraido.strip()
    if not texto_extraido:
        raise ValueError("texto_extraido no puede estar vacio.")

    tipo_evidencia = _normalize_evidence_type(payload.tipo_evidencia)
    archivo_url = (payload.archivo_url or "").strip()
    descripcion = payload.descripcion.strip() if payload.descripcion else None

    try:
        evidencia = create_processed_evidence(
            db,
            id_incidente=incidente.id_incidente,
            tipo_evidencia=tipo_evidencia,
            archivo_url=archivo_url,
            texto_extraido=texto_extraido,
            descripcion=descripcion,
        )
        db.commit()
        return _to_evidencia_procesada_response(
            evidencia,
            mensaje=(
                "Evidencia procesada registrada correctamente. "
                "Se recomienda volver a ejecutar CU25 para reanalizar el incidente."
            ),
        )
    except Exception:
        db.rollback()
        raise


def listar_evidencias_procesadas_incidente_service(
    db: Session,
    id_incidente: int,
) -> list[EvidenciaProcesadaResponse]:
    incidente = get_incidente_by_id(db, id_incidente)
    if not incidente:
        raise IncidentNotFoundError("Incidente no encontrado.")

    evidencias = list_evidences_by_incidente_id(db, id_incidente)
    return [
        _to_evidencia_procesada_response(evidencia)
        for evidencia in evidencias
    ]


def transcribir_evidencias_audio_incidente_service(
    db: Session,
    id_incidente: int,
) -> list[EvidenciaProcesadaResponse]:
    incidente = get_incidente_by_id(db, id_incidente)
    if not incidente:
        raise IncidentNotFoundError("Incidente no encontrado.")

    evidencias = list_evidences_by_incidente_id(db, id_incidente)
    actualizadas = []
    try:
        for evidencia in evidencias:
            if not _is_audio_evidence(evidencia):
                continue
            if evidencia.texto_extraido and evidencia.texto_extraido.strip():
                actualizadas.append(evidencia)
                continue
            transcript = _run_gemini_audio_transcription(
                archivo_url=_serialize_archivo_url(evidencia.archivo_url) or ""
            )
            actualizadas.append(
                update_evidencia_texto_extraido(
                    db,
                    evidencia,
                    texto_extraido=transcript,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return [
        _to_evidencia_procesada_response(
            evidencia,
            mensaje="Audio transcrito automaticamente con Gemini.",
        )
        for evidencia in actualizadas
    ]


def transcribir_audio_desde_url_service(archivo_url: str) -> str:
    normalized_url = _serialize_archivo_url(archivo_url)
    if not normalized_url:
        raise ValueError("archivo_url es obligatoria para transcribir el audio.")
    return _run_gemini_audio_transcription(archivo_url=normalized_url)


def orquestar_incidente_reportado_service(
    db: Session,
    id_incidente: int,
) -> dict:
    evidencias_audio = list_evidences_by_incidente_id(db, id_incidente)
    if any(_is_audio_evidence(evidencia) for evidencia in evidencias_audio):
        try:
            transcribir_evidencias_audio_incidente_service(db, id_incidente)
        except Exception:
            if not settings.AI_USE_FALLBACK:
                raise

    analysis = analizar_incidente_por_id_service(db, id_incidente)
    result = {
        "analisis_ejecutado": True,
        "requiere_mas_info": analysis.requiere_mas_info,
        "clasificacion_ia": analysis.clasificacion_ia,
        "solicitudes_generadas": 0,
    }

    if analysis.requiere_mas_info:
        return result

    try:
        asignacion = asignar_taller_inteligentemente_service(db, id_incidente)
        result["solicitudes_generadas"] = asignacion.total_candidatos
        result["estado_orquestacion"] = "BUSCANDO_TALLER"
    except NoCandidateTallerFoundError:
        result["estado_orquestacion"] = "SIN_CANDIDATOS"
    return result


def asignar_taller_inteligentemente_service(
    db: Session,
    id_incidente: int,
) -> AsignacionInteligenteResponse:
    incidente = get_incidente_with_assignment_context(db, id_incidente)
    _validate_incidente_for_intelligent_assignment(incidente)

    incident_lat = float(incidente.latitud)
    incident_lon = float(incidente.longitud)
    vehicle_type_id = incidente.vehiculo.id_tipo_vehiculo

    talleres = list_available_talleres_with_resources(db)
    candidate_entries: list[dict] = []
    fuente_evaluacion = "reglas"
    modelo_evaluacion = None
    fallback_usado = False
    justificacion_global = None

    for taller in talleres:
        if taller.latitud is None or taller.longitud is None or taller.radio_cobertura_km is None:
            continue

        taller_activo = bool(taller.usuario and taller.usuario.estado)
        taller_disponible = bool(taller.disponible)
        tecnico_disponible = _has_available_tecnico(taller)
        unidad_movil_disponible = _has_available_unidad_movil(taller)
        compatible_tipo_vehiculo = _is_vehicle_type_compatible(taller, vehicle_type_id)
        horario_compatible = _is_taller_schedule_compatible(taller, incidente)

        if (
            not taller_activo
            or not taller_disponible
            or not compatible_tipo_vehiculo
        ):
            continue

        auxilio_compatible = _get_feasible_auxilio_for_incidente(
            taller,
            incidente=incidente,
            unidad_movil_disponible=unidad_movil_disponible,
        )
        if auxilio_compatible is None:
            continue

        distance_km = _haversine_distance_km(
            incident_lat,
            incident_lon,
            float(taller.latitud),
            float(taller.longitud),
        )
        coverage_km = float(taller.radio_cobertura_km)
        if distance_km > coverage_km:
            continue

        distance_score = _calculate_distance_score(distance_km, coverage_km)
        unit_score = 10.0 if (
            unidad_movil_disponible or not auxilio_compatible.tipo_auxilio.requiere_unidad_movil
        ) else 0.0
        tecnico_score = 20.0 if tecnico_disponible else 0.0
        horario_score = 10.0 if horario_compatible else 0.0
        total_score = 35.0 + tecnico_score + 15.0 + horario_score + unit_score + distance_score

        existing_solicitud = get_solicitud_taller_by_incidente_and_taller(
            db,
            id_incidente=incidente.id_incidente,
            id_taller=taller.id_taller,
        )
        if existing_solicitud and existing_solicitud.estado_solicitud in ESTADOS_SOLICITUD_EXCLUIDOS:
            continue

        candidate_entries.append(
            {
                "taller": taller,
                "distancia_km": round(distance_km, 2),
                "puntaje_base": round(total_score, 2),
                "puntaje_final": round(total_score, 2),
                "taller_disponible": taller_disponible,
                "tecnico_disponible": tecnico_disponible,
                "unidad_movil_disponible": unidad_movil_disponible,
                "existing_solicitud": existing_solicitud,
                "estado_solicitud": (
                    existing_solicitud.estado_solicitud
                    if existing_solicitud
                    else ESTADO_SOLICITUD_INTELIGENTE
                ),
                "servicio_compatible": (
                    auxilio_compatible.tipo_auxilio.nombre
                    if auxilio_compatible and auxilio_compatible.tipo_auxilio
                    else None
                ),
                "requiere_unidad_movil": bool(
                    auxilio_compatible.tipo_auxilio.requiere_unidad_movil
                ),
                "justificacion_ranking": None,
            }
        )

    if not candidate_entries:
        db.rollback()
        raise NoCandidateTallerFoundError(
            "No existen talleres disponibles y compatibles para atender el incidente."
        )

    if settings.AI_PROVIDER.strip().lower() == "gemini" and settings.GEMINI_API_KEY:
        try:
            ranking_result = _run_gemini_taller_ranking_analysis(
                incidente=incidente,
                candidatos=[
                    {
                        "id_taller": entry["taller"].id_taller,
                        "nombre_taller": entry["taller"].nombre_taller,
                        "distancia_km": entry["distancia_km"],
                        "puntaje_base": entry["puntaje_base"],
                        "servicio_compatible": entry["servicio_compatible"],
                        "tipo_vehiculo_compatible": True,
                        "taller_disponible": entry["taller_disponible"],
                        "tecnico_disponible": entry["tecnico_disponible"],
                        "unidad_movil_disponible": entry["unidad_movil_disponible"],
                        "requiere_unidad_movil": entry["requiere_unidad_movil"],
                    }
                    for entry in candidate_entries
                ],
            )
            rank_map = {
                candidate.id_taller: candidate
                for candidate in ranking_result.candidatos
            }
            for entry in candidate_entries:
                llm_candidate = rank_map.get(entry["taller"].id_taller)
                if llm_candidate is None:
                    continue
                adjusted_score = entry["puntaje_base"] + llm_candidate.ajuste_puntaje
                entry["puntaje_final"] = round(min(max(adjusted_score, 0.0), 100.0), 2)
                entry["justificacion_ranking"] = llm_candidate.justificacion.strip()

            fuente_evaluacion = "gemini"
            modelo_evaluacion = settings.GEMINI_MODEL
            justificacion_global = ranking_result.justificacion_global.strip()
        except Exception:
            if not settings.AI_USE_FALLBACK:
                db.rollback()
                raise
            fallback_usado = True
            justificacion_global = (
                "No fue posible obtener evaluacion directa de Gemini. "
                "Se aplico el ranking deterministico configurado."
            )

    candidatos_registrados: list[TallerCandidatoResponse] = []
    for entry in candidate_entries:
        if entry["existing_solicitud"]:
            solicitud = update_solicitud_taller_candidate_data(
                db,
                entry["existing_solicitud"],
                distancia_km=entry["distancia_km"],
                puntaje_asignacion=entry["puntaje_final"],
            )
        else:
            solicitud = create_solicitud_taller(
                db,
                id_incidente=incidente.id_incidente,
                id_taller=entry["taller"].id_taller,
                distancia_km=entry["distancia_km"],
                puntaje_asignacion=entry["puntaje_final"],
                estado_solicitud=ESTADO_SOLICITUD_INTELIGENTE,
            )

        candidatos_registrados.append(
            _build_taller_candidate_response(
                taller=entry["taller"],
                distancia_km=entry["distancia_km"],
                puntaje_asignacion=entry["puntaje_final"],
                taller_disponible=entry["taller_disponible"],
                tecnico_disponible=entry["tecnico_disponible"],
                unidad_movil_disponible=entry["unidad_movil_disponible"],
                estado_solicitud=solicitud.estado_solicitud,
                justificacion_ranking=entry["justificacion_ranking"],
            )
        )

    candidatos_registrados.sort(
        key=lambda candidato: (
            -candidato.puntaje_asignacion,
            candidato.distancia_km,
        ),
    )

    try:
        estado_buscando_taller = get_estado_servicio_by_nombre(
            db,
            ESTADO_INCIDENTE_BUSCANDO_TALLER,
        )
        if estado_buscando_taller:
            incidente.id_estado_servicio_actual = estado_buscando_taller.id_estado_servicio
            db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise

    taller_recomendado = candidatos_registrados[0]
    return AsignacionInteligenteResponse(
        id_incidente=incidente.id_incidente,
        clasificacion_ia=incidente.clasificacion_ia,
        auxilio_sugerido=_resolve_auxilio_name_for_incidente(incidente),
        taller_recomendado=TallerRecomendadoResponse(
            id_taller=taller_recomendado.id_taller,
            nombre_taller=taller_recomendado.nombre_taller,
            distancia_km=taller_recomendado.distancia_km,
            puntaje_asignacion=taller_recomendado.puntaje_asignacion,
            justificacion_ranking=taller_recomendado.justificacion_ranking,
        ),
        candidatos=candidatos_registrados,
        total_candidatos=len(candidatos_registrados),
        mensaje="Talleres candidatos seleccionados correctamente.",
        fuente_evaluacion=fuente_evaluacion,
        modelo_evaluacion=modelo_evaluacion,
        fallback_usado=fallback_usado,
        justificacion_global=justificacion_global,
    )


def listar_metricas_incidentes_service(
    db: Session,
) -> list[MetricaIncidenteListResponse]:
    incidentes = list_incidentes_metrics_context(db)
    if not incidentes:
        return []

    try:
        metricas = [
            _to_metrica_incidente_list_response(
                incidente,
                _build_metric_snapshot(db, incidente),
            )
            for incidente in incidentes
        ]
        db.commit()
        return metricas
    except Exception:
        db.rollback()
        raise


def obtener_metrica_incidente_service(
    db: Session,
    id_incidente: int,
) -> MetricaIncidenteDetailResponse:
    incidente = get_incidente_metrics_context_by_id(db, id_incidente)
    if not incidente:
        raise IncidentNotFoundError("El incidente especificado no existe.")

    try:
        snapshot = _build_metric_snapshot(db, incidente)
        db.commit()
        return _to_metrica_incidente_detail_response(incidente, snapshot)
    except Exception:
        db.rollback()
        raise


def _to_comision_list_response(comision) -> ComisionPlataformaListResponse:
    pago = comision.pago_servicio
    incidente = pago.incidente
    taller = comision.taller or resolve_pago_taller(pago)
    return ComisionPlataformaListResponse(
        id_comision=comision.id_comision,
        id_pago_servicio=comision.id_pago_servicio,
        id_incidente=pago.id_incidente,
        titulo_incidente=incidente.titulo,
        id_taller=comision.id_taller,
        nombre_taller=taller.nombre_taller,
        monto_total_pago=commission_decimal_amount(pago.monto_total),
        porcentaje=commission_decimal_amount(comision.porcentaje),
        monto_comision=commission_decimal_amount(comision.monto_comision),
        estado=comision.estado,
        estado_pago=pago.estado_pago,
        fecha_pago=pago.fecha_pago,
        fecha_calculo=comision.fecha_calculo,
        referencia_transaccion=pago.referencia_transaccion,
    )


def _to_comision_detail_response(comision) -> ComisionPlataformaDetailResponse:
    base = _to_comision_list_response(comision)
    pago = comision.pago_servicio
    return ComisionPlataformaDetailResponse(
        **base.model_dump(),
        metodo_pago=pago.metodo_pago,
        detalles_pago=[
            ComisionDetallePagoResponse(
                id_detalle_pago=detalle.id_detalle_pago,
                descripcion=detalle.descripcion,
                cantidad=detalle.cantidad,
                precio_unitario=commission_decimal_amount(detalle.precio_unitario),
                subtotal=commission_decimal_amount(detalle.subtotal),
                id_taller_auxilio=detalle.id_taller_auxilio,
                tipo_auxilio=(
                    detalle.taller_auxilio.tipo_auxilio.nombre
                    if detalle.taller_auxilio and detalle.taller_auxilio.tipo_auxilio
                    else None
                ),
            )
            for detalle in pago.detalles_pago
        ],
    )


def listar_comisiones_plataforma_service(
    db: Session,
    *,
    id_taller: int | None = None,
    estado: str | None = None,
    id_pago_servicio: int | None = None,
    id_incidente: int | None = None,
) -> list[ComisionPlataformaListResponse]:
    comisiones = list_comisiones_plataforma(
        db,
        id_taller=id_taller,
        estado=estado,
        id_pago_servicio=id_pago_servicio,
        id_incidente=id_incidente,
    )
    return [_to_comision_list_response(comision) for comision in comisiones]


def obtener_comision_plataforma_service(
    db: Session,
    id_comision: int,
) -> ComisionPlataformaDetailResponse:
    comision = get_comision_plataforma_by_id(db, id_comision)
    if not comision:
        raise CommissionNotFoundError("La comision especificada no existe.")
    return _to_comision_detail_response(comision)


def generar_comisiones_plataforma_service(
    db: Session,
    current_user,
    payload: ComisionPlataformaGenerateRequest,
) -> ComisionPlataformaGenerateResponse:
    try:
        if payload.id_pago_servicio is not None:
            pagos = [get_pago_servicio_with_comision_by_id(db, payload.id_pago_servicio)]
        else:
            pagos = list_pagos_servicio_elegibles_para_comision(
                db,
                incluir_con_comision=payload.recalcular,
            )

        pagos = [pago for pago in pagos if pago is not None]
        if not pagos:
            raise NoCommissionEligiblePaymentsError(
                "No existen pagos elegibles para generar comision."
            )

        resultados: list[ComisionPlataformaGenerateItemResponse] = []
        for pago_servicio in pagos:
            comision, creada = generate_platform_commission_for_payment(
                db,
                pago_servicio=pago_servicio,
                recalcular=payload.recalcular,
                id_usuario_actor=current_user.id_usuario,
            )
            resultados.append(
                ComisionPlataformaGenerateItemResponse(
                    id_comision=comision.id_comision,
                    id_pago_servicio=comision.id_pago_servicio,
                    id_incidente=pago_servicio.id_incidente,
                    id_taller=comision.id_taller,
                    porcentaje=_decimal_amount(comision.porcentaje),
                    monto_comision=_decimal_amount(comision.monto_comision),
                    estado=comision.estado,
                    creada=creada,
                    recalculada=not creada,
                )
            )

        db.commit()
        return ComisionPlataformaGenerateResponse(
            total_procesadas=len(resultados),
            comisiones=resultados,
            mensaje=(
                "Comisiones generadas correctamente."
                if any(item.creada for item in resultados)
                else "Comisiones recalculadas correctamente."
            ),
        )
    except Exception:
        db.rollback()
        raise
