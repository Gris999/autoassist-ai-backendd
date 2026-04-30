from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenciaCreateRequest(BaseModel):
    tipo_evidencia: str = Field(min_length=2, max_length=50)
    archivo_url: str = Field(min_length=3, max_length=500)
    texto_extraido: str | None = Field(default=None, max_length=5000)
    descripcion: str | None = Field(default=None, max_length=255)


class EvidenciaUploadResponse(BaseModel):
    tipo_evidencia: str
    archivo_url: str
    nombre_archivo: str
    tamano_bytes: int
    content_type: str | None = None


class AudioTranscriptionRequest(BaseModel):
    archivo_url: str = Field(min_length=3, max_length=500)


class AudioTranscriptionResponse(BaseModel):
    archivo_url: str
    texto_extraido: str
    mensaje: str


class IncidenteCreateRequest(BaseModel):
    id_vehiculo: int
    id_tipo_incidente: int
    titulo: str = Field(min_length=5, max_length=150)
    descripcion_texto: str | None = Field(default=None, max_length=2000)
    direccion_referencia: str | None = Field(default=None, max_length=255)
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    evidencias: list[EvidenciaCreateRequest] = Field(default_factory=list)


class CompletarInformacionIncidenteRequest(BaseModel):
    descripcion_texto: str | None = Field(default=None, max_length=2000)
    direccion_referencia: str | None = Field(default=None, max_length=255)
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    evidencias: list[EvidenciaCreateRequest] = Field(default_factory=list)


class TipoIncidenteResponse(BaseModel):
    id_tipo_incidente: int
    nombre: str
    descripcion: str | None = None
    estado: bool

    model_config = ConfigDict(from_attributes=True)


class IncidenteResponse(BaseModel):
    id_incidente: int
    id_cliente: int
    id_vehiculo: int
    id_tipo_incidente: int
    id_prioridad: int
    id_estado_servicio_actual: int
    titulo: str
    descripcion_texto: str | None = None
    direccion_referencia: str | None = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    fecha_reporte: datetime
    clasificacion_ia: str | None = None
    confianza_clasificacion: Decimal | None = None
    resumen_ia: str | None = None
    requiere_mas_info: bool

    model_config = ConfigDict(from_attributes=True)

class IncidenteDisponibleResponse(BaseModel):
    id_solicitud_taller: int
    id_incidente: int
    id_taller: int
    distancia_km: Decimal | None = None
    puntaje_asignacion: Decimal | None = None
    estado_solicitud: str
    fecha_envio: datetime
    fecha_respuesta: datetime | None = None
    titulo: str
    descripcion_texto: str | None = None
    direccion_referencia: str | None = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    fecha_reporte: datetime
    fecha_envio: datetime
    distancia_km: Decimal | None = None
    puntaje_asignacion: Decimal | None = None
    estado_solicitud: str

    id_vehiculo: int
    id_tipo_incidente: int
    tipo_incidente: str

    id_prioridad: int
    prioridad: str

    id_estado_servicio_actual: int
    estado_servicio_actual: str
    clasificacion_ia: str | None = None
    auxilio_sugerido: str | None = None
    problema_detectado_ia: str | None = None
    problema_detectado_origen: str | None = None
    tipo_auxilio_requerido: str | None = None


class SolicitudAtencionDetalleResponse(BaseModel):
    id_solicitud_taller: int
    id_incidente: int
    id_taller: int
    distancia_km: Decimal | None = None
    puntaje_asignacion: Decimal | None = None
    estado_solicitud: str
    fecha_envio: datetime
    fecha_respuesta: datetime | None = None
    titulo_incidente: str
    descripcion_texto: str | None = None
    direccion_referencia: str | None = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    fecha_reporte: datetime
    id_tipo_incidente: int
    tipo_incidente: str
    id_prioridad: int
    prioridad: str
    id_estado_servicio_actual: int
    estado_servicio_actual: str


class ResponderSolicitudAtencionRequest(BaseModel):
    accion: Literal["aceptar", "rechazar"]


class RespuestaSolicitudAtencionResponse(BaseModel):
    id_solicitud_taller: int
    id_incidente: int
    id_taller: int
    accion: Literal["aceptar", "rechazar"]
    estado_solicitud: str
    fecha_respuesta: datetime
    id_estado_servicio_actual: int
    estado_servicio_actual: str


class TecnicoDisponibleAsignacionResponse(BaseModel):
    id_tecnico: int
    id_usuario: int
    nombres: str
    apellidos: str
    telefono_contacto: str
    disponible: bool
    estado: bool


class UnidadMovilDisponibleAsignacionResponse(BaseModel):
    id_unidad_movil: int
    id_taller: int
    placa: str
    tipo_unidad: str
    disponible: bool
    estado: bool


class AsignacionIncidenteRequest(BaseModel):
    id_tecnico: int
    id_unidad_movil: int
    tiempo_estimado_min: int | None = Field(default=None, ge=0)
    observaciones: str | None = Field(default=None, max_length=2000)


class AsignacionIncidenteResponse(BaseModel):
    id_asignacion: int
    id_incidente: int
    id_taller: int
    id_tecnico: int
    id_unidad_movil: int | None = None
    fecha_asignacion: datetime
    tiempo_estimado_min: int | None = None
    estado_asignacion: str
    observaciones: str | None = None
    id_estado_servicio_actual: int
    estado_servicio_actual: str


class EstadoServicioIncidenteResponse(BaseModel):
    id_incidente: int
    id_taller: int
    id_estado_servicio_actual: int
    estado_servicio_actual: str
    orden_flujo_actual: int
    estado_asignacion: str | None = None


class ActualizarEstadoServicioRequest(BaseModel):
    id_estado_servicio: int
    detalle: str | None = Field(default=None, max_length=2000)


class ActualizacionEstadoServicioResponse(BaseModel):
    id_incidente: int
    id_taller: int
    id_estado_anterior: int
    estado_anterior: str
    id_estado_nuevo: int
    estado_nuevo: str
    fecha_hora: datetime
    detalle: str | None = None


class EvidenciaIncidenteResponse(BaseModel):
    id_evidencia: int
    tipo_evidencia: str
    archivo_url: str
    texto_extraido: str | None = None
    descripcion: str | None = None
    fecha_registro: datetime


class IncidenteAsignadoListResponse(BaseModel):
    id_incidente: int
    id_asignacion: int
    titulo: str
    descripcion_texto: str | None = None
    direccion_referencia: str | None = None
    fecha_reporte: datetime
    tipo_incidente: str
    prioridad: str
    estado_servicio_actual: str
    estado_asignacion: str


class IncidenteAsignadoDetailResponse(BaseModel):
    id_incidente: int
    id_asignacion: int
    id_taller: int
    id_tecnico: int
    id_unidad_movil: int | None = None
    titulo: str
    descripcion_texto: str | None = None
    direccion_referencia: str | None = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    fecha_reporte: datetime
    tipo_incidente: str
    prioridad: str
    estado_servicio_actual: str
    estado_asignacion: str
    tiempo_estimado_min: int | None = None
    observaciones: str | None = None
    placa_vehiculo: str
    marca_vehiculo: str
    modelo_vehiculo: str
    color_vehiculo: str | None = None
    tipo_vehiculo: str
    evidencias: list[EvidenciaIncidenteResponse]
