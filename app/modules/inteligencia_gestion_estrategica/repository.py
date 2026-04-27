from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modules.autenticacion_seguridad.models import Usuario
from app.modules.gestion_clientes.models import Cliente, Vehiculo
from app.modules.gestion_incidentes_atencion.models import (
    AsignacionServicio,
    Evidencia,
    Incidente,
    Prioridad,
    SolicitudTaller,
)
from app.modules.gestion_operativa_taller_tecnico.models import (
    Taller,
    TallerAuxilio,
    TallerTipoVehiculo,
    Tecnico,
    UnidadMovil,
)
from app.modules.seguimiento_monitoreo_servicio.models import Notificacion


def get_incidente_by_id(db: Session, id_incidente: int) -> Incidente | None:
    return db.execute(
        select(Incidente).where(Incidente.id_incidente == id_incidente)
    ).scalar_one_or_none()


def get_evidencia_textos_by_incidente_id(db: Session, id_incidente: int) -> list[str]:
    return [
        texto
        for texto in db.execute(
            select(Evidencia.texto_extraido).where(
                Evidencia.id_incidente == id_incidente,
                Evidencia.texto_extraido.is_not(None),
            )
        ).scalars()
        if texto and texto.strip()
    ]


def get_evidencia_by_id_and_incidente_id(
    db: Session,
    *,
    id_incidente: int,
    id_evidencia: int,
) -> Evidencia | None:
    return db.execute(
        select(Evidencia).where(
            Evidencia.id_incidente == id_incidente,
            Evidencia.id_evidencia == id_evidencia,
        )
    ).scalar_one_or_none()


def get_latest_image_evidence_by_incidente_id(
    db: Session,
    id_incidente: int,
) -> Evidencia | None:
    return db.execute(
        select(Evidencia)
        .where(
            Evidencia.id_incidente == id_incidente,
            Evidencia.archivo_url.is_not(None),
            Evidencia.tipo_evidencia.in_(("IMAGEN", "FOTO", "IMAGE")),
        )
        .order_by(Evidencia.fecha_registro.desc(), Evidencia.id_evidencia.desc())
    ).scalar_one_or_none()


def update_incidente_analysis_result(
    db: Session,
    incidente: Incidente,
    *,
    clasificacion_ia: str,
    confianza_clasificacion: float,
    resumen_ia: str,
    requiere_mas_info: bool,
    id_prioridad: int | None = None,
) -> Incidente:
    incidente.clasificacion_ia = clasificacion_ia
    incidente.confianza_clasificacion = round(confianza_clasificacion, 2)
    incidente.resumen_ia = resumen_ia
    incidente.requiere_mas_info = requiere_mas_info
    if id_prioridad is not None:
        incidente.id_prioridad = id_prioridad
    db.flush()
    db.refresh(incidente)
    return incidente


def get_prioridad_by_nombre(db: Session, nombre: str) -> Prioridad | None:
    return db.execute(
        select(Prioridad).where(Prioridad.nombre == nombre.upper())
    ).scalar_one_or_none()


def get_cliente_by_id(db: Session, id_cliente: int) -> Cliente | None:
    return db.execute(
        select(Cliente).where(Cliente.id_cliente == id_cliente)
    ).scalar_one_or_none()


def get_usuario_by_id(db: Session, id_usuario: int) -> Usuario | None:
    return db.execute(
        select(Usuario).where(Usuario.id_usuario == id_usuario)
    ).scalar_one_or_none()


def get_pending_notification_by_incidente_usuario_tipo(
    db: Session,
    *,
    id_incidente: int,
    id_usuario: int,
    tipo_notificacion: str,
) -> Notificacion | None:
    return db.execute(
        select(Notificacion).where(
            Notificacion.id_incidente == id_incidente,
            Notificacion.id_usuario == id_usuario,
            Notificacion.tipo_notificacion == tipo_notificacion,
            Notificacion.leido == False,
        )
    ).scalar_one_or_none()


def create_notification(
    db: Session,
    *,
    id_usuario: int,
    id_incidente: int,
    titulo: str,
    mensaje: str,
    tipo_notificacion: str,
) -> Notificacion:
    notification = Notificacion(
        id_usuario=id_usuario,
        id_incidente=id_incidente,
        titulo=titulo,
        mensaje=mensaje,
        tipo_notificacion=tipo_notificacion,
        leido=False,
    )
    db.add(notification)
    db.flush()
    db.refresh(notification)
    return notification


def create_processed_evidence(
    db: Session,
    *,
    id_incidente: int,
    tipo_evidencia: str,
    archivo_url: str,
    texto_extraido: str,
    descripcion: str | None,
) -> Evidencia:
    evidence = Evidencia(
        id_incidente=id_incidente,
        tipo_evidencia=tipo_evidencia,
        archivo_url=archivo_url,
        texto_extraido=texto_extraido,
        descripcion=descripcion,
    )
    db.add(evidence)
    db.flush()
    db.refresh(evidence)
    return evidence


def list_evidences_by_incidente_id(db: Session, id_incidente: int) -> list[Evidencia]:
    return list(
        db.execute(
            select(Evidencia)
            .where(Evidencia.id_incidente == id_incidente)
            .order_by(Evidencia.fecha_registro.desc(), Evidencia.id_evidencia.desc())
        ).scalars()
    )


def get_incidente_with_assignment_context(db: Session, id_incidente: int) -> Incidente | None:
    return db.execute(
        select(Incidente)
        .options(
            joinedload(Incidente.vehiculo).joinedload(Vehiculo.tipo_vehiculo),
            joinedload(Incidente.estado_servicio_actual),
            joinedload(Incidente.asignacion_servicio).joinedload(AsignacionServicio.taller),
            joinedload(Incidente.solicitudes_taller),
        )
        .where(Incidente.id_incidente == id_incidente)
    ).scalar_one_or_none()


def list_available_talleres_with_resources(db: Session) -> list[Taller]:
    return list(
        db.execute(
            select(Taller)
            .options(
                joinedload(Taller.talleres_auxilio).joinedload(TallerAuxilio.tipo_auxilio),
                joinedload(Taller.talleres_tipo_vehiculo).joinedload(TallerTipoVehiculo.tipo_vehiculo),
                joinedload(Taller.tecnicos),
                joinedload(Taller.unidades_moviles),
            )
            .where(Taller.disponible == True)
            .order_by(Taller.id_taller.asc())
        ).unique().scalars()
    )


def get_solicitud_taller_by_incidente_and_taller(
    db: Session,
    *,
    id_incidente: int,
    id_taller: int,
) -> SolicitudTaller | None:
    return db.execute(
        select(SolicitudTaller).where(
            SolicitudTaller.id_incidente == id_incidente,
            SolicitudTaller.id_taller == id_taller,
        )
    ).scalar_one_or_none()


def create_solicitud_taller(
    db: Session,
    *,
    id_incidente: int,
    id_taller: int,
    distancia_km: float,
    puntaje_asignacion: float,
    estado_solicitud: str,
) -> SolicitudTaller:
    solicitud = SolicitudTaller(
        id_incidente=id_incidente,
        id_taller=id_taller,
        distancia_km=round(distancia_km, 2),
        puntaje_asignacion=round(puntaje_asignacion, 2),
        estado_solicitud=estado_solicitud,
    )
    db.add(solicitud)
    db.flush()
    db.refresh(solicitud)
    return solicitud


def update_solicitud_taller_candidate_data(
    db: Session,
    solicitud_taller: SolicitudTaller,
    *,
    distancia_km: float,
    puntaje_asignacion: float,
    estado_solicitud: str | None = None,
) -> SolicitudTaller:
    solicitud_taller.distancia_km = round(distancia_km, 2)
    solicitud_taller.puntaje_asignacion = round(puntaje_asignacion, 2)
    if estado_solicitud is not None:
        solicitud_taller.estado_solicitud = estado_solicitud
    if solicitud_taller.fecha_envio is None:
        solicitud_taller.fecha_envio = datetime.utcnow()
    db.flush()
    db.refresh(solicitud_taller)
    return solicitud_taller
