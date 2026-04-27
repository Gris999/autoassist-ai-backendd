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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.session import Base


class Notificacion(Base):
    __tablename__ = "notificacion"

    id_notificacion: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario"),
        nullable=False,
    )
    id_incidente: Mapped[int | None] = mapped_column(
        ForeignKey("incidente.id_incidente"),
        nullable=True,
    )
    titulo: Mapped[str] = mapped_column(String(150), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_notificacion: Mapped[str] = mapped_column(String(50), nullable=False)
    leido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    push_estado: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDIENTE")
    push_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_envio_push: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fecha_envio: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    usuario = relationship("Usuario")
    incidente = relationship("Incidente")


class DispositivoPushUsuario(Base):
    __tablename__ = "dispositivo_push_usuario"

    id_dispositivo_push: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario"),
        nullable=False,
    )
    token_push: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    plataforma: Mapped[str] = mapped_column(String(30), nullable=False)
    proveedor: Mapped[str] = mapped_column(String(30), nullable=False, default="EXPO")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    usuario = relationship("Usuario")


class PagoServicio(Base):
    __tablename__ = "pago_servicio"

    id_pago_servicio: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_incidente: Mapped[int] = mapped_column(
        ForeignKey("incidente.id_incidente"),
        nullable=False,
        unique=True,
    )
    monto_total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    metodo_pago: Mapped[str] = mapped_column(String(50), nullable=False)
    estado_pago: Mapped[str] = mapped_column(String(50), nullable=False)
    fecha_pago: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    referencia_transaccion: Mapped[str | None] = mapped_column(String(150), nullable=True)

    incidente = relationship("Incidente")
    detalles_pago: Mapped[list["DetallePago"]] = relationship(
        back_populates="pago_servicio",
        cascade="all, delete-orphan",
    )
    comision_plataforma: Mapped["ComisionPlataforma | None"] = relationship(
        back_populates="pago_servicio",
        cascade="all, delete-orphan",
        uselist=False,
    )


class DetallePago(Base):
    __tablename__ = "detalle_pago"

    id_detalle_pago: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_pago_servicio: Mapped[int] = mapped_column(
        ForeignKey("pago_servicio.id_pago_servicio"),
        nullable=False,
    )
    id_taller_auxilio: Mapped[int] = mapped_column(
        ForeignKey("taller_auxilio.id_taller_auxilio"),
        nullable=False,
    )
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    pago_servicio: Mapped["PagoServicio"] = relationship(back_populates="detalles_pago")
    taller_auxilio = relationship("TallerAuxilio")


class ComisionPlataforma(Base):
    __tablename__ = "comision_plataforma"

    id_comision: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_pago_servicio: Mapped[int] = mapped_column(
        ForeignKey("pago_servicio.id_pago_servicio"),
        nullable=False,
        unique=True,
    )
    id_taller: Mapped[int] = mapped_column(
        ForeignKey("taller.id_taller"),
        nullable=False,
    )
    porcentaje: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    monto_comision: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    fecha_calculo: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    estado: Mapped[str] = mapped_column(String(50), nullable=False)

    pago_servicio: Mapped["PagoServicio"] = relationship(back_populates="comision_plataforma")
    taller = relationship("Taller")


class CalificacionServicio(Base):
    __tablename__ = "calificacion_servicio"

    id_calificacion: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_incidente: Mapped[int] = mapped_column(
        ForeignKey("incidente.id_incidente"),
        nullable=False,
        unique=True,
    )
    id_cliente: Mapped[int] = mapped_column(
        ForeignKey("cliente.id_cliente"),
        nullable=False,
    )
    id_taller: Mapped[int] = mapped_column(
        ForeignKey("taller.id_taller"),
        nullable=False,
    )
    id_tecnico: Mapped[int | None] = mapped_column(
        ForeignKey("tecnico.id_tecnico"),
        nullable=True,
    )
    puntuacion: Mapped[float] = mapped_column(Numeric(3, 1), nullable=False)
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_calificacion: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    incidente = relationship("Incidente")
    cliente = relationship("Cliente")
    taller = relationship("Taller")
    tecnico = relationship("Tecnico")


class MetricaIncidente(Base):
    __tablename__ = "metrica_incidente"

    id_metrica: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_incidente: Mapped[int] = mapped_column(
        ForeignKey("incidente.id_incidente"),
        nullable=False,
        unique=True,
    )
    tiempo_asignacion_seg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tiempo_llegada_seg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tiempo_resolucion_seg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cantidad_rechazos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fue_reasignado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    incidente = relationship("Incidente")
