from sqlalchemy.orm import Session

from app.modules.gestion_clientes.repository import (
    create_calificacion,
    create_vehiculo,
    get_asignacion_by_incidente_id,
    get_calificacion_by_incidente_id,
    get_cliente_by_usuario_id,
    get_incidente_by_id,
    get_incidentes_finalizados_pendientes_calificacion,
    get_tipo_vehiculo_by_id,
    get_vehiculo_by_placa,
    get_vehiculos_by_cliente_id,
    list_tipos_vehiculo,
)
from app.modules.gestion_clientes.schemas import (
    CalificacionServicioCreateRequest,
    CalificacionServicioResponse,
    ServicioPendienteCalificacionResponse,
    TipoVehiculoResponse,
    VehiculoCreateRequest,
    VehiculoResponse,
)


def listar_tipos_vehiculo_service(db: Session) -> list[TipoVehiculoResponse]:
    tipos = list_tipos_vehiculo(db)
    return [TipoVehiculoResponse.model_validate(tipo) for tipo in tipos]


def register_vehiculo_service(
    db: Session,
    current_user,
    payload: VehiculoCreateRequest,
) -> VehiculoResponse:
    cliente = get_cliente_by_usuario_id(db, current_user.id_usuario)
    if not cliente:
        raise ValueError("El usuario autenticado no tiene perfil de cliente.")

    tipo_vehiculo = get_tipo_vehiculo_by_id(db, payload.id_tipo_vehiculo)
    if not tipo_vehiculo:
        raise ValueError("El tipo de vehículo seleccionado no existe.")

    existing_vehiculo = get_vehiculo_by_placa(db, payload.placa)
    if existing_vehiculo:
        raise ValueError("Ya existe un vehículo registrado con esa placa.")

    try:
        vehiculo = create_vehiculo(
            db,
            id_cliente=cliente.id_cliente,
            id_tipo_vehiculo=payload.id_tipo_vehiculo,
            placa=payload.placa,
            marca=payload.marca,
            modelo=payload.modelo,
            anio=payload.anio,
            color=payload.color,
            descripcion_referencia=payload.descripcion_referencia,
        )

        db.commit()
        db.refresh(vehiculo)

        return VehiculoResponse.model_validate(vehiculo)
    except Exception:
        db.rollback()
        raise


def get_mis_vehiculos_service(
    db: Session,
    current_user,
) -> list[VehiculoResponse]:
    cliente = get_cliente_by_usuario_id(db, current_user.id_usuario)
    if not cliente:
        raise ValueError("El usuario autenticado no tiene perfil de cliente.")

    vehiculos = get_vehiculos_by_cliente_id(db, cliente.id_cliente)
    return [VehiculoResponse.model_validate(v) for v in vehiculos]


def listar_servicios_pendientes_calificacion_service(
    db: Session,
    current_user,
) -> list[ServicioPendienteCalificacionResponse]:
    cliente = get_cliente_by_usuario_id(db, current_user.id_usuario)
    if not cliente:
        raise ValueError("El usuario autenticado no tiene perfil de cliente.")

    incidentes = get_incidentes_finalizados_pendientes_calificacion(
        db, cliente.id_cliente
    )
    result = []
    for incidente in incidentes:
        asignacion = get_asignacion_by_incidente_id(db, incidente.id_incidente)
        if asignacion:
            nombre_tecnico = asignacion.tecnico.usuario.nombres + " " + asignacion.tecnico.usuario.apellidos if asignacion.tecnico else None
            result.append(
                ServicioPendienteCalificacionResponse(
                    id_incidente=incidente.id_incidente,
                    titulo=incidente.titulo,
                    fecha_reporte=incidente.fecha_reporte.isoformat(),
                    id_taller=asignacion.id_taller,
                    nombre_taller=asignacion.taller.nombre_taller,
                    id_tecnico=asignacion.id_tecnico,
                    nombre_tecnico=nombre_tecnico,
                )
            )
    return result


def registrar_calificacion_service(
    db: Session,
    current_user,
    payload: CalificacionServicioCreateRequest,
) -> CalificacionServicioResponse:
    cliente = get_cliente_by_usuario_id(db, current_user.id_usuario)
    if not cliente:
        raise ValueError("El usuario autenticado no tiene perfil de cliente.")

    incidente = get_incidente_by_id(db, payload.id_incidente)
    if not incidente:
        raise ValueError("El incidente especificado no existe.")

    if incidente.id_cliente != cliente.id_cliente:
        raise ValueError("El incidente no pertenece al cliente autenticado.")

    if incidente.id_estado_servicio_actual != 7:  # FINALIZADO
        raise ValueError("El servicio aún no se encuentra finalizado.")

    existing_calificacion = get_calificacion_by_incidente_id(db, payload.id_incidente)
    if existing_calificacion:
        raise ValueError("El servicio ya ha sido calificado previamente.")

    asignacion = get_asignacion_by_incidente_id(db, payload.id_incidente)
    if not asignacion:
        raise ValueError("No se encontró asignación para este incidente.")

    try:
        calificacion = create_calificacion(
            db,
            id_incidente=payload.id_incidente,
            id_cliente=cliente.id_cliente,
            id_taller=asignacion.id_taller,
            id_tecnico=asignacion.id_tecnico,
            puntuacion=payload.puntuacion,
            comentario=payload.comentario,
        )

        db.commit()
        db.refresh(calificacion)

        return CalificacionServicioResponse.model_validate(calificacion)
    except Exception:
        db.rollback()
        raise
