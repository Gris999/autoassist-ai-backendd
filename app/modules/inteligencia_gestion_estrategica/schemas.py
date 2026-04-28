from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AnalisisIncidenteManualRequest(BaseModel):
    descripcion_texto: str | None = Field(default=None, max_length=2000)
    texto_evidencias: list[str] = Field(default_factory=list)
    latitud: Decimal | None = None
    longitud: Decimal | None = None

    model_config = ConfigDict(extra="forbid")


class PreguntasSugeridasResponse(BaseModel):
    preguntas_sugeridas: list[str] = Field(default_factory=list)


class AnalisisIncidenteResponse(PreguntasSugeridasResponse):
    id_incidente: int | None = None
    clasificacion_ia: str
    confianza_clasificacion: float = Field(ge=0.0, le=1.0)
    prioridad: str
    resumen_ia: str
    requiere_mas_info: bool
    fuente_analisis: str = "reglas"
    modelo_analisis: str | None = None
    fallback_usado: bool = False


class AnalisisIncidenteLLMResult(PreguntasSugeridasResponse):
    clasificacion_ia: str
    confianza_clasificacion: float = Field(ge=0.0, le=1.0)
    prioridad: str
    resumen_ia: str = Field(min_length=1, max_length=2000)
    requiere_mas_info: bool


class SolicitudMasInformacionResponse(PreguntasSugeridasResponse):
    id_incidente: int
    id_usuario_destino: int
    solicitud_emitida: bool
    mensaje: str
    id_notificacion: int | None = None


class RegistrarEvidenciaProcesadaRequest(BaseModel):
    tipo_evidencia: str
    archivo_url: str | None = None
    texto_extraido: str
    descripcion: str | None = None

    model_config = ConfigDict(extra="forbid")


class EvidenciaProcesadaResponse(BaseModel):
    id_evidencia: int
    id_incidente: int
    tipo_evidencia: str
    archivo_url: str | None = None
    texto_extraido: str | None = None
    descripcion: str | None = None
    mensaje: str | None = None


class AnalizarImagenIncidenteRequest(BaseModel):
    id_evidencia: int | None = None
    archivo_url: str | None = None
    descripcion: str | None = None

    model_config = ConfigDict(extra="forbid")


class AnalisisImagenRoboflowResponse(BaseModel):
    id_incidente: int
    id_evidencia_origen: int | None = None
    id_evidencia_procesada: int
    archivo_url: str
    proveedor: str
    tipo_modelo: str
    modelo: str
    clase_principal: str
    confianza: float = Field(ge=0.0, le=1.0)
    categoria_sugerida: str
    resumen_visual: str
    detecciones: list[str] = Field(default_factory=list)
    mensaje: str


class TallerCandidatoResponse(BaseModel):
    id_taller: int
    nombre_taller: str
    distancia_km: float
    puntaje_asignacion: float
    compatible_servicio: bool
    compatible_tipo_vehiculo: bool
    taller_disponible: bool
    tecnico_disponible: bool
    unidad_movil_disponible: bool
    estado_solicitud: str
    justificacion_ranking: str | None = None


class TallerRecomendadoResponse(BaseModel):
    id_taller: int
    nombre_taller: str
    distancia_km: float
    puntaje_asignacion: float
    justificacion_ranking: str | None = None


class AsignacionInteligenteResponse(BaseModel):
    id_incidente: int
    clasificacion_ia: str
    taller_recomendado: TallerRecomendadoResponse
    candidatos: list[TallerCandidatoResponse]
    total_candidatos: int
    mensaje: str
    fuente_evaluacion: str = "reglas"
    modelo_evaluacion: str | None = None
    fallback_usado: bool = False
    justificacion_global: str | None = None


class MetricaIncidenteListResponse(BaseModel):
    id_incidente: int
    titulo: str
    fecha_reporte: datetime
    estado_actual: str
    tiempo_respuesta_seg: int | None = None
    incidentes_atendidos: int
    estado_frecuente: str | None = None
    rendimiento_operativo: str
    fecha_generacion: datetime


class MetricaIncidenteDetailResponse(MetricaIncidenteListResponse):
    clasificacion_ia: str | None = None
    prioridad: str | None = None
    tipo_incidente: str | None = None
    tiempo_asignacion_seg: int | None = None
    tiempo_llegada_seg: int | None = None
    tiempo_resolucion_seg: int | None = None
    cantidad_rechazos: int
    fue_reasignado: bool


class GeminiTallerRankingCandidate(BaseModel):
    id_taller: int
    ajuste_puntaje: float = Field(ge=-15.0, le=15.0)
    justificacion: str = Field(min_length=1, max_length=400)


class GeminiTallerRankingResult(BaseModel):
    justificacion_global: str = Field(min_length=1, max_length=1200)
    candidatos: list[GeminiTallerRankingCandidate] = Field(default_factory=list)


class ComisionPlataformaGenerateRequest(BaseModel):
    id_pago_servicio: int | None = None
    recalcular: bool = False

    model_config = ConfigDict(extra="forbid")


class ComisionPlataformaListResponse(BaseModel):
    id_comision: int
    id_pago_servicio: int
    id_incidente: int
    titulo_incidente: str
    id_taller: int
    nombre_taller: str
    monto_total_pago: Decimal
    porcentaje: Decimal
    monto_comision: Decimal
    estado: str
    estado_pago: str
    fecha_pago: datetime | None = None
    fecha_calculo: datetime
    referencia_transaccion: str | None = None


class ComisionDetallePagoResponse(BaseModel):
    id_detalle_pago: int
    descripcion: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal
    id_taller_auxilio: int
    tipo_auxilio: str | None = None


class ComisionPlataformaDetailResponse(ComisionPlataformaListResponse):
    metodo_pago: str
    detalles_pago: list[ComisionDetallePagoResponse] = Field(default_factory=list)


class ComisionPlataformaGenerateItemResponse(BaseModel):
    id_comision: int
    id_pago_servicio: int
    id_incidente: int
    id_taller: int
    porcentaje: Decimal
    monto_comision: Decimal
    estado: str
    creada: bool
    recalculada: bool


class ComisionPlataformaGenerateResponse(BaseModel):
    total_procesadas: int
    comisiones: list[ComisionPlataformaGenerateItemResponse] = Field(default_factory=list)
    mensaje: str

