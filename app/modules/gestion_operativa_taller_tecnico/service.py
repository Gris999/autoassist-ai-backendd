from sqlalchemy.orm import Session

from app.core.security.security import hash_password
from app.modules.autenticacion_seguridad.repository import (
    assign_rol_to_usuario,
    create_usuario,
    get_rol_by_nombre,
    get_usuario_by_email,
)
from app.modules.gestion_operativa_taller_tecnico.repository import (
    create_unidad_movil,
    create_tecnico,
    create_tecnico_especialidad,
    create_horario_disponibilidad_taller,
    create_taller_tipo_vehiculo,
    create_taller_auxilio,
    delete_horarios_disponibilidad_by_taller_id,
    delete_taller_tipos_vehiculo_by_ids,
    delete_tecnico_especialidades_by_ids,
    get_especialidades_by_ids,
    get_especialidades_disponibles,
    get_asignacion_activa_by_tecnico_id,
    get_taller_auxilio_by_id,
    get_taller_auxilio_by_taller_id_tipo_auxilio,
    get_taller_by_usuario_id,
    get_horarios_disponibilidad_by_taller_id,
    get_unidad_movil_by_id,
    get_unidad_movil_by_placa,
    get_unidades_moviles_by_taller_id,
    get_servicios_auxilio_por_taller_id,
    get_taller_tipos_vehiculo_by_taller_id,
    get_tecnico_with_usuario_by_id,
    get_tecnicos_by_taller_id,
    get_tecnico_by_usuario_id,
    get_tecnico_especialidades_by_tecnico_id,
    get_talleres_disponibles,
    list_tipos_auxilio_disponibles,
    get_tipos_vehiculo_by_ids,
    get_tipos_vehiculo_disponibles,
    get_tipo_auxilio_by_id,
    set_disponibilidad_taller_auxilio,
    update_estado_tecnico,
    update_disponibilidad_tecnico,
    update_disponibilidad_taller,
    update_taller_auxilio,
    update_unidad_movil,
    update_tecnico,
    update_usuario_tecnico,
)
from app.modules.gestion_operativa_taller_tecnico.schemas import (
    ActualizarDisponibilidadTecnicoRequest,
    ActualizarDisponibilidadTallerRequest,
    DisponibilidadTecnicoResponse,
    DisponibilidadTallerResponse,
    EspecialidadResponse,
    HorarioDisponibilidadTallerResponse,
    TecnicoCreateRequest,
    TecnicoDetailResponse,
    TecnicoEstadoResponse,
    TecnicoEspecialidadesAssignRequest,
    TecnicoEspecialidadesResponse,
    TecnicoEspecialidadesUpdateRequest,
    TecnicoListResponse,
    TecnicoUpdateRequest,
    TallerTiposVehiculoConfigRequest,
    TallerTiposVehiculoConfigResponse,
    TipoAuxilioCatalogResponse,
    TallerAuxilioCreateRequest,
    TallerAuxilioResponse,
    TallerAuxilioUpdateRequest,
    TipoVehiculoResponse,
    TallerInfoResponse,
    UnidadMovilCreateRequest,
    UnidadMovilDetailResponse,
    UnidadMovilEstadoDisponibilidadRequest,
    UnidadMovilListResponse,
    UnidadMovilUpdateRequest,
)


def _get_taller_gestor_service(db: Session, current_user):
    taller = get_taller_by_usuario_id(db, current_user.id_usuario)
    if not taller:
        raise ValueError("El usuario autenticado no tiene perfil de taller.")
    return taller


def _to_horario_disponibilidad_response(horario) -> HorarioDisponibilidadTallerResponse:
    return HorarioDisponibilidadTallerResponse.model_validate(horario)


def _to_disponibilidad_taller_response(
    taller,
    horarios,
) -> DisponibilidadTallerResponse:
    return DisponibilidadTallerResponse(
        id_taller=taller.id_taller,
        nombre_taller=taller.nombre_taller,
        disponible=taller.disponible,
        direccion=taller.direccion,
        latitud=float(taller.latitud) if taller.latitud is not None else None,
        longitud=float(taller.longitud) if taller.longitud is not None else None,
        radio_cobertura_km=(
            float(taller.radio_cobertura_km) if taller.radio_cobertura_km is not None else None
        ),
        fecha_registro=taller.fecha_registro,
        horarios=[_to_horario_disponibilidad_response(horario) for horario in horarios],
    )


def _validar_conflictos_horarios(horarios) -> None:
    horarios_por_dia: dict[str, list] = {}
    for horario in horarios:
        horarios_por_dia.setdefault(horario.dia_semana, []).append(horario)

    for dia_semana, horarios_dia in horarios_por_dia.items():
        ordenados = sorted(horarios_dia, key=lambda item: item.hora_inicio)
        for indice in range(1, len(ordenados)):
            anterior = ordenados[indice - 1]
            actual = ordenados[indice]
            if actual.hora_inicio < anterior.hora_fin:
                raise ValueError(
                    f"Existe conflicto entre horarios registrados para {dia_semana}."
                )


def _validar_tecnico_del_taller(db: Session, id_tecnico: int, id_taller: int):
    tecnico = get_tecnico_with_usuario_by_id(db, id_tecnico)
    if not tecnico:
        raise ValueError("El tecnico especificado no existe.")
    if tecnico.id_taller != id_taller:
        raise ValueError("El tecnico no pertenece al taller autenticado.")
    return tecnico


def _to_tecnico_list_response(tecnico) -> TecnicoListResponse:
    return TecnicoListResponse(
        id_tecnico=tecnico.id_tecnico,
        id_usuario=tecnico.id_usuario,
        nombres=tecnico.usuario.nombres,
        apellidos=tecnico.usuario.apellidos,
        email=tecnico.usuario.email,
        celular=tecnico.usuario.celular,
        telefono_contacto=tecnico.telefono_contacto,
        disponible=tecnico.disponible,
        estado=tecnico.estado,
    )


def _to_tecnico_detail_response(tecnico) -> TecnicoDetailResponse:
    return TecnicoDetailResponse(
        id_tecnico=tecnico.id_tecnico,
        id_usuario=tecnico.id_usuario,
        id_taller=tecnico.id_taller,
        nombres=tecnico.usuario.nombres,
        apellidos=tecnico.usuario.apellidos,
        email=tecnico.usuario.email,
        celular=tecnico.usuario.celular,
        telefono_contacto=tecnico.telefono_contacto,
        disponible=tecnico.disponible,
        estado=tecnico.estado,
        latitud_actual=float(tecnico.latitud_actual) if tecnico.latitud_actual is not None else None,
        longitud_actual=float(tecnico.longitud_actual) if tecnico.longitud_actual is not None else None,
    )


def _to_tecnico_estado_response(tecnico) -> TecnicoEstadoResponse:
    return TecnicoEstadoResponse(
        id_tecnico=tecnico.id_tecnico,
        id_usuario=tecnico.id_usuario,
        estado=tecnico.estado,
        disponible=tecnico.disponible,
    )


def _validar_ids_especialidad(ids_especialidad: list[int]) -> None:
    if any(id_especialidad <= 0 for id_especialidad in ids_especialidad):
        raise ValueError("Se enviaron ids de especialidad invalidos.")
    if len(set(ids_especialidad)) != len(ids_especialidad):
        raise ValueError("No se permiten ids de especialidad repetidos en la misma peticion.")


def _obtener_especialidades_validas(db: Session, ids_especialidad: list[int]):
    especialidades = get_especialidades_by_ids(db, ids_especialidad)
    if len(especialidades) != len(set(ids_especialidad)):
        raise ValueError("Una o mas especialidades especificadas no existen.")
    return especialidades


def _to_especialidad_response(especialidad) -> EspecialidadResponse:
    return EspecialidadResponse(
        id_especialidad=especialidad.id_especialidad,
        nombre=especialidad.nombre,
        descripcion=especialidad.descripcion,
    )


def _to_tecnico_especialidades_response(
    id_tecnico: int,
    tecnico_especialidades,
) -> TecnicoEspecialidadesResponse:
    return TecnicoEspecialidadesResponse(
        id_tecnico=id_tecnico,
        especialidades=[
            _to_especialidad_response(tecnico_especialidad.especialidad)
            for tecnico_especialidad in tecnico_especialidades
        ],
    )


def _validar_ids_tipo_vehiculo(ids_tipo_vehiculo: list[int]) -> None:
    if any(id_tipo_vehiculo <= 0 for id_tipo_vehiculo in ids_tipo_vehiculo):
        raise ValueError("Se enviaron ids de tipo de vehiculo invalidos.")
    if len(set(ids_tipo_vehiculo)) != len(ids_tipo_vehiculo):
        raise ValueError("No se permiten ids de tipo de vehiculo repetidos en la misma peticion.")


def _obtener_tipos_vehiculo_validos(db: Session, ids_tipo_vehiculo: list[int]):
    tipos_vehiculo = get_tipos_vehiculo_by_ids(db, ids_tipo_vehiculo)
    if len(tipos_vehiculo) != len(set(ids_tipo_vehiculo)):
        raise ValueError("Uno o mas tipos de vehiculo especificados no existen.")
    return tipos_vehiculo


def _to_tipo_vehiculo_response(tipo_vehiculo) -> TipoVehiculoResponse:
    return TipoVehiculoResponse(
        id_tipo_vehiculo=tipo_vehiculo.id_tipo_vehiculo,
        nombre=tipo_vehiculo.nombre,
        descripcion=tipo_vehiculo.descripcion,
    )


def _to_tipo_auxilio_catalog_response(tipo_auxilio) -> TipoAuxilioCatalogResponse:
    return TipoAuxilioCatalogResponse(
        id_tipo_auxilio=tipo_auxilio.id_tipo_auxilio,
        nombre=tipo_auxilio.nombre,
        descripcion=tipo_auxilio.descripcion,
        requiere_unidad_movil=tipo_auxilio.requiere_unidad_movil,
        requiere_remolque=tipo_auxilio.requiere_remolque,
    )


def _to_taller_tipos_vehiculo_config_response(
    id_taller: int,
    taller_tipos_vehiculo,
) -> TallerTiposVehiculoConfigResponse:
    return TallerTiposVehiculoConfigResponse(
        id_taller=id_taller,
        tipos_vehiculo=[
            _to_tipo_vehiculo_response(taller_tipo_vehiculo.tipo_vehiculo)
            for taller_tipo_vehiculo in taller_tipos_vehiculo
        ],
    )


def _validar_unidad_movil_del_taller(db: Session, id_unidad_movil: int, id_taller: int):
    unidad_movil = get_unidad_movil_by_id(db, id_unidad_movil)
    if not unidad_movil:
        raise ValueError("La unidad movil especificada no existe.")
    if unidad_movil.id_taller != id_taller:
        raise ValueError("La unidad movil no pertenece al taller autenticado.")
    return unidad_movil


def _validar_consistencia_unidad_movil(*, disponible: bool, estado: bool) -> None:
    if not estado and disponible:
        raise ValueError("No se puede marcar como disponible una unidad movil deshabilitada.")


def _to_unidad_movil_list_response(unidad_movil) -> UnidadMovilListResponse:
    return UnidadMovilListResponse(
        id_unidad_movil=unidad_movil.id_unidad_movil,
        id_taller=unidad_movil.id_taller,
        placa=unidad_movil.placa,
        tipo_unidad=unidad_movil.tipo_unidad,
        disponible=unidad_movil.disponible,
        estado=unidad_movil.estado,
    )


def _to_unidad_movil_detail_response(unidad_movil) -> UnidadMovilDetailResponse:
    return UnidadMovilDetailResponse(
        id_unidad_movil=unidad_movil.id_unidad_movil,
        id_taller=unidad_movil.id_taller,
        placa=unidad_movil.placa,
        tipo_unidad=unidad_movil.tipo_unidad,
        disponible=unidad_movil.disponible,
        estado=unidad_movil.estado,
        latitud_actual=float(unidad_movil.latitud_actual)
        if unidad_movil.latitud_actual is not None
        else None,
        longitud_actual=float(unidad_movil.longitud_actual)
        if unidad_movil.longitud_actual is not None
        else None,
    )


def obtener_disponibilidad_taller_service(
    db: Session,
    current_user,
) -> DisponibilidadTallerResponse:
    taller = get_taller_by_usuario_id(db, current_user.id_usuario)
    if not taller:
        raise ValueError("El usuario autenticado no tiene perfil de taller.")

    horarios = get_horarios_disponibilidad_by_taller_id(db, taller.id_taller)
    return _to_disponibilidad_taller_response(taller, horarios)


def actualizar_disponibilidad_taller_service(
    db: Session,
    current_user,
    payload: ActualizarDisponibilidadTallerRequest,
) -> DisponibilidadTallerResponse:
    taller = get_taller_by_usuario_id(db, current_user.id_usuario)
    if not taller:
        raise ValueError("El usuario autenticado no tiene perfil de taller.")

    try:
        if payload.horarios is not None:
            _validar_conflictos_horarios(payload.horarios)

        taller_actualizado = update_disponibilidad_taller(
            db,
            id_taller=taller.id_taller,
            disponible=payload.disponible,
            latitud=payload.latitud,
            longitud=payload.longitud,
            radio_cobertura_km=payload.radio_cobertura_km,
        )

        if payload.horarios is not None:
            delete_horarios_disponibilidad_by_taller_id(db, id_taller=taller.id_taller)
            for horario in payload.horarios:
                create_horario_disponibilidad_taller(
                    db,
                    id_taller=taller.id_taller,
                    dia_semana=horario.dia_semana,
                    hora_inicio=horario.hora_inicio,
                    hora_fin=horario.hora_fin,
                    estado=horario.estado,
                )

        db.commit()
        db.refresh(taller_actualizado)
        horarios = get_horarios_disponibilidad_by_taller_id(db, taller.id_taller)
        return _to_disponibilidad_taller_response(taller_actualizado, horarios)
    except Exception:
        db.rollback()
        raise


def obtener_talleres_disponibles_service(
    db: Session,
) -> list[TallerInfoResponse]:
    talleres = get_talleres_disponibles(db)
    return [TallerInfoResponse.model_validate(t) for t in talleres]


def obtener_informacion_taller_service(
    db: Session,
    current_user,
) -> TallerInfoResponse:
    taller = get_taller_by_usuario_id(db, current_user.id_usuario)
    if not taller:
        raise ValueError("El usuario autenticado no tiene perfil de taller.")

    return TallerInfoResponse.model_validate(taller)


def listar_tecnicos_service(
    db: Session,
    current_user,
) -> list[TecnicoListResponse]:
    taller = _get_taller_gestor_service(db, current_user)
    tecnicos = get_tecnicos_by_taller_id(db, taller.id_taller)
    return [_to_tecnico_list_response(tecnico) for tecnico in tecnicos]


def obtener_tecnico_service(
    db: Session,
    current_user,
    id_tecnico: int,
) -> TecnicoDetailResponse:
    taller = _get_taller_gestor_service(db, current_user)
    tecnico = _validar_tecnico_del_taller(db, id_tecnico, taller.id_taller)
    return _to_tecnico_detail_response(tecnico)


def registrar_tecnico_service(
    db: Session,
    current_user,
    payload: TecnicoCreateRequest,
) -> TecnicoDetailResponse:
    taller = _get_taller_gestor_service(db, current_user)

    existing_user = get_usuario_by_email(db, payload.email)
    if existing_user:
        raise ValueError("Ya existe un usuario registrado con ese email.")

    rol_tecnico = get_rol_by_nombre(db, "TECNICO")
    if not rol_tecnico:
        raise ValueError("No existe el rol TECNICO en la base de datos.")

    try:
        usuario = create_usuario(
            db,
            nombres=payload.nombres,
            apellidos=payload.apellidos,
            celular=payload.celular,
            email=payload.email,
            password_hash=hash_password(payload.password),
        )

        assign_rol_to_usuario(
            db,
            id_usuario=usuario.id_usuario,
            id_rol=rol_tecnico.id_rol,
        )

        tecnico = create_tecnico(
            db,
            id_usuario=usuario.id_usuario,
            id_taller=taller.id_taller,
            telefono_contacto=payload.telefono_contacto,
            disponible=payload.disponible if payload.estado else False,
            estado=payload.estado,
        )

        db.commit()
        tecnico = get_tecnico_with_usuario_by_id(db, tecnico.id_tecnico)
        return _to_tecnico_detail_response(tecnico)
    except Exception:
        db.rollback()
        raise


def actualizar_tecnico_service(
    db: Session,
    current_user,
    id_tecnico: int,
    payload: TecnicoUpdateRequest,
) -> TecnicoDetailResponse:
    taller = _get_taller_gestor_service(db, current_user)
    tecnico = _validar_tecnico_del_taller(db, id_tecnico, taller.id_taller)

    if (
        payload.nombres is None
        and payload.apellidos is None
        and payload.celular is None
        and payload.email is None
        and payload.telefono_contacto is None
        and payload.disponible is None
    ):
        raise ValueError("Debe indicar al menos un campo para actualizar.")

    if payload.email is not None:
        existing_user = get_usuario_by_email(db, payload.email)
        if existing_user and existing_user.id_usuario != tecnico.id_usuario:
            raise ValueError("Ya existe un usuario registrado con ese email.")

    if payload.disponible is True and not tecnico.estado:
        raise ValueError("No se puede marcar como disponible un tecnico deshabilitado.")

    try:
        update_usuario_tecnico(
            db,
            tecnico.usuario,
            nombres=payload.nombres,
            apellidos=payload.apellidos,
            celular=payload.celular,
            email=payload.email,
        )

        update_tecnico(
            db,
            tecnico,
            telefono_contacto=payload.telefono_contacto,
            disponible=payload.disponible,
        )

        db.commit()
        tecnico_actualizado = get_tecnico_with_usuario_by_id(db, tecnico.id_tecnico)
        return _to_tecnico_detail_response(tecnico_actualizado)
    except Exception:
        db.rollback()
        raise


def habilitar_tecnico_service(
    db: Session,
    current_user,
    id_tecnico: int,
) -> TecnicoEstadoResponse:
    taller = _get_taller_gestor_service(db, current_user)
    tecnico = _validar_tecnico_del_taller(db, id_tecnico, taller.id_taller)

    try:
        tecnico_actualizado = update_estado_tecnico(
            db,
            tecnico,
            estado=True,
        )
        db.commit()
        db.refresh(tecnico_actualizado)
        return _to_tecnico_estado_response(tecnico_actualizado)
    except Exception:
        db.rollback()
        raise


def deshabilitar_tecnico_service(
    db: Session,
    current_user,
    id_tecnico: int,
) -> TecnicoEstadoResponse:
    taller = _get_taller_gestor_service(db, current_user)
    tecnico = _validar_tecnico_del_taller(db, id_tecnico, taller.id_taller)

    try:
        tecnico_actualizado = update_estado_tecnico(
            db,
            tecnico,
            estado=False,
        )
        db.commit()
        db.refresh(tecnico_actualizado)
        return _to_tecnico_estado_response(tecnico_actualizado)
    except Exception:
        db.rollback()
        raise


def listar_especialidades_disponibles_service(
    db: Session,
    current_user,
) -> list[EspecialidadResponse]:
    _get_taller_gestor_service(db, current_user)
    especialidades = get_especialidades_disponibles(db)
    return [_to_especialidad_response(especialidad) for especialidad in especialidades]


def listar_especialidades_tecnico_service(
    db: Session,
    current_user,
    id_tecnico: int,
) -> TecnicoEspecialidadesResponse:
    taller = _get_taller_gestor_service(db, current_user)
    tecnico = _validar_tecnico_del_taller(db, id_tecnico, taller.id_taller)
    tecnico_especialidades = get_tecnico_especialidades_by_tecnico_id(db, tecnico.id_tecnico)
    return _to_tecnico_especialidades_response(tecnico.id_tecnico, tecnico_especialidades)


def asignar_especialidades_tecnico_service(
    db: Session,
    current_user,
    id_tecnico: int,
    payload: TecnicoEspecialidadesAssignRequest,
) -> TecnicoEspecialidadesResponse:
    _validar_ids_especialidad(payload.ids_especialidad)
    taller = _get_taller_gestor_service(db, current_user)
    tecnico = _validar_tecnico_del_taller(db, id_tecnico, taller.id_taller)
    _obtener_especialidades_validas(db, payload.ids_especialidad)

    tecnico_especialidades_actuales = get_tecnico_especialidades_by_tecnico_id(db, tecnico.id_tecnico)
    ids_actuales = {item.id_especialidad for item in tecnico_especialidades_actuales}
    ids_duplicados = ids_actuales.intersection(payload.ids_especialidad)
    if ids_duplicados:
        raise ValueError("Una o mas especialidades ya estan asignadas al tecnico.")

    try:
        for id_especialidad in payload.ids_especialidad:
            create_tecnico_especialidad(
                db,
                id_tecnico=tecnico.id_tecnico,
                id_especialidad=id_especialidad,
            )

        db.commit()
        tecnico_especialidades_actualizadas = get_tecnico_especialidades_by_tecnico_id(db, tecnico.id_tecnico)
        return _to_tecnico_especialidades_response(
            tecnico.id_tecnico,
            tecnico_especialidades_actualizadas,
        )
    except Exception:
        db.rollback()
        raise


def actualizar_especialidades_tecnico_service(
    db: Session,
    current_user,
    id_tecnico: int,
    payload: TecnicoEspecialidadesUpdateRequest,
) -> TecnicoEspecialidadesResponse:
    _validar_ids_especialidad(payload.ids_especialidad)
    taller = _get_taller_gestor_service(db, current_user)
    tecnico = _validar_tecnico_del_taller(db, id_tecnico, taller.id_taller)
    _obtener_especialidades_validas(db, payload.ids_especialidad)

    tecnico_especialidades_actuales = get_tecnico_especialidades_by_tecnico_id(db, tecnico.id_tecnico)
    ids_actuales = {item.id_especialidad for item in tecnico_especialidades_actuales}
    ids_nuevos = set(payload.ids_especialidad)
    ids_a_quitar = list(ids_actuales - ids_nuevos)
    ids_a_agregar = [
        id_especialidad
        for id_especialidad in payload.ids_especialidad
        if id_especialidad not in ids_actuales
    ]

    try:
        delete_tecnico_especialidades_by_ids(
            db,
            id_tecnico=tecnico.id_tecnico,
            ids_especialidad=ids_a_quitar,
        )

        for id_especialidad in ids_a_agregar:
            create_tecnico_especialidad(
                db,
                id_tecnico=tecnico.id_tecnico,
                id_especialidad=id_especialidad,
            )

        db.commit()
        tecnico_especialidades_actualizadas = get_tecnico_especialidades_by_tecnico_id(db, tecnico.id_tecnico)
        return _to_tecnico_especialidades_response(
            tecnico.id_tecnico,
            tecnico_especialidades_actualizadas,
        )
    except Exception:
        db.rollback()
        raise


def quitar_especialidad_tecnico_service(
    db: Session,
    current_user,
    id_tecnico: int,
    id_especialidad: int,
) -> TecnicoEspecialidadesResponse:
    _validar_ids_especialidad([id_especialidad])
    taller = _get_taller_gestor_service(db, current_user)
    tecnico = _validar_tecnico_del_taller(db, id_tecnico, taller.id_taller)
    _obtener_especialidades_validas(db, [id_especialidad])

    tecnico_especialidades_actuales = get_tecnico_especialidades_by_tecnico_id(db, tecnico.id_tecnico)
    ids_actuales = {item.id_especialidad for item in tecnico_especialidades_actuales}
    if id_especialidad not in ids_actuales:
        raise ValueError("La especialidad especificada no esta asignada al tecnico.")

    try:
        delete_tecnico_especialidades_by_ids(
            db,
            id_tecnico=tecnico.id_tecnico,
            ids_especialidad=[id_especialidad],
        )
        db.commit()
        tecnico_especialidades_actualizadas = get_tecnico_especialidades_by_tecnico_id(db, tecnico.id_tecnico)
        return _to_tecnico_especialidades_response(
            tecnico.id_tecnico,
            tecnico_especialidades_actualizadas,
        )
    except Exception:
        db.rollback()
        raise


def listar_tipos_vehiculo_disponibles_service(
    db: Session,
    current_user,
) -> list[TipoVehiculoResponse]:
    _get_taller_gestor_service(db, current_user)
    tipos_vehiculo = get_tipos_vehiculo_disponibles(db)
    return [_to_tipo_vehiculo_response(tipo_vehiculo) for tipo_vehiculo in tipos_vehiculo]


def listar_tipos_auxilio_disponibles_service(
    db: Session,
    current_user,
) -> list[TipoAuxilioCatalogResponse]:
    _get_taller_gestor_service(db, current_user)
    tipos_auxilio = list_tipos_auxilio_disponibles(db)
    return [_to_tipo_auxilio_catalog_response(tipo_auxilio) for tipo_auxilio in tipos_auxilio]


def obtener_configuracion_tipos_vehiculo_taller_service(
    db: Session,
    current_user,
) -> TallerTiposVehiculoConfigResponse:
    taller = _get_taller_gestor_service(db, current_user)
    taller_tipos_vehiculo = get_taller_tipos_vehiculo_by_taller_id(db, taller.id_taller)
    return _to_taller_tipos_vehiculo_config_response(taller.id_taller, taller_tipos_vehiculo)


def configurar_tipos_vehiculo_taller_service(
    db: Session,
    current_user,
    payload: TallerTiposVehiculoConfigRequest,
) -> TallerTiposVehiculoConfigResponse:
    _validar_ids_tipo_vehiculo(payload.ids_tipo_vehiculo)
    taller = _get_taller_gestor_service(db, current_user)
    _obtener_tipos_vehiculo_validos(db, payload.ids_tipo_vehiculo)

    taller_tipos_vehiculo_actuales = get_taller_tipos_vehiculo_by_taller_id(db, taller.id_taller)
    ids_actuales = {item.id_tipo_vehiculo for item in taller_tipos_vehiculo_actuales}
    ids_nuevos = set(payload.ids_tipo_vehiculo)
    ids_a_quitar = list(ids_actuales - ids_nuevos)
    ids_a_agregar = [
        id_tipo_vehiculo
        for id_tipo_vehiculo in payload.ids_tipo_vehiculo
        if id_tipo_vehiculo not in ids_actuales
    ]

    try:
        delete_taller_tipos_vehiculo_by_ids(
            db,
            id_taller=taller.id_taller,
            ids_tipo_vehiculo=ids_a_quitar,
        )

        for id_tipo_vehiculo in ids_a_agregar:
            create_taller_tipo_vehiculo(
                db,
                id_taller=taller.id_taller,
                id_tipo_vehiculo=id_tipo_vehiculo,
            )

        db.commit()
        taller_tipos_vehiculo_actualizados = get_taller_tipos_vehiculo_by_taller_id(db, taller.id_taller)
        return _to_taller_tipos_vehiculo_config_response(
            taller.id_taller,
            taller_tipos_vehiculo_actualizados,
        )
    except Exception:
        db.rollback()
        raise


def listar_unidades_moviles_service(
    db: Session,
    current_user,
) -> list[UnidadMovilListResponse]:
    taller = _get_taller_gestor_service(db, current_user)
    unidades_moviles = get_unidades_moviles_by_taller_id(db, taller.id_taller)
    return [_to_unidad_movil_list_response(unidad_movil) for unidad_movil in unidades_moviles]


def obtener_unidad_movil_service(
    db: Session,
    current_user,
    id_unidad_movil: int,
) -> UnidadMovilDetailResponse:
    taller = _get_taller_gestor_service(db, current_user)
    unidad_movil = _validar_unidad_movil_del_taller(db, id_unidad_movil, taller.id_taller)
    return _to_unidad_movil_detail_response(unidad_movil)


def registrar_unidad_movil_service(
    db: Session,
    current_user,
    payload: UnidadMovilCreateRequest,
) -> UnidadMovilDetailResponse:
    taller = _get_taller_gestor_service(db, current_user)
    _validar_consistencia_unidad_movil(
        disponible=payload.disponible,
        estado=payload.estado,
    )

    unidad_existente = get_unidad_movil_by_placa(db, payload.placa)
    if unidad_existente:
        raise ValueError("Ya existe una unidad movil registrada con esa placa.")

    try:
        unidad_movil = create_unidad_movil(
            db,
            id_taller=taller.id_taller,
            placa=payload.placa,
            tipo_unidad=payload.tipo_unidad,
            disponible=payload.disponible,
            estado=payload.estado,
            latitud_actual=payload.latitud_actual,
            longitud_actual=payload.longitud_actual,
        )
        db.commit()
        db.refresh(unidad_movil)
        return _to_unidad_movil_detail_response(unidad_movil)
    except Exception:
        db.rollback()
        raise


def actualizar_unidad_movil_service(
    db: Session,
    current_user,
    id_unidad_movil: int,
    payload: UnidadMovilUpdateRequest,
) -> UnidadMovilDetailResponse:
    taller = _get_taller_gestor_service(db, current_user)
    unidad_movil = _validar_unidad_movil_del_taller(db, id_unidad_movil, taller.id_taller)

    if (
        payload.placa is None
        and payload.tipo_unidad is None
        and payload.disponible is None
        and payload.estado is None
        and payload.latitud_actual is None
        and payload.longitud_actual is None
    ):
        raise ValueError("Debe indicar al menos un campo para actualizar.")

    if payload.placa is not None:
        unidad_existente = get_unidad_movil_by_placa(db, payload.placa)
        if unidad_existente and unidad_existente.id_unidad_movil != unidad_movil.id_unidad_movil:
            raise ValueError("Ya existe una unidad movil registrada con esa placa.")

    estado_final = payload.estado if payload.estado is not None else unidad_movil.estado
    disponible_final = (
        payload.disponible if payload.disponible is not None else unidad_movil.disponible
    )
    _validar_consistencia_unidad_movil(
        disponible=disponible_final,
        estado=estado_final,
    )

    try:
        unidad_movil_actualizada = update_unidad_movil(
            db,
            unidad_movil,
            placa=payload.placa,
            tipo_unidad=payload.tipo_unidad,
            disponible=payload.disponible,
            estado=payload.estado,
            latitud_actual=payload.latitud_actual,
            longitud_actual=payload.longitud_actual,
        )
        db.commit()
        db.refresh(unidad_movil_actualizada)
        return _to_unidad_movil_detail_response(unidad_movil_actualizada)
    except Exception:
        db.rollback()
        raise


def actualizar_estado_disponibilidad_unidad_movil_service(
    db: Session,
    current_user,
    id_unidad_movil: int,
    payload: UnidadMovilEstadoDisponibilidadRequest,
) -> UnidadMovilDetailResponse:
    taller = _get_taller_gestor_service(db, current_user)
    unidad_movil = _validar_unidad_movil_del_taller(db, id_unidad_movil, taller.id_taller)

    if payload.disponible is None and payload.estado is None:
        raise ValueError("Debe indicar disponibilidad, estado o ambos para actualizar.")

    estado_final = payload.estado if payload.estado is not None else unidad_movil.estado
    disponible_final = (
        payload.disponible if payload.disponible is not None else unidad_movil.disponible
    )
    _validar_consistencia_unidad_movil(
        disponible=disponible_final,
        estado=estado_final,
    )

    try:
        unidad_movil_actualizada = update_unidad_movil(
            db,
            unidad_movil,
            disponible=payload.disponible,
            estado=payload.estado,
        )
        db.commit()
        db.refresh(unidad_movil_actualizada)
        return _to_unidad_movil_detail_response(unidad_movil_actualizada)
    except Exception:
        db.rollback()
        raise


def obtener_disponibilidad_tecnico_service(
    db: Session,
    current_user,
) -> DisponibilidadTecnicoResponse:
    tecnico = get_tecnico_by_usuario_id(db, current_user.id_usuario)
    if not tecnico:
        raise ValueError("El usuario autenticado no tiene perfil de tecnico.")
    if not tecnico.estado:
        raise ValueError("El tecnico no se encuentra habilitado en el sistema.")

    return DisponibilidadTecnicoResponse.model_validate(tecnico)


def actualizar_disponibilidad_tecnico_service(
    db: Session,
    current_user,
    payload: ActualizarDisponibilidadTecnicoRequest,
) -> DisponibilidadTecnicoResponse:
    tecnico = get_tecnico_by_usuario_id(db, current_user.id_usuario)
    if not tecnico:
        raise ValueError("El usuario autenticado no tiene perfil de tecnico.")
    if not tecnico.estado:
        raise ValueError("El tecnico no se encuentra habilitado en el sistema.")

    asignacion_activa = get_asignacion_activa_by_tecnico_id(db, tecnico.id_tecnico)
    if payload.disponible and asignacion_activa:
        raise ValueError(
            "El tecnico tiene una asignacion activa y no puede marcarse como disponible."
        )

    try:
        tecnico_actualizado = update_disponibilidad_tecnico(
            db,
            id_tecnico=tecnico.id_tecnico,
            disponible=payload.disponible,
        )

        db.commit()
        db.refresh(tecnico_actualizado)

        return DisponibilidadTecnicoResponse.model_validate(tecnico_actualizado)
    except Exception:
        db.rollback()
        raise


def listar_servicios_auxilio_service(
    db: Session,
    current_user,
) -> list[TallerAuxilioResponse]:
    taller = get_taller_by_usuario_id(db, current_user.id_usuario)
    if not taller:
        raise ValueError("El usuario autenticado no tiene perfil de taller.")

    servicios = get_servicios_auxilio_por_taller_id(db, taller.id_taller)
    return [
        TallerAuxilioResponse(
            id_taller_auxilio=s.id_taller_auxilio,
            id_taller=s.id_taller,
            id_tipo_auxilio=s.id_tipo_auxilio,
            nombre_tipo_auxilio=s.tipo_auxilio.nombre,
            descripcion_tipo_auxilio=s.tipo_auxilio.descripcion,
            precio_referencial=float(s.precio_referencial),
            disponible=s.disponible,
        )
        for s in servicios
    ]


def registrar_servicio_auxilio_service(
    db: Session,
    current_user,
    payload: TallerAuxilioCreateRequest,
) -> TallerAuxilioResponse:
    taller = get_taller_by_usuario_id(db, current_user.id_usuario)
    if not taller:
        raise ValueError("El usuario autenticado no tiene perfil de taller.")

    tipo_auxilio = get_tipo_auxilio_by_id(db, payload.id_tipo_auxilio)
    if not tipo_auxilio:
        raise ValueError("El tipo de auxilio especificado no existe.")

    existing = get_taller_auxilio_by_taller_id_tipo_auxilio(
        db,
        id_taller=taller.id_taller,
        id_tipo_auxilio=payload.id_tipo_auxilio,
    )
    if existing:
        raise ValueError("El taller ya ofrece ese tipo de auxilio.")

    try:
        servicio = create_taller_auxilio(
            db,
            id_taller=taller.id_taller,
            id_tipo_auxilio=payload.id_tipo_auxilio,
            precio_referencial=payload.precio_referencial,
            disponible=payload.disponible,
        )
        db.commit()
        db.refresh(servicio)
        return TallerAuxilioResponse(
            id_taller_auxilio=servicio.id_taller_auxilio,
            id_taller=servicio.id_taller,
            id_tipo_auxilio=servicio.id_tipo_auxilio,
            nombre_tipo_auxilio=servicio.tipo_auxilio.nombre,
            descripcion_tipo_auxilio=servicio.tipo_auxilio.descripcion,
            precio_referencial=float(servicio.precio_referencial),
            disponible=servicio.disponible,
        )
    except Exception:
        db.rollback()
        raise


def actualizar_servicio_auxilio_service(
    db: Session,
    current_user,
    id_taller_auxilio: int,
    payload: TallerAuxilioUpdateRequest,
) -> TallerAuxilioResponse:
    taller = get_taller_by_usuario_id(db, current_user.id_usuario)
    if not taller:
        raise ValueError("El usuario autenticado no tiene perfil de taller.")

    servicio = get_taller_auxilio_by_id(db, id_taller_auxilio)
    if not servicio:
        raise ValueError("El servicio de auxilio especificado no existe.")
    if servicio.id_taller != taller.id_taller:
        raise ValueError("El servicio no pertenece al taller autenticado.")

    try:
        servicio_actualizado = update_taller_auxilio(
            db,
            servicio,
            precio_referencial=payload.precio_referencial,
            disponible=payload.disponible,
        )
        db.commit()
        db.refresh(servicio_actualizado)
        return TallerAuxilioResponse(
            id_taller_auxilio=servicio_actualizado.id_taller_auxilio,
            id_taller=servicio_actualizado.id_taller,
            id_tipo_auxilio=servicio_actualizado.id_tipo_auxilio,
            nombre_tipo_auxilio=servicio_actualizado.tipo_auxilio.nombre,
            descripcion_tipo_auxilio=servicio_actualizado.tipo_auxilio.descripcion,
            precio_referencial=float(servicio_actualizado.precio_referencial),
            disponible=servicio_actualizado.disponible,
        )
    except Exception:
        db.rollback()
        raise


def deshabilitar_servicio_auxilio_service(
    db: Session,
    current_user,
    id_taller_auxilio: int,
) -> TallerAuxilioResponse:
    taller = get_taller_by_usuario_id(db, current_user.id_usuario)
    if not taller:
        raise ValueError("El usuario autenticado no tiene perfil de taller.")

    servicio = get_taller_auxilio_by_id(db, id_taller_auxilio)
    if not servicio:
        raise ValueError("El servicio de auxilio especificado no existe.")
    if servicio.id_taller != taller.id_taller:
        raise ValueError("El servicio no pertenece al taller autenticado.")

    try:
        servicio_actualizado = set_disponibilidad_taller_auxilio(
            db,
            servicio,
            disponible=False,
        )
        db.commit()
        db.refresh(servicio_actualizado)
        return TallerAuxilioResponse(
            id_taller_auxilio=servicio_actualizado.id_taller_auxilio,
            id_taller=servicio_actualizado.id_taller,
            id_tipo_auxilio=servicio_actualizado.id_tipo_auxilio,
            nombre_tipo_auxilio=servicio_actualizado.tipo_auxilio.nombre,
            descripcion_tipo_auxilio=servicio_actualizado.tipo_auxilio.descripcion,
            precio_referencial=float(servicio_actualizado.precio_referencial),
            disponible=servicio_actualizado.disponible,
        )
    except Exception:
        db.rollback()
        raise
