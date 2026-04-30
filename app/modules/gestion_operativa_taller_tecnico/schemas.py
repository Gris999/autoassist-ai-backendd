from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


DIAS_SEMANA_VALIDOS = {
    "LUNES",
    "MARTES",
    "MIERCOLES",
    "JUEVES",
    "VIERNES",
    "SABADO",
    "DOMINGO",
}


class HorarioDisponibilidadTallerRequest(BaseModel):
    dia_semana: str = Field(min_length=5, max_length=15)
    hora_inicio: time
    hora_fin: time
    estado: bool = True

    @model_validator(mode="after")
    def validar_rango_horario(self):
        self.dia_semana = self.dia_semana.strip().upper()
        if self.dia_semana not in DIAS_SEMANA_VALIDOS:
            raise ValueError("El dia_semana no es valido.")
        if self.hora_inicio >= self.hora_fin:
            raise ValueError("La hora_inicio debe ser menor que la hora_fin.")
        return self


class HorarioDisponibilidadTallerResponse(BaseModel):
    id_horario_disponibilidad: int
    dia_semana: str
    hora_inicio: time
    hora_fin: time
    estado: bool

    model_config = ConfigDict(from_attributes=True)


class ActualizarDisponibilidadTallerRequest(BaseModel):
    disponible: bool | None = Field(
        default=None,
        description="Indicar si el taller esta disponible",
    )
    latitud: float | None = Field(default=None, ge=-90, le=90)
    longitud: float | None = Field(default=None, ge=-180, le=180)
    radio_cobertura_km: float | None = Field(default=None, gt=0)
    horarios: list[HorarioDisponibilidadTallerRequest] | None = None

    @model_validator(mode="after")
    def validar_coordenadas_completas(self):
        if (self.latitud is None) != (self.longitud is None):
            raise ValueError(
                "Latitud y longitud deben enviarse juntas o ambas omitirse."
            )
        return self


class DisponibilidadTallerResponse(BaseModel):
    id_taller: int
    nombre_taller: str
    disponible: bool
    direccion: str
    latitud: float | None = None
    longitud: float | None = None
    radio_cobertura_km: float | None = None
    fecha_registro: datetime
    horarios: list[HorarioDisponibilidadTallerResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TallerInfoResponse(BaseModel):
    id_taller: int
    nombre_taller: str
    nit: str
    direccion: str
    disponible: bool
    latitud: float | None = None
    longitud: float | None = None
    radio_cobertura_km: float | None = None
    id_tipo_taller: int
    fecha_registro: datetime

    model_config = ConfigDict(from_attributes=True)


class TipoAuxilioCatalogResponse(BaseModel):
    id_tipo_auxilio: int
    nombre: str
    descripcion: str | None = None
    requiere_unidad_movil: bool
    requiere_remolque: bool

    model_config = ConfigDict(from_attributes=True)


class TallerAuxilioCreateRequest(BaseModel):
    id_tipo_auxilio: int
    precio_referencial: float = Field(ge=0)
    disponible: bool = Field(default=True)


class TallerAuxilioUpdateRequest(BaseModel):
    precio_referencial: float | None = Field(default=None, ge=0)
    disponible: bool | None = None


class TallerAuxilioResponse(BaseModel):
    id_taller_auxilio: int
    id_taller: int
    id_tipo_auxilio: int
    nombre_tipo_auxilio: str
    descripcion_tipo_auxilio: str | None = None
    precio_referencial: float
    disponible: bool

    model_config = ConfigDict(from_attributes=True)


class ActualizarDisponibilidadTecnicoRequest(BaseModel):
    disponible: bool = Field(description="Indicar si el tecnico esta disponible")


class DisponibilidadTecnicoResponse(BaseModel):
    id_tecnico: int
    id_usuario: int
    disponible: bool
    estado: bool
    latitud_actual: float | None = None
    longitud_actual: float | None = None

    model_config = ConfigDict(from_attributes=True)


class TecnicoInfoResponse(BaseModel):
    id_tecnico: int
    id_usuario: int
    id_taller: int
    telefono_contacto: str
    disponible: bool
    estado: bool
    latitud_actual: float | None = None
    longitud_actual: float | None = None

    model_config = ConfigDict(from_attributes=True)


class TecnicoCreateRequest(BaseModel):
    nombres: str = Field(min_length=2, max_length=100)
    apellidos: str = Field(min_length=2, max_length=100)
    celular: str = Field(min_length=7, max_length=20)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    telefono_contacto: str = Field(min_length=7, max_length=20)
    disponible: bool = True
    estado: bool = True


class TecnicoUpdateRequest(BaseModel):
    nombres: str | None = Field(default=None, min_length=2, max_length=100)
    apellidos: str | None = Field(default=None, min_length=2, max_length=100)
    celular: str | None = Field(default=None, min_length=7, max_length=20)
    email: EmailStr | None = None
    telefono_contacto: str | None = Field(default=None, min_length=7, max_length=20)
    disponible: bool | None = None


class TecnicoListResponse(BaseModel):
    id_tecnico: int
    id_usuario: int
    nombres: str
    apellidos: str
    email: EmailStr
    celular: str
    telefono_contacto: str
    disponible: bool
    estado: bool

    model_config = ConfigDict(from_attributes=True)


class TecnicoDetailResponse(BaseModel):
    id_tecnico: int
    id_usuario: int
    id_taller: int
    nombres: str
    apellidos: str
    email: EmailStr
    celular: str
    telefono_contacto: str
    disponible: bool
    estado: bool
    latitud_actual: float | None = None
    longitud_actual: float | None = None

    model_config = ConfigDict(from_attributes=True)


class TecnicoEstadoResponse(BaseModel):
    id_tecnico: int
    id_usuario: int
    estado: bool
    disponible: bool

    model_config = ConfigDict(from_attributes=True)


class EspecialidadResponse(BaseModel):
    id_especialidad: int
    nombre: str
    descripcion: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TecnicoEspecialidadesResponse(BaseModel):
    id_tecnico: int
    especialidades: list[EspecialidadResponse]


class TecnicoEspecialidadesAssignRequest(BaseModel):
    ids_especialidad: list[int] = Field(min_length=1)


class TecnicoEspecialidadesUpdateRequest(BaseModel):
    ids_especialidad: list[int] = Field(default_factory=list)


class TipoVehiculoResponse(BaseModel):
    id_tipo_vehiculo: int
    nombre: str
    descripcion: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TallerTiposVehiculoConfigResponse(BaseModel):
    id_taller: int
    tipos_vehiculo: list[TipoVehiculoResponse]


class TallerTiposVehiculoConfigRequest(BaseModel):
    ids_tipo_vehiculo: list[int] = Field(min_length=1)


class UnidadMovilCreateRequest(BaseModel):
    placa: str = Field(min_length=5, max_length=20)
    tipo_unidad: str = Field(min_length=2, max_length=100)
    disponible: bool = True
    estado: bool = True
    latitud_actual: float | None = None
    longitud_actual: float | None = None


class UnidadMovilUpdateRequest(BaseModel):
    placa: str | None = Field(default=None, min_length=5, max_length=20)
    tipo_unidad: str | None = Field(default=None, min_length=2, max_length=100)
    disponible: bool | None = None
    estado: bool | None = None
    latitud_actual: float | None = None
    longitud_actual: float | None = None


class UnidadMovilEstadoDisponibilidadRequest(BaseModel):
    disponible: bool | None = None
    estado: bool | None = None


class UnidadMovilListResponse(BaseModel):
    id_unidad_movil: int
    id_taller: int
    placa: str
    tipo_unidad: str
    disponible: bool
    estado: bool

    model_config = ConfigDict(from_attributes=True)


class UnidadMovilDetailResponse(BaseModel):
    id_unidad_movil: int
    id_taller: int
    placa: str
    tipo_unidad: str
    disponible: bool
    estado: bool
    latitud_actual: float | None = None
    longitud_actual: float | None = None

    model_config = ConfigDict(from_attributes=True)
