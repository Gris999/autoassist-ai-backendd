from datetime import datetime, time, timedelta

from sqlalchemy import func, select

from app.core.db.seed_data import (
    BASE_TIME,
    DEFAULT_PASSWORD,
    ensure_catalog_row,
    ensure_user_role,
    ensure_usuario,
    get_by_name,
    get_or_create,
    run_seeds,
)
from app.core.db.session import SessionLocal
from app.core.security.security import hash_password
from app.modules.autenticacion_seguridad.models import BitacoraSistema, Rol, Usuario, UsuarioRol
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
    DispositivoPushUsuario,
    MetricaIncidente,
    Notificacion,
    PagoServicio,
)


SCZ_POINTS = {
    "equipetrol": ("Equipetrol, Santa Cruz de la Sierra", -17.7635000, -63.1954000),
    "alemana": ("Av. Alemana y 3er anillo, Santa Cruz de la Sierra", -17.7570000, -63.1793000),
    "banzer": ("Av. Banzer y 5to anillo, Santa Cruz de la Sierra", -17.7248000, -63.1708000),
    "cristo_redentor": ("Av. Cristo Redentor y 4to anillo, Santa Cruz de la Sierra", -17.7517000, -63.1765000),
    "santos_dumont": ("Av. Santos Dumont y 4to anillo, Santa Cruz de la Sierra", -17.8147000, -63.1761000),
    "doble_via_guardia": ("Doble Via La Guardia y 4to anillo, Santa Cruz de la Sierra", -17.8241000, -63.1886000),
    "plan_3000": ("Plan Tres Mil, Santa Cruz de la Sierra", -17.8325000, -63.1376000),
    "villa_1ro_mayo": ("Villa 1ro de Mayo, Santa Cruz de la Sierra", -17.7816000, -63.0918000),
    "urubo": ("Puente Urubo, Santa Cruz de la Sierra", -17.7560000, -63.2148000),
    "bimodal": ("Terminal Bimodal, Santa Cruz de la Sierra", -17.7892000, -63.1582000),
    "parque_industrial": ("Parque Industrial, Santa Cruz de la Sierra", -17.7585000, -63.1004000),
    "cotoca": ("Carretera a Cotoca km 8, Santa Cruz de la Sierra", -17.7673000, -63.0339000),
}


def set_fields(instance, **values):
    for key, value in values.items():
        setattr(instance, key, value)
    return instance


def ensure_cliente(session, usuario: Usuario) -> Cliente:
    cliente = session.execute(
        select(Cliente).where(Cliente.id_usuario == usuario.id_usuario)
    ).scalar_one_or_none()
    if cliente:
        return cliente
    cliente = Cliente(id_usuario=usuario.id_usuario)
    session.add(cliente)
    session.flush()
    return cliente


def ensure_taller(
    session,
    *,
    usuario: Usuario,
    tipo_taller: TipoTaller,
    nombre_taller: str,
    nit: str,
    direccion: str,
    latitud: float,
    longitud: float,
    radio_cobertura_km: float,
    disponible: bool = True,
) -> Taller:
    taller = session.execute(
        select(Taller).where(Taller.id_usuario == usuario.id_usuario)
    ).scalar_one_or_none()
    if not taller:
        taller = session.execute(select(Taller).where(Taller.nit == nit)).scalar_one_or_none()

    if taller:
        return set_fields(
            taller,
            id_usuario=usuario.id_usuario,
            id_tipo_taller=tipo_taller.id_tipo_taller,
            nombre_taller=nombre_taller,
            nit=nit,
            direccion=direccion,
            latitud=latitud,
            longitud=longitud,
            radio_cobertura_km=radio_cobertura_km,
            disponible=disponible,
        )

    taller = Taller(
        id_usuario=usuario.id_usuario,
        id_tipo_taller=tipo_taller.id_tipo_taller,
        nombre_taller=nombre_taller,
        nit=nit,
        direccion=direccion,
        latitud=latitud,
        longitud=longitud,
        radio_cobertura_km=radio_cobertura_km,
        disponible=disponible,
        fecha_registro=BASE_TIME,
    )
    session.add(taller)
    session.flush()
    return taller


def ensure_tecnico(
    session,
    *,
    usuario: Usuario,
    taller: Taller,
    telefono_contacto: str,
    disponible: bool,
    estado: bool,
    latitud_actual: float,
    longitud_actual: float,
) -> Tecnico:
    tecnico = session.execute(
        select(Tecnico).where(Tecnico.id_usuario == usuario.id_usuario)
    ).scalar_one_or_none()
    if tecnico:
        return set_fields(
            tecnico,
            id_taller=taller.id_taller,
            telefono_contacto=telefono_contacto,
            disponible=disponible,
            estado=estado,
            latitud_actual=latitud_actual,
            longitud_actual=longitud_actual,
        )

    tecnico = Tecnico(
        id_usuario=usuario.id_usuario,
        id_taller=taller.id_taller,
        telefono_contacto=telefono_contacto,
        disponible=disponible,
        estado=estado,
        latitud_actual=latitud_actual,
        longitud_actual=longitud_actual,
    )
    session.add(tecnico)
    session.flush()
    return tecnico


def ensure_unidad_movil(
    session,
    *,
    taller: Taller,
    placa: str,
    tipo_unidad: str,
    disponible: bool,
    latitud_actual: float,
    longitud_actual: float,
    estado: bool,
) -> UnidadMovil:
    unidad = session.execute(
        select(UnidadMovil).where(UnidadMovil.placa == placa)
    ).scalar_one_or_none()
    if unidad:
        return set_fields(
            unidad,
            id_taller=taller.id_taller,
            tipo_unidad=tipo_unidad,
            disponible=disponible,
            latitud_actual=latitud_actual,
            longitud_actual=longitud_actual,
            estado=estado,
        )

    unidad = UnidadMovil(
        id_taller=taller.id_taller,
        placa=placa,
        tipo_unidad=tipo_unidad,
        disponible=disponible,
        latitud_actual=latitud_actual,
        longitud_actual=longitud_actual,
        estado=estado,
    )
    session.add(unidad)
    session.flush()
    return unidad


def ensure_push_device(
    session,
    *,
    usuario: Usuario,
    token_push: str,
    plataforma: str = "ANDROID",
    proveedor: str = "FCM",
    activo: bool = True,
) -> DispositivoPushUsuario:
    dispositivo = session.execute(
        select(DispositivoPushUsuario).where(DispositivoPushUsuario.token_push == token_push)
    ).scalar_one_or_none()
    if dispositivo:
        return set_fields(
            dispositivo,
            id_usuario=usuario.id_usuario,
            plataforma=plataforma,
            proveedor=proveedor,
            activo=activo,
            fecha_actualizacion=BASE_TIME + timedelta(days=4),
        )

    dispositivo = DispositivoPushUsuario(
        id_usuario=usuario.id_usuario,
        token_push=token_push,
        plataforma=plataforma,
        proveedor=proveedor,
        activo=activo,
        fecha_registro=BASE_TIME + timedelta(days=4),
        fecha_actualizacion=BASE_TIME + timedelta(days=4),
    )
    session.add(dispositivo)
    session.flush()
    return dispositivo


def normalize_existing_demo_to_santa_cruz(session):
    workshop_overrides = {
        "Taller Okenan": ("La Campana, Santa Cruz de la Sierra", -17.7833000, -63.1821000, 18),
        "Electro Sur": SCZ_POINTS["alemana"],
        "Gruas Altiplano": SCZ_POINTS["banzer"],
        "Taller Demo Central": SCZ_POINTS["cristo_redentor"],
    }
    for taller in session.execute(select(Taller)).scalars():
        if taller.nombre_taller in workshop_overrides:
            data = workshop_overrides[taller.nombre_taller]
            if len(data) == 4:
                direccion, latitud, longitud, radio = data
            else:
                direccion, latitud, longitud = data
                radio = 15
            set_fields(
                taller,
                direccion=direccion,
                latitud=latitud,
                longitud=longitud,
                radio_cobertura_km=radio,
                disponible=True,
            )

    incident_overrides = {
        "Bateria descargada en zona Sur": SCZ_POINTS["santos_dumont"],
        "Pinchazo en carretera al Norte": SCZ_POINTS["banzer"],
        "Camion sin combustible en perifera": SCZ_POINTS["parque_industrial"],
    }
    for incidente in session.execute(select(Incidente)).scalars():
        if incidente.titulo in incident_overrides:
            direccion, latitud, longitud = incident_overrides[incidente.titulo]
            incidente.direccion_referencia = direccion
            incidente.latitud = latitud
            incidente.longitud = longitud

    tecnico_points = {
        "carlos.quispe@autoassist.com": SCZ_POINTS["cristo_redentor"],
        "elena.soto@autoassist.com": SCZ_POINTS["equipetrol"],
        "marco.vargas@autoassist.com": SCZ_POINTS["alemana"],
        "sofia.mamani@autoassist.com": SCZ_POINTS["banzer"],
    }
    for tecnico in session.execute(select(Tecnico)).scalars():
        usuario = session.execute(
            select(Usuario).where(Usuario.id_usuario == tecnico.id_usuario)
        ).scalar_one_or_none()
        if usuario and usuario.email in tecnico_points:
            _, latitud, longitud = tecnico_points[usuario.email]
            tecnico.latitud_actual = latitud
            tecnico.longitud_actual = longitud

    unidad_points = {
        "OKN-001": SCZ_POINTS["cristo_redentor"],
        "OKN-002": SCZ_POINTS["equipetrol"],
        "ELS-101": SCZ_POINTS["alemana"],
        "GRA-900": SCZ_POINTS["banzer"],
    }
    for unidad in session.execute(select(UnidadMovil)).scalars():
        if unidad.placa in unidad_points:
            _, latitud, longitud = unidad_points[unidad.placa]
            unidad.latitud_actual = latitud
            unidad.longitud_actual = longitud


def seed_expanded_demo_data(session):
    roles = {rol.nombre: rol for rol in session.execute(select(Rol)).scalars()}
    tipos_taller = {item.nombre: item for item in session.execute(select(TipoTaller)).scalars()}
    tipos_vehiculo = {item.nombre: item for item in session.execute(select(TipoVehiculo)).scalars()}
    tipos_incidente = {item.nombre: item for item in session.execute(select(TipoIncidente)).scalars()}
    prioridades = {item.nombre: item for item in session.execute(select(Prioridad)).scalars()}
    estados = {item.nombre: item for item in session.execute(select(EstadoServicio)).scalars()}
    especialidades = {item.nombre: item for item in session.execute(select(Especialidad)).scalars()}
    tipos_auxilio = {item.nombre: item for item in session.execute(select(TipoAuxilio)).scalars()}

    user_specs = [
        ("pedro_cliente", "pedroalaca07@gmail.com", "Pedro", "Alaca", "76540111", "CLIENTE"),
        ("ana_cliente", "ana.rojas@autoassist.com", "Ana", "Rojas", "70100001", "CLIENTE"),
        ("luis_cliente", "luis.fernandez@autoassist.com", "Luis", "Fernandez", "70100002", "CLIENTE"),
        ("maria_cliente", "maria.choque@autoassist.com", "Maria", "Choque", "70100003", "CLIENTE"),
        ("carla_cliente", "carla.suarez@autoassist.com", "Carla", "Suarez", "70100004", "CLIENTE"),
        ("diego_cliente", "diego.peredo@autoassist.com", "Diego", "Peredo", "70100005", "CLIENTE"),
        ("valeria_cliente", "valeria.melgar@autoassist.com", "Valeria", "Melgar", "70100006", "CLIENTE"),
        ("demo_taller", "taller.demo1@gmail.com", "Carlos", "Mendez", "76543210", "TALLER"),
        ("okenan_taller", "taller.okenan@autoassist.com", "Yohan", "Cuenta", "76304135", "TALLER"),
        ("electro_taller", "electro.sur@autoassist.com", "Gabriela", "Lopez", "70120001", "TALLER"),
        ("grua_taller", "gruas.altiplano@autoassist.com", "Rene", "Mamani", "70120002", "TALLER"),
        ("llantas_taller", "llantas.expres@autoassist.com", "Paola", "Roca", "70120003", "TALLER"),
        ("apertura_taller", "apertura.norte@autoassist.com", "Jorge", "Salvatierra", "70120004", "TALLER"),
        ("tecnico_juan", "juan.perez@autoassist.com", "Juan", "Perez", "70210010", "TECNICO"),
        ("tecnico_mario", "mario.rivero@autoassist.com", "Mario", "Rivero", "70210011", "TECNICO"),
        ("tecnico_carlos", "carlos.quispe@autoassist.com", "Carlos", "Quispe", "70210001", "TECNICO"),
        ("tecnico_elena", "elena.soto@autoassist.com", "Elena", "Soto", "70210002", "TECNICO"),
        ("tecnico_marco", "marco.vargas@autoassist.com", "Marco", "Vargas", "70210003", "TECNICO"),
        ("tecnico_sofia", "sofia.mamani@autoassist.com", "Sofia", "Mamani", "70210004", "TECNICO"),
        ("tecnico_lucia", "lucia.moreno@autoassist.com", "Lucia", "Moreno", "70210012", "TECNICO"),
        ("tecnico_raul", "raul.guzman@autoassist.com", "Raul", "Guzman", "70210013", "TECNICO"),
        ("tecnico_nancy", "nancy.vaca@autoassist.com", "Nancy", "Vaca", "70210014", "TECNICO"),
        ("tecnico_oscar", "oscar.arias@autoassist.com", "Oscar", "Arias", "70210015", "TECNICO"),
    ]

    usuarios = {}
    for key, email, nombres, apellidos, celular, role_name in user_specs:
        usuario = ensure_usuario(
            session,
            email=email,
            nombres=nombres,
            apellidos=apellidos,
            celular=celular,
            password=DEFAULT_PASSWORD,
            estado=True,
        )
        ensure_user_role(session, usuario, role_name)
        usuarios[key] = usuario

    clientes = {
        key: ensure_cliente(session, usuarios[key])
        for key in [
            "pedro_cliente",
            "ana_cliente",
            "luis_cliente",
            "maria_cliente",
            "carla_cliente",
            "diego_cliente",
            "valeria_cliente",
        ]
    }

    workshop_specs = [
        (
            "demo_central",
            usuarios["demo_taller"],
            tipos_taller["MECANICO_GENERAL"],
            "Taller Demo Central",
            "SCZ1001",
            *SCZ_POINTS["cristo_redentor"],
            12,
        ),
        (
            "okenan",
            usuarios["okenan_taller"],
            tipos_taller["MECANICO_GENERAL"],
            "Taller Okenan",
            "SCZ1002",
            "La Campana, Santa Cruz de la Sierra",
            -17.7833000,
            -63.1821000,
            18,
        ),
        (
            "electro_sur",
            usuarios["electro_taller"],
            tipos_taller["ELECTROMECANICO"],
            "Electro Sur",
            "SCZ1003",
            *SCZ_POINTS["alemana"],
            14,
        ),
        (
            "gruas_altiplano",
            usuarios["grua_taller"],
            tipos_taller["GRUAS_Y_REMOLQUE"],
            "Gruas Altiplano",
            "SCZ1004",
            *SCZ_POINTS["banzer"],
            25,
        ),
        (
            "llantas_express",
            usuarios["llantas_taller"],
            tipos_taller["MECANICO_GENERAL"],
            "Llantas Express SCZ",
            "SCZ1005",
            *SCZ_POINTS["plan_3000"],
            10,
        ),
        (
            "apertura_norte",
            usuarios["apertura_taller"],
            tipos_taller["ELECTROMECANICO"],
            "Apertura Norte",
            "SCZ1006",
            *SCZ_POINTS["urubo"],
            11,
        ),
    ]

    talleres = {}
    for key, usuario, tipo_taller, nombre_taller, nit, direccion, latitud, longitud, radio in workshop_specs:
        talleres[key] = ensure_taller(
            session,
            usuario=usuario,
            tipo_taller=tipo_taller,
            nombre_taller=nombre_taller,
            nit=nit,
            direccion=direccion,
            latitud=latitud,
            longitud=longitud,
            radio_cobertura_km=radio,
            disponible=True,
        )

    horarios = {
        "demo_central": [(dia, time(7, 0), time(22, 0), True) for dia in ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"]],
        "okenan": [(dia, time(8, 0), time(20, 0), True) for dia in ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO"]],
        "electro_sur": [(dia, time(7, 30), time(21, 0), True) for dia in ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO"]],
        "gruas_altiplano": [(dia, time(0, 0), time(23, 59), True) for dia in ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"]],
        "llantas_express": [(dia, time(6, 30), time(21, 30), True) for dia in ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"]],
        "apertura_norte": [(dia, time(6, 0), time(23, 0), True) for dia in ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"]],
    }
    for taller_key, items in horarios.items():
        for dia_semana, hora_inicio, hora_fin, estado in items:
            get_or_create(
                session,
                HorarioDisponibilidadTaller,
                id_taller=talleres[taller_key].id_taller,
                dia_semana=dia_semana,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                defaults={"estado": estado},
            )

    technician_specs = [
        ("juan", usuarios["tecnico_juan"], "demo_central", "70210010", True, *SCZ_POINTS["cristo_redentor"][1:]),
        ("mario", usuarios["tecnico_mario"], "demo_central", "70210011", True, *SCZ_POINTS["equipetrol"][1:]),
        ("carlos", usuarios["tecnico_carlos"], "okenan", "70210001", True, *SCZ_POINTS["cristo_redentor"][1:]),
        ("elena", usuarios["tecnico_elena"], "okenan", "70210002", False, *SCZ_POINTS["equipetrol"][1:]),
        ("marco", usuarios["tecnico_marco"], "electro_sur", "70210003", True, *SCZ_POINTS["alemana"][1:]),
        ("sofia", usuarios["tecnico_sofia"], "gruas_altiplano", "70210004", True, *SCZ_POINTS["banzer"][1:]),
        ("lucia", usuarios["tecnico_lucia"], "llantas_express", "70210012", True, *SCZ_POINTS["plan_3000"][1:]),
        ("raul", usuarios["tecnico_raul"], "apertura_norte", "70210013", True, *SCZ_POINTS["urubo"][1:]),
        ("nancy", usuarios["tecnico_nancy"], "electro_sur", "70210014", True, *SCZ_POINTS["alemana"][1:]),
        ("oscar", usuarios["tecnico_oscar"], "gruas_altiplano", "70210015", True, *SCZ_POINTS["banzer"][1:]),
    ]

    tecnicos = {}
    for key, usuario, taller_key, telefono, disponible, latitud, longitud in technician_specs:
        tecnicos[key] = ensure_tecnico(
            session,
            usuario=usuario,
            taller=talleres[taller_key],
            telefono_contacto=telefono,
            disponible=disponible,
            estado=True,
            latitud_actual=latitud,
            longitud_actual=longitud,
        )

    tecnico_especialidades = {
        "juan": ["MECANICA_GENERAL", "LLANTAS_Y_NEUMATICOS"],
        "mario": ["MECANICA_GENERAL"],
        "carlos": ["MECANICA_GENERAL", "LLANTAS_Y_NEUMATICOS"],
        "elena": ["ELECTRICIDAD_AUTOMOTRIZ"],
        "marco": ["ELECTRICIDAD_AUTOMOTRIZ"],
        "sofia": ["GRUA_Y_REMOLQUE"],
        "lucia": ["LLANTAS_Y_NEUMATICOS"],
        "raul": ["ELECTRICIDAD_AUTOMOTRIZ"],
        "nancy": ["ELECTRICIDAD_AUTOMOTRIZ"],
        "oscar": ["GRUA_Y_REMOLQUE"],
    }
    for tecnico_key, especialidad_names in tecnico_especialidades.items():
        for nombre in especialidad_names:
            get_or_create(
                session,
                TecnicoEspecialidad,
                id_tecnico=tecnicos[tecnico_key].id_tecnico,
                id_especialidad=especialidades[nombre].id_especialidad,
            )

    unit_specs = [
        ("1234-ABC", "demo_central", "GRUA_LIVIANA", True, *SCZ_POINTS["cristo_redentor"][1:]),
        ("1234-XYZ", "demo_central", "CAMIONETA_TALLER", True, *SCZ_POINTS["equipetrol"][1:]),
        ("OKN-001", "okenan", "CAMIONETA_TALLER", True, *SCZ_POINTS["cristo_redentor"][1:]),
        ("OKN-002", "okenan", "MOTO_AUXILIO", True, *SCZ_POINTS["equipetrol"][1:]),
        ("ELS-101", "electro_sur", "FURGON_ELECTRICO", True, *SCZ_POINTS["alemana"][1:]),
        ("ELS-102", "electro_sur", "CAMIONETA_ELECTRICA", True, *SCZ_POINTS["alemana"][1:]),
        ("GRA-900", "gruas_altiplano", "GRUA_PESADA", True, *SCZ_POINTS["banzer"][1:]),
        ("GRA-901", "gruas_altiplano", "CAMION_APOYO", True, *SCZ_POINTS["banzer"][1:]),
        ("LLE-201", "llantas_express", "MOTO_AUXILIO", True, *SCZ_POINTS["plan_3000"][1:]),
        ("APN-301", "apertura_norte", "CAMIONETA_CERRAJERIA", True, *SCZ_POINTS["urubo"][1:]),
    ]
    unidades = {}
    for placa, taller_key, tipo_unidad, disponible, latitud, longitud in unit_specs:
        unidades[placa] = ensure_unidad_movil(
            session,
            taller=talleres[taller_key],
            placa=placa,
            tipo_unidad=tipo_unidad,
            disponible=disponible,
            latitud_actual=latitud,
            longitud_actual=longitud,
            estado=True,
        )

    taller_vehicle_types = {
        "demo_central": ["AUTOMOVIL", "CAMIONETA", "MINIBUS"],
        "okenan": ["AUTOMOVIL", "CAMIONETA"],
        "electro_sur": ["AUTOMOVIL", "MOTOCICLETA", "CAMIONETA"],
        "gruas_altiplano": ["AUTOMOVIL", "CAMIONETA", "MINIBUS", "CAMION"],
        "llantas_express": ["AUTOMOVIL", "CAMIONETA", "MOTOCICLETA"],
        "apertura_norte": ["AUTOMOVIL", "CAMIONETA", "MINIBUS"],
    }
    for taller_key, names in taller_vehicle_types.items():
        for tipo_nombre in names:
            get_or_create(
                session,
                TallerTipoVehiculo,
                id_taller=talleres[taller_key].id_taller,
                id_tipo_vehiculo=tipos_vehiculo[tipo_nombre].id_tipo_vehiculo,
            )

    taller_services = {
        "demo_central": [
            ("CAMBIO_DE_LLANTA", 1400, True),
            ("AUXILIO_MECANICO_BASICO", 1800, True),
            ("SUMINISTRO_COMBUSTIBLE", 800, True),
        ],
        "okenan": [
            ("CAMBIO_DE_LLANTA", 80, True),
            ("AUXILIO_MECANICO_BASICO", 180, True),
            ("SUMINISTRO_COMBUSTIBLE", 70, True),
        ],
        "electro_sur": [
            ("AUXILIO_ELECTRICO", 160, True),
            ("APERTURA_VEHICULO", 90, True),
            ("CAMBIO_DE_LLANTA", 85, True),
        ],
        "gruas_altiplano": [
            ("REMOLQUE", 350, True),
            ("AUXILIO_MECANICO_BASICO", 200, True),
            ("SUMINISTRO_COMBUSTIBLE", 100, True),
        ],
        "llantas_express": [
            ("CAMBIO_DE_LLANTA", 95, True),
            ("AUXILIO_MECANICO_BASICO", 170, True),
        ],
        "apertura_norte": [
            ("APERTURA_VEHICULO", 110, True),
            ("AUXILIO_ELECTRICO", 175, True),
        ],
    }
    taller_auxilios = {}
    for taller_key, servicios in taller_services.items():
        for auxilio_name, precio, disponible in servicios:
            rel, _ = get_or_create(
                session,
                TallerAuxilio,
                id_taller=talleres[taller_key].id_taller,
                id_tipo_auxilio=tipos_auxilio[auxilio_name].id_tipo_auxilio,
                defaults={"precio_referencial": precio, "disponible": disponible},
            )
            rel.precio_referencial = precio
            rel.disponible = disponible
            taller_auxilios[(taller_key, auxilio_name)] = rel

    vehicle_specs = [
        ("PED-111", "pedro_cliente", "AUTOMOVIL", "Toyota", "Yaris", 2020, "Blanco", "Compacto blanco con rayones leves"),
        ("PED-222", "pedro_cliente", "CAMIONETA", "Mitsubishi", "L200", 2019, "Gris", "Camioneta gris doble cabina"),
        ("ANA-333", "ana_cliente", "AUTOMOVIL", "Hyundai", "Accent", 2018, "Rojo", "Sedan rojo familiar"),
        ("ANA-444", "ana_cliente", "MOTOCICLETA", "Honda", "CB190", 2022, "Negro", "Moto negra con baul"),
        ("LUI-555", "luis_cliente", "CAMIONETA", "Nissan", "Frontier", 2018, "Plata", "Camioneta con parrilla negra"),
        ("MAR-666", "maria_cliente", "CAMION", "Volvo", "FH", 2017, "Azul", "Camion azul de carga"),
        ("CAR-777", "carla_cliente", "AUTOMOVIL", "Kia", "Rio", 2021, "Azul", "Vehiculo azul hatchback"),
        ("DIE-888", "diego_cliente", "MINIBUS", "Toyota", "Hiace", 2016, "Blanco", "Minibus de transporte escolar"),
        ("VAL-999", "valeria_cliente", "AUTOMOVIL", "Suzuki", "Swift", 2023, "Verde", "Auto compacto verde"),
        ("VAL-101", "valeria_cliente", "CAMIONETA", "Chevrolet", "D-Max", 2020, "Negro", "Camioneta negra con canopy"),
    ]
    vehiculos = {}
    for placa, cliente_key, tipo_nombre, marca, modelo, anio, color, referencia in vehicle_specs:
        vehiculo, _ = get_or_create(
            session,
            Vehiculo,
            placa=placa,
            defaults={
                "id_cliente": clientes[cliente_key].id_cliente,
                "id_tipo_vehiculo": tipos_vehiculo[tipo_nombre].id_tipo_vehiculo,
                "marca": marca,
                "modelo": modelo,
                "anio": anio,
                "color": color,
                "descripcion_referencia": referencia,
                "estado": True,
            },
        )
        set_fields(
            vehiculo,
            id_cliente=clientes[cliente_key].id_cliente,
            id_tipo_vehiculo=tipos_vehiculo[tipo_nombre].id_tipo_vehiculo,
            marca=marca,
            modelo=modelo,
            anio=anio,
            color=color,
            descripcion_referencia=referencia,
            estado=True,
        )
        vehiculos[placa] = vehiculo

    session.flush()

    incident_specs = [
        ("SCZ-BAT-001", "pedro_cliente", "PED-111", "BATERIA_DESCARGADA", "MEDIA", "FINALIZADO", "Auto no enciende en Equipetrol", "El vehiculo no enciende tras quedar parqueado toda la tarde.", "equipetrol", "bateria", 95.0, "Posible bateria descargada. Requiere auxilio electrico.", False),
        ("SCZ-LLA-002", "ana_cliente", "ANA-333", "PINCHAZO_LLANTA", "ALTA", "FINALIZADO", "Llanta pinchada cerca de la Bimodal", "Se revienta la llanta delantera y no cuenta con repuesto instalado.", "bimodal", "llanta", 93.0, "Pinchazo de llanta con necesidad de cambio en sitio.", False),
        ("SCZ-COM-003", "luis_cliente", "LUI-555", "SIN_COMBUSTIBLE", "MEDIA", "BUSCANDO_TALLER", "Sin combustible en Av. Banzer", "La camioneta se quedo sin combustible rumbo al norte.", "banzer", "combustible", 88.0, "Suministro de combustible requerido en ruta.", False),
        ("SCZ-LLA-004", "maria_cliente", "MAR-666", "LLAVES_DENTRO", "BAJA", "ASIGNADO", "Llaves dentro en Urubo", "El cliente cerro la camioneta con las llaves dentro.", "urubo", "llave", 91.0, "Apertura de vehiculo requerida sin danos.", False),
        ("SCZ-MEC-005", "carla_cliente", "CAR-777", "FALLA_MECANICA", "ALTA", "EN_CAMINO", "Falla mecanica en Santos Dumont", "Se apago el motor y no mantiene marcha minima.", "santos_dumont", "motor", 86.0, "Posible falla mecanica basica en motor.", False),
        ("SCZ-ACC-006", "diego_cliente", "DIE-888", "ACCIDENTE_MENOR", "CRITICA", "EN_ATENCION", "Choque menor en Doble Via La Guardia", "Minibus con golpe frontal leve y direccion comprometida.", "doble_via_guardia", "choque", 97.0, "Se recomienda remolque y evaluacion mecanica posterior.", False),
        ("SCZ-SOB-007", "valeria_cliente", "VAL-999", "SOBRECALENTAMIENTO", "MEDIA", "REPORTADO", "Motor sobrecalentado en Parque Industrial", "El vehiculo comenzo a humear y la temperatura subio al maximo.", "parque_industrial", "motor", 82.0, "Posible sobrecalentamiento de motor.", True),
        ("SCZ-BAT-008", "pedro_cliente", "PED-222", "BATERIA_DESCARGADA", "MEDIA", "BUSCANDO_TALLER", "Camioneta descargada en Plan 3000", "La camioneta no responde tras dejar las luces encendidas.", "plan_3000", "bateria", 90.0, "Bateria descargada. Buscar auxilio electrico cercano.", False),
        ("SCZ-LLA-009", "carla_cliente", "CAR-777", "PINCHAZO_LLANTA", "MEDIA", "ASIGNADO", "Llanta lateral en Villa 1ro de Mayo", "Dano de llanta tras caer en bache.", "villa_1ro_mayo", "llanta", 89.0, "Cambio de llanta requerido con herramienta rapida.", False),
        ("SCZ-LLA-010", "valeria_cliente", "VAL-101", "SIN_COMBUSTIBLE", "BAJA", "REPORTADO", "Consulta de combustible en Cotoca", "No recuerda si el problema es combustible o bateria y comparte audio confuso.", "cotoca", "combustible", 70.0, "Requiere confirmacion adicional del tipo de ayuda.", True),
    ]

    incidentes = {}
    for code, cliente_key, placa, tipo_nombre, prioridad_nombre, estado_nombre, titulo, descripcion, point_key, clasif, confianza, resumen, requiere_mas_info in incident_specs:
        direccion, latitud, longitud = SCZ_POINTS[point_key]
        fecha_reporte = BASE_TIME + timedelta(days=2, minutes=len(incidentes) * 17)
        incidente, _ = get_or_create(
            session,
            Incidente,
            titulo=titulo,
            id_cliente=clientes[cliente_key].id_cliente,
            defaults={
                "id_vehiculo": vehiculos[placa].id_vehiculo,
                "id_tipo_incidente": tipos_incidente[tipo_nombre].id_tipo_incidente,
                "id_prioridad": prioridades[prioridad_nombre].id_prioridad,
                "id_estado_servicio_actual": estados[estado_nombre].id_estado_servicio,
                "descripcion_texto": descripcion,
                "direccion_referencia": direccion,
                "latitud": latitud,
                "longitud": longitud,
                "fecha_reporte": fecha_reporte,
                "clasificacion_ia": clasif,
                "confianza_clasificacion": confianza,
                "resumen_ia": resumen,
                "requiere_mas_info": requiere_mas_info,
            },
        )
        set_fields(
            incidente,
            id_cliente=clientes[cliente_key].id_cliente,
            id_vehiculo=vehiculos[placa].id_vehiculo,
            id_tipo_incidente=tipos_incidente[tipo_nombre].id_tipo_incidente,
            id_prioridad=prioridades[prioridad_nombre].id_prioridad,
            id_estado_servicio_actual=estados[estado_nombre].id_estado_servicio,
            descripcion_texto=descripcion,
            direccion_referencia=direccion,
            latitud=latitud,
            longitud=longitud,
            clasificacion_ia=clasif,
            confianza_clasificacion=confianza,
            resumen_ia=resumen,
            requiere_mas_info=requiere_mas_info,
        )
        if not incidente.fecha_reporte:
            incidente.fecha_reporte = fecha_reporte
        incidentes[code] = incidente

    session.flush()

    evidence_specs = [
        ("SCZ-BAT-001", "IMAGEN", "https://media.autoassist.demo/scz/bat001-tablero.jpg", "Tablero sin energia al girar llave.", "Foto del tablero apagado"),
        ("SCZ-BAT-001", "AUDIO", "https://media.autoassist.demo/scz/bat001-audio.mp3", "No prende nada, parece bateria descargada.", "Audio del cliente"),
        ("SCZ-LLA-002", "IMAGEN", "https://media.autoassist.demo/scz/lla002-neumatico.jpg", None, "Llanta delantera reventada"),
        ("SCZ-COM-003", "AUDIO", "https://media.autoassist.demo/scz/com003-audio.mp3", "Me quede sin combustible camino al norte.", "Audio confirmando falta de combustible"),
        ("SCZ-ACC-006", "VIDEO", "https://media.autoassist.demo/scz/acc006-video.mp4", None, "Video del dano frontal"),
        ("SCZ-SOB-007", "IMAGEN", "https://media.autoassist.demo/scz/sob007-humo.jpg", None, "Foto del humo del motor"),
        ("SCZ-LLA-009", "IMAGEN", "https://media.autoassist.demo/scz/lla009-costado.jpg", None, "Foto del costado de la llanta danada"),
        ("SCZ-LLA-010", "AUDIO", "https://media.autoassist.demo/scz/lla010-audio.mp3", "Creo que es combustible, pero tambien se siente raro el arranque.", "Audio ambiguo del cliente"),
    ]
    for incident_code, tipo_evidencia, archivo_url, texto_extraido, descripcion in evidence_specs:
        get_or_create(
            session,
            Evidencia,
            id_incidente=incidentes[incident_code].id_incidente,
            archivo_url=archivo_url,
            defaults={
                "tipo_evidencia": tipo_evidencia,
                "texto_extraido": texto_extraido,
                "descripcion": descripcion,
                "fecha_registro": BASE_TIME + timedelta(days=2),
            },
        )

    solicitud_specs = [
        ("SCZ-BAT-001", "electro_sur", 3.1, 97.5, "ACEPTADA", 10, 12),
        ("SCZ-BAT-001", "demo_central", 5.8, 82.0, "CANCELADA", 11, 12),
        ("SCZ-LLA-002", "demo_central", 2.8, 96.0, "ACEPTADA", 20, 23),
        ("SCZ-LLA-002", "llantas_express", 4.0, 89.0, "RECHAZADA", 21, 25),
        ("SCZ-COM-003", "gruas_altiplano", 4.3, 93.0, "PENDIENTE", 15, None),
        ("SCZ-COM-003", "okenan", 9.2, 62.0, "PENDIENTE", 18, None),
        ("SCZ-LLA-004", "apertura_norte", 3.9, 95.0, "ACEPTADA", 12, 14),
        ("SCZ-MEC-005", "okenan", 2.6, 94.0, "ACEPTADA", 14, 16),
        ("SCZ-MEC-005", "demo_central", 6.2, 77.0, "CANCELADA", 15, 16),
        ("SCZ-ACC-006", "gruas_altiplano", 3.5, 98.0, "ACEPTADA", 8, 9),
        ("SCZ-BAT-008", "electro_sur", 6.1, 92.0, "PENDIENTE", 13, None),
        ("SCZ-BAT-008", "demo_central", 5.4, 88.0, "PENDIENTE", 14, None),
        ("SCZ-LLA-009", "llantas_express", 2.1, 96.5, "ACEPTADA", 9, 11),
        ("SCZ-LLA-009", "demo_central", 6.8, 70.0, "CANCELADA", 10, 11),
    ]
    solicitudes = {}
    for code, taller_key, distancia, puntaje, estado_solicitud, envio_offset, respuesta_offset in solicitud_specs:
        solicitud, _ = get_or_create(
            session,
            SolicitudTaller,
            id_incidente=incidentes[code].id_incidente,
            id_taller=talleres[taller_key].id_taller,
            defaults={
                "distancia_km": distancia,
                "puntaje_asignacion": puntaje,
                "estado_solicitud": estado_solicitud,
                "fecha_envio": incidentes[code].fecha_reporte + timedelta(minutes=envio_offset),
                "fecha_respuesta": (
                    incidentes[code].fecha_reporte + timedelta(minutes=respuesta_offset)
                    if respuesta_offset is not None
                    else None
                ),
            },
        )
        set_fields(
            solicitud,
            distancia_km=distancia,
            puntaje_asignacion=puntaje,
            estado_solicitud=estado_solicitud,
            fecha_envio=incidentes[code].fecha_reporte + timedelta(minutes=envio_offset),
            fecha_respuesta=(
                incidentes[code].fecha_reporte + timedelta(minutes=respuesta_offset)
                if respuesta_offset is not None
                else None
            ),
        )
        solicitudes[(code, taller_key)] = solicitud

    assignment_specs = [
        ("SCZ-BAT-001", "electro_sur", "marco", "ELS-101", 22, "FINALIZADA", "Atencion electrica completada en sitio."),
        ("SCZ-LLA-002", "demo_central", "juan", "1234-ABC", 28, "FINALIZADA", "Cambio de llanta completado y presion verificada."),
        ("SCZ-LLA-004", "apertura_norte", "raul", "APN-301", 18, "ASIGNADO", "Tecnico preparado para apertura segura."),
        ("SCZ-MEC-005", "okenan", "carlos", "OKN-001", 30, "EN_CAMINO", "Equipo mecanico en ruta."),
        ("SCZ-ACC-006", "gruas_altiplano", "sofia", "GRA-900", 25, "EN_ATENCION", "Grua estabilizando vehiculo y evaluando remolque."),
        ("SCZ-LLA-009", "llantas_express", "lucia", "LLE-201", 20, "ASIGNADO", "Tecnico con kit de neumaticos listo."),
    ]
    asignaciones = {}
    for code, taller_key, tecnico_key, placa_unidad, tiempo_estimado, estado_asignacion, observaciones in assignment_specs:
        asignacion, _ = get_or_create(
            session,
            AsignacionServicio,
            id_incidente=incidentes[code].id_incidente,
            defaults={
                "id_taller": talleres[taller_key].id_taller,
                "id_tecnico": tecnicos[tecnico_key].id_tecnico,
                "id_unidad_movil": unidades[placa_unidad].id_unidad_movil,
                "fecha_asignacion": incidentes[code].fecha_reporte + timedelta(minutes=18),
                "tiempo_estimado_min": tiempo_estimado,
                "estado_asignacion": estado_asignacion,
                "observaciones": observaciones,
            },
        )
        set_fields(
            asignacion,
            id_taller=talleres[taller_key].id_taller,
            id_tecnico=tecnicos[tecnico_key].id_tecnico,
            id_unidad_movil=unidades[placa_unidad].id_unidad_movil,
            tiempo_estimado_min=tiempo_estimado,
            estado_asignacion=estado_asignacion,
            observaciones=observaciones,
        )
        asignaciones[code] = asignacion

    history_templates = {
        "FINALIZADO": ["REPORTADO", "BUSCANDO_TALLER", "ASIGNADO", "EN_CAMINO", "EN_ATENCION", "FINALIZADO"],
        "EN_ATENCION": ["REPORTADO", "BUSCANDO_TALLER", "ASIGNADO", "EN_CAMINO", "EN_ATENCION"],
        "EN_CAMINO": ["REPORTADO", "BUSCANDO_TALLER", "ASIGNADO", "EN_CAMINO"],
        "ASIGNADO": ["REPORTADO", "BUSCANDO_TALLER", "ASIGNADO"],
        "BUSCANDO_TALLER": ["REPORTADO", "BUSCANDO_TALLER"],
        "REPORTADO": ["REPORTADO"],
    }
    actor_for_state = {
        "REPORTADO": lambda code: clientes[next(k for k, c in clientes.items() if c.id_cliente == incidentes[code].id_cliente)],
        "BUSCANDO_TALLER": lambda code: usuarios["demo_taller"],
        "ASIGNADO": lambda code: usuarios["demo_taller"],
        "EN_CAMINO": lambda code: usuarios["tecnico_juan"],
        "EN_ATENCION": lambda code: usuarios["tecnico_juan"],
        "FINALIZADO": lambda code: usuarios["tecnico_juan"],
    }
    detalle_for_state = {
        "REPORTADO": "Cliente reporta el incidente desde la app movil.",
        "BUSCANDO_TALLER": "El sistema analiza el incidente y busca talleres compatibles.",
        "ASIGNADO": "Un taller acepta la solicitud y toma el caso.",
        "EN_CAMINO": "Tecnico y unidad movil salen rumbo al incidente.",
        "EN_ATENCION": "Se inicia la atencion del incidente en sitio.",
        "FINALIZADO": "El servicio queda resuelto y listo para pago/calificacion.",
    }
    for code, incidente in incidentes.items():
        current_state = next(name for name, state in estados.items() if state.id_estado_servicio == incidente.id_estado_servicio_actual)
        sequence = history_templates[current_state]
        for idx, state_name in enumerate(sequence):
            estado_nuevo = estados[state_name]
            estado_anterior = estados[sequence[idx - 1]] if idx > 0 else None
            actor = actor_for_state[state_name](code)
            if isinstance(actor, Cliente):
                actor_id = actor.id_usuario
            else:
                actor_id = actor.id_usuario
            get_or_create(
                session,
                HistorialIncidente,
                id_incidente=incidente.id_incidente,
                id_estado_nuevo=estado_nuevo.id_estado_servicio,
                id_usuario_actor=actor_id,
                detalle=detalle_for_state[state_name],
                defaults={
                    "id_estado_anterior": estado_anterior.id_estado_servicio if estado_anterior else None,
                    "fecha_hora": incidente.fecha_reporte + timedelta(minutes=idx * 9),
                },
            )

    paid_incidents = [
        ("SCZ-BAT-001", "electro_sur", "AUXILIO_ELECTRICO", 160, "PAGADO", "TRX-SCZ-BAT-001", "pedro_cliente", "marco", 4.9, "Excelente atencion, muy rapida."),
        ("SCZ-LLA-002", "demo_central", "CAMBIO_DE_LLANTA", 1400, "PAGADO", "TRX-SCZ-LLA-002", "ana_cliente", "juan", 4.7, "Llegaron rapido y cambiaron la llanta sin problemas."),
    ]
    for code, taller_key, auxilio_name, monto, estado_pago, referencia, cliente_key, tecnico_key, puntuacion, comentario in paid_incidents:
        pago, _ = get_or_create(
            session,
            PagoServicio,
            id_incidente=incidentes[code].id_incidente,
            defaults={
                "monto_total": monto,
                "metodo_pago": "DEMO_CARD",
                "estado_pago": estado_pago,
                "fecha_pago": incidentes[code].fecha_reporte + timedelta(hours=2),
                "referencia_transaccion": referencia,
            },
        )
        set_fields(
            pago,
            monto_total=monto,
            metodo_pago="DEMO_CARD",
            estado_pago=estado_pago,
            fecha_pago=incidentes[code].fecha_reporte + timedelta(hours=2),
            referencia_transaccion=referencia,
        )
        session.flush()
        get_or_create(
            session,
            DetallePago,
            id_pago_servicio=pago.id_pago_servicio,
            id_taller_auxilio=taller_auxilios[(taller_key, auxilio_name)].id_taller_auxilio,
            descripcion=f"Servicio de {auxilio_name} para incidente {code}",
            defaults={"cantidad": 1, "precio_unitario": monto, "subtotal": monto},
        )
        get_or_create(
            session,
            ComisionPlataforma,
            id_pago_servicio=pago.id_pago_servicio,
            defaults={
                "id_taller": talleres[taller_key].id_taller,
                "porcentaje": 10,
                "monto_comision": round(monto * 0.10, 2),
                "fecha_calculo": incidentes[code].fecha_reporte + timedelta(hours=2, minutes=5),
                "estado": "LIQUIDADA",
            },
        )
        get_or_create(
            session,
            CalificacionServicio,
            id_incidente=incidentes[code].id_incidente,
            defaults={
                "id_cliente": clientes[cliente_key].id_cliente,
                "id_taller": talleres[taller_key].id_taller,
                "id_tecnico": tecnicos[tecnico_key].id_tecnico,
                "puntuacion": puntuacion,
                "comentario": comentario,
                "fecha_calificacion": incidentes[code].fecha_reporte + timedelta(hours=2, minutes=10),
            },
        )

    metric_specs = [
        ("SCZ-BAT-001", 720, 1500, 3600, 0, False),
        ("SCZ-LLA-002", 900, 1680, 4200, 1, False),
        ("SCZ-COM-003", 1200, None, None, 0, False),
        ("SCZ-LLA-004", 840, None, None, 0, False),
        ("SCZ-MEC-005", 960, None, None, 1, False),
        ("SCZ-ACC-006", 540, 1200, None, 0, False),
        ("SCZ-SOB-007", None, None, None, 0, False),
        ("SCZ-BAT-008", 1020, None, None, 0, False),
        ("SCZ-LLA-009", 780, None, None, 0, False),
        ("SCZ-LLA-010", None, None, None, 0, False),
    ]
    for code, asignacion_seg, llegada_seg, resolucion_seg, rechazos, fue_reasignado in metric_specs:
        get_or_create(
            session,
            MetricaIncidente,
            id_incidente=incidentes[code].id_incidente,
            defaults={
                "tiempo_asignacion_seg": asignacion_seg,
                "tiempo_llegada_seg": llegada_seg,
                "tiempo_resolucion_seg": resolucion_seg,
                "cantidad_rechazos": rechazos,
                "fue_reasignado": fue_reasignado,
                "fecha_registro": incidentes[code].fecha_reporte + timedelta(hours=1),
            },
        )

    notification_specs = [
        ("pedro_cliente", "SCZ-BAT-001", "Taller acepto tu solicitud", "Electro Sur acepto la atencion de tu incidente.", "TALLER_ACEPTO", False),
        ("ana_cliente", "SCZ-LLA-002", "Tecnico en camino", "Juan Perez va rumbo a tu ubicacion.", "EN_CAMINO", False),
        ("luis_cliente", "SCZ-COM-003", "Buscando taller compatible", "Se enviaron solicitudes a talleres compatibles en Santa Cruz.", "BUSCANDO_TALLER", False),
        ("maria_cliente", "SCZ-LLA-004", "Auxilio asignado", "Apertura Norte fue asignado a tu caso.", "ASIGNACION_TECNICO", False),
        ("carla_cliente", "SCZ-MEC-005", "Tecnico en camino", "Carlos Quispe se dirige al punto del incidente.", "EN_CAMINO", False),
        ("diego_cliente", "SCZ-ACC-006", "Tecnico en sitio", "La grua ya llego al lugar del incidente.", "TECNICO_EN_SITIO", False),
        ("valeria_cliente", "SCZ-SOB-007", "Se requiere mas informacion", "Comparte foto del tablero o confirma si hay fuga de refrigerante.", "SOLICITUD_MAS_INFORMACION", False),
        ("demo_taller", "SCZ-LLA-002", "Solicitud atendida", "La solicitud fue aceptada y se asignaron recursos.", "OPERATIVA", True),
        ("grua_taller", "SCZ-ACC-006", "Nuevo incidente critico", "Se detecto un accidente menor que requiere remolque.", "OPERATIVA", False),
        ("tecnico_juan", "SCZ-LLA-002", "Nuevo incidente asignado", "Atiende un cambio de llanta en la zona Bimodal.", "ASIGNACION_TECNICO", True),
    ]
    for user_key, code, titulo, mensaje, tipo_notificacion, leido in notification_specs:
        get_or_create(
            session,
            Notificacion,
            id_usuario=usuarios[user_key].id_usuario,
            titulo=titulo,
            mensaje=mensaje,
            defaults={
                "id_incidente": incidentes[code].id_incidente,
                "tipo_notificacion": tipo_notificacion,
                "leido": leido,
                "push_estado": "PENDIENTE",
                "fecha_envio": incidentes[code].fecha_reporte + timedelta(minutes=30),
            },
        )

    for key, usuario in usuarios.items():
        if "cliente" in key or "taller" in key or "tecnico" in key:
            ensure_push_device(
                session,
                usuario=usuario,
                token_push=f"fcm_{usuario.email.replace('@', '_at_').replace('.', '_')}",
                plataforma="ANDROID",
                proveedor="FCM",
                activo=True,
            )

    bitacora_specs = [
        ("pedro_cliente", "REPORTE_INCIDENTE", "gestion_incidentes_atencion", "Pedro reporta bateria descargada en Equipetrol."),
        ("demo_taller", "ACEPTAR_SOLICITUD", "gestion_incidentes_atencion", "Taller Demo Central acepta solicitud de cambio de llanta."),
        ("electro_taller", "REGISTRO_SERVICIO_AUXILIO", "gestion_operativa_taller_tecnico", "Electro Sur actualiza servicio de auxilio electrico."),
        ("tecnico_juan", "ASIGNACION_RECIBIDA", "gestion_incidentes_atencion", "Juan Perez recibe asignacion para llanta pinchada."),
        ("tecnico_sofia", "LLEGADA_INCIDENTE", "seguimiento_monitoreo_servicio", "Sofia confirma llegada con grua a incidente critico."),
    ]
    for idx, (user_key, accion, modulo, descripcion) in enumerate(bitacora_specs):
        get_or_create(
            session,
            BitacoraSistema,
            id_usuario=usuarios[user_key].id_usuario,
            accion=accion,
            modulo=modulo,
            descripcion=descripcion,
            defaults={
                "fecha_hora": BASE_TIME + timedelta(days=3, minutes=idx * 7),
                "ip_origen": "127.0.0.1" if "cliente" in user_key or "taller" in user_key else "internal",
            },
        )


def print_rich_summary(session):
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
        DispositivoPushUsuario,
        PagoServicio,
        DetallePago,
        ComisionPlataforma,
        CalificacionServicio,
        MetricaIncidente,
    ]

    print("Resumen de poblado rico Santa Cruz:")
    for model in modelos:
        total = session.execute(select(func.count()).select_from(model)).scalar_one()
        print(f"- {model.__tablename__}: {total}")


def run_rich_santa_cruz_seeds():
    run_seeds()

    session = SessionLocal()
    try:
        normalize_existing_demo_to_santa_cruz(session)
        seed_expanded_demo_data(session)
        session.commit()
        print("Poblado rico de Santa Cruz ejecutado correctamente.")
        print_rich_summary(session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_rich_santa_cruz_seeds()
