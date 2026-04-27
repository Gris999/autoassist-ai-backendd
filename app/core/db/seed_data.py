from datetime import datetime, time, timedelta

from sqlalchemy import func, select

from app.core.db.session import SessionLocal
from app.core.security.security import hash_password
from app.modules.autenticacion_seguridad.models import (
    BitacoraSistema,
    Rol,
    Usuario,
    UsuarioRol,
)
from app.modules.gestion_clientes.models import Cliente, TipoVehiculo, Vehiculo
from app.modules.gestion_incidentes_atencion.models import (
    AsignacionServicio,
    EstadoServicio,
    Evidencia,
    HistorialIncidente,
    Incidente,
    Prioridad,
    SolicitudTaller,
    TipoIncidente,
)
from app.modules.gestion_operativa_taller_tecnico.models import (
    Especialidad,
    HorarioDisponibilidadTaller,
    Taller,
    TallerAuxilio,
    TallerTipoVehiculo,
    Tecnico,
    TecnicoEspecialidad,
    TipoAuxilio,
    TipoTaller,
    UnidadMovil,
)
from app.modules.seguimiento_monitoreo_servicio.models import (
    CalificacionServicio,
    ComisionPlataforma,
    DetallePago,
    MetricaIncidente,
    Notificacion,
    PagoServicio,
)

BASE_TIME = datetime(2026, 4, 24, 8, 0, 0)
DEFAULT_PASSWORD = "DemoAutoAssist123"


def get_or_create(session, model, defaults=None, **filters):
    instance = session.execute(
        select(model).filter_by(**filters)
    ).scalar_one_or_none()

    if instance:
        return instance, False

    params = {**filters, **(defaults or {})}
    instance = model(**params)
    session.add(instance)
    return instance, True


def get_by_name(session, model, nombre):
    instance = session.execute(
        select(model).where(model.nombre == nombre)
    ).scalar_one_or_none()
    if not instance:
        raise ValueError(f"No existe {model.__name__} con nombre '{nombre}'.")
    return instance


def ensure_user_role(session, usuario, role_name):
    rol = get_by_name(session, Rol, role_name)
    asignacion = session.execute(
        select(UsuarioRol).where(
            UsuarioRol.id_usuario == usuario.id_usuario,
            UsuarioRol.id_rol == rol.id_rol,
        )
    ).scalar_one_or_none()
    if not asignacion:
        session.add(
            UsuarioRol(
                id_usuario=usuario.id_usuario,
                id_rol=rol.id_rol,
            )
        )


def ensure_usuario(
    session,
    *,
    email,
    nombres,
    apellidos,
    celular,
    password=DEFAULT_PASSWORD,
    estado=True,
):
    usuario = session.execute(
        select(Usuario).where(Usuario.email == email)
    ).scalar_one_or_none()

    if usuario:
        usuario.nombres = nombres
        usuario.apellidos = apellidos
        usuario.celular = celular
        usuario.estado = estado
        if not usuario.password_hash:
            usuario.password_hash = hash_password(password)
        return usuario

    usuario = Usuario(
        nombres=nombres,
        apellidos=apellidos,
        celular=celular,
        email=email,
        password_hash=hash_password(password),
        estado=estado,
        fecha_registro=BASE_TIME,
    )
    session.add(usuario)
    session.flush()
    return usuario


def ensure_catalog_row(session, model, unique_field, payload):
    filters = {unique_field: payload[unique_field]}
    instance = session.execute(
        select(model).filter_by(**filters)
    ).scalar_one_or_none()
    if instance:
        for key, value in payload.items():
            setattr(instance, key, value)
        return instance

    instance = model(**payload)
    session.add(instance)
    return instance


def seed_roles(session):
    roles = [
        {"nombre": "CLIENTE", "descripcion": "Cliente que reporta incidentes y solicita auxilio"},
        {"nombre": "TALLER", "descripcion": "Taller que ofrece servicios de auxilio"},
        {"nombre": "TECNICO", "descripcion": "Tecnico asignado para atender incidentes"},
        {"nombre": "ADMIN", "descripcion": "Administrador de la plataforma"},
        {"nombre": "SISTEMA", "descripcion": "Actor automatico del sistema e integraciones de IA"},
    ]

    for item in roles:
        ensure_catalog_row(session, Rol, "nombre", item)

    rol_superadmin = session.execute(
        select(Rol).where(Rol.nombre == "SUPERADMIN")
    ).scalar_one_or_none()
    if rol_superadmin:
        asignaciones_superadmin = session.execute(
            select(UsuarioRol).where(UsuarioRol.id_rol == rol_superadmin.id_rol)
        ).scalars().all()
        for asignacion in asignaciones_superadmin:
            session.delete(asignacion)
        session.flush()
        session.delete(rol_superadmin)


def seed_admin_user(session):
    admin_email = "admin@autoassist.com"
    legacy_admin_email = "admin@autoassist.local"
    admin_password = "AdminAutoAssist123"

    usuario = session.execute(
        select(Usuario).where(
            Usuario.email.in_([admin_email, legacy_admin_email])
        )
    ).scalar_one_or_none()

    if usuario:
        usuario.email = admin_email
        usuario.nombres = "Admin"
        usuario.apellidos = "AutoAssist"
        usuario.celular = "70000000"
        usuario.estado = True
        if not usuario.password_hash:
            usuario.password_hash = hash_password(admin_password)
    else:
        usuario = Usuario(
            nombres="Admin",
            apellidos="AutoAssist",
            celular="70000000",
            email=admin_email,
            password_hash=hash_password(admin_password),
            estado=True,
            fecha_registro=BASE_TIME,
        )
        session.add(usuario)
        session.flush()

    rol_admin = get_by_name(session, Rol, "ADMIN")
    roles_legacy = list(
        session.execute(
            select(Rol).where(Rol.nombre.in_(["SUPERADMIN", "ADMIN"]))
        ).scalars()
    )

    for rol in roles_legacy:
        existe_asignacion = session.execute(
            select(UsuarioRol).where(
                UsuarioRol.id_usuario == usuario.id_usuario,
                UsuarioRol.id_rol == rol.id_rol,
            )
        ).scalar_one_or_none()
        if existe_asignacion and rol.nombre == "SUPERADMIN":
            session.delete(existe_asignacion)

    existe_admin = session.execute(
        select(UsuarioRol).where(
            UsuarioRol.id_usuario == usuario.id_usuario,
            UsuarioRol.id_rol == rol_admin.id_rol,
        )
    ).scalar_one_or_none()
    if not existe_admin:
        session.add(
            UsuarioRol(
                id_usuario=usuario.id_usuario,
                id_rol=rol_admin.id_rol,
            )
        )

    return usuario


def seed_tipos_taller(session):
    tipos = [
        {"nombre": "MECANICO_GENERAL", "descripcion": "Taller mecanico general"},
        {"nombre": "ELECTROMECANICO", "descripcion": "Taller especializado en sistemas electricos"},
        {"nombre": "GRUAS_Y_REMOLQUE", "descripcion": "Taller o empresa con servicio de grua y remolque"},
    ]

    for item in tipos:
        ensure_catalog_row(session, TipoTaller, "nombre", item)


def seed_tipos_vehiculo(session):
    tipos = [
        {"nombre": "AUTOMOVIL", "descripcion": "Vehiculo liviano particular"},
        {"nombre": "MOTOCICLETA", "descripcion": "Motocicleta de dos ruedas"},
        {"nombre": "CAMIONETA", "descripcion": "Vehiculo utilitario liviano"},
        {"nombre": "MINIBUS", "descripcion": "Vehiculo de transporte mediano"},
        {"nombre": "CAMION", "descripcion": "Vehiculo pesado de carga"},
    ]

    for item in tipos:
        ensure_catalog_row(session, TipoVehiculo, "nombre", item)


def seed_tipos_auxilio(session):
    tipos = [
        {
            "nombre": "REMOLQUE",
            "descripcion": "Traslado del vehiculo mediante grua",
            "requiere_unidad_movil": True,
            "requiere_remolque": True,
            "estado": True,
        },
        {
            "nombre": "AUXILIO_ELECTRICO",
            "descripcion": "Asistencia por bateria descargada o falla electrica basica",
            "requiere_unidad_movil": True,
            "requiere_remolque": False,
            "estado": True,
        },
        {
            "nombre": "CAMBIO_DE_LLANTA",
            "descripcion": "Cambio de llanta o asistencia por pinchazo",
            "requiere_unidad_movil": True,
            "requiere_remolque": False,
            "estado": True,
        },
        {
            "nombre": "SUMINISTRO_COMBUSTIBLE",
            "descripcion": "Entrega de combustible en ruta",
            "requiere_unidad_movil": True,
            "requiere_remolque": False,
            "estado": True,
        },
        {
            "nombre": "APERTURA_VEHICULO",
            "descripcion": "Apertura por llaves dentro del vehiculo",
            "requiere_unidad_movil": True,
            "requiere_remolque": False,
            "estado": True,
        },
        {
            "nombre": "AUXILIO_MECANICO_BASICO",
            "descripcion": "Asistencia mecanica basica en sitio",
            "requiere_unidad_movil": True,
            "requiere_remolque": False,
            "estado": True,
        },
    ]

    for item in tipos:
        ensure_catalog_row(session, TipoAuxilio, "nombre", item)


def seed_prioridades(session):
    prioridades = [
        {"nombre": "BAJA", "nivel": 1, "descripcion": "Incidente de baja urgencia"},
        {"nombre": "MEDIA", "nivel": 2, "descripcion": "Incidente de urgencia moderada"},
        {"nombre": "ALTA", "nivel": 3, "descripcion": "Incidente de alta urgencia"},
        {"nombre": "CRITICA", "nivel": 4, "descripcion": "Incidente critico o de riesgo alto"},
    ]

    for item in prioridades:
        ensure_catalog_row(session, Prioridad, "nombre", item)


def seed_estados_servicio(session):
    estados = [
        {"nombre": "REPORTADO", "descripcion": "Incidente reportado por el cliente", "orden_flujo": 1, "estado": True},
        {"nombre": "EN_VALIDACION", "descripcion": "Incidente en validacion inicial", "orden_flujo": 2, "estado": True},
        {"nombre": "BUSCANDO_TALLER", "descripcion": "Buscando taller candidato", "orden_flujo": 3, "estado": True},
        {"nombre": "ASIGNADO", "descripcion": "Servicio asignado a un taller/tecnico", "orden_flujo": 4, "estado": True},
        {"nombre": "EN_CAMINO", "descripcion": "Tecnico o unidad movil en camino", "orden_flujo": 5, "estado": True},
        {"nombre": "EN_ATENCION", "descripcion": "Incidente siendo atendido", "orden_flujo": 6, "estado": True},
        {"nombre": "FINALIZADO", "descripcion": "Servicio finalizado", "orden_flujo": 7, "estado": True},
        {"nombre": "CANCELADO", "descripcion": "Servicio cancelado", "orden_flujo": 8, "estado": True},
    ]

    for item in estados:
        ensure_catalog_row(session, EstadoServicio, "nombre", item)


def seed_tipos_incidente(session):
    tipos = [
        {"nombre": "FALLA_MECANICA", "descripcion": "Problema mecanico general", "estado": True},
        {"nombre": "BATERIA_DESCARGADA", "descripcion": "Vehiculo no enciende por bateria", "estado": True},
        {"nombre": "PINCHAZO_LLANTA", "descripcion": "Pinchazo o dano de llanta", "estado": True},
        {"nombre": "SIN_COMBUSTIBLE", "descripcion": "Vehiculo sin combustible", "estado": True},
        {"nombre": "LLAVES_DENTRO", "descripcion": "Llaves dentro del vehiculo o bloqueo", "estado": True},
        {"nombre": "ACCIDENTE_MENOR", "descripcion": "Accidente leve o colision menor", "estado": True},
        {"nombre": "SOBRECALENTAMIENTO", "descripcion": "Motor sobrecalentado", "estado": True},
    ]

    for item in tipos:
        ensure_catalog_row(session, TipoIncidente, "nombre", item)


def seed_especialidades(session):
    especialidades = [
        {"nombre": "MECANICA_GENERAL", "descripcion": "Diagnostico y reparacion mecanica basica"},
        {"nombre": "ELECTRICIDAD_AUTOMOTRIZ", "descripcion": "Diagnostico electrico automotriz"},
        {"nombre": "LLANTAS_Y_NEUMATICOS", "descripcion": "Cambio y soporte de llantas"},
        {"nombre": "GRUA_Y_REMOLQUE", "descripcion": "Operacion de grua y remolque"},
    ]

    for item in especialidades:
        ensure_catalog_row(session, Especialidad, "nombre", item)


def seed_demo_usuarios(session):
    usuarios = {
        "sistema": ensure_usuario(
            session,
            email="sistema@autoassist.com",
            nombres="Sistema",
            apellidos="AutoAssist",
            celular="79999999",
            password="SistemaAutoAssist123",
        ),
        "cliente_ana": ensure_usuario(
            session,
            email="ana.rojas@autoassist.com",
            nombres="Ana",
            apellidos="Rojas",
            celular="70100001",
        ),
        "cliente_luis": ensure_usuario(
            session,
            email="luis.fernandez@autoassist.com",
            nombres="Luis",
            apellidos="Fernandez",
            celular="70100002",
        ),
        "cliente_maria": ensure_usuario(
            session,
            email="maria.choque@autoassist.com",
            nombres="Maria",
            apellidos="Choque",
            celular="70100003",
        ),
        "taller_okenan": ensure_usuario(
            session,
            email="taller.okenan@autoassist.com",
            nombres="Yohan",
            apellidos="Cuenta",
            celular="76304135",
        ),
        "taller_electro": ensure_usuario(
            session,
            email="electro.sur@autoassist.com",
            nombres="Gabriela",
            apellidos="Lopez",
            celular="70120001",
        ),
        "taller_gruas": ensure_usuario(
            session,
            email="gruas.altiplano@autoassist.com",
            nombres="Rene",
            apellidos="Mamani",
            celular="70120002",
        ),
        "tecnico_carlos": ensure_usuario(
            session,
            email="carlos.quispe@autoassist.com",
            nombres="Carlos",
            apellidos="Quispe",
            celular="70210001",
        ),
        "tecnico_elena": ensure_usuario(
            session,
            email="elena.soto@autoassist.com",
            nombres="Elena",
            apellidos="Soto",
            celular="70210002",
        ),
        "tecnico_marco": ensure_usuario(
            session,
            email="marco.vargas@autoassist.com",
            nombres="Marco",
            apellidos="Vargas",
            celular="70210003",
        ),
        "tecnico_sofia": ensure_usuario(
            session,
            email="sofia.mamani@autoassist.com",
            nombres="Sofia",
            apellidos="Mamani",
            celular="70210004",
        ),
    }

    ensure_user_role(session, usuarios["sistema"], "SISTEMA")
    ensure_user_role(session, usuarios["cliente_ana"], "CLIENTE")
    ensure_user_role(session, usuarios["cliente_luis"], "CLIENTE")
    ensure_user_role(session, usuarios["cliente_maria"], "CLIENTE")
    ensure_user_role(session, usuarios["taller_okenan"], "TALLER")
    ensure_user_role(session, usuarios["taller_electro"], "TALLER")
    ensure_user_role(session, usuarios["taller_gruas"], "TALLER")
    ensure_user_role(session, usuarios["tecnico_carlos"], "TECNICO")
    ensure_user_role(session, usuarios["tecnico_elena"], "TECNICO")
    ensure_user_role(session, usuarios["tecnico_marco"], "TECNICO")
    ensure_user_role(session, usuarios["tecnico_sofia"], "TECNICO")

    return usuarios


def seed_demo_clientes(session, usuarios):
    clientes = {
        "ana": get_or_create(
            session,
            Cliente,
            id_usuario=usuarios["cliente_ana"].id_usuario,
        )[0],
        "luis": get_or_create(
            session,
            Cliente,
            id_usuario=usuarios["cliente_luis"].id_usuario,
        )[0],
        "maria": get_or_create(
            session,
            Cliente,
            id_usuario=usuarios["cliente_maria"].id_usuario,
        )[0],
    }
    session.flush()
    return clientes


def seed_demo_talleres(session, usuarios):
    tipos_taller = {
        "mecanico": get_by_name(session, TipoTaller, "MECANICO_GENERAL"),
        "electro": get_by_name(session, TipoTaller, "ELECTROMECANICO"),
        "grua": get_by_name(session, TipoTaller, "GRUAS_Y_REMOLQUE"),
    }

    talleres = {
        "okenan": get_or_create(
            session,
            Taller,
            nit="12345",
            defaults={
                "id_usuario": usuarios["taller_okenan"].id_usuario,
                "id_tipo_taller": tipos_taller["mecanico"].id_tipo_taller,
                "nombre_taller": "Taller Okenan",
                "direccion": "La Campana, Santa Cruz",
                "latitud": -17.7833000,
                "longitud": -63.1821000,
                "radio_cobertura_km": 18,
                "disponible": True,
                "fecha_registro": BASE_TIME,
            },
        )[0],
        "electro_sur": get_or_create(
            session,
            Taller,
            nit="89001",
            defaults={
                "id_usuario": usuarios["taller_electro"].id_usuario,
                "id_tipo_taller": tipos_taller["electro"].id_tipo_taller,
                "nombre_taller": "Electro Sur",
                "direccion": "Av. Busch 1200, La Paz",
                "latitud": -16.5037000,
                "longitud": -68.1316000,
                "radio_cobertura_km": 15,
                "disponible": True,
                "fecha_registro": BASE_TIME,
            },
        )[0],
        "gruas_altiplano": get_or_create(
            session,
            Taller,
            nit="45500",
            defaults={
                "id_usuario": usuarios["taller_gruas"].id_usuario,
                "id_tipo_taller": tipos_taller["grua"].id_tipo_taller,
                "nombre_taller": "Gruas Altiplano",
                "direccion": "Zona 16 de Julio, El Alto",
                "latitud": -16.5047000,
                "longitud": -68.1644000,
                "radio_cobertura_km": 25,
                "disponible": True,
                "fecha_registro": BASE_TIME,
            },
        )[0],
    }

    session.flush()
    return talleres


def seed_horarios_taller(session, talleres):
    horarios = {
        "okenan": [
            ("LUNES", time(8, 0), time(12, 0), True),
            ("LUNES", time(14, 0), time(18, 0), True),
            ("MARTES", time(8, 0), time(18, 0), True),
            ("MIERCOLES", time(8, 0), time(18, 0), True),
            ("JUEVES", time(8, 0), time(18, 0), True),
            ("VIERNES", time(8, 0), time(18, 0), True),
        ],
        "electro_sur": [
            ("LUNES", time(9, 0), time(19, 0), True),
            ("MARTES", time(9, 0), time(19, 0), True),
            ("MIERCOLES", time(9, 0), time(19, 0), True),
            ("JUEVES", time(9, 0), time(19, 0), True),
            ("VIERNES", time(9, 0), time(19, 0), True),
            ("SABADO", time(9, 0), time(14, 0), True),
        ],
        "gruas_altiplano": [
            ("LUNES", time(0, 0), time(23, 59), True),
            ("MARTES", time(0, 0), time(23, 59), True),
            ("MIERCOLES", time(0, 0), time(23, 59), True),
            ("JUEVES", time(0, 0), time(23, 59), True),
            ("VIERNES", time(0, 0), time(23, 59), True),
            ("SABADO", time(0, 0), time(23, 59), True),
            ("DOMINGO", time(0, 0), time(23, 59), True),
        ],
    }

    for taller_key, items in horarios.items():
        taller = talleres[taller_key]
        for dia_semana, hora_inicio, hora_fin, estado in items:
            get_or_create(
                session,
                HorarioDisponibilidadTaller,
                id_taller=taller.id_taller,
                dia_semana=dia_semana,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                defaults={"estado": estado},
            )


def seed_demo_tecnicos(session, usuarios, talleres):
    tecnicos = {
        "carlos": get_or_create(
            session,
            Tecnico,
            id_usuario=usuarios["tecnico_carlos"].id_usuario,
            defaults={
                "id_taller": talleres["okenan"].id_taller,
                "telefono_contacto": "70210001",
                "disponible": True,
                "estado": True,
                "latitud_actual": -17.7841000,
                "longitud_actual": -63.1818000,
            },
        )[0],
        "elena": get_or_create(
            session,
            Tecnico,
            id_usuario=usuarios["tecnico_elena"].id_usuario,
            defaults={
                "id_taller": talleres["okenan"].id_taller,
                "telefono_contacto": "70210002",
                "disponible": False,
                "estado": True,
                "latitud_actual": -17.7850000,
                "longitud_actual": -63.1805000,
            },
        )[0],
        "marco": get_or_create(
            session,
            Tecnico,
            id_usuario=usuarios["tecnico_marco"].id_usuario,
            defaults={
                "id_taller": talleres["electro_sur"].id_taller,
                "telefono_contacto": "70210003",
                "disponible": True,
                "estado": True,
                "latitud_actual": -16.5028000,
                "longitud_actual": -68.1329000,
            },
        )[0],
        "sofia": get_or_create(
            session,
            Tecnico,
            id_usuario=usuarios["tecnico_sofia"].id_usuario,
            defaults={
                "id_taller": talleres["gruas_altiplano"].id_taller,
                "telefono_contacto": "70210004",
                "disponible": True,
                "estado": True,
                "latitud_actual": -16.5051000,
                "longitud_actual": -68.1650000,
            },
        )[0],
    }
    session.flush()
    return tecnicos


def seed_tecnico_especialidades(session, tecnicos):
    especialidades = {
        "mecanica": get_by_name(session, Especialidad, "MECANICA_GENERAL"),
        "electrica": get_by_name(session, Especialidad, "ELECTRICIDAD_AUTOMOTRIZ"),
        "llantas": get_by_name(session, Especialidad, "LLANTAS_Y_NEUMATICOS"),
        "grua": get_by_name(session, Especialidad, "GRUA_Y_REMOLQUE"),
    }

    relaciones = [
        (tecnicos["carlos"], especialidades["mecanica"]),
        (tecnicos["carlos"], especialidades["llantas"]),
        (tecnicos["elena"], especialidades["electrica"]),
        (tecnicos["marco"], especialidades["electrica"]),
        (tecnicos["sofia"], especialidades["grua"]),
    ]

    for tecnico, especialidad in relaciones:
        get_or_create(
            session,
            TecnicoEspecialidad,
            id_tecnico=tecnico.id_tecnico,
            id_especialidad=especialidad.id_especialidad,
        )


def seed_unidades_moviles(session, talleres):
    unidades = {
        "okenan_camioneta": get_or_create(
            session,
            UnidadMovil,
            placa="OKN-001",
            defaults={
                "id_taller": talleres["okenan"].id_taller,
                "tipo_unidad": "CAMIONETA_TALLER",
                "disponible": True,
                "latitud_actual": -17.7838000,
                "longitud_actual": -63.1817000,
                "estado": True,
            },
        )[0],
        "okenan_moto": get_or_create(
            session,
            UnidadMovil,
            placa="OKN-002",
            defaults={
                "id_taller": talleres["okenan"].id_taller,
                "tipo_unidad": "MOTO_AUXILIO",
                "disponible": True,
                "latitud_actual": -17.7834000,
                "longitud_actual": -63.1824000,
                "estado": True,
            },
        )[0],
        "electro_furgon": get_or_create(
            session,
            UnidadMovil,
            placa="ELS-101",
            defaults={
                "id_taller": talleres["electro_sur"].id_taller,
                "tipo_unidad": "FURGON_ELECTRICO",
                "disponible": True,
                "latitud_actual": -16.5035000,
                "longitud_actual": -68.1321000,
                "estado": True,
            },
        )[0],
        "grua_pesada": get_or_create(
            session,
            UnidadMovil,
            placa="GRA-900",
            defaults={
                "id_taller": talleres["gruas_altiplano"].id_taller,
                "tipo_unidad": "GRUA_PESADA",
                "disponible": True,
                "latitud_actual": -16.5049000,
                "longitud_actual": -68.1649000,
                "estado": True,
            },
        )[0],
    }
    session.flush()
    return unidades


def seed_talleres_tipo_vehiculo(session, talleres):
    tipos_vehiculo = {
        "AUTOMOVIL": get_by_name(session, TipoVehiculo, "AUTOMOVIL"),
        "MOTOCICLETA": get_by_name(session, TipoVehiculo, "MOTOCICLETA"),
        "CAMIONETA": get_by_name(session, TipoVehiculo, "CAMIONETA"),
        "MINIBUS": get_by_name(session, TipoVehiculo, "MINIBUS"),
        "CAMION": get_by_name(session, TipoVehiculo, "CAMION"),
    }

    relaciones = {
        "okenan": ["AUTOMOVIL", "CAMIONETA"],
        "electro_sur": ["AUTOMOVIL", "MOTOCICLETA", "MINIBUS"],
        "gruas_altiplano": ["AUTOMOVIL", "CAMIONETA", "MINIBUS", "CAMION"],
    }

    for taller_key, tipos in relaciones.items():
        taller = talleres[taller_key]
        for tipo_nombre in tipos:
            tipo_vehiculo = tipos_vehiculo[tipo_nombre]
            get_or_create(
                session,
                TallerTipoVehiculo,
                id_taller=taller.id_taller,
                id_tipo_vehiculo=tipo_vehiculo.id_tipo_vehiculo,
            )


def seed_talleres_auxilio(session, talleres):
    tipos_auxilio = {
        "REMOLQUE": get_by_name(session, TipoAuxilio, "REMOLQUE"),
        "AUXILIO_ELECTRICO": get_by_name(session, TipoAuxilio, "AUXILIO_ELECTRICO"),
        "CAMBIO_DE_LLANTA": get_by_name(session, TipoAuxilio, "CAMBIO_DE_LLANTA"),
        "SUMINISTRO_COMBUSTIBLE": get_by_name(session, TipoAuxilio, "SUMINISTRO_COMBUSTIBLE"),
        "APERTURA_VEHICULO": get_by_name(session, TipoAuxilio, "APERTURA_VEHICULO"),
        "AUXILIO_MECANICO_BASICO": get_by_name(session, TipoAuxilio, "AUXILIO_MECANICO_BASICO"),
    }

    servicios = [
        ("okenan", "AUXILIO_MECANICO_BASICO", 180, True),
        ("okenan", "CAMBIO_DE_LLANTA", 80, True),
        ("okenan", "SUMINISTRO_COMBUSTIBLE", 70, True),
        ("electro_sur", "AUXILIO_ELECTRICO", 160, True),
        ("electro_sur", "APERTURA_VEHICULO", 90, True),
        ("electro_sur", "CAMBIO_DE_LLANTA", 85, True),
        ("gruas_altiplano", "REMOLQUE", 350, True),
        ("gruas_altiplano", "AUXILIO_MECANICO_BASICO", 200, True),
        ("gruas_altiplano", "SUMINISTRO_COMBUSTIBLE", 100, True),
    ]

    relaciones = {}
    for taller_key, tipo_auxilio_nombre, precio_referencial, disponible in servicios:
        taller = talleres[taller_key]
        tipo_auxilio = tipos_auxilio[tipo_auxilio_nombre]
        relacion = get_or_create(
            session,
            TallerAuxilio,
            id_taller=taller.id_taller,
            id_tipo_auxilio=tipo_auxilio.id_tipo_auxilio,
            defaults={
                "precio_referencial": precio_referencial,
                "disponible": disponible,
            },
        )[0]
        relaciones[(taller_key, tipo_auxilio_nombre)] = relacion

    session.flush()
    return relaciones


def seed_vehiculos(session, clientes):
    tipos = {
        "AUTOMOVIL": get_by_name(session, TipoVehiculo, "AUTOMOVIL"),
        "MOTOCICLETA": get_by_name(session, TipoVehiculo, "MOTOCICLETA"),
        "CAMIONETA": get_by_name(session, TipoVehiculo, "CAMIONETA"),
        "MINIBUS": get_by_name(session, TipoVehiculo, "MINIBUS"),
        "CAMION": get_by_name(session, TipoVehiculo, "CAMION"),
    }

    vehiculos = {
        "ana_auto": get_or_create(
            session,
            Vehiculo,
            placa="1234ABC",
            defaults={
                "id_cliente": clientes["ana"].id_cliente,
                "id_tipo_vehiculo": tipos["AUTOMOVIL"].id_tipo_vehiculo,
                "marca": "Toyota",
                "modelo": "Corolla",
                "anio": 2019,
                "color": "Blanco",
                "descripcion_referencia": "Sedan blanco con sticker lateral",
                "estado": True,
            },
        )[0],
        "luis_camioneta": get_or_create(
            session,
            Vehiculo,
            placa="5678DEF",
            defaults={
                "id_cliente": clientes["luis"].id_cliente,
                "id_tipo_vehiculo": tipos["CAMIONETA"].id_tipo_vehiculo,
                "marca": "Nissan",
                "modelo": "Frontier",
                "anio": 2018,
                "color": "Plata",
                "descripcion_referencia": "Camioneta con parrilla negra",
                "estado": True,
            },
        )[0],
        "maria_camion": get_or_create(
            session,
            Vehiculo,
            placa="9012GHI",
            defaults={
                "id_cliente": clientes["maria"].id_cliente,
                "id_tipo_vehiculo": tipos["CAMION"].id_tipo_vehiculo,
                "marca": "Volvo",
                "modelo": "FH",
                "anio": 2017,
                "color": "Azul",
                "descripcion_referencia": "Camion de carga azul con lona",
                "estado": True,
            },
        )[0],
        "ana_moto": get_or_create(
            session,
            Vehiculo,
            placa="3456JKL",
            defaults={
                "id_cliente": clientes["ana"].id_cliente,
                "id_tipo_vehiculo": tipos["MOTOCICLETA"].id_tipo_vehiculo,
                "marca": "Suzuki",
                "modelo": "Gixxer",
                "anio": 2021,
                "color": "Negro",
                "descripcion_referencia": "Moto negra con casco rojo",
                "estado": True,
            },
        )[0],
    }

    session.flush()
    return vehiculos


def seed_incidentes(
    session,
    *,
    clientes,
    vehiculos,
    talleres,
    tecnicos,
    unidades,
    usuarios,
):
    prioridades = {
        "BAJA": get_by_name(session, Prioridad, "BAJA"),
        "MEDIA": get_by_name(session, Prioridad, "MEDIA"),
        "ALTA": get_by_name(session, Prioridad, "ALTA"),
    }
    estados = {
        "REPORTADO": get_by_name(session, EstadoServicio, "REPORTADO"),
        "BUSCANDO_TALLER": get_by_name(session, EstadoServicio, "BUSCANDO_TALLER"),
        "ASIGNADO": get_by_name(session, EstadoServicio, "ASIGNADO"),
        "EN_CAMINO": get_by_name(session, EstadoServicio, "EN_CAMINO"),
        "EN_ATENCION": get_by_name(session, EstadoServicio, "EN_ATENCION"),
        "FINALIZADO": get_by_name(session, EstadoServicio, "FINALIZADO"),
    }
    tipos_incidente = {
        "BATERIA_DESCARGADA": get_by_name(session, TipoIncidente, "BATERIA_DESCARGADA"),
        "PINCHAZO_LLANTA": get_by_name(session, TipoIncidente, "PINCHAZO_LLANTA"),
        "SIN_COMBUSTIBLE": get_by_name(session, TipoIncidente, "SIN_COMBUSTIBLE"),
    }

    incidentes = {
        "bateria_ana": get_or_create(
            session,
            Incidente,
            titulo="Bateria descargada en zona Sur",
            defaults={
                "id_cliente": clientes["ana"].id_cliente,
                "id_vehiculo": vehiculos["ana_auto"].id_vehiculo,
                "id_tipo_incidente": tipos_incidente["BATERIA_DESCARGADA"].id_tipo_incidente,
                "id_prioridad": prioridades["MEDIA"].id_prioridad,
                "id_estado_servicio_actual": estados["FINALIZADO"].id_estado_servicio,
                "descripcion_texto": "El vehiculo no enciende desde hace 20 minutos.",
                "direccion_referencia": "Av. Ballivian, frente al supermercado",
                "latitud": -16.5342000,
                "longitud": -68.0878000,
                "fecha_reporte": BASE_TIME,
                "clasificacion_ia": "AUXILIO_ELECTRICO",
                "confianza_clasificacion": 92.50,
                "resumen_ia": "Posible bateria descargada. Recomienda taller electrico cercano.",
                "requiere_mas_info": False,
            },
        )[0],
        "llanta_luis": get_or_create(
            session,
            Incidente,
            titulo="Pinchazo en carretera al Norte",
            defaults={
                "id_cliente": clientes["luis"].id_cliente,
                "id_vehiculo": vehiculos["luis_camioneta"].id_vehiculo,
                "id_tipo_incidente": tipos_incidente["PINCHAZO_LLANTA"].id_tipo_incidente,
                "id_prioridad": prioridades["ALTA"].id_prioridad,
                "id_estado_servicio_actual": estados["EN_CAMINO"].id_estado_servicio,
                "descripcion_texto": "La camioneta sufrio un pinchazo, no cuento con gato hidraulico.",
                "direccion_referencia": "Ruta al Norte km 12",
                "latitud": -17.7355000,
                "longitud": -63.1332000,
                "fecha_reporte": BASE_TIME + timedelta(hours=2),
                "clasificacion_ia": "CAMBIO_DE_LLANTA",
                "confianza_clasificacion": 88.20,
                "resumen_ia": "Se recomienda enviar unidad ligera con herramientas para llanta.",
                "requiere_mas_info": False,
            },
        )[0],
        "combustible_maria": get_or_create(
            session,
            Incidente,
            titulo="Camion sin combustible en perifera",
            defaults={
                "id_cliente": clientes["maria"].id_cliente,
                "id_vehiculo": vehiculos["maria_camion"].id_vehiculo,
                "id_tipo_incidente": tipos_incidente["SIN_COMBUSTIBLE"].id_tipo_incidente,
                "id_prioridad": prioridades["BAJA"].id_prioridad,
                "id_estado_servicio_actual": estados["BUSCANDO_TALLER"].id_estado_servicio,
                "descripcion_texto": "El camion quedo detenido y necesita combustible para llegar a la estacion.",
                "direccion_referencia": "Periferica altura puente rojo",
                "latitud": -16.4703000,
                "longitud": -68.1311000,
                "fecha_reporte": BASE_TIME + timedelta(hours=4),
                "clasificacion_ia": "SUMINISTRO_COMBUSTIBLE",
                "confianza_clasificacion": 84.70,
                "resumen_ia": "Servicio compatible con unidad movil y suministro en ruta.",
                "requiere_mas_info": True,
            },
        )[0],
    }

    incidentes["bateria_ana"].id_estado_servicio_actual = estados["FINALIZADO"].id_estado_servicio
    incidentes["llanta_luis"].id_estado_servicio_actual = estados["EN_CAMINO"].id_estado_servicio
    incidentes["combustible_maria"].id_estado_servicio_actual = estados["BUSCANDO_TALLER"].id_estado_servicio
    session.flush()

    evidencias = [
        (
            incidentes["bateria_ana"],
            "IMAGEN",
            "https://example.com/evidencias/bateria-ana-1.jpg",
            "Tablero sin respuesta al girar llave",
            "Foto del tablero del vehiculo",
            BASE_TIME,
        ),
        (
            incidentes["llanta_luis"],
            "IMAGEN",
            "https://example.com/evidencias/llanta-luis-1.jpg",
            None,
            "Foto de la llanta pinchada",
            BASE_TIME + timedelta(hours=2),
        ),
        (
            incidentes["combustible_maria"],
            "AUDIO",
            "https://example.com/evidencias/combustible-maria-1.mp3",
            "Cliente indica que el tanque esta vacio y la unidad esta asegurada.",
            "Audio del cliente describiendo la situacion",
            BASE_TIME + timedelta(hours=4),
        ),
    ]

    for incidente, tipo_evidencia, archivo_url, texto_extraido, descripcion, fecha_registro in evidencias:
        get_or_create(
            session,
            Evidencia,
            id_incidente=incidente.id_incidente,
            archivo_url=archivo_url,
            defaults={
                "tipo_evidencia": tipo_evidencia,
                "texto_extraido": texto_extraido,
                "descripcion": descripcion,
                "fecha_registro": fecha_registro,
            },
        )

    solicitudes = [
        (
            incidentes["bateria_ana"],
            talleres["electro_sur"],
            4.2,
            95.5,
            "ACEPTADA",
            BASE_TIME + timedelta(minutes=5),
            BASE_TIME + timedelta(minutes=8),
        ),
        (
            incidentes["bateria_ana"],
            talleres["okenan"],
            7.8,
            74.0,
            "RECHAZADA",
            BASE_TIME + timedelta(minutes=6),
            BASE_TIME + timedelta(minutes=12),
        ),
        (
            incidentes["llanta_luis"],
            talleres["okenan"],
            6.1,
            90.0,
            "ACEPTADA",
            BASE_TIME + timedelta(hours=2, minutes=5),
            BASE_TIME + timedelta(hours=2, minutes=10),
        ),
        (
            incidentes["combustible_maria"],
            talleres["gruas_altiplano"],
            5.4,
            87.2,
            "PENDIENTE",
            BASE_TIME + timedelta(hours=4, minutes=4),
            None,
        ),
        (
            incidentes["combustible_maria"],
            talleres["okenan"],
            12.6,
            55.0,
            "RECHAZADA",
            BASE_TIME + timedelta(hours=4, minutes=6),
            BASE_TIME + timedelta(hours=4, minutes=20),
        ),
    ]

    for incidente, taller, distancia_km, puntaje_asignacion, estado_solicitud, fecha_envio, fecha_respuesta in solicitudes:
        get_or_create(
            session,
            SolicitudTaller,
            id_incidente=incidente.id_incidente,
            id_taller=taller.id_taller,
            defaults={
                "distancia_km": distancia_km,
                "puntaje_asignacion": puntaje_asignacion,
                "estado_solicitud": estado_solicitud,
                "fecha_envio": fecha_envio,
                "fecha_respuesta": fecha_respuesta,
            },
        )

    asignaciones = {
        "bateria_ana": get_or_create(
            session,
            AsignacionServicio,
            id_incidente=incidentes["bateria_ana"].id_incidente,
            defaults={
                "id_taller": talleres["electro_sur"].id_taller,
                "id_tecnico": tecnicos["marco"].id_tecnico,
                "id_unidad_movil": unidades["electro_furgon"].id_unidad_movil,
                "fecha_asignacion": BASE_TIME + timedelta(minutes=10),
                "tiempo_estimado_min": 25,
                "estado_asignacion": "FINALIZADA",
                "observaciones": "Atencion electrica completada en sitio.",
            },
        )[0],
        "llanta_luis": get_or_create(
            session,
            AsignacionServicio,
            id_incidente=incidentes["llanta_luis"].id_incidente,
            defaults={
                "id_taller": talleres["okenan"].id_taller,
                "id_tecnico": tecnicos["carlos"].id_tecnico,
                "id_unidad_movil": unidades["okenan_camioneta"].id_unidad_movil,
                "fecha_asignacion": BASE_TIME + timedelta(hours=2, minutes=12),
                "tiempo_estimado_min": 30,
                "estado_asignacion": "EN_CAMINO",
                "observaciones": "Tecnico en ruta con kit de cambio de llanta.",
            },
        )[0],
    }

    historial = [
        (
            incidentes["bateria_ana"],
            None,
            estados["REPORTADO"],
            usuarios["cliente_ana"],
            BASE_TIME,
            "Cliente reporta que el vehiculo no enciende.",
        ),
        (
            incidentes["bateria_ana"],
            estados["REPORTADO"],
            estados["BUSCANDO_TALLER"],
            usuarios["sistema"],
            BASE_TIME + timedelta(minutes=3),
            "Sistema analiza el incidente y busca taller electrico cercano.",
        ),
        (
            incidentes["bateria_ana"],
            estados["BUSCANDO_TALLER"],
            estados["ASIGNADO"],
            usuarios["taller_electro"],
            BASE_TIME + timedelta(minutes=10),
            "Taller Electro Sur acepta la solicitud.",
        ),
        (
            incidentes["bateria_ana"],
            estados["ASIGNADO"],
            estados["EN_CAMINO"],
            usuarios["tecnico_marco"],
            BASE_TIME + timedelta(minutes=15),
            "Tecnico sale hacia el punto del incidente.",
        ),
        (
            incidentes["bateria_ana"],
            estados["EN_CAMINO"],
            estados["EN_ATENCION"],
            usuarios["tecnico_marco"],
            BASE_TIME + timedelta(minutes=35),
            "Tecnico inicia revision electrica del vehiculo.",
        ),
        (
            incidentes["bateria_ana"],
            estados["EN_ATENCION"],
            estados["FINALIZADO"],
            usuarios["tecnico_marco"],
            BASE_TIME + timedelta(minutes=55),
            "Se realiza paso de corriente y verificacion de bateria.",
        ),
        (
            incidentes["llanta_luis"],
            None,
            estados["REPORTADO"],
            usuarios["cliente_luis"],
            BASE_TIME + timedelta(hours=2),
            "Cliente reporta pinchazo en carretera.",
        ),
        (
            incidentes["llanta_luis"],
            estados["REPORTADO"],
            estados["BUSCANDO_TALLER"],
            usuarios["sistema"],
            BASE_TIME + timedelta(hours=2, minutes=2),
            "Sistema prioriza el incidente por ubicacion en carretera.",
        ),
        (
            incidentes["llanta_luis"],
            estados["BUSCANDO_TALLER"],
            estados["ASIGNADO"],
            usuarios["taller_okenan"],
            BASE_TIME + timedelta(hours=2, minutes=12),
            "Taller Okenan acepta la atencion.",
        ),
        (
            incidentes["llanta_luis"],
            estados["ASIGNADO"],
            estados["EN_CAMINO"],
            usuarios["tecnico_carlos"],
            BASE_TIME + timedelta(hours=2, minutes=18),
            "Tecnico en desplazamiento con herramientas.",
        ),
        (
            incidentes["combustible_maria"],
            None,
            estados["REPORTADO"],
            usuarios["cliente_maria"],
            BASE_TIME + timedelta(hours=4),
            "Cliente reporta unidad pesada sin combustible.",
        ),
        (
            incidentes["combustible_maria"],
            estados["REPORTADO"],
            estados["BUSCANDO_TALLER"],
            usuarios["sistema"],
            BASE_TIME + timedelta(hours=4, minutes=3),
            "Sistema solicita mas informacion y propone talleres candidatos.",
        ),
    ]

    for incidente, estado_anterior, estado_nuevo, usuario_actor, fecha_hora, detalle in historial:
        filters = {
            "id_incidente": incidente.id_incidente,
            "id_estado_nuevo": estado_nuevo.id_estado_servicio,
            "id_usuario_actor": usuario_actor.id_usuario,
            "detalle": detalle,
        }
        defaults = {
            "id_estado_anterior": (
                estado_anterior.id_estado_servicio if estado_anterior else None
            ),
            "fecha_hora": fecha_hora,
        }
        get_or_create(session, HistorialIncidente, defaults=defaults, **filters)

    session.flush()
    return incidentes, asignaciones


def seed_seguimiento_y_finanzas(
    session,
    *,
    incidentes,
    asignaciones,
    talleres_auxilio,
    talleres,
    clientes,
    tecnicos,
):
    pago_bateria = get_or_create(
        session,
        PagoServicio,
        id_incidente=incidentes["bateria_ana"].id_incidente,
        defaults={
            "monto_total": 160,
            "metodo_pago": "QR",
            "estado_pago": "PAGADO",
            "fecha_pago": BASE_TIME + timedelta(hours=1, minutes=5),
            "referencia_transaccion": "TRX-BA-20260424-001",
        },
    )[0]
    session.flush()

    get_or_create(
        session,
        DetallePago,
        id_pago_servicio=pago_bateria.id_pago_servicio,
        id_taller_auxilio=talleres_auxilio[("electro_sur", "AUXILIO_ELECTRICO")].id_taller_auxilio,
        descripcion="Servicio de auxilio electrico en sitio",
        defaults={
            "cantidad": 1,
            "precio_unitario": 160,
            "subtotal": 160,
        },
    )

    get_or_create(
        session,
        ComisionPlataforma,
        id_pago_servicio=pago_bateria.id_pago_servicio,
        defaults={
            "id_taller": talleres["electro_sur"].id_taller,
            "porcentaje": 10,
            "monto_comision": 16,
            "fecha_calculo": BASE_TIME + timedelta(hours=1, minutes=6),
            "estado": "LIQUIDADA",
        },
    )

    get_or_create(
        session,
        CalificacionServicio,
        id_incidente=incidentes["bateria_ana"].id_incidente,
        defaults={
            "id_cliente": clientes["ana"].id_cliente,
            "id_taller": talleres["electro_sur"].id_taller,
            "id_tecnico": tecnicos["marco"].id_tecnico,
            "puntuacion": 4.8,
            "comentario": "Atencion rapida y explicacion clara del problema.",
            "fecha_calificacion": BASE_TIME + timedelta(hours=1, minutes=20),
        },
    )

    get_or_create(
        session,
        MetricaIncidente,
        id_incidente=incidentes["bateria_ana"].id_incidente,
        defaults={
            "tiempo_asignacion_seg": 600,
            "tiempo_llegada_seg": 1500,
            "tiempo_resolucion_seg": 3300,
            "cantidad_rechazos": 1,
            "fue_reasignado": False,
            "fecha_registro": BASE_TIME + timedelta(hours=1, minutes=10),
        },
    )

    get_or_create(
        session,
        MetricaIncidente,
        id_incidente=incidentes["llanta_luis"].id_incidente,
        defaults={
            "tiempo_asignacion_seg": 720,
            "tiempo_llegada_seg": None,
            "tiempo_resolucion_seg": None,
            "cantidad_rechazos": 0,
            "fue_reasignado": False,
            "fecha_registro": BASE_TIME + timedelta(hours=2, minutes=20),
        },
    )


def seed_notificaciones(session, incidentes, usuarios):
    notificaciones = [
        (
            usuarios["cliente_ana"].id_usuario,
            incidentes["bateria_ana"].id_incidente,
            "Taller asignado",
            "Electro Sur atendera tu incidente de bateria.",
            "ASIGNACION",
            True,
            BASE_TIME + timedelta(minutes=11),
        ),
        (
            usuarios["tecnico_marco"].id_usuario,
            incidentes["bateria_ana"].id_incidente,
            "Nuevo incidente electrico",
            "Te fue asignado un incidente de bateria descargada.",
            "OPERATIVA",
            True,
            BASE_TIME + timedelta(minutes=11),
        ),
        (
            usuarios["cliente_luis"].id_usuario,
            incidentes["llanta_luis"].id_incidente,
            "Tecnico en camino",
            "Carlos Quispe va rumbo a tu ubicacion.",
            "SEGUIMIENTO",
            False,
            BASE_TIME + timedelta(hours=2, minutes=19),
        ),
        (
            usuarios["cliente_maria"].id_usuario,
            incidentes["combustible_maria"].id_incidente,
            "Se requiere mas informacion",
            "El sistema solicita confirmar tipo de combustible y ubicacion exacta.",
            "VALIDACION",
            False,
            BASE_TIME + timedelta(hours=4, minutes=5),
        ),
        (
            usuarios["sistema"].id_usuario,
            None,
            "Ciclo de seeds ejecutado",
            "La base de datos de demostracion fue poblada correctamente.",
            "SISTEMA",
            True,
            BASE_TIME + timedelta(hours=6),
        ),
    ]

    for id_usuario, id_incidente, titulo, mensaje, tipo_notificacion, leido, fecha_envio in notificaciones:
        get_or_create(
            session,
            Notificacion,
            id_usuario=id_usuario,
            titulo=titulo,
            mensaje=mensaje,
            defaults={
                "id_incidente": id_incidente,
                "tipo_notificacion": tipo_notificacion,
                "leido": leido,
                "fecha_envio": fecha_envio,
            },
        )


def seed_bitacora(session, usuarios):
    registros = [
        (
            usuarios["cliente_ana"].id_usuario,
            "REPORTE_INCIDENTE",
            "gestion_incidentes_atencion",
            "Cliente Ana Rojas reporta incidente de bateria descargada.",
            BASE_TIME,
            "127.0.0.1",
        ),
        (
            usuarios["taller_okenan"].id_usuario,
            "ACTUALIZAR_DISPONIBILIDAD",
            "gestion_operativa_taller_tecnico",
            "Taller Okenan confirma disponibilidad y cobertura.",
            BASE_TIME + timedelta(minutes=1),
            "127.0.0.1",
        ),
        (
            usuarios["taller_electro"].id_usuario,
            "ACEPTAR_SOLICITUD",
            "gestion_incidentes_atencion",
            "Electro Sur acepta incidente de bateria descargada.",
            BASE_TIME + timedelta(minutes=10),
            "127.0.0.1",
        ),
        (
            usuarios["sistema"].id_usuario,
            "CLASIFICACION_IA",
            "inteligencia_gestion_estrategica",
            "Sistema clasifica automaticamente un incidente como AUXILIO_ELECTRICO.",
            BASE_TIME + timedelta(minutes=2),
            "internal",
        ),
        (
            usuarios["sistema"].id_usuario,
            "SEED_COMPLETO",
            "core.db.seed_data",
            "Poblado integral de la base de datos de demostracion.",
            BASE_TIME + timedelta(hours=6),
            "internal",
        ),
    ]

    for id_usuario, accion, modulo, descripcion, fecha_hora, ip_origen in registros:
        get_or_create(
            session,
            BitacoraSistema,
            id_usuario=id_usuario,
            accion=accion,
            modulo=modulo,
            descripcion=descripcion,
            defaults={
                "fecha_hora": fecha_hora,
                "ip_origen": ip_origen,
            },
        )


def print_seed_summary(session):
    modelos = [
        Rol,
        Usuario,
        UsuarioRol,
        Cliente,
        TipoTaller,
        Taller,
        HorarioDisponibilidadTaller,
        Tecnico,
        Especialidad,
        TecnicoEspecialidad,
        UnidadMovil,
        TipoVehiculo,
        Vehiculo,
        TallerTipoVehiculo,
        TipoAuxilio,
        TallerAuxilio,
        TipoIncidente,
        Prioridad,
        EstadoServicio,
        Incidente,
        Evidencia,
        SolicitudTaller,
        AsignacionServicio,
        HistorialIncidente,
        BitacoraSistema,
        Notificacion,
        PagoServicio,
        DetallePago,
        ComisionPlataforma,
        CalificacionServicio,
        MetricaIncidente,
    ]

    print("Resumen de poblado:")
    for model in modelos:
        total = session.execute(
            select(func.count()).select_from(model)
        ).scalar_one()
        print(f"- {model.__tablename__}: {total}")


def run_seeds():
    session = SessionLocal()
    try:
        seed_roles(session)
        admin = seed_admin_user(session)
        seed_tipos_taller(session)
        seed_tipos_vehiculo(session)
        seed_tipos_auxilio(session)
        seed_prioridades(session)
        seed_estados_servicio(session)
        seed_tipos_incidente(session)
        seed_especialidades(session)

        usuarios = seed_demo_usuarios(session)
        usuarios["admin"] = admin
        clientes = seed_demo_clientes(session, usuarios)
        talleres = seed_demo_talleres(session, usuarios)
        seed_horarios_taller(session, talleres)
        tecnicos = seed_demo_tecnicos(session, usuarios, talleres)
        seed_tecnico_especialidades(session, tecnicos)
        unidades = seed_unidades_moviles(session, talleres)
        seed_talleres_tipo_vehiculo(session, talleres)
        talleres_auxilio = seed_talleres_auxilio(session, talleres)
        vehiculos = seed_vehiculos(session, clientes)
        incidentes, asignaciones = seed_incidentes(
            session,
            clientes=clientes,
            vehiculos=vehiculos,
            talleres=talleres,
            tecnicos=tecnicos,
            unidades=unidades,
            usuarios=usuarios,
        )
        seed_seguimiento_y_finanzas(
            session,
            incidentes=incidentes,
            asignaciones=asignaciones,
            talleres_auxilio=talleres_auxilio,
            talleres=talleres,
            clientes=clientes,
            tecnicos=tecnicos,
        )
        seed_notificaciones(session, incidentes, usuarios)
        seed_bitacora(session, usuarios)

        session.commit()
        print("Seeds integrales ejecutados correctamente.")
        print_seed_summary(session)
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


if __name__ == "__main__":
    run_seeds()
