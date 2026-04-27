from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modules.autenticacion_seguridad.models import Usuario
from app.modules.gestion_clientes.models import TipoVehiculo
from app.modules.gestion_incidentes_atencion.models import (
    AsignacionServicio,
    EstadoServicio,
    Incidente,
)
from app.modules.gestion_operativa_taller_tecnico.models import (
    HorarioDisponibilidadTaller,
    Especialidad,
    Taller,
    TallerAuxilio,
    Tecnico,
    TecnicoEspecialidad,
    TallerTipoVehiculo,
    TipoAuxilio,
    UnidadMovil,
)


def get_taller_by_usuario_id(db: Session, id_usuario: int) -> Taller | None:
    return db.execute(
        select(Taller).where(Taller.id_usuario == id_usuario)
    ).scalar_one_or_none()


def get_taller_by_id(db: Session, id_taller: int) -> Taller | None:
    return db.execute(
        select(Taller).where(Taller.id_taller == id_taller)
    ).scalar_one_or_none()


def update_disponibilidad_taller(
    db: Session,
    *,
    id_taller: int,
    disponible: bool,
    latitud: float | None = None,
    longitud: float | None = None,
    radio_cobertura_km: float | None = None,
) -> Taller:
    taller = get_taller_by_id(db, id_taller)
    if taller:
        taller.disponible = disponible
        if latitud is not None:
            taller.latitud = latitud
        if longitud is not None:
            taller.longitud = longitud
        if radio_cobertura_km is not None:
            taller.radio_cobertura_km = radio_cobertura_km
        db.flush()
        db.refresh(taller)
    return taller


def get_talleres_disponibles(db: Session) -> list[Taller]:
    return list(
        db.execute(
            select(Taller).where(Taller.disponible == True)
        ).scalars()
    )


def get_horarios_disponibilidad_by_taller_id(
    db: Session,
    id_taller: int,
) -> list[HorarioDisponibilidadTaller]:
    return list(
        db.execute(
            select(HorarioDisponibilidadTaller)
            .where(HorarioDisponibilidadTaller.id_taller == id_taller)
            .order_by(
                HorarioDisponibilidadTaller.dia_semana.asc(),
                HorarioDisponibilidadTaller.hora_inicio.asc(),
            )
        ).scalars()
    )


def create_horario_disponibilidad_taller(
    db: Session,
    *,
    id_taller: int,
    dia_semana: str,
    hora_inicio,
    hora_fin,
    estado: bool,
) -> HorarioDisponibilidadTaller:
    horario = HorarioDisponibilidadTaller(
        id_taller=id_taller,
        dia_semana=dia_semana,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        estado=estado,
    )
    db.add(horario)
    db.flush()
    db.refresh(horario)
    return horario


def delete_horarios_disponibilidad_by_taller_id(
    db: Session,
    *,
    id_taller: int,
) -> None:
    horarios = db.execute(
        select(HorarioDisponibilidadTaller).where(
            HorarioDisponibilidadTaller.id_taller == id_taller
        )
    ).scalars().all()

    for horario in horarios:
        db.delete(horario)

    db.flush()


def get_tipo_auxilio_by_id(db: Session, id_tipo_auxilio: int) -> TipoAuxilio | None:
    return db.execute(
        select(TipoAuxilio).where(
            TipoAuxilio.id_tipo_auxilio == id_tipo_auxilio,
            TipoAuxilio.estado == True,
        )
    ).scalar_one_or_none()


def get_servicios_auxilio_por_taller_id(db: Session, id_taller: int) -> list[TallerAuxilio]:
    return list(
        db.execute(
            select(TallerAuxilio).where(TallerAuxilio.id_taller == id_taller)
        ).scalars()
    )


def get_taller_auxilio_by_id(db: Session, id_taller_auxilio: int) -> TallerAuxilio | None:
    return db.execute(
        select(TallerAuxilio).where(
            TallerAuxilio.id_taller_auxilio == id_taller_auxilio
        )
    ).scalar_one_or_none()


def get_taller_auxilio_by_taller_id_tipo_auxilio(
    db: Session,
    id_taller: int,
    id_tipo_auxilio: int,
) -> TallerAuxilio | None:
    return db.execute(
        select(TallerAuxilio).where(
            TallerAuxilio.id_taller == id_taller,
            TallerAuxilio.id_tipo_auxilio == id_tipo_auxilio,
        )
    ).scalar_one_or_none()


def create_taller_auxilio(
    db: Session,
    *,
    id_taller: int,
    id_tipo_auxilio: int,
    precio_referencial: float,
    disponible: bool,
) -> TallerAuxilio:
    servicio = TallerAuxilio(
        id_taller=id_taller,
        id_tipo_auxilio=id_tipo_auxilio,
        precio_referencial=precio_referencial,
        disponible=disponible,
    )
    db.add(servicio)
    db.flush()
    db.refresh(servicio)
    return servicio


def update_taller_auxilio(
    db: Session,
    taller_auxilio: TallerAuxilio,
    *,
    precio_referencial: float | None = None,
    disponible: bool | None = None,
) -> TallerAuxilio:
    if precio_referencial is not None:
        taller_auxilio.precio_referencial = precio_referencial
    if disponible is not None:
        taller_auxilio.disponible = disponible
    db.flush()
    db.refresh(taller_auxilio)
    return taller_auxilio


def set_disponibilidad_taller_auxilio(
    db: Session,
    taller_auxilio: TallerAuxilio,
    disponible: bool,
) -> TallerAuxilio:
    taller_auxilio.disponible = disponible
    db.flush()
    db.refresh(taller_auxilio)
    return taller_auxilio


def get_tecnico_by_usuario_id(db: Session, id_usuario: int) -> Tecnico | None:
    return db.execute(
        select(Tecnico).where(Tecnico.id_usuario == id_usuario)
    ).scalar_one_or_none()


def get_tecnico_by_id(db: Session, id_tecnico: int) -> Tecnico | None:
    return db.execute(
        select(Tecnico).where(Tecnico.id_tecnico == id_tecnico)
    ).scalar_one_or_none()


def get_tecnicos_by_taller_id(db: Session, id_taller: int) -> list[Tecnico]:
    return list(
        db.execute(
            select(Tecnico)
            .options(joinedload(Tecnico.usuario))
            .where(Tecnico.id_taller == id_taller)
            .order_by(Tecnico.id_tecnico.desc())
        ).scalars()
    )


def get_tecnico_with_usuario_by_id(db: Session, id_tecnico: int) -> Tecnico | None:
    return db.execute(
        select(Tecnico)
        .options(joinedload(Tecnico.usuario))
        .where(Tecnico.id_tecnico == id_tecnico)
    ).scalar_one_or_none()


def update_disponibilidad_tecnico(
    db: Session,
    *,
    id_tecnico: int,
    disponible: bool,
) -> Tecnico:
    tecnico = get_tecnico_by_id(db, id_tecnico)
    if tecnico:
        tecnico.disponible = disponible
        db.flush()
        db.refresh(tecnico)
    return tecnico


def get_tecnicos_disponibles(db: Session) -> list[Tecnico]:
    return list(
        db.execute(
            select(Tecnico).where(Tecnico.disponible == True, Tecnico.estado == True)
        ).scalars()
    )


def create_tecnico(
    db: Session,
    *,
    id_usuario: int,
    id_taller: int,
    telefono_contacto: str,
    disponible: bool,
    estado: bool,
) -> Tecnico:
    tecnico = Tecnico(
        id_usuario=id_usuario,
        id_taller=id_taller,
        telefono_contacto=telefono_contacto,
        disponible=disponible,
        estado=estado,
    )
    db.add(tecnico)
    db.flush()
    db.refresh(tecnico)
    return tecnico


def update_usuario_tecnico(
    db: Session,
    usuario: Usuario,
    *,
    nombres: str | None = None,
    apellidos: str | None = None,
    celular: str | None = None,
    email: str | None = None,
    estado: bool | None = None,
) -> Usuario:
    if nombres is not None:
        usuario.nombres = nombres
    if apellidos is not None:
        usuario.apellidos = apellidos
    if celular is not None:
        usuario.celular = celular
    if email is not None:
        usuario.email = email
    if estado is not None:
        usuario.estado = estado
    db.flush()
    db.refresh(usuario)
    return usuario


def update_tecnico(
    db: Session,
    tecnico: Tecnico,
    *,
    telefono_contacto: str | None = None,
    disponible: bool | None = None,
    latitud_actual: float | None = None,
    longitud_actual: float | None = None,
) -> Tecnico:
    if telefono_contacto is not None:
        tecnico.telefono_contacto = telefono_contacto
    if disponible is not None:
        tecnico.disponible = disponible
    if latitud_actual is not None:
        tecnico.latitud_actual = latitud_actual
    if longitud_actual is not None:
        tecnico.longitud_actual = longitud_actual
    db.flush()
    db.refresh(tecnico)
    return tecnico


def update_estado_tecnico(
    db: Session,
    tecnico: Tecnico,
    *,
    estado: bool,
) -> Tecnico:
    tecnico.estado = estado
    if not estado:
        tecnico.disponible = False
    db.flush()
    db.refresh(tecnico)
    return tecnico


def get_unidades_moviles_by_taller_id(db: Session, id_taller: int) -> list[UnidadMovil]:
    return list(
        db.execute(
            select(UnidadMovil)
            .where(UnidadMovil.id_taller == id_taller)
            .order_by(UnidadMovil.id_unidad_movil.desc())
        ).scalars()
    )


def get_unidad_movil_by_id(db: Session, id_unidad_movil: int) -> UnidadMovil | None:
    return db.execute(
        select(UnidadMovil).where(UnidadMovil.id_unidad_movil == id_unidad_movil)
    ).scalar_one_or_none()


def get_unidad_movil_by_placa(db: Session, placa: str) -> UnidadMovil | None:
    return db.execute(
        select(UnidadMovil).where(UnidadMovil.placa == placa)
    ).scalar_one_or_none()


def create_unidad_movil(
    db: Session,
    *,
    id_taller: int,
    placa: str,
    tipo_unidad: str,
    disponible: bool,
    estado: bool,
    latitud_actual: float | None = None,
    longitud_actual: float | None = None,
) -> UnidadMovil:
    unidad_movil = UnidadMovil(
        id_taller=id_taller,
        placa=placa,
        tipo_unidad=tipo_unidad,
        disponible=disponible,
        estado=estado,
        latitud_actual=latitud_actual,
        longitud_actual=longitud_actual,
    )
    db.add(unidad_movil)
    db.flush()
    db.refresh(unidad_movil)
    return unidad_movil


def update_unidad_movil(
    db: Session,
    unidad_movil: UnidadMovil,
    *,
    placa: str | None = None,
    tipo_unidad: str | None = None,
    disponible: bool | None = None,
    estado: bool | None = None,
    latitud_actual: float | None = None,
    longitud_actual: float | None = None,
) -> UnidadMovil:
    if placa is not None:
        unidad_movil.placa = placa
    if tipo_unidad is not None:
        unidad_movil.tipo_unidad = tipo_unidad
    if estado is not None:
        unidad_movil.estado = estado
    if disponible is not None:
        unidad_movil.disponible = disponible
    if latitud_actual is not None:
        unidad_movil.latitud_actual = latitud_actual
    if longitud_actual is not None:
        unidad_movil.longitud_actual = longitud_actual
    if unidad_movil.estado is False:
        unidad_movil.disponible = False
    db.flush()
    db.refresh(unidad_movil)
    return unidad_movil


def get_especialidades_disponibles(db: Session) -> list[Especialidad]:
    return list(
        db.execute(
            select(Especialidad).order_by(Especialidad.nombre.asc())
        ).scalars()
    )


def get_especialidades_by_ids(db: Session, ids_especialidad: list[int]) -> list[Especialidad]:
    if not ids_especialidad:
        return []
    return list(
        db.execute(
            select(Especialidad).where(Especialidad.id_especialidad.in_(ids_especialidad))
        ).scalars()
    )


def get_tecnico_especialidades_by_tecnico_id(
    db: Session,
    id_tecnico: int,
) -> list[TecnicoEspecialidad]:
    return list(
        db.execute(
            select(TecnicoEspecialidad)
            .options(joinedload(TecnicoEspecialidad.especialidad))
            .where(TecnicoEspecialidad.id_tecnico == id_tecnico)
            .order_by(TecnicoEspecialidad.id_tecnico_especialidad.asc())
        ).scalars()
    )


def create_tecnico_especialidad(
    db: Session,
    *,
    id_tecnico: int,
    id_especialidad: int,
) -> TecnicoEspecialidad:
    tecnico_especialidad = TecnicoEspecialidad(
        id_tecnico=id_tecnico,
        id_especialidad=id_especialidad,
    )
    db.add(tecnico_especialidad)
    db.flush()
    db.refresh(tecnico_especialidad)
    return tecnico_especialidad


def delete_tecnico_especialidades_by_ids(
    db: Session,
    *,
    id_tecnico: int,
    ids_especialidad: list[int],
) -> None:
    if not ids_especialidad:
        return

    tecnico_especialidades = db.execute(
        select(TecnicoEspecialidad).where(
            TecnicoEspecialidad.id_tecnico == id_tecnico,
            TecnicoEspecialidad.id_especialidad.in_(ids_especialidad),
        )
    ).scalars().all()

    for tecnico_especialidad in tecnico_especialidades:
        db.delete(tecnico_especialidad)

    db.flush()


def get_tipos_vehiculo_disponibles(db: Session) -> list[TipoVehiculo]:
    return list(
        db.execute(
            select(TipoVehiculo).order_by(TipoVehiculo.nombre.asc())
        ).scalars()
    )


def get_tipos_vehiculo_by_ids(db: Session, ids_tipo_vehiculo: list[int]) -> list[TipoVehiculo]:
    if not ids_tipo_vehiculo:
        return []
    return list(
        db.execute(
            select(TipoVehiculo).where(TipoVehiculo.id_tipo_vehiculo.in_(ids_tipo_vehiculo))
        ).scalars()
    )


def get_taller_tipos_vehiculo_by_taller_id(
    db: Session,
    id_taller: int,
) -> list[TallerTipoVehiculo]:
    return list(
        db.execute(
            select(TallerTipoVehiculo)
            .options(joinedload(TallerTipoVehiculo.tipo_vehiculo))
            .where(TallerTipoVehiculo.id_taller == id_taller)
            .order_by(TallerTipoVehiculo.id_taller_tipo_vehiculo.asc())
        ).scalars()
    )


def create_taller_tipo_vehiculo(
    db: Session,
    *,
    id_taller: int,
    id_tipo_vehiculo: int,
) -> TallerTipoVehiculo:
    taller_tipo_vehiculo = TallerTipoVehiculo(
        id_taller=id_taller,
        id_tipo_vehiculo=id_tipo_vehiculo,
    )
    db.add(taller_tipo_vehiculo)
    db.flush()
    db.refresh(taller_tipo_vehiculo)
    return taller_tipo_vehiculo


def delete_taller_tipos_vehiculo_by_ids(
    db: Session,
    *,
    id_taller: int,
    ids_tipo_vehiculo: list[int],
) -> None:
    if not ids_tipo_vehiculo:
        return

    taller_tipos_vehiculo = db.execute(
        select(TallerTipoVehiculo).where(
            TallerTipoVehiculo.id_taller == id_taller,
            TallerTipoVehiculo.id_tipo_vehiculo.in_(ids_tipo_vehiculo),
        )
    ).scalars().all()

    for taller_tipo_vehiculo in taller_tipos_vehiculo:
        db.delete(taller_tipo_vehiculo)

    db.flush()


def get_asignacion_activa_by_tecnico_id(
    db: Session,
    id_tecnico: int,
) -> AsignacionServicio | None:
    return (
        db.execute(
            select(AsignacionServicio)
            .join(Incidente, AsignacionServicio.id_incidente == Incidente.id_incidente)
            .join(
                EstadoServicio,
                Incidente.id_estado_servicio_actual == EstadoServicio.id_estado_servicio,
            )
            .where(
                AsignacionServicio.id_tecnico == id_tecnico,
                EstadoServicio.nombre.notin_(["FINALIZADO", "CANCELADO"]),
            )
            .order_by(AsignacionServicio.fecha_asignacion.desc())
        )
        .scalars()
        .first()
    )
