from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modules.gestion_clientes.models import Vehiculo
from app.modules.gestion_incidentes_atencion.models import (
    AsignacionServicio,
    Evidencia,
    EstadoServicio,
    HistorialIncidente,
    Incidente,
    Prioridad,
    SolicitudTaller,
    TipoIncidente,
)
from app.modules.gestion_operativa_taller_tecnico.models import (
    EspecialidadTipoAuxilio,
    Tecnico,
    TecnicoEspecialidad,
    TipoAuxilio,
    UnidadMovil,
)


def get_tipo_incidente_by_id(db: Session, id_tipo_incidente: int) -> TipoIncidente | None:
    return db.execute(
        select(TipoIncidente).where(TipoIncidente.id_tipo_incidente == id_tipo_incidente)
    ).scalar_one_or_none()


def list_tipos_incidente(db: Session) -> list[TipoIncidente]:
    return list(
        db.execute(
            select(TipoIncidente)
            .where(TipoIncidente.estado == True)
            .order_by(TipoIncidente.nombre.asc())
        ).scalars()
    )


def get_prioridad_by_nombre(db: Session, nombre: str) -> Prioridad | None:
    return db.execute(
        select(Prioridad).where(Prioridad.nombre == nombre)
    ).scalar_one_or_none()


def get_estado_servicio_by_nombre(db: Session, nombre: str) -> EstadoServicio | None:
    return db.execute(
        select(EstadoServicio).where(EstadoServicio.nombre == nombre)
    ).scalar_one_or_none()


def get_estado_servicio_by_id(db: Session, id_estado_servicio: int) -> EstadoServicio | None:
    return db.execute(
        select(EstadoServicio).where(
            EstadoServicio.id_estado_servicio == id_estado_servicio,
            EstadoServicio.estado == True,
        )
    ).scalar_one_or_none()


def get_vehiculo_by_id_and_cliente(db: Session, id_vehiculo: int, id_cliente: int) -> Vehiculo | None:
    return db.execute(
        select(Vehiculo).where(
            Vehiculo.id_vehiculo == id_vehiculo,
            Vehiculo.id_cliente == id_cliente,
        )
    ).scalar_one_or_none()


def create_incidente(
    db: Session,
    *,
    id_cliente: int,
    id_vehiculo: int,
    id_tipo_incidente: int,
    id_prioridad: int,
    id_estado_servicio_actual: int,
    titulo: str,
    descripcion_texto: str | None,
    direccion_referencia: str | None,
    latitud,
    longitud,
) -> Incidente:
    incidente = Incidente(
        id_cliente=id_cliente,
        id_vehiculo=id_vehiculo,
        id_tipo_incidente=id_tipo_incidente,
        id_prioridad=id_prioridad,
        id_estado_servicio_actual=id_estado_servicio_actual,
        titulo=titulo,
        descripcion_texto=descripcion_texto,
        direccion_referencia=direccion_referencia,
        latitud=latitud,
        longitud=longitud,
        clasificacion_ia=None,
        confianza_clasificacion=None,
        resumen_ia=None,
        requiere_mas_info=False,
    )
    db.add(incidente)
    db.flush()
    db.refresh(incidente)
    return incidente


def create_evidencia(
    db: Session,
    *,
    id_incidente: int,
    tipo_evidencia: str,
    archivo_url: str,
    texto_extraido: str | None,
    descripcion: str | None,
) -> Evidencia:
    evidencia = Evidencia(
        id_incidente=id_incidente,
        tipo_evidencia=tipo_evidencia,
        archivo_url=archivo_url,
        texto_extraido=texto_extraido,
        descripcion=descripcion,
    )
    db.add(evidencia)
    db.flush()
    db.refresh(evidencia)
    return evidencia


def get_incidentes_by_cliente_id(db: Session, id_cliente: int) -> list[Incidente]:
    return db.execute(
        select(Incidente).where(Incidente.id_cliente == id_cliente)
    ).scalars().all()


def get_incidente_by_id_and_cliente(db: Session, id_incidente: int, id_cliente: int) -> Incidente | None:
    return db.execute(
        select(Incidente)
        .options(
            joinedload(Incidente.tipo_incidente),
            joinedload(Incidente.prioridad),
            joinedload(Incidente.estado_servicio_actual),
        )
        .where(
            Incidente.id_incidente == id_incidente,
            Incidente.id_cliente == id_cliente,
        )
    ).scalar_one_or_none()

def get_solicitudes_taller_disponibles(db: Session, id_taller: int) -> list[SolicitudTaller]:
    return db.execute(
        select(SolicitudTaller)
        .join(SolicitudTaller.incidente)
        .join(Incidente.estado_servicio_actual)
        .options(
            joinedload(SolicitudTaller.incidente).joinedload(Incidente.tipo_incidente),
            joinedload(SolicitudTaller.incidente).joinedload(Incidente.prioridad),
            joinedload(SolicitudTaller.incidente).joinedload(Incidente.estado_servicio_actual),
        )
        .where(
            SolicitudTaller.id_taller == id_taller,
            SolicitudTaller.estado_solicitud == "PENDIENTE",
            EstadoServicio.nombre.notin_(
                ["ASIGNADO", "EN_CAMINO", "EN_ATENCION", "FINALIZADO", "CANCELADO"]
            ),
        )
        .order_by(SolicitudTaller.fecha_envio.desc())
    ).scalars().all()


def get_incidentes_disponibles_by_taller_id(
    db: Session,
    id_taller: int,
) -> list[SolicitudTaller]:
    return get_solicitudes_taller_disponibles(db, id_taller)


def get_incidente_by_id(db: Session, id_incidente: int) -> Incidente | None:
    return db.execute(
        select(Incidente)
        .options(
            joinedload(Incidente.tipo_incidente),
            joinedload(Incidente.prioridad),
            joinedload(Incidente.estado_servicio_actual),
        )
        .where(Incidente.id_incidente == id_incidente)
    ).scalar_one_or_none()


def get_incidente_by_id_for_update(db: Session, id_incidente: int) -> Incidente | None:
    return db.execute(
        select(Incidente)
        .where(Incidente.id_incidente == id_incidente)
        .with_for_update()
    ).scalar_one_or_none()


def get_solicitud_taller_by_id(db: Session, id_solicitud_taller: int) -> SolicitudTaller | None:
    return db.execute(
        select(SolicitudTaller)
        .options(
            joinedload(SolicitudTaller.incidente).joinedload(Incidente.tipo_incidente),
            joinedload(SolicitudTaller.incidente).joinedload(Incidente.prioridad),
            joinedload(SolicitudTaller.incidente).joinedload(Incidente.estado_servicio_actual),
        )
        .where(SolicitudTaller.id_solicitud_taller == id_solicitud_taller)
    ).scalar_one_or_none()


def get_solicitud_taller_by_id_for_update(
    db: Session,
    id_solicitud_taller: int,
) -> SolicitudTaller | None:
    return db.execute(
        select(SolicitudTaller)
        .where(SolicitudTaller.id_solicitud_taller == id_solicitud_taller)
        .with_for_update()
    ).scalar_one_or_none()


def get_solicitud_aceptada_by_incidente_id(
    db: Session,
    id_incidente: int,
) -> SolicitudTaller | None:
    return db.execute(
        select(SolicitudTaller).where(
            SolicitudTaller.id_incidente == id_incidente,
            SolicitudTaller.estado_solicitud == "ACEPTADA",
        )
    ).scalar_one_or_none()


def get_solicitud_aceptada_by_incidente_and_taller_id(
    db: Session,
    *,
    id_incidente: int,
    id_taller: int,
) -> SolicitudTaller | None:
    return db.execute(
        select(SolicitudTaller).where(
            SolicitudTaller.id_incidente == id_incidente,
            SolicitudTaller.id_taller == id_taller,
            SolicitudTaller.estado_solicitud == "ACEPTADA",
        )
    ).scalar_one_or_none()


def get_asignacion_servicio_by_incidente_id(
    db: Session,
    id_incidente: int,
) -> AsignacionServicio | None:
    return db.execute(
        select(AsignacionServicio).where(AsignacionServicio.id_incidente == id_incidente)
    ).scalar_one_or_none()


def get_asignaciones_servicio_by_tecnico_id(
    db: Session,
    id_tecnico: int,
) -> list[AsignacionServicio]:
    return list(
        db.execute(
            select(AsignacionServicio)
            .options(
                joinedload(AsignacionServicio.incidente).joinedload(Incidente.tipo_incidente),
                joinedload(AsignacionServicio.incidente).joinedload(Incidente.prioridad),
                joinedload(AsignacionServicio.incidente).joinedload(Incidente.estado_servicio_actual),
            )
            .where(AsignacionServicio.id_tecnico == id_tecnico)
            .order_by(AsignacionServicio.fecha_asignacion.desc())
        ).scalars()
    )


def get_asignacion_servicio_detalle_by_incidente_and_tecnico_id(
    db: Session,
    *,
    id_incidente: int,
    id_tecnico: int,
) -> AsignacionServicio | None:
    return db.execute(
        select(AsignacionServicio)
        .options(
            joinedload(AsignacionServicio.incidente).joinedload(Incidente.tipo_incidente),
            joinedload(AsignacionServicio.incidente).joinedload(Incidente.prioridad),
            joinedload(AsignacionServicio.incidente).joinedload(Incidente.estado_servicio_actual),
            joinedload(AsignacionServicio.incidente).joinedload(Incidente.evidencias),
            joinedload(AsignacionServicio.incidente)
            .joinedload(Incidente.vehiculo)
            .joinedload(Vehiculo.tipo_vehiculo),
        )
        .where(
            AsignacionServicio.id_incidente == id_incidente,
            AsignacionServicio.id_tecnico == id_tecnico,
        )
    ).scalar_one_or_none()


def get_asignacion_servicio_by_incidente_id_for_update(
    db: Session,
    id_incidente: int,
) -> AsignacionServicio | None:
    return db.execute(
        select(AsignacionServicio)
        .where(AsignacionServicio.id_incidente == id_incidente)
        .with_for_update()
    ).scalar_one_or_none()


def get_tecnicos_disponibles_by_taller_id(db: Session, id_taller: int) -> list[Tecnico]:
    return list(
        db.execute(
            select(Tecnico)
            .options(joinedload(Tecnico.usuario))
            .where(
                Tecnico.id_taller == id_taller,
                Tecnico.disponible == True,
                Tecnico.estado == True,
            )
            .order_by(Tecnico.id_tecnico.asc())
        ).scalars()
    )


def get_tipo_auxilio_by_nombre(db: Session, nombre: str) -> TipoAuxilio | None:
    return db.execute(
        select(TipoAuxilio).where(
            TipoAuxilio.nombre == nombre,
            TipoAuxilio.estado == True,
        )
    ).scalar_one_or_none()


def get_tecnicos_disponibles_by_taller_id_and_tipo_auxilio(
    db: Session,
    *,
    id_taller: int,
    id_tipo_auxilio: int,
) -> list[Tecnico]:
    return list(
        db.execute(
            select(Tecnico)
            .join(
                TecnicoEspecialidad,
                TecnicoEspecialidad.id_tecnico == Tecnico.id_tecnico,
            )
            .join(
                EspecialidadTipoAuxilio,
                EspecialidadTipoAuxilio.id_especialidad
                == TecnicoEspecialidad.id_especialidad,
            )
            .options(joinedload(Tecnico.usuario))
            .where(
                Tecnico.id_taller == id_taller,
                Tecnico.disponible == True,
                Tecnico.estado == True,
                EspecialidadTipoAuxilio.id_tipo_auxilio == id_tipo_auxilio,
            )
            .order_by(Tecnico.id_tecnico.asc())
            .distinct()
        ).scalars()
    )


def get_unidades_moviles_disponibles_by_taller_id(db: Session, id_taller: int) -> list[UnidadMovil]:
    return list(
        db.execute(
            select(UnidadMovil)
            .where(
                UnidadMovil.id_taller == id_taller,
                UnidadMovil.disponible == True,
                UnidadMovil.estado == True,
            )
            .order_by(UnidadMovil.id_unidad_movil.asc())
        ).scalars()
    )


def get_tecnico_by_id_for_update(db: Session, id_tecnico: int) -> Tecnico | None:
    return db.execute(
        select(Tecnico)
        .where(Tecnico.id_tecnico == id_tecnico)
        .with_for_update()
    ).scalar_one_or_none()


def get_unidad_movil_by_id_for_update(db: Session, id_unidad_movil: int) -> UnidadMovil | None:
    return db.execute(
        select(UnidadMovil)
        .where(UnidadMovil.id_unidad_movil == id_unidad_movil)
        .with_for_update()
    ).scalar_one_or_none()


def update_solicitud_taller_respuesta(
    db: Session,
    solicitud_taller: SolicitudTaller,
    *,
    estado_solicitud: str,
) -> SolicitudTaller:
    solicitud_taller.estado_solicitud = estado_solicitud
    solicitud_taller.fecha_respuesta = datetime.utcnow()
    db.flush()
    db.refresh(solicitud_taller)
    return solicitud_taller


def cancel_pending_solicitudes_by_incidente_except(
    db: Session,
    *,
    id_incidente: int,
    exclude_id_solicitud_taller: int,
) -> list[SolicitudTaller]:
    solicitudes = list(
        db.execute(
            select(SolicitudTaller)
            .where(
                SolicitudTaller.id_incidente == id_incidente,
                SolicitudTaller.id_solicitud_taller != exclude_id_solicitud_taller,
                SolicitudTaller.estado_solicitud == "PENDIENTE",
            )
        ).scalars()
    )
    for solicitud in solicitudes:
        solicitud.estado_solicitud = "CANCELADA"
        solicitud.fecha_respuesta = datetime.utcnow()
    db.flush()
    return solicitudes


def update_incidente_estado_servicio_actual(
    db: Session,
    incidente: Incidente,
    *,
    id_estado_servicio_actual: int,
) -> Incidente:
    incidente.id_estado_servicio_actual = id_estado_servicio_actual
    db.flush()
    db.refresh(incidente)
    return incidente


def create_asignacion_servicio(
    db: Session,
    *,
    id_incidente: int,
    id_taller: int,
    id_tecnico: int,
    id_unidad_movil: int | None,
    tiempo_estimado_min: int | None,
    estado_asignacion: str,
    observaciones: str | None,
) -> AsignacionServicio:
    asignacion = AsignacionServicio(
        id_incidente=id_incidente,
        id_taller=id_taller,
        id_tecnico=id_tecnico,
        id_unidad_movil=id_unidad_movil,
        tiempo_estimado_min=tiempo_estimado_min,
        estado_asignacion=estado_asignacion,
        observaciones=observaciones,
    )
    db.add(asignacion)
    db.flush()
    db.refresh(asignacion)
    return asignacion


def update_tecnico_disponibilidad(
    db: Session,
    tecnico: Tecnico,
    *,
    disponible: bool,
) -> Tecnico:
    tecnico.disponible = disponible
    db.flush()
    db.refresh(tecnico)
    return tecnico


def update_unidad_movil_disponibilidad(
    db: Session,
    unidad_movil: UnidadMovil,
    *,
    disponible: bool,
) -> UnidadMovil:
    unidad_movil.disponible = disponible
    db.flush()
    db.refresh(unidad_movil)
    return unidad_movil


def update_asignacion_servicio_estado(
    db: Session,
    asignacion_servicio: AsignacionServicio,
    *,
    estado_asignacion: str,
) -> AsignacionServicio:
    asignacion_servicio.estado_asignacion = estado_asignacion
    db.flush()
    db.refresh(asignacion_servicio)
    return asignacion_servicio


def create_historial_incidente(
    db: Session,
    *,
    id_incidente: int,
    id_estado_anterior: int | None,
    id_estado_nuevo: int,
    id_usuario_actor: int,
    detalle: str | None,
) -> HistorialIncidente:
    historial = HistorialIncidente(
        id_incidente=id_incidente,
        id_estado_anterior=id_estado_anterior,
        id_estado_nuevo=id_estado_nuevo,
        id_usuario_actor=id_usuario_actor,
        detalle=detalle,
    )
    db.add(historial)
    db.flush()
    db.refresh(historial)
    return historial
