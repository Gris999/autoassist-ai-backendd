from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.session import Base


class TipoIncidente(Base):
    __tablename__ = "tipo_incidente"

    id_tipo_incidente: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    incidentes: Mapped[list["Incidente"]] = relationship(back_populates="tipo_incidente")


class Prioridad(Base):
    __tablename__ = "prioridad"

    id_prioridad: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    nivel: Mapped[int] = mapped_column(Integer, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)

    incidentes: Mapped[list["Incidente"]] = relationship(back_populates="prioridad")


class EstadoServicio(Base):
    __tablename__ = "estado_servicio"

    id_estado_servicio: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    orden_flujo: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Incidente(Base):
    __tablename__ = "incidente"

    id_incidente: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_cliente: Mapped[int] = mapped_column(
        ForeignKey("cliente.id_cliente"),
        nullable=False,
    )
    id_vehiculo: Mapped[int] = mapped_column(
        ForeignKey("vehiculo.id_vehiculo"),
        nullable=False,
    )
    id_tipo_incidente: Mapped[int] = mapped_column(
        ForeignKey("tipo_incidente.id_tipo_incidente"),
        nullable=False,
    )
    id_prioridad: Mapped[int] = mapped_column(
        ForeignKey("prioridad.id_prioridad"),
        nullable=False,
    )
    id_estado_servicio_actual: Mapped[int] = mapped_column(
        ForeignKey("estado_servicio.id_estado_servicio"),
        nullable=False,
    )
    titulo: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcion_texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    direccion_referencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitud: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitud: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    fecha_reporte: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    clasificacion_ia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confianza_clasificacion: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    resumen_ia: Mapped[str | None] = mapped_column(Text, nullable=True)
    requiere_mas_info: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    cliente = relationship("Cliente")
    vehiculo = relationship("Vehiculo")
    tipo_incidente: Mapped["TipoIncidente"] = relationship(back_populates="incidentes")
    prioridad: Mapped["Prioridad"] = relationship(back_populates="incidentes")
    estado_servicio_actual = relationship("EstadoServicio", foreign_keys=[id_estado_servicio_actual])

    evidencias: Mapped[list["Evidencia"]] = relationship(
        back_populates="incidente",
        cascade="all, delete-orphan",
    )
    solicitudes_taller: Mapped[list["SolicitudTaller"]] = relationship(
        back_populates="incidente",
        cascade="all, delete-orphan",
    )
    asignacion_servicio: Mapped["AsignacionServicio | None"] = relationship(
        back_populates="incidente",
        cascade="all, delete-orphan",
        uselist=False,
    )
    historial: Mapped[list["HistorialIncidente"]] = relationship(
        back_populates="incidente",
        cascade="all, delete-orphan",
    )


class Evidencia(Base):
    __tablename__ = "evidencia"

    id_evidencia: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_incidente: Mapped[int] = mapped_column(
        ForeignKey("incidente.id_incidente"),
        nullable=False,
    )
    tipo_evidencia: Mapped[str] = mapped_column(String(50), nullable=False)
    archivo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    texto_extraido: Mapped[str | None] = mapped_column(Text, nullable=True)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    incidente: Mapped["Incidente"] = relationship(back_populates="evidencias")


class SolicitudTaller(Base):
    __tablename__ = "solicitud_taller"
    __table_args__ = (
        UniqueConstraint(
            "id_incidente",
            "id_taller",
            name="uq_solicitud_taller_incidente_taller",
        ),
    )

    id_solicitud_taller: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_incidente: Mapped[int] = mapped_column(
        ForeignKey("incidente.id_incidente"),
        nullable=False,
    )
    id_taller: Mapped[int] = mapped_column(
        ForeignKey("taller.id_taller"),
        nullable=False,
    )
    distancia_km: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    puntaje_asignacion: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    estado_solicitud: Mapped[str] = mapped_column(String(50), nullable=False)
    fecha_envio: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    fecha_respuesta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    incidente: Mapped["Incidente"] = relationship(back_populates="solicitudes_taller")
    taller = relationship("Taller")


class AsignacionServicio(Base):
    __tablename__ = "asignacion_servicio"

    id_asignacion: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_incidente: Mapped[int] = mapped_column(
        ForeignKey("incidente.id_incidente"),
        nullable=False,
        unique=True,
    )
    id_taller: Mapped[int] = mapped_column(
        ForeignKey("taller.id_taller"),
        nullable=False,
    )
    id_tecnico: Mapped[int] = mapped_column(
        ForeignKey("tecnico.id_tecnico"),
        nullable=False,
    )
    id_unidad_movil: Mapped[int | None] = mapped_column(
        ForeignKey("unidad_movil.id_unidad_movil"),
        nullable=True,
    )
    fecha_asignacion: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    tiempo_estimado_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estado_asignacion: Mapped[str] = mapped_column(String(50), nullable=False)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)

    incidente: Mapped["Incidente"] = relationship(back_populates="asignacion_servicio")
    taller = relationship("Taller")
    tecnico = relationship("Tecnico")
    unidad_movil = relationship("UnidadMovil")


class HistorialIncidente(Base):
    __tablename__ = "historial_incidente"

    id_historial: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_incidente: Mapped[int] = mapped_column(
        ForeignKey("incidente.id_incidente"),
        nullable=False,
    )
    id_estado_anterior: Mapped[int | None] = mapped_column(
        ForeignKey("estado_servicio.id_estado_servicio"),
        nullable=True,
    )
    id_estado_nuevo: Mapped[int] = mapped_column(
        ForeignKey("estado_servicio.id_estado_servicio"),
        nullable=False,
    )
    id_usuario_actor: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario"),
        nullable=False,
    )
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)

    incidente: Mapped["Incidente"] = relationship(back_populates="historial")
    estado_anterior = relationship("EstadoServicio", foreign_keys=[id_estado_anterior])
    estado_nuevo = relationship("EstadoServicio", foreign_keys=[id_estado_nuevo])
    usuario_actor = relationship("Usuario")
