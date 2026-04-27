from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.gestion_clientes.models import Cliente, TipoVehiculo, Vehiculo
from app.modules.gestion_incidentes_atencion.models import AsignacionServicio, Incidente
from app.modules.seguimiento_monitoreo_servicio.models import CalificacionServicio


def get_cliente_by_usuario_id(db: Session, id_usuario: int) -> Cliente | None:
    return db.execute(
        select(Cliente).where(Cliente.id_usuario == id_usuario)
    ).scalar_one_or_none()


def get_tipo_vehiculo_by_id(db: Session, id_tipo_vehiculo: int) -> TipoVehiculo | None:
    return db.execute(
        select(TipoVehiculo).where(TipoVehiculo.id_tipo_vehiculo == id_tipo_vehiculo)
    ).scalar_one_or_none()


def list_tipos_vehiculo(db: Session) -> list[TipoVehiculo]:
    return list(
        db.execute(
            select(TipoVehiculo).order_by(TipoVehiculo.nombre.asc())
        ).scalars()
    )


def get_vehiculo_by_placa(db: Session, placa: str) -> Vehiculo | None:
    return db.execute(
        select(Vehiculo).where(Vehiculo.placa == placa)
    ).scalar_one_or_none()


def create_vehiculo(
    db: Session,
    *,
    id_cliente: int,
    id_tipo_vehiculo: int,
    placa: str,
    marca: str,
    modelo: str,
    anio: int,
    color: str | None,
    descripcion_referencia: str | None,
) -> Vehiculo:
    vehiculo = Vehiculo(
        id_cliente=id_cliente,
        id_tipo_vehiculo=id_tipo_vehiculo,
        placa=placa,
        marca=marca,
        modelo=modelo,
        anio=anio,
        color=color,
        descripcion_referencia=descripcion_referencia,
        estado=True,
    )
    db.add(vehiculo)
    db.flush()
    db.refresh(vehiculo)
    return vehiculo


def get_vehiculos_by_cliente_id(db: Session, id_cliente: int) -> list[Vehiculo]:
    return db.execute(
        select(Vehiculo).where(Vehiculo.id_cliente == id_cliente)
    ).scalars().all()


def get_incidentes_finalizados_pendientes_calificacion(
    db: Session, id_cliente: int
) -> list[Incidente]:
    # Estado finalizado: orden_flujo = 7
    from sqlalchemy import exists
    subquery = select(CalificacionServicio.id_calificacion).where(
        CalificacionServicio.id_incidente == Incidente.id_incidente
    )
    return list(
        db.execute(
            select(Incidente)
            .where(
                Incidente.id_cliente == id_cliente,
                Incidente.id_estado_servicio_actual == 7,  # FINALIZADO
                ~exists(subquery),  # No existe calificación
            )
        ).scalars()
    )


def get_incidente_by_id(db: Session, id_incidente: int) -> Incidente | None:
    return db.execute(
        select(Incidente).where(Incidente.id_incidente == id_incidente)
    ).scalar_one_or_none()


def get_asignacion_by_incidente_id(
    db: Session, id_incidente: int
) -> AsignacionServicio | None:
    return db.execute(
        select(AsignacionServicio).where(
            AsignacionServicio.id_incidente == id_incidente
        )
    ).scalar_one_or_none()


def get_calificacion_by_incidente_id(
    db: Session, id_incidente: int
) -> CalificacionServicio | None:
    return db.execute(
        select(CalificacionServicio).where(
            CalificacionServicio.id_incidente == id_incidente
        )
    ).scalar_one_or_none()


def create_calificacion(
    db: Session,
    *,
    id_incidente: int,
    id_cliente: int,
    id_taller: int,
    id_tecnico: int | None,
    puntuacion: float,
    comentario: str | None,
) -> CalificacionServicio:
    calificacion = CalificacionServicio(
        id_incidente=id_incidente,
        id_cliente=id_cliente,
        id_taller=id_taller,
        id_tecnico=id_tecnico,
        puntuacion=puntuacion,
        comentario=comentario,
    )
    db.add(calificacion)
    db.flush()
    db.refresh(calificacion)
    return calificacion


def get_cliente_by_usuario_id(db: Session, id_usuario: int) -> Cliente | None:
    return db.execute(
        select(Cliente).where(Cliente.id_usuario == id_usuario)
    ).scalar_one_or_none()
