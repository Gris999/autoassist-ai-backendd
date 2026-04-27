from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class EstadoServicioDetalleResponse(BaseModel):
    id_incidente: int
    titulo: str
    fecha_reporte: datetime

    id_vehiculo: int
    id_tipo_incidente: int
    tipo_incidente: str

    id_prioridad: int
    prioridad: str

    id_estado_servicio_actual: int
    estado_servicio_actual: str

    direccion_referencia: str | None = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None

    clasificacion_ia: str | None = None
    confianza_clasificacion: Decimal | None = None
    resumen_ia: str | None = None
    requiere_mas_info: bool


class ActualizarUbicacionActualRequest(BaseModel):
    latitud: Decimal = Field(ge=-90, le=90)
    longitud: Decimal = Field(ge=-180, le=180)
    confirmar_envio: bool = True

    @model_validator(mode="after")
    def validar_confirmacion(self):
        if not self.confirmar_envio:
            raise ValueError("Debe confirmar el envio de la ubicacion actual.")
        return self


class UbicacionActualTecnicoResponse(BaseModel):
    id_incidente: int
    id_tecnico: int
    id_unidad_movil: int | None = None
    latitud_actual: Decimal
    longitud_actual: Decimal
    fecha_actualizacion: datetime
    estado_asignacion: str
    estado_servicio_actual: str
    mensaje: str


class ClienteIncidenteListResponse(BaseModel):
    id_incidente: int
    titulo: str
    fecha_reporte: datetime
    id_estado_servicio_actual: int
    estado_servicio_actual: str
    tiene_asignacion: bool


class TallerAsignadoResponse(BaseModel):
    id_taller: int
    nombre_taller: str
    direccion: str


class TecnicoAsignadoResponse(BaseModel):
    id_tecnico: int
    nombres: str
    apellidos: str
    telefono_contacto: str


class UnidadMovilAsignadaResponse(BaseModel):
    id_unidad_movil: int
    placa: str
    tipo_unidad: str


class AsignacionAuxilioDetalleResponse(BaseModel):
    id_incidente: int
    titulo: str
    fecha_reporte: datetime
    tipo_incidente: str
    descripcion_texto: str | None = None
    direccion_referencia: str | None = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    id_estado_servicio_actual: int
    estado_servicio_actual: str
    estado_asignacion: str | None = None
    tiempo_estimado_min: int | None = None
    asignacion_definida: bool
    mensaje: str | None = None
    taller: TallerAsignadoResponse | None = None
    tecnico: TecnicoAsignadoResponse | None = None
    unidad_movil: UnidadMovilAsignadaResponse | None = None
    placa_vehiculo: str | None = None
    marca_vehiculo: str | None = None
    modelo_vehiculo: str | None = None


class NotificacionCreateRequest(BaseModel):
    id_usuario: int
    id_incidente: int | None = None
    titulo: str
    mensaje: str
    tipo_notificacion: str


class NotificacionListResponse(BaseModel):
    id_notificacion: int
    id_incidente: int | None = None
    titulo: str
    mensaje: str
    tipo_notificacion: str
    leido: bool
    fecha_envio: datetime


class NotificacionDetailResponse(BaseModel):
    id_notificacion: int
    id_usuario: int
    id_incidente: int | None = None
    titulo: str
    mensaje: str
    tipo_notificacion: str
    leido: bool
    fecha_envio: datetime


class NotificacionLeidaResponse(BaseModel):
    id_notificacion: int
    leido: bool
    mensaje: str


class IncidenteHistorialListResponse(BaseModel):
    id_incidente: int
    titulo: str
    fecha_reporte: datetime
    tipo_incidente: str
    id_estado_servicio_actual: int
    estado_servicio_actual: str


class HistorialIncidenteEventoResponse(BaseModel):
    fecha_hora: datetime
    tipo_evento: str
    actor: str | None = None
    detalle: str | None = None
    estado_anterior: str | None = None
    estado_nuevo: str | None = None
    estado_solicitud: str | None = None
    id_taller: int | None = None
    nombre_taller: str | None = None
    id_tecnico: int | None = None
    nombre_tecnico: str | None = None
    id_unidad_movil: int | None = None
    placa_unidad_movil: str | None = None


class IncidenteHistorialDetailResponse(BaseModel):
    id_incidente: int
    titulo: str
    fecha_reporte: datetime
    tipo_incidente: str
    prioridad: str
    id_estado_servicio_actual: int
    estado_servicio_actual: str
    descripcion_texto: str | None = None
    direccion_referencia: str | None = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    historial: list[HistorialIncidenteEventoResponse]
    mensaje: str | None = None


class MetodoPagoDisponibleResponse(BaseModel):
    codigo: str
    nombre: str
    descripcion: str


class DetalleCobroAuxilioResponse(BaseModel):
    descripcion: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal
    id_taller_auxilio: int
    tipo_auxilio: str


class PagoIncidenteDetalleResponse(BaseModel):
    id_incidente: int
    titulo: str
    estado_servicio_actual: str
    id_estado_servicio_actual: int
    tipo_incidente: str
    nombre_taller: str
    id_taller: int
    moneda: str
    monto_total: Decimal
    habilitado_para_pago: bool
    mensaje: str | None = None
    metodos_pago_disponibles: list[MetodoPagoDisponibleResponse]
    detalles_cobro: list[DetalleCobroAuxilioResponse]
    pago_existente: bool
    estado_pago: str | None = None
    referencia_transaccion: str | None = None


class CrearIntencionPagoRequest(BaseModel):
    metodo_pago: str = Field(min_length=2, max_length=50)


class ConfirmarPagoDemoRequest(BaseModel):
    metodo_pago: str = Field(default="DEMO_CARD", min_length=2, max_length=50)
    referencia_demo: str | None = Field(default=None, max_length=150)


class IntencionPagoResponse(BaseModel):
    id_pago_servicio: int
    id_incidente: int
    monto_total: Decimal
    moneda: str
    estado_pago: str
    client_secret: str
    payment_intent_id: str
    publishable_key: str | None = None
    metodo_pago: str
    mensaje: str


class ComisionPlataformaResponse(BaseModel):
    porcentaje: Decimal
    monto_comision: Decimal
    estado: str
    fecha_calculo: datetime


class ComprobantePagoResponse(BaseModel):
    id_pago_servicio: int
    id_incidente: int
    titulo_incidente: str
    nombre_taller: str
    metodo_pago: str
    estado_pago: str
    monto_total: Decimal
    moneda: str
    fecha_pago: datetime | None = None
    referencia_transaccion: str | None = None
    receipt_url: str | None = None
    detalles: list[DetalleCobroAuxilioResponse]
    comision_plataforma: ComisionPlataformaResponse | None = None


class ConfirmacionPagoDemoResponse(BaseModel):
    id_pago_servicio: int
    id_incidente: int
    estado_pago: str
    referencia_transaccion: str
    mensaje: str


class WebhookStripeResponse(BaseModel):
    recibido: bool
    evento: str
    mensaje: str
