from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config.settings import settings
from app.modules.gestion_operativa_taller_tecnico.repository import (
    get_taller_by_usuario_id,
    get_tecnico_by_usuario_id,
    get_tecnico_with_usuario_by_id,
    get_unidad_movil_by_id,
)
from app.modules.gestion_clientes.repository import get_cliente_by_usuario_id
from app.modules.inteligencia_gestion_estrategica.service import (
    orquestar_incidente_reportado_service,
    transcribir_audio_desde_url_service,
)
from app.modules.seguimiento_monitoreo_servicio.repository import (
    create_notificacion,
    get_cliente_by_id,
)
from app.modules.seguimiento_monitoreo_servicio.service import (
    dispatch_push_notification_service,
)
from app.modules.gestion_incidentes_atencion.repository import (
    cancel_pending_solicitudes_by_incidente_except,
    create_historial_incidente,
    create_asignacion_servicio,
    create_evidencia,
    create_incidente,
    get_asignacion_servicio_by_incidente_id,
    get_asignacion_servicio_by_incidente_id_for_update,
    get_asignacion_servicio_detalle_by_incidente_and_tecnico_id,
    get_asignaciones_servicio_by_tecnico_id,
    get_estado_servicio_by_id,
    get_incidente_by_id_for_update,
    get_incidente_by_id,
    get_estado_servicio_by_nombre,
    get_incidentes_by_cliente_id,
    get_prioridad_by_nombre,
    get_solicitud_aceptada_by_incidente_id,
    get_solicitud_aceptada_by_incidente_and_taller_id,
    get_solicitudes_taller_disponibles,
    get_solicitud_taller_by_id,
    get_solicitud_taller_by_id_for_update,
    get_tecnico_by_id_for_update,
    get_tecnicos_disponibles_by_taller_id,
    get_tecnicos_disponibles_by_taller_id_and_tipo_auxilio,
    get_tipo_auxilio_by_nombre,
    get_tipo_incidente_by_id,
    list_tipos_incidente,
    get_unidad_movil_by_id_for_update,
    get_unidades_moviles_disponibles_by_taller_id,
    get_vehiculo_by_id_and_cliente,
    get_incidentes_disponibles_by_taller_id,
    update_tecnico_disponibilidad,
    update_incidente_estado_servicio_actual,
    update_solicitud_taller_respuesta,
    update_asignacion_servicio_estado,
    update_unidad_movil_disponibilidad,
)
from app.modules.gestion_incidentes_atencion.schemas import (
    ActualizacionEstadoServicioResponse,
    ActualizarEstadoServicioRequest,
    AsignacionIncidenteRequest,
    AsignacionIncidenteResponse,
    CompletarInformacionIncidenteRequest,
    EvidenciaIncidenteResponse,
    EvidenciaUploadResponse,
    EstadoServicioIncidenteResponse,
    IncidenteAsignadoDetailResponse,
    IncidenteAsignadoListResponse,
    IncidenteCreateRequest,
    IncidenteResponse,
    IncidenteDisponibleResponse,
    AudioTranscriptionResponse,
    ResponderSolicitudAtencionRequest,
    RespuestaSolicitudAtencionResponse,
    SolicitudAtencionDetalleResponse,
    TecnicoDisponibleAsignacionResponse,
    TipoIncidenteResponse,
    UnidadMovilDisponibleAsignacionResponse,
)

ESTADO_SOLICITUD_PENDIENTE = "PENDIENTE"
ESTADO_SOLICITUD_ACEPTADA = "ACEPTADA"
ESTADO_SOLICITUD_RECHAZADA = "RECHAZADA"
ESTADO_SOLICITUD_CANCELADA = "CANCELADA"
ESTADO_ASIGNACION_SERVICIO = "ASIGNADO"
TIPO_NOTIFICACION_TALLER_ACEPTO = "TALLER_ACEPTO"
TIPO_NOTIFICACION_ASIGNACION_TECNICO = "ASIGNACION_TECNICO"
ESTADOS_FINALES_SERVICIO = {"FINALIZADO", "CANCELADO"}
ESTADOS_CONSULTABLES_TECNICO = {"ASIGNADO", "EN_CAMINO", "EN_ATENCION", "FINALIZADO"}
ESTADOS_INCIDENTE_NO_DISPONIBLE_RESPUESTA = {
    "ASIGNADO",
    "EN_CAMINO",
    "EN_ATENCION",
    "FINALIZADO",
    "CANCELADO",
}
INCIDENT_TYPE_TO_AUXILIO = {
    "BATERIA_DESCARGADA": "AUXILIO_ELECTRICO",
    "PINCHAZO_LLANTA": "CAMBIO_DE_LLANTA",
    "SIN_COMBUSTIBLE": "SUMINISTRO_COMBUSTIBLE",
    "LLAVES_DENTRO": "APERTURA_VEHICULO",
    "FALLA_MECANICA": "AUXILIO_MECANICO_BASICO",
    "SOBRECALENTAMIENTO": "AUXILIO_MECANICO_BASICO",
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
ALLOWED_EVIDENCIA_UPLOAD_TYPES = {
    "image/jpeg": "IMAGEN",
    "image/jpg": "IMAGEN",
    "image/png": "IMAGEN",
    "image/webp": "IMAGEN",
    "video/mp4": "VIDEO",
    "video/quicktime": "VIDEO",
    "video/x-msvideo": "VIDEO",
    "video/webm": "VIDEO",
    "video/mpeg": "VIDEO",
    "audio/mpeg": "AUDIO",
    "audio/mp3": "AUDIO",
    "audio/wav": "AUDIO",
    "audio/x-wav": "AUDIO",
    "audio/mp4": "AUDIO",
    "audio/x-m4a": "AUDIO",
    "audio/aac": "AUDIO",
    "audio/ogg": "AUDIO",
    "audio/webm": "AUDIO",
}
ALLOWED_EVIDENCIA_EXTENSIONS = {
    ".jpg": "IMAGEN",
    ".jpeg": "IMAGEN",
    ".png": "IMAGEN",
    ".webp": "IMAGEN",
    ".mp4": "VIDEO",
    ".mov": "VIDEO",
    ".avi": "VIDEO",
    ".webm": "VIDEO",
    ".mpeg": "VIDEO",
    ".mpg": "VIDEO",
    ".mp3": "AUDIO",
    ".wav": "AUDIO",
    ".m4a": "AUDIO",
    ".aac": "AUDIO",
    ".ogg": "AUDIO",
    ".webm": "AUDIO",
}


def _get_taller_actor_service(db: Session, current_user):
    taller = get_taller_by_usuario_id(db, current_user.id_usuario)
    if not taller:
        raise ValueError("El usuario autenticado no tiene perfil de taller.")
    return taller


def _validar_solicitud_del_taller(solicitud_taller, id_taller: int):
    if not solicitud_taller:
        raise ValueError("La solicitud de atencion especificada no existe.")
    if solicitud_taller.id_taller != id_taller:
        raise ValueError("La solicitud no pertenece al taller autenticado.")
    return solicitud_taller


def _to_solicitud_atencion_detalle_response(
    solicitud_taller,
) -> SolicitudAtencionDetalleResponse:
    incidente = solicitud_taller.incidente
    return SolicitudAtencionDetalleResponse(
        id_solicitud_taller=solicitud_taller.id_solicitud_taller,
        id_incidente=solicitud_taller.id_incidente,
        id_taller=solicitud_taller.id_taller,
        distancia_km=solicitud_taller.distancia_km,
        puntaje_asignacion=solicitud_taller.puntaje_asignacion,
        estado_solicitud=solicitud_taller.estado_solicitud,
        fecha_envio=solicitud_taller.fecha_envio,
        fecha_respuesta=solicitud_taller.fecha_respuesta,
        titulo_incidente=incidente.titulo,
        descripcion_texto=incidente.descripcion_texto,
        direccion_referencia=incidente.direccion_referencia,
        latitud=incidente.latitud,
        longitud=incidente.longitud,
        fecha_reporte=incidente.fecha_reporte,
        id_tipo_incidente=incidente.id_tipo_incidente,
        tipo_incidente=incidente.tipo_incidente.nombre,
        id_prioridad=incidente.id_prioridad,
        prioridad=incidente.prioridad.nombre,
        id_estado_servicio_actual=incidente.id_estado_servicio_actual,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
    )


def _to_respuesta_solicitud_atencion_response(
    solicitud_taller,
    *,
    accion: str,
) -> RespuestaSolicitudAtencionResponse:
    incidente = solicitud_taller.incidente
    return RespuestaSolicitudAtencionResponse(
        id_solicitud_taller=solicitud_taller.id_solicitud_taller,
        id_incidente=solicitud_taller.id_incidente,
        id_taller=solicitud_taller.id_taller,
        accion=accion,
        estado_solicitud=solicitud_taller.estado_solicitud,
        fecha_respuesta=solicitud_taller.fecha_respuesta,
        id_estado_servicio_actual=incidente.id_estado_servicio_actual,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
    )


def _to_incidente_disponible_response(
    solicitud_taller,
) -> IncidenteDisponibleResponse:
    incidente = solicitud_taller.incidente
    clasificacion_ia = incidente.clasificacion_ia
    tipo_incidente_nombre = incidente.tipo_incidente.nombre if incidente.tipo_incidente else None
    problema_detectado_ia = clasificacion_ia
    problema_detectado_origen = "ia" if clasificacion_ia and clasificacion_ia.strip() else None
    if (not problema_detectado_ia or not problema_detectado_ia.strip()) and tipo_incidente_nombre:
        problema_detectado_ia = tipo_incidente_nombre
        problema_detectado_origen = "fallback"

    auxilio_sugerido = None
    if clasificacion_ia and clasificacion_ia.strip():
        auxilio_sugerido = CLASSIFICATION_TO_AUXILIO.get(clasificacion_ia.strip().lower())
    if auxilio_sugerido is None and tipo_incidente_nombre:
        auxilio_sugerido = INCIDENT_TYPE_TO_AUXILIO.get(tipo_incidente_nombre)

    return IncidenteDisponibleResponse(
        id_solicitud_taller=solicitud_taller.id_solicitud_taller,
        id_incidente=solicitud_taller.id_incidente,
        id_taller=solicitud_taller.id_taller,
        distancia_km=solicitud_taller.distancia_km,
        puntaje_asignacion=solicitud_taller.puntaje_asignacion,
        estado_solicitud=solicitud_taller.estado_solicitud,
        fecha_envio=solicitud_taller.fecha_envio,
        fecha_respuesta=solicitud_taller.fecha_respuesta,
        titulo=incidente.titulo,
        descripcion_texto=incidente.descripcion_texto,
        direccion_referencia=incidente.direccion_referencia,
        latitud=incidente.latitud,
        longitud=incidente.longitud,
        fecha_reporte=incidente.fecha_reporte,
        id_vehiculo=incidente.id_vehiculo,
        id_tipo_incidente=incidente.id_tipo_incidente,
        tipo_incidente=incidente.tipo_incidente.nombre,
        id_prioridad=incidente.id_prioridad,
        prioridad=incidente.prioridad.nombre,
        id_estado_servicio_actual=incidente.id_estado_servicio_actual,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
        clasificacion_ia=clasificacion_ia,
        auxilio_sugerido=auxilio_sugerido,
        problema_detectado_ia=problema_detectado_ia,
        problema_detectado_origen=problema_detectado_origen,
        tipo_auxilio_requerido=auxilio_sugerido,
    )


def _validar_incidente_disponible_para_respuesta(incidente) -> None:
    if incidente.estado_servicio_actual.nombre in ESTADOS_INCIDENTE_NO_DISPONIBLE_RESPUESTA:
        raise ValueError("El incidente ya no se encuentra disponible para responder esta solicitud.")


def _registrar_notificacion_taller_acepto(db: Session, *, incidente, taller) -> None:
    cliente = get_cliente_by_id(db, incidente.id_cliente)
    if not cliente:
        return

    notificacion = create_notificacion(
        db,
        id_usuario=cliente.id_usuario,
        id_incidente=incidente.id_incidente,
        titulo="Taller acepto tu solicitud",
        mensaje=(
            f"El taller '{taller.nombre_taller}' acepto la atencion de tu incidente "
            f"'{incidente.titulo}'."
        ),
        tipo_notificacion=TIPO_NOTIFICACION_TALLER_ACEPTO,
    )
    dispatch_push_notification_service(db, notificacion)


def _registrar_notificacion_recursos_asignados(
    db: Session,
    *,
    incidente,
    taller,
    tecnico,
    unidad_movil,
    tiempo_estimado_min: int | None,
) -> None:
    cliente = get_cliente_by_id(db, incidente.id_cliente)
    if not cliente:
        return

    nombre_tecnico = (
        f"{tecnico.usuario.nombres} {tecnico.usuario.apellidos}".strip()
        if getattr(tecnico, "usuario", None)
        else f"Tecnico #{tecnico.id_tecnico}"
    )
    descripcion_vehiculo = unidad_movil.placa if unidad_movil else "unidad movil asignada"
    detalle_tiempo = (
        f" Tiempo estimado de llegada: {tiempo_estimado_min} min."
        if tiempo_estimado_min
        else ""
    )

    notificacion = create_notificacion(
        db,
        id_usuario=cliente.id_usuario,
        id_incidente=incidente.id_incidente,
        titulo="Tecnico y unidad movil asignados",
        mensaje=(
            f"El taller '{taller.nombre_taller}' asigno a {nombre_tecnico} con "
            f"{descripcion_vehiculo} para atender tu incidente '{incidente.titulo}'."
            f"{detalle_tiempo}"
        ),
        tipo_notificacion=TIPO_NOTIFICACION_ASIGNACION_TECNICO,
    )
    dispatch_push_notification_service(db, notificacion)


def _to_tecnico_disponible_asignacion_response(
    tecnico,
) -> TecnicoDisponibleAsignacionResponse:
    return TecnicoDisponibleAsignacionResponse(
        id_tecnico=tecnico.id_tecnico,
        id_usuario=tecnico.id_usuario,
        nombres=tecnico.usuario.nombres,
        apellidos=tecnico.usuario.apellidos,
        telefono_contacto=tecnico.telefono_contacto,
        disponible=tecnico.disponible,
        estado=tecnico.estado,
    )


def _to_unidad_movil_disponible_asignacion_response(
    unidad_movil,
) -> UnidadMovilDisponibleAsignacionResponse:
    return UnidadMovilDisponibleAsignacionResponse(
        id_unidad_movil=unidad_movil.id_unidad_movil,
        id_taller=unidad_movil.id_taller,
        placa=unidad_movil.placa,
        tipo_unidad=unidad_movil.tipo_unidad,
        disponible=unidad_movil.disponible,
        estado=unidad_movil.estado,
    )


def _to_asignacion_incidente_response(
    asignacion,
    incidente,
) -> AsignacionIncidenteResponse:
    return AsignacionIncidenteResponse(
        id_asignacion=asignacion.id_asignacion,
        id_incidente=asignacion.id_incidente,
        id_taller=asignacion.id_taller,
        id_tecnico=asignacion.id_tecnico,
        id_unidad_movil=asignacion.id_unidad_movil,
        fecha_asignacion=asignacion.fecha_asignacion,
        tiempo_estimado_min=asignacion.tiempo_estimado_min,
        estado_asignacion=asignacion.estado_asignacion,
        observaciones=asignacion.observaciones,
        id_estado_servicio_actual=incidente.id_estado_servicio_actual,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
    )


def _to_estado_servicio_incidente_response(
    incidente,
    asignacion_servicio,
    *,
    id_taller: int,
) -> EstadoServicioIncidenteResponse:
    return EstadoServicioIncidenteResponse(
        id_incidente=incidente.id_incidente,
        id_taller=id_taller,
        id_estado_servicio_actual=incidente.id_estado_servicio_actual,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
        orden_flujo_actual=incidente.estado_servicio_actual.orden_flujo,
        estado_asignacion=asignacion_servicio.estado_asignacion if asignacion_servicio else None,
    )


def _to_actualizacion_estado_servicio_response(
    *,
    id_incidente: int,
    id_taller: int,
    estado_anterior,
    estado_nuevo,
    historial,
) -> ActualizacionEstadoServicioResponse:
    return ActualizacionEstadoServicioResponse(
        id_incidente=id_incidente,
        id_taller=id_taller,
        id_estado_anterior=estado_anterior.id_estado_servicio,
        estado_anterior=estado_anterior.nombre,
        id_estado_nuevo=estado_nuevo.id_estado_servicio,
        estado_nuevo=estado_nuevo.nombre,
        fecha_hora=historial.fecha_hora,
        detalle=historial.detalle,
    )


def _get_tecnico_actor_service(db: Session, current_user):
    tecnico = get_tecnico_by_usuario_id(db, current_user.id_usuario)
    if not tecnico:
        raise ValueError("El usuario autenticado no tiene perfil de tecnico.")
    if not tecnico.estado:
        raise ValueError("El tecnico no se encuentra habilitado en la plataforma.")
    return tecnico


def _validar_incidente_aceptado_para_taller(db: Session, *, id_incidente: int, id_taller: int):
    incidente = get_incidente_by_id(db, id_incidente)
    if not incidente:
        raise ValueError("El incidente especificado no existe.")

    solicitud_aceptada = get_solicitud_aceptada_by_incidente_id(db, id_incidente)
    if not solicitud_aceptada:
        raise ValueError("El incidente no tiene una solicitud aceptada para atencion.")
    if solicitud_aceptada.id_taller != id_taller:
        raise ValueError("El incidente no corresponde al taller autenticado.")

    if incidente.estado_servicio_actual.nombre != "ASIGNADO":
        raise ValueError("El incidente no se encuentra en un estado apto para asignacion.")

    asignacion_existente = get_asignacion_servicio_by_incidente_id(db, id_incidente)
    if asignacion_existente:
        raise ValueError("El incidente ya tiene una asignacion registrada.")

    return incidente


def _validar_incidente_asignado_al_taller_para_estado(
    db: Session,
    *,
    id_incidente: int,
    id_taller: int,
):
    incidente = get_incidente_by_id(db, id_incidente)
    if not incidente:
        raise ValueError("El incidente especificado no existe.")

    asignacion_servicio = get_asignacion_servicio_by_incidente_id(db, id_incidente)
    if not asignacion_servicio:
        raise ValueError("El incidente no tiene una asignacion de servicio registrada.")
    if asignacion_servicio.id_taller != id_taller:
        raise ValueError("El incidente no pertenece al taller autenticado.")

    return incidente, asignacion_servicio


def _validar_transicion_estado_servicio(estado_actual, nuevo_estado) -> None:
    if estado_actual.id_estado_servicio == nuevo_estado.id_estado_servicio:
        raise ValueError("El nuevo estado no puede ser igual al estado actual.")

    if estado_actual.nombre in ESTADOS_FINALES_SERVICIO:
        raise ValueError("No se puede actualizar un servicio que ya se encuentra finalizado o cancelado.")

    if nuevo_estado.nombre == "CANCELADO":
        return

    if nuevo_estado.orden_flujo != estado_actual.orden_flujo + 1:
        raise ValueError("La transicion de estado no es valida segun el flujo configurado.")


def _validar_incidente_consultable_para_tecnico(incidente) -> None:
    if incidente.estado_servicio_actual.nombre not in ESTADOS_CONSULTABLES_TECNICO:
        raise ValueError("El incidente no se encuentra disponible para consulta en su estado actual.")


def _to_evidencia_incidente_response(evidencia) -> EvidenciaIncidenteResponse:
    return EvidenciaIncidenteResponse(
        id_evidencia=evidencia.id_evidencia,
        tipo_evidencia=evidencia.tipo_evidencia,
        archivo_url=evidencia.archivo_url,
        texto_extraido=evidencia.texto_extraido,
        descripcion=evidencia.descripcion,
        fecha_registro=evidencia.fecha_registro,
    )


def _resolve_texto_extraido_para_evidencia(tipo_evidencia: str, texto_extraido, descripcion) -> str | None:
    evidence_type = tipo_evidencia.strip().upper()
    extracted_text = texto_extraido.strip() if texto_extraido and texto_extraido.strip() else None
    if extracted_text:
        return extracted_text
    if evidence_type in {"AUDIO", "AUDIO_TRANSCRITO"} and descripcion and descripcion.strip():
        return descripcion.strip()
    return None


def _crear_evidencias_incidente(
    db: Session,
    *,
    id_incidente: int,
    evidencias_payload,
) -> None:
    for evidencia_payload in evidencias_payload:
        create_evidencia(
            db,
            id_incidente=id_incidente,
            tipo_evidencia=evidencia_payload.tipo_evidencia.strip().upper(),
            archivo_url=evidencia_payload.archivo_url.strip(),
            texto_extraido=_resolve_texto_extraido_para_evidencia(
                evidencia_payload.tipo_evidencia,
                evidencia_payload.texto_extraido,
                evidencia_payload.descripcion,
            ),
            descripcion=(
                evidencia_payload.descripcion.strip()
                if evidencia_payload.descripcion and evidencia_payload.descripcion.strip()
                else None
            ),
        )


def _infer_evidencia_tipo_for_upload(file: UploadFile) -> str:
    content_type = (file.content_type or "").strip().lower()
    if content_type in ALLOWED_EVIDENCIA_UPLOAD_TYPES:
        return ALLOWED_EVIDENCIA_UPLOAD_TYPES[content_type]

    extension = Path(file.filename or "").suffix.strip().lower()
    if extension in ALLOWED_EVIDENCIA_EXTENSIONS:
        return ALLOWED_EVIDENCIA_EXTENSIONS[extension]

    raise ValueError(
        "Tipo de archivo no permitido. Solo se aceptan imagenes JPG/PNG/WEBP, videos MP4/MOV/AVI/WEBM/MPEG y audios MP3/WAV/M4A/AAC/OGG/WEBM."
    )


def _resolver_tipo_auxilio_requerido_incidente(incidente) -> str | None:
    tipo_incidente_nombre = incidente.tipo_incidente.nombre if incidente.tipo_incidente else None
    if tipo_incidente_nombre:
        auxilio_por_tipo = INCIDENT_TYPE_TO_AUXILIO.get(tipo_incidente_nombre)
        if auxilio_por_tipo:
            return auxilio_por_tipo
    clasificacion_ia = incidente.clasificacion_ia
    if clasificacion_ia and clasificacion_ia.strip():
        return CLASSIFICATION_TO_AUXILIO.get(clasificacion_ia.strip().lower())
    return None


def _get_tecnicos_compatibles_por_incidente(
    db: Session,
    *,
    id_taller: int,
    incidente,
):
    auxilio_requerido = _resolver_tipo_auxilio_requerido_incidente(incidente)
    if not auxilio_requerido:
        return get_tecnicos_disponibles_by_taller_id(db, id_taller)

    tipo_auxilio = get_tipo_auxilio_by_nombre(db, auxilio_requerido)
    if not tipo_auxilio:
        raise ValueError(
            f"No existe el tipo de auxilio '{auxilio_requerido}' en la base de datos."
        )

    tecnicos = get_tecnicos_disponibles_by_taller_id_and_tipo_auxilio(
        db,
        id_taller=id_taller,
        id_tipo_auxilio=tipo_auxilio.id_tipo_auxilio,
    )
    if not tecnicos:
        raise ValueError(
            "No existen tecnicos disponibles con especialidad compatible para el tipo de auxilio requerido."
        )
    return tecnicos


def _build_safe_upload_filename(original_filename: str | None) -> str:
    original_extension = Path(original_filename or "").suffix.strip().lower()
    extension = original_extension if original_extension in ALLOWED_EVIDENCIA_EXTENSIONS else ""
    return f"{uuid4().hex}{extension}"


def upload_evidencia_service(file: UploadFile, *, public_base_url: str) -> EvidenciaUploadResponse:
    tipo_evidencia = _infer_evidencia_tipo_for_upload(file)
    safe_name = _build_safe_upload_filename(file.filename)
    target_directory = Path(settings.MEDIA_ROOT) / "evidencias" / tipo_evidencia.lower()
    target_directory.mkdir(parents=True, exist_ok=True)
    target_path = target_directory / safe_name

    max_bytes = settings.MAX_EVIDENCIA_FILE_SIZE_MB * 1024 * 1024
    file.file.seek(0)
    content = file.file.read()
    file.file.seek(0)

    if not content:
        raise ValueError("El archivo enviado esta vacio.")
    if len(content) > max_bytes:
        raise ValueError(
            f"El archivo excede el tamano maximo permitido de {settings.MAX_EVIDENCIA_FILE_SIZE_MB} MB."
        )

    target_path.write_bytes(content)

    normalized_base_url = public_base_url.rstrip("/")
    relative_url = f"{settings.MEDIA_URL_PREFIX}/evidencias/{tipo_evidencia.lower()}/{safe_name}"
    archivo_url = f"{normalized_base_url}{relative_url}"

    return EvidenciaUploadResponse(
        tipo_evidencia=tipo_evidencia,
        archivo_url=archivo_url,
        nombre_archivo=safe_name,
        tamano_bytes=len(content),
        content_type=file.content_type,
    )


def transcribir_audio_subido_service(*, archivo_url: str) -> AudioTranscriptionResponse:
    transcript = transcribir_audio_desde_url_service(archivo_url.strip())
    return AudioTranscriptionResponse(
        archivo_url=archivo_url.strip(),
        texto_extraido=transcript,
        mensaje="Audio transcrito correctamente con Gemini.",
    )


def _to_incidente_asignado_list_response(
    asignacion_servicio,
) -> IncidenteAsignadoListResponse:
    incidente = asignacion_servicio.incidente
    return IncidenteAsignadoListResponse(
        id_incidente=incidente.id_incidente,
        id_asignacion=asignacion_servicio.id_asignacion,
        titulo=incidente.titulo,
        descripcion_texto=incidente.descripcion_texto,
        direccion_referencia=incidente.direccion_referencia,
        fecha_reporte=incidente.fecha_reporte,
        tipo_incidente=incidente.tipo_incidente.nombre,
        prioridad=incidente.prioridad.nombre,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
        estado_asignacion=asignacion_servicio.estado_asignacion,
    )


def _to_incidente_asignado_detail_response(
    asignacion_servicio,
) -> IncidenteAsignadoDetailResponse:
    incidente = asignacion_servicio.incidente
    vehiculo = incidente.vehiculo
    return IncidenteAsignadoDetailResponse(
        id_incidente=incidente.id_incidente,
        id_asignacion=asignacion_servicio.id_asignacion,
        id_taller=asignacion_servicio.id_taller,
        id_tecnico=asignacion_servicio.id_tecnico,
        id_unidad_movil=asignacion_servicio.id_unidad_movil,
        titulo=incidente.titulo,
        descripcion_texto=incidente.descripcion_texto,
        direccion_referencia=incidente.direccion_referencia,
        latitud=incidente.latitud,
        longitud=incidente.longitud,
        fecha_reporte=incidente.fecha_reporte,
        tipo_incidente=incidente.tipo_incidente.nombre,
        prioridad=incidente.prioridad.nombre,
        estado_servicio_actual=incidente.estado_servicio_actual.nombre,
        estado_asignacion=asignacion_servicio.estado_asignacion,
        tiempo_estimado_min=asignacion_servicio.tiempo_estimado_min,
        observaciones=asignacion_servicio.observaciones,
        placa_vehiculo=vehiculo.placa,
        marca_vehiculo=vehiculo.marca,
        modelo_vehiculo=vehiculo.modelo,
        color_vehiculo=vehiculo.color,
        tipo_vehiculo=vehiculo.tipo_vehiculo.nombre,
        evidencias=[
            _to_evidencia_incidente_response(evidencia)
            for evidencia in incidente.evidencias
        ],
    )


def report_incidente_service(
    db: Session,
    current_user,
    payload: IncidenteCreateRequest,
) -> IncidenteResponse:
    cliente = get_cliente_by_usuario_id(db, current_user.id_usuario)
    if not cliente:
        raise ValueError("El usuario autenticado no tiene perfil de cliente.")

    vehiculo = get_vehiculo_by_id_and_cliente(db, payload.id_vehiculo, cliente.id_cliente)
    if not vehiculo:
        raise ValueError("El vehículo no existe o no pertenece al cliente autenticado.")

    tipo_incidente = get_tipo_incidente_by_id(db, payload.id_tipo_incidente)
    if not tipo_incidente:
        raise ValueError("El tipo de incidente seleccionado no existe.")

    prioridad = get_prioridad_by_nombre(db, "MEDIA")
    if not prioridad:
        raise ValueError("No existe la prioridad MEDIA en la base de datos.")

    estado_reportado = get_estado_servicio_by_nombre(db, "REPORTADO")
    if not estado_reportado:
        raise ValueError("No existe el estado REPORTADO en la base de datos.")

    try:
        incidente = create_incidente(
            db,
            id_cliente=cliente.id_cliente,
            id_vehiculo=payload.id_vehiculo,
            id_tipo_incidente=payload.id_tipo_incidente,
            id_prioridad=prioridad.id_prioridad,
            id_estado_servicio_actual=estado_reportado.id_estado_servicio,
            titulo=payload.titulo,
            descripcion_texto=payload.descripcion_texto,
            direccion_referencia=payload.direccion_referencia,
            latitud=payload.latitud,
            longitud=payload.longitud,
        )

        _crear_evidencias_incidente(
            db,
            id_incidente=incidente.id_incidente,
            evidencias_payload=payload.evidencias,
        )

        db.commit()
        db.refresh(incidente)
        try:
            orquestar_incidente_reportado_service(db, incidente.id_incidente)
            db.refresh(incidente)
        except Exception:
            if not incidente.requiere_mas_info:
                db.refresh(incidente)

        return IncidenteResponse.model_validate(incidente)
    except Exception:
        db.rollback()
        raise


def listar_tipos_incidente_service(db: Session) -> list[TipoIncidenteResponse]:
    tipos = list_tipos_incidente(db)
    return [TipoIncidenteResponse.model_validate(tipo) for tipo in tipos]


def get_mis_incidentes_service(
    db: Session,
    current_user,
) -> list[IncidenteResponse]:
    cliente = get_cliente_by_usuario_id(db, current_user.id_usuario)
    if not cliente:
        raise ValueError("El usuario autenticado no tiene perfil de cliente.")

    incidentes = get_incidentes_by_cliente_id(db, cliente.id_cliente)
    return [IncidenteResponse.model_validate(i) for i in incidentes]


def completar_informacion_incidente_service(
    db: Session,
    current_user,
    id_incidente: int,
    payload: CompletarInformacionIncidenteRequest,
) -> IncidenteResponse:
    cliente = get_cliente_by_usuario_id(db, current_user.id_usuario)
    if not cliente:
        raise ValueError("El usuario autenticado no tiene perfil de cliente.")

    if (
        payload.descripcion_texto is None
        and payload.direccion_referencia is None
        and payload.latitud is None
        and payload.longitud is None
        and not payload.evidencias
    ):
        raise ValueError("Debe enviar al menos un dato adicional o una evidencia.")

    incidente = get_incidente_by_id_for_update(db, id_incidente)
    if not incidente or incidente.id_cliente != cliente.id_cliente:
        raise ValueError("El incidente no existe o no pertenece al cliente autenticado.")

    if not incidente.requiere_mas_info:
        raise ValueError("El incidente no requiere informacion adicional en este momento.")

    if payload.descripcion_texto and payload.descripcion_texto.strip():
        descripcion_extra = payload.descripcion_texto.strip()
        if incidente.descripcion_texto and incidente.descripcion_texto.strip():
            incidente.descripcion_texto = (
                f"{incidente.descripcion_texto.strip()}\n\nInformacion adicional: {descripcion_extra}"
            )
        else:
            incidente.descripcion_texto = descripcion_extra

    if payload.direccion_referencia is not None:
        incidente.direccion_referencia = (
            payload.direccion_referencia.strip()
            if payload.direccion_referencia and payload.direccion_referencia.strip()
            else None
        )

    if payload.latitud is not None:
        incidente.latitud = payload.latitud
    if payload.longitud is not None:
        incidente.longitud = payload.longitud

    try:
        _crear_evidencias_incidente(
            db,
            id_incidente=incidente.id_incidente,
            evidencias_payload=payload.evidencias,
        )
        db.commit()
        db.refresh(incidente)

        try:
            orquestar_incidente_reportado_service(db, incidente.id_incidente)
            db.refresh(incidente)
        except Exception:
            db.refresh(incidente)

        return IncidenteResponse.model_validate(incidente)
    except Exception:
        db.rollback()
        raise



def get_incidentes_disponibles_service(
    db: Session,
    current_user,
) -> list[IncidenteDisponibleResponse]:
    taller = _get_taller_actor_service(db, current_user)
    solicitudes = get_incidentes_disponibles_by_taller_id(db, taller.id_taller)
    return [_to_incidente_disponible_response(solicitud) for solicitud in solicitudes]


def get_solicitud_atencion_detalle_service(
    db: Session,
    current_user,
    id_solicitud_taller: int,
) -> SolicitudAtencionDetalleResponse:
    taller = _get_taller_actor_service(db, current_user)
    solicitud_taller = get_solicitud_taller_by_id(db, id_solicitud_taller)
    solicitud_taller = _validar_solicitud_del_taller(solicitud_taller, taller.id_taller)
    return _to_solicitud_atencion_detalle_response(solicitud_taller)


def responder_solicitud_atencion_service(
    db: Session,
    current_user,
    id_solicitud_taller: int,
    payload: ResponderSolicitudAtencionRequest,
) -> RespuestaSolicitudAtencionResponse:
    taller = _get_taller_actor_service(db, current_user)

    try:
        solicitud_taller = get_solicitud_taller_by_id_for_update(db, id_solicitud_taller)
        solicitud_taller = _validar_solicitud_del_taller(solicitud_taller, taller.id_taller)

        if solicitud_taller.estado_solicitud != ESTADO_SOLICITUD_PENDIENTE:
            raise ValueError("La solicitud ya fue respondida y no admite una nueva respuesta.")

        incidente = get_incidente_by_id_for_update(db, solicitud_taller.id_incidente)
        if not incidente:
            raise ValueError("El incidente asociado a la solicitud no existe.")
        _validar_incidente_disponible_para_respuesta(incidente)

        solicitud_aceptada = get_solicitud_aceptada_by_incidente_id(db, solicitud_taller.id_incidente)
        if solicitud_aceptada and solicitud_aceptada.id_solicitud_taller != solicitud_taller.id_solicitud_taller:
            raise ValueError("La solicitud ya fue tomada por otro taller.")

        if payload.accion == "aceptar":
            estado_asignado = get_estado_servicio_by_nombre(db, "ASIGNADO")
            if not estado_asignado:
                raise ValueError("No existe el estado ASIGNADO en la base de datos.")

            update_solicitud_taller_respuesta(
                db,
                solicitud_taller,
                estado_solicitud=ESTADO_SOLICITUD_ACEPTADA,
            )
            update_incidente_estado_servicio_actual(
                db,
                incidente,
                id_estado_servicio_actual=estado_asignado.id_estado_servicio,
            )
            cancel_pending_solicitudes_by_incidente_except(
                db,
                id_incidente=solicitud_taller.id_incidente,
                exclude_id_solicitud_taller=solicitud_taller.id_solicitud_taller,
            )
            _registrar_notificacion_taller_acepto(
                db,
                incidente=incidente,
                taller=taller,
            )
        else:
            update_solicitud_taller_respuesta(
                db,
                solicitud_taller,
                estado_solicitud=ESTADO_SOLICITUD_RECHAZADA,
            )

        db.commit()
        solicitud_taller_actualizada = get_solicitud_taller_by_id(db, solicitud_taller.id_solicitud_taller)
        return _to_respuesta_solicitud_atencion_response(
            solicitud_taller_actualizada,
            accion=payload.accion,
        )
    except Exception:
        db.rollback()
        raise


def listar_tecnicos_disponibles_para_incidente_service(
    db: Session,
    current_user,
    id_incidente: int,
) -> list[TecnicoDisponibleAsignacionResponse]:
    taller = _get_taller_actor_service(db, current_user)
    incidente = _validar_incidente_aceptado_para_taller(
        db,
        id_incidente=id_incidente,
        id_taller=taller.id_taller,
    )
    tecnicos = _get_tecnicos_compatibles_por_incidente(
        db,
        id_taller=taller.id_taller,
        incidente=incidente,
    )
    return [_to_tecnico_disponible_asignacion_response(tecnico) for tecnico in tecnicos]


def listar_unidades_moviles_disponibles_para_incidente_service(
    db: Session,
    current_user,
    id_incidente: int,
) -> list[UnidadMovilDisponibleAsignacionResponse]:
    taller = _get_taller_actor_service(db, current_user)
    _validar_incidente_aceptado_para_taller(
        db,
        id_incidente=id_incidente,
        id_taller=taller.id_taller,
    )
    unidades_moviles = get_unidades_moviles_disponibles_by_taller_id(db, taller.id_taller)
    return [
        _to_unidad_movil_disponible_asignacion_response(unidad_movil)
        for unidad_movil in unidades_moviles
    ]


def asignar_tecnico_unidad_incidente_service(
    db: Session,
    current_user,
    id_incidente: int,
    payload: AsignacionIncidenteRequest,
) -> AsignacionIncidenteResponse:
    taller = _get_taller_actor_service(db, current_user)

    try:
        incidente = get_incidente_by_id_for_update(db, id_incidente)
        if not incidente:
            raise ValueError("El incidente especificado no existe.")

        solicitud_aceptada = get_solicitud_aceptada_by_incidente_and_taller_id(
            db,
            id_incidente=id_incidente,
            id_taller=taller.id_taller,
        )
        if not solicitud_aceptada:
            solicitud_aceptada_otro_taller = get_solicitud_aceptada_by_incidente_id(db, id_incidente)
            if solicitud_aceptada_otro_taller:
                raise ValueError("El incidente fue aceptado por otro taller.")
            raise ValueError("El incidente no fue aceptado previamente por el taller autenticado.")

        if incidente.estado_servicio_actual.nombre != "ASIGNADO":
            raise ValueError("El incidente no se encuentra en un estado apto para asignacion.")

        asignacion_existente = get_asignacion_servicio_by_incidente_id_for_update(db, id_incidente)
        if asignacion_existente:
            raise ValueError("El incidente ya tiene una asignacion registrada.")

        tecnico = get_tecnico_by_id_for_update(db, payload.id_tecnico)
        if not tecnico:
            raise ValueError("El tecnico especificado no existe.")
        if tecnico.id_taller != taller.id_taller:
            raise ValueError("El tecnico no pertenece al taller autenticado.")
        if not tecnico.estado or not tecnico.disponible:
            raise ValueError("El tecnico seleccionado no se encuentra disponible.")

        tecnicos_compatibles = _get_tecnicos_compatibles_por_incidente(
            db,
            id_taller=taller.id_taller,
            incidente=incidente,
        )
        ids_tecnicos_compatibles = {tecnico_compatible.id_tecnico for tecnico_compatible in tecnicos_compatibles}
        if tecnico.id_tecnico not in ids_tecnicos_compatibles:
            raise ValueError(
                "El tecnico seleccionado no tiene una especialidad compatible con el tipo de auxilio requerido."
            )

        unidad_movil = get_unidad_movil_by_id_for_update(db, payload.id_unidad_movil)
        if not unidad_movil:
            raise ValueError("La unidad movil especificada no existe.")
        if unidad_movil.id_taller != taller.id_taller:
            raise ValueError("La unidad movil no pertenece al taller autenticado.")
        if not unidad_movil.estado or not unidad_movil.disponible:
            raise ValueError("La unidad movil seleccionada no se encuentra disponible.")

        estado_asignado = get_estado_servicio_by_nombre(db, "ASIGNADO")
        if not estado_asignado:
            raise ValueError("No existe el estado ASIGNADO en la base de datos.")

        asignacion = create_asignacion_servicio(
            db,
            id_incidente=id_incidente,
            id_taller=taller.id_taller,
            id_tecnico=payload.id_tecnico,
            id_unidad_movil=payload.id_unidad_movil,
            tiempo_estimado_min=payload.tiempo_estimado_min,
            estado_asignacion=ESTADO_ASIGNACION_SERVICIO,
            observaciones=payload.observaciones,
        )
        update_tecnico_disponibilidad(db, tecnico, disponible=False)
        update_unidad_movil_disponibilidad(db, unidad_movil, disponible=False)
        update_incidente_estado_servicio_actual(
            db,
            incidente,
            id_estado_servicio_actual=estado_asignado.id_estado_servicio,
        )
        tecnico_detalle = get_tecnico_with_usuario_by_id(db, payload.id_tecnico)
        unidad_movil_detalle = get_unidad_movil_by_id(db, payload.id_unidad_movil)
        if tecnico_detalle and unidad_movil_detalle:
            _registrar_notificacion_recursos_asignados(
                db,
                incidente=incidente,
                taller=taller,
                tecnico=tecnico_detalle,
                unidad_movil=unidad_movil_detalle,
                tiempo_estimado_min=payload.tiempo_estimado_min,
            )

        db.commit()
        incidente_actualizado = get_incidente_by_id(db, id_incidente)
        return _to_asignacion_incidente_response(asignacion, incidente_actualizado)
    except Exception:
        db.rollback()
        raise


def get_estado_servicio_incidente_service(
    db: Session,
    current_user,
    id_incidente: int,
) -> EstadoServicioIncidenteResponse:
    taller = _get_taller_actor_service(db, current_user)
    incidente, asignacion_servicio = _validar_incidente_asignado_al_taller_para_estado(
        db,
        id_incidente=id_incidente,
        id_taller=taller.id_taller,
    )
    return _to_estado_servicio_incidente_response(
        incidente,
        asignacion_servicio,
        id_taller=taller.id_taller,
    )


def actualizar_estado_servicio_incidente_service(
    db: Session,
    current_user,
    id_incidente: int,
    payload: ActualizarEstadoServicioRequest,
) -> ActualizacionEstadoServicioResponse:
    taller = _get_taller_actor_service(db, current_user)

    try:
        incidente = get_incidente_by_id_for_update(db, id_incidente)
        if not incidente:
            raise ValueError("El incidente especificado no existe.")

        asignacion_servicio = get_asignacion_servicio_by_incidente_id_for_update(db, id_incidente)
        if not asignacion_servicio:
            raise ValueError("El incidente no tiene una asignacion de servicio registrada.")
        if asignacion_servicio.id_taller != taller.id_taller:
            raise ValueError("El incidente no pertenece al taller autenticado.")

        estado_actual = incidente.estado_servicio_actual
        nuevo_estado = get_estado_servicio_by_id(db, payload.id_estado_servicio)
        if not nuevo_estado:
            raise ValueError("El estado de servicio especificado no existe.")

        _validar_transicion_estado_servicio(estado_actual, nuevo_estado)

        update_incidente_estado_servicio_actual(
            db,
            incidente,
            id_estado_servicio_actual=nuevo_estado.id_estado_servicio,
        )
        update_asignacion_servicio_estado(
            db,
            asignacion_servicio,
            estado_asignacion=nuevo_estado.nombre,
        )

        if nuevo_estado.nombre in ESTADOS_FINALES_SERVICIO:
            tecnico = asignacion_servicio.tecnico
            unidad_movil = asignacion_servicio.unidad_movil
            if tecnico and tecnico.estado:
                update_tecnico_disponibilidad(db, tecnico, disponible=True)
            if unidad_movil and unidad_movil.estado:
                update_unidad_movil_disponibilidad(db, unidad_movil, disponible=True)

        historial = create_historial_incidente(
            db,
            id_incidente=incidente.id_incidente,
            id_estado_anterior=estado_actual.id_estado_servicio,
            id_estado_nuevo=nuevo_estado.id_estado_servicio,
            id_usuario_actor=current_user.id_usuario,
            detalle=payload.detalle,
        )

        db.commit()
        return _to_actualizacion_estado_servicio_response(
            id_incidente=incidente.id_incidente,
            id_taller=taller.id_taller,
            estado_anterior=estado_actual,
            estado_nuevo=nuevo_estado,
            historial=historial,
        )
    except Exception:
        db.rollback()
        raise


def listar_incidentes_asignados_tecnico_service(
    db: Session,
    current_user,
) -> list[IncidenteAsignadoListResponse]:
    tecnico = _get_tecnico_actor_service(db, current_user)
    asignaciones = get_asignaciones_servicio_by_tecnico_id(db, tecnico.id_tecnico)

    asignaciones_consultables = []
    for asignacion in asignaciones:
        try:
            _validar_incidente_consultable_para_tecnico(asignacion.incidente)
            asignaciones_consultables.append(asignacion)
        except ValueError:
            continue

    return [
        _to_incidente_asignado_list_response(asignacion)
        for asignacion in asignaciones_consultables
    ]


def obtener_incidente_asignado_tecnico_service(
    db: Session,
    current_user,
    id_incidente: int,
) -> IncidenteAsignadoDetailResponse:
    tecnico = _get_tecnico_actor_service(db, current_user)
    asignacion = get_asignacion_servicio_detalle_by_incidente_and_tecnico_id(
        db,
        id_incidente=id_incidente,
        id_tecnico=tecnico.id_tecnico,
    )
    if not asignacion:
        raise ValueError("El incidente no existe o no pertenece al tecnico autenticado.")

    _validar_incidente_consultable_para_tecnico(asignacion.incidente)
    return _to_incidente_asignado_detail_response(asignacion)
