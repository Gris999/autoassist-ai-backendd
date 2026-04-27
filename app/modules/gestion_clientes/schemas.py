from pydantic import BaseModel, ConfigDict, Field


class TipoVehiculoResponse(BaseModel):
    id_tipo_vehiculo: int
    nombre: str
    descripcion: str | None = None

    model_config = ConfigDict(from_attributes=True)


class VehiculoCreateRequest(BaseModel):
    id_tipo_vehiculo: int
    placa: str = Field(min_length=5, max_length=20)
    marca: str = Field(min_length=2, max_length=100)
    modelo: str = Field(min_length=1, max_length=100)
    anio: int = Field(ge=1900, le=2100)
    color: str | None = Field(default=None, max_length=50)
    descripcion_referencia: str | None = Field(default=None, max_length=255)


class VehiculoResponse(BaseModel):
    id_vehiculo: int
    id_cliente: int
    id_tipo_vehiculo: int
    placa: str
    marca: str
    modelo: str
    anio: int
    color: str | None = None
    descripcion_referencia: str | None = None
    estado: bool

    model_config = ConfigDict(from_attributes=True)


class CalificacionServicioCreateRequest(BaseModel):
    id_incidente: int
    puntuacion: float = Field(ge=1.0, le=5.0)
    comentario: str | None = Field(default=None, max_length=500)


class CalificacionServicioResponse(BaseModel):
    id_calificacion: int
    id_incidente: int
    id_cliente: int
    id_taller: int
    id_tecnico: int | None
    puntuacion: float
    comentario: str | None
    fecha_calificacion: str

    model_config = ConfigDict(from_attributes=True)


class ServicioPendienteCalificacionResponse(BaseModel):
    id_incidente: int
    titulo: str
    fecha_reporte: str
    id_taller: int
    nombre_taller: str
    id_tecnico: int | None
    nombre_tecnico: str | None

    model_config = ConfigDict(from_attributes=True)
