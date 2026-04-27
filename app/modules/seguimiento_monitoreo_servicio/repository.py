from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.modules.autenticacion_seguridad.models import Rol, Usuario, UsuarioRol
from app.modules.gestion_incidentes_atencion.models import (
    AsignacionServicio,
    HistorialIncidente,
    Incidente,
    SolicitudTaller,
)
from app.modules.gestion_operativa_taller_tecnico.models import (
    TallerAuxilio,
    Tecnico,
    Taller,
    UnidadMovil,
)
from app.modules.seguimiento_monitoreo_servicio.models import (
    ComisionPlataforma,
    DetallePago,
    Notificacion,
    PagoServicio,
)


def get_incidentes_by_cliente_id(db: Session, id_cliente: int) -> list[Incidente]:
    return list(
        db.execute(
            select(Incidente)
            .options(
                joinedload(Incidente.estado_servicio_actual),
                joinedload(Incidente.asignacion_servicio),
            )
            .where(Incidente.id_cliente == id_cliente)
            .order_by(Incidente.fecha_reporte.desc())
        ).scalars()
    )


def get_incidente_asignacion_by_id_and_cliente(
    db: Session,
    *,
    id_incidente: int,
    id_cliente: int,
) -> Incidente | None:
    return db.execute(
        select(Incidente)
        .options(
            joinedload(Incidente.tipo_incidente),
            joinedload(Incidente.estado_servicio_actual),
            joinedload(Incidente.vehiculo),
            joinedload(Incidente.asignacion_servicio)
            .joinedload(AsignacionServicio.taller.of_type(Taller)),
            joinedload(Incidente.asignacion_servicio)
            .joinedload(AsignacionServicio.tecnico.of_type(Tecnico))
            .joinedload(Tecnico.usuario),
            joinedload(Incidente.asignacion_servicio)
            .joinedload(AsignacionServicio.unidad_movil.of_type(UnidadMovil)),
        )
        .where(
            Incidente.id_incidente == id_incidente,
            Incidente.id_cliente == id_cliente,
        )
    ).scalar_one_or_none()


def get_incidente_pago_context_by_id_and_cliente(
    db: Session,
    *,
    id_incidente: int,
    id_cliente: int,
) -> Incidente | None:
    return db.execute(
        select(Incidente)
        .options(
            joinedload(Incidente.tipo_incidente),
            joinedload(Incidente.estado_servicio_actual),
            joinedload(Incidente.vehiculo),
            joinedload(Incidente.asignacion_servicio)
            .joinedload(AsignacionServicio.taller.of_type(Taller))
            .joinedload(Taller.talleres_auxilio)
            .joinedload(TallerAuxilio.tipo_auxilio),
        )
        .where(
            Incidente.id_incidente == id_incidente,
            Incidente.id_cliente == id_cliente,
        )
    ).unique().scalar_one_or_none()


def get_usuario_by_id(db: Session, id_usuario: int) -> Usuario | None:
    return db.execute(
        select(Usuario).where(Usuario.id_usuario == id_usuario)
    ).scalar_one_or_none()


def get_incidente_by_id(db: Session, id_incidente: int) -> Incidente | None:
    return db.execute(
        select(Incidente).where(Incidente.id_incidente == id_incidente)
    ).scalar_one_or_none()


def get_notificaciones_by_usuario_id(db: Session, id_usuario: int) -> list[Notificacion]:
    return list(
        db.execute(
            select(Notificacion)
            .where(Notificacion.id_usuario == id_usuario)
            .order_by(Notificacion.leido.asc(), Notificacion.fecha_envio.desc())
        ).scalars()
    )


def get_notificacion_by_id_and_usuario(
    db: Session,
    *,
    id_notificacion: int,
    id_usuario: int,
) -> Notificacion | None:
    return db.execute(
        select(Notificacion).where(
            Notificacion.id_notificacion == id_notificacion,
            Notificacion.id_usuario == id_usuario,
        )
    ).scalar_one_or_none()


def get_pago_servicio_by_incidente_id(db: Session, id_incidente: int) -> PagoServicio | None:
    return db.execute(
        select(PagoServicio)
        .options(
            joinedload(PagoServicio.detalles_pago)
            .joinedload(DetallePago.taller_auxilio)
            .joinedload(TallerAuxilio.tipo_auxilio),
            joinedload(PagoServicio.comision_plataforma),
            joinedload(PagoServicio.incidente)
            .joinedload(Incidente.asignacion_servicio)
            .joinedload(AsignacionServicio.taller.of_type(Taller)),
        )
        .where(PagoServicio.id_incidente == id_incidente)
    ).unique().scalar_one_or_none()


def get_pago_servicio_by_id(db: Session, id_pago_servicio: int) -> PagoServicio | None:
    return db.execute(
        select(PagoServicio)
        .options(
            joinedload(PagoServicio.detalles_pago)
            .joinedload(DetallePago.taller_auxilio)
            .joinedload(TallerAuxilio.tipo_auxilio),
            joinedload(PagoServicio.comision_plataforma),
            joinedload(PagoServicio.incidente)
            .joinedload(Incidente.asignacion_servicio)
            .joinedload(AsignacionServicio.taller.of_type(Taller)),
        )
        .where(PagoServicio.id_pago_servicio == id_pago_servicio)
    ).unique().scalar_one_or_none()


def get_pago_servicio_by_referencia_transaccion(
    db: Session,
    referencia_transaccion: str,
) -> PagoServicio | None:
    return db.execute(
        select(PagoServicio)
        .options(
            joinedload(PagoServicio.detalles_pago)
            .joinedload(DetallePago.taller_auxilio)
            .joinedload(TallerAuxilio.tipo_auxilio),
            joinedload(PagoServicio.comision_plataforma),
            joinedload(PagoServicio.incidente)
            .joinedload(Incidente.tipo_incidente),
            joinedload(PagoServicio.incidente)
            .joinedload(Incidente.estado_servicio_actual),
            joinedload(PagoServicio.incidente)
            .joinedload(Incidente.asignacion_servicio)
            .joinedload(AsignacionServicio.taller.of_type(Taller))
            .joinedload(Taller.talleres_auxilio)
            .joinedload(TallerAuxilio.tipo_auxilio),
        )
        .where(PagoServicio.referencia_transaccion == referencia_transaccion)
    ).unique().scalar_one_or_none()


def create_notificacion(
    db: Session,
    *,
    id_usuario: int,
    id_incidente: int | None,
    titulo: str,
    mensaje: str,
    tipo_notificacion: str,
) -> Notificacion:
    notificacion = Notificacion(
        id_usuario=id_usuario,
        id_incidente=id_incidente,
        titulo=titulo,
        mensaje=mensaje,
        tipo_notificacion=tipo_notificacion,
        leido=False,
    )
    db.add(notificacion)
    db.flush()
    db.refresh(notificacion)
    return notificacion


def update_notificacion_leido(
    db: Session,
    notificacion: Notificacion,
    *,
    leido: bool,
) -> Notificacion:
    notificacion.leido = leido
    db.flush()
    db.refresh(notificacion)
    return notificacion


def create_pago_servicio(
    db: Session,
    *,
    id_incidente: int,
    monto_total,
    metodo_pago: str,
    estado_pago: str,
    referencia_transaccion: str | None,
    fecha_pago=None,
) -> PagoServicio:
    pago = PagoServicio(
        id_incidente=id_incidente,
        monto_total=monto_total,
        metodo_pago=metodo_pago,
        estado_pago=estado_pago,
        referencia_transaccion=referencia_transaccion,
        fecha_pago=fecha_pago,
    )
    db.add(pago)
    db.flush()
    db.refresh(pago)
    return pago


def update_pago_servicio(
    db: Session,
    pago_servicio: PagoServicio,
    *,
    monto_total=None,
    metodo_pago: str | None = None,
    estado_pago: str | None = None,
    referencia_transaccion: str | None = None,
    fecha_pago=None,
) -> PagoServicio:
    if monto_total is not None:
        pago_servicio.monto_total = monto_total
    if metodo_pago is not None:
        pago_servicio.metodo_pago = metodo_pago
    if estado_pago is not None:
        pago_servicio.estado_pago = estado_pago
    if referencia_transaccion is not None:
        pago_servicio.referencia_transaccion = referencia_transaccion
    if fecha_pago is not None:
        pago_servicio.fecha_pago = fecha_pago
    db.flush()
    db.refresh(pago_servicio)
    return pago_servicio


def clear_detalles_pago(db: Session, pago_servicio: PagoServicio) -> None:
    for detalle in list(pago_servicio.detalles_pago):
        db.delete(detalle)
    db.flush()


def create_detalle_pago(
    db: Session,
    *,
    id_pago_servicio: int,
    id_taller_auxilio: int,
    descripcion: str,
    cantidad: int,
    precio_unitario,
    subtotal,
) -> DetallePago:
    detalle = DetallePago(
        id_pago_servicio=id_pago_servicio,
        id_taller_auxilio=id_taller_auxilio,
        descripcion=descripcion,
        cantidad=cantidad,
        precio_unitario=precio_unitario,
        subtotal=subtotal,
    )
    db.add(detalle)
    db.flush()
    db.refresh(detalle)
    return detalle


def upsert_comision_plataforma(
    db: Session,
    *,
    pago_servicio: PagoServicio,
    id_taller: int,
    porcentaje,
    monto_comision,
    estado: str,
) -> ComisionPlataforma:
    comision = pago_servicio.comision_plataforma
    if comision is None:
        comision = ComisionPlataforma(
            id_pago_servicio=pago_servicio.id_pago_servicio,
            id_taller=id_taller,
            porcentaje=porcentaje,
            monto_comision=monto_comision,
            estado=estado,
        )
        db.add(comision)
    else:
        comision.id_taller = id_taller
        comision.porcentaje = porcentaje
        comision.monto_comision = monto_comision
        comision.estado = estado
    db.flush()
    db.refresh(comision)
    return comision


def get_roles_by_usuario_id(db: Session, id_usuario: int) -> list[str]:
    return list(
        db.execute(
            select(Rol.nombre)
            .join(UsuarioRol, UsuarioRol.id_rol == Rol.id_rol)
            .where(UsuarioRol.id_usuario == id_usuario)
        ).scalars()
    )


def get_incidentes_historial_all(db: Session) -> list[Incidente]:
    return list(
        db.execute(
            select(Incidente)
            .options(
                joinedload(Incidente.tipo_incidente),
                joinedload(Incidente.estado_servicio_actual),
            )
            .order_by(Incidente.fecha_reporte.desc())
        ).scalars()
    )


def get_incidentes_historial_by_taller_id(db: Session, id_taller: int) -> list[Incidente]:
    return list(
        db.execute(
            select(Incidente)
            .options(
                joinedload(Incidente.tipo_incidente),
                joinedload(Incidente.estado_servicio_actual),
            )
            .outerjoin(AsignacionServicio, AsignacionServicio.id_incidente == Incidente.id_incidente)
            .outerjoin(SolicitudTaller, SolicitudTaller.id_incidente == Incidente.id_incidente)
            .where(
                or_(
                    AsignacionServicio.id_taller == id_taller,
                    and_(
                        SolicitudTaller.id_taller == id_taller,
                        SolicitudTaller.estado_solicitud == "ACEPTADA",
                    ),
                )
            )
            .order_by(Incidente.fecha_reporte.desc())
            .distinct()
        ).scalars()
    )


def get_incidentes_historial_by_tecnico_id(db: Session, id_tecnico: int) -> list[Incidente]:
    return list(
        db.execute(
            select(Incidente)
            .options(
                joinedload(Incidente.tipo_incidente),
                joinedload(Incidente.estado_servicio_actual),
            )
            .join(AsignacionServicio, AsignacionServicio.id_incidente == Incidente.id_incidente)
            .where(AsignacionServicio.id_tecnico == id_tecnico)
            .order_by(Incidente.fecha_reporte.desc())
        ).scalars()
    )


def get_incidente_historial_by_id(db: Session, id_incidente: int) -> Incidente | None:
    return db.execute(
        select(Incidente)
        .options(
            joinedload(Incidente.tipo_incidente),
            joinedload(Incidente.prioridad),
            joinedload(Incidente.estado_servicio_actual),
            joinedload(Incidente.asignacion_servicio)
            .joinedload(AsignacionServicio.taller.of_type(Taller)),
            joinedload(Incidente.asignacion_servicio)
            .joinedload(AsignacionServicio.tecnico.of_type(Tecnico))
            .joinedload(Tecnico.usuario),
            joinedload(Incidente.asignacion_servicio)
            .joinedload(AsignacionServicio.unidad_movil.of_type(UnidadMovil)),
            joinedload(Incidente.historial)
            .joinedload(HistorialIncidente.estado_anterior),
            joinedload(Incidente.historial)
            .joinedload(HistorialIncidente.estado_nuevo),
            joinedload(Incidente.historial)
            .joinedload(HistorialIncidente.usuario_actor),
            joinedload(Incidente.solicitudes_taller)
            .joinedload(SolicitudTaller.taller.of_type(Taller)),
        )
        .where(Incidente.id_incidente == id_incidente)
    ).unique().scalar_one_or_none()
