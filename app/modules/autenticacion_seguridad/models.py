from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.session import Base
def ahora_bolivia() -> datetime:
    return datetime.now(ZoneInfo("America/La_Paz")).replace(tzinfo=None)

class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    nombres: Mapped[str] = mapped_column(String(100), nullable=False)
    apellidos: Mapped[str] = mapped_column(String(100), nullable=False)
    celular: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=ahora_bolivia,
    )

    usuario_roles: Mapped[list["UsuarioRol"]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
    )
    bitacoras: Mapped[list["BitacoraSistema"]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
    )


class Rol(Base):
    __tablename__ = "rol"

    id_rol: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)

    usuario_roles: Mapped[list["UsuarioRol"]] = relationship(
        back_populates="rol",
        cascade="all, delete-orphan",
    )


class UsuarioRol(Base):
    __tablename__ = "usuario_rol"
    __table_args__ = (
        UniqueConstraint("id_usuario", "id_rol", name="uq_usuario_rol"),
    )

    id_usuario_rol: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario"),
        nullable=False,
    )
    id_rol: Mapped[int] = mapped_column(
        ForeignKey("rol.id_rol"),
        nullable=False,
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="usuario_roles")
    rol: Mapped["Rol"] = relationship(back_populates="usuario_roles")


class BitacoraSistema(Base):
    __tablename__ = "bitacora_sistema"

    id_bitacora: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario"),
        nullable=False,
    )
    accion: Mapped[str] = mapped_column(String(100), nullable=False)
    modulo: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_hora: Mapped[datetime] = mapped_column(
    DateTime,
    nullable=False,
    default=ahora_bolivia,
    )
    ip_origen: Mapped[str | None] = mapped_column(String(45), nullable=True)

    usuario: Mapped["Usuario"] = relationship(back_populates="bitacoras")
    