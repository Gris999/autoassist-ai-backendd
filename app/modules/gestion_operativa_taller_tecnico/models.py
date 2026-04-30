from datetime import datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.session import Base


class TipoTaller(Base):
    __tablename__ = "tipo_taller"

    id_tipo_taller: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)

    talleres: Mapped[list["Taller"]] = relationship(
        back_populates="tipo_taller",
    )


class Taller(Base):
    __tablename__ = "taller"

    id_taller: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario"),
        nullable=False,
        unique=True,
    )
    id_tipo_taller: Mapped[int] = mapped_column(
        ForeignKey("tipo_taller.id_tipo_taller"),
        nullable=False,
    )
    nombre_taller: Mapped[str] = mapped_column(String(150), nullable=False)
    nit: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    direccion: Mapped[str] = mapped_column(String(255), nullable=False)
    latitud: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitud: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    radio_cobertura_km: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    disponible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    usuario = relationship("Usuario")
    tipo_taller: Mapped["TipoTaller"] = relationship(back_populates="talleres")
    tecnicos: Mapped[list["Tecnico"]] = relationship(
        back_populates="taller",
        cascade="all, delete-orphan",
    )
    unidades_moviles: Mapped[list["UnidadMovil"]] = relationship(
        back_populates="taller",
        cascade="all, delete-orphan",
    )
    talleres_tipo_vehiculo: Mapped[list["TallerTipoVehiculo"]] = relationship(
        back_populates="taller",
        cascade="all, delete-orphan",
    )
    talleres_auxilio: Mapped[list["TallerAuxilio"]] = relationship(
        back_populates="taller",
        cascade="all, delete-orphan",
    )
    horarios_disponibilidad: Mapped[list["HorarioDisponibilidadTaller"]] = relationship(
        back_populates="taller",
        cascade="all, delete-orphan",
    )


class HorarioDisponibilidadTaller(Base):
    __tablename__ = "horario_disponibilidad_taller"
    __table_args__ = (
        UniqueConstraint(
            "id_taller",
            "dia_semana",
            "hora_inicio",
            "hora_fin",
            name="uq_taller_horario_disponibilidad",
        ),
    )

    id_horario_disponibilidad: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_taller: Mapped[int] = mapped_column(
        ForeignKey("taller.id_taller"),
        nullable=False,
    )
    dia_semana: Mapped[str] = mapped_column(String(15), nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time] = mapped_column(Time, nullable=False)
    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    taller: Mapped["Taller"] = relationship(back_populates="horarios_disponibilidad")


class Tecnico(Base):
    __tablename__ = "tecnico"

    id_tecnico: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario"),
        nullable=False,
        unique=True,
    )
    id_taller: Mapped[int] = mapped_column(
        ForeignKey("taller.id_taller"),
        nullable=False,
    )
    telefono_contacto: Mapped[str] = mapped_column(String(20), nullable=False)
    disponible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    latitud_actual: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitud_actual: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)

    usuario = relationship("Usuario")
    taller: Mapped["Taller"] = relationship(back_populates="tecnicos")
    tecnico_especialidades: Mapped[list["TecnicoEspecialidad"]] = relationship(
        back_populates="tecnico",
        cascade="all, delete-orphan",
    )


class Especialidad(Base):
    __tablename__ = "especialidad"

    id_especialidad: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)

    tecnico_especialidades: Mapped[list["TecnicoEspecialidad"]] = relationship(
        back_populates="especialidad",
        cascade="all, delete-orphan",
    )
    especialidad_tipos_auxilio: Mapped[list["EspecialidadTipoAuxilio"]] = relationship(
        back_populates="especialidad",
        cascade="all, delete-orphan",
    )


class TecnicoEspecialidad(Base):
    __tablename__ = "tecnico_especialidad"
    __table_args__ = (
        UniqueConstraint("id_tecnico", "id_especialidad", name="uq_tecnico_especialidad"),
    )

    id_tecnico_especialidad: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_tecnico: Mapped[int] = mapped_column(
        ForeignKey("tecnico.id_tecnico"),
        nullable=False,
    )
    id_especialidad: Mapped[int] = mapped_column(
        ForeignKey("especialidad.id_especialidad"),
        nullable=False,
    )

    tecnico: Mapped["Tecnico"] = relationship(back_populates="tecnico_especialidades")
    especialidad: Mapped["Especialidad"] = relationship(back_populates="tecnico_especialidades")


class UnidadMovil(Base):
    __tablename__ = "unidad_movil"

    id_unidad_movil: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_taller: Mapped[int] = mapped_column(
        ForeignKey("taller.id_taller"),
        nullable=False,
    )
    placa: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    tipo_unidad: Mapped[str] = mapped_column(String(100), nullable=False)
    disponible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    latitud_actual: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitud_actual: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    taller: Mapped["Taller"] = relationship(back_populates="unidades_moviles")


class TallerTipoVehiculo(Base):
    __tablename__ = "taller_tipo_vehiculo"
    __table_args__ = (
        UniqueConstraint("id_taller", "id_tipo_vehiculo", name="uq_taller_tipo_vehiculo"),
    )

    id_taller_tipo_vehiculo: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_taller: Mapped[int] = mapped_column(
        ForeignKey("taller.id_taller"),
        nullable=False,
    )
    id_tipo_vehiculo: Mapped[int] = mapped_column(
        ForeignKey("tipo_vehiculo.id_tipo_vehiculo"),
        nullable=False,
    )

    taller: Mapped["Taller"] = relationship(back_populates="talleres_tipo_vehiculo")
    tipo_vehiculo = relationship("TipoVehiculo")


class TipoAuxilio(Base):
    __tablename__ = "tipo_auxilio"

    id_tipo_auxilio: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requiere_unidad_movil: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requiere_remolque: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    talleres_auxilio: Mapped[list["TallerAuxilio"]] = relationship(
        back_populates="tipo_auxilio",
        cascade="all, delete-orphan",
    )
    especialidad_tipos_auxilio: Mapped[list["EspecialidadTipoAuxilio"]] = relationship(
        back_populates="tipo_auxilio",
        cascade="all, delete-orphan",
    )


class TallerAuxilio(Base):
    __tablename__ = "taller_auxilio"
    __table_args__ = (
        UniqueConstraint("id_taller", "id_tipo_auxilio", name="uq_taller_tipo_auxilio"),
    )

    id_taller_auxilio: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_taller: Mapped[int] = mapped_column(
        ForeignKey("taller.id_taller"),
        nullable=False,
    )
    id_tipo_auxilio: Mapped[int] = mapped_column(
        ForeignKey("tipo_auxilio.id_tipo_auxilio"),
        nullable=False,
    )
    precio_referencial: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    disponible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    taller: Mapped["Taller"] = relationship(back_populates="talleres_auxilio")
    tipo_auxilio: Mapped["TipoAuxilio"] = relationship(back_populates="talleres_auxilio")


class EspecialidadTipoAuxilio(Base):
    __tablename__ = "especialidad_tipo_auxilio"
    __table_args__ = (
        UniqueConstraint(
            "id_especialidad",
            "id_tipo_auxilio",
            name="uq_especialidad_tipo_auxilio",
        ),
    )

    id_especialidad_tipo_auxilio: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_especialidad: Mapped[int] = mapped_column(
        ForeignKey("especialidad.id_especialidad"),
        nullable=False,
    )
    id_tipo_auxilio: Mapped[int] = mapped_column(
        ForeignKey("tipo_auxilio.id_tipo_auxilio"),
        nullable=False,
    )

    especialidad: Mapped["Especialidad"] = relationship(
        back_populates="especialidad_tipos_auxilio"
    )
    tipo_auxilio: Mapped["TipoAuxilio"] = relationship(
        back_populates="especialidad_tipos_auxilio"
    )
