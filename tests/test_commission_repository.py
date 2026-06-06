from datetime import UTC, datetime
from types import SimpleNamespace

from app.modules.inteligencia_gestion_estrategica import repository as repo


class DummyResult:
    def __init__(self, value):
        self.value = value

    def unique(self):
        return self

    def scalar_one_or_none(self):
        return self.value


class DummyDB:
    def __init__(self):
        self.added = []
        self.flush_called = 0
        self.refresh_called = []
        self.commit_called = 0
        self.executed_statement = None
        self.result_value = None

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flush_called += 1

    def refresh(self, obj):
        self.refresh_called.append(obj)

    def commit(self):
        self.commit_called += 1

    def execute(self, statement):
        self.executed_statement = statement
        return DummyResult(self.result_value)


def test_update_comision_plataforma_estado_operativo_updates_only_operational_fields():
    db = DummyDB()
    fecha_calculo = datetime(2026, 6, 6, 10, 0, tzinfo=UTC)
    fecha_liquidacion_existente = datetime(2026, 6, 5, 9, 0, tzinfo=UTC)
    fecha_accion = datetime(2026, 6, 6, 11, 0, tzinfo=UTC)
    nueva_fecha_liquidacion = datetime(2026, 6, 6, 12, 0, tzinfo=UTC)
    comision = SimpleNamespace(
        estado="PENDIENTE_LIQUIDACION",
        observacion_estado=None,
        referencia_liquidacion=None,
        id_usuario_ultima_accion=None,
        fecha_ultima_accion=None,
        fecha_liquidacion=fecha_liquidacion_existente,
        porcentaje=10,
        monto_comision=25,
        id_taller=4,
        id_pago_servicio=7,
        fecha_calculo=fecha_calculo,
    )

    updated = repo.update_comision_plataforma_estado_operativo(
        db,
        comision,
        estado_nuevo="LIQUIDADA",
        id_usuario_actor=99,
        observacion="Liquidacion validada",
        referencia="LQ-001",
        fecha_accion=fecha_accion,
        fecha_liquidacion=nueva_fecha_liquidacion,
    )

    assert updated is comision
    assert comision.estado == "LIQUIDADA"
    assert comision.observacion_estado == "Liquidacion validada"
    assert comision.referencia_liquidacion == "LQ-001"
    assert comision.id_usuario_ultima_accion == 99
    assert comision.fecha_ultima_accion == fecha_accion
    assert comision.fecha_liquidacion == nueva_fecha_liquidacion
    assert comision.porcentaje == 10
    assert comision.monto_comision == 25
    assert comision.id_taller == 4
    assert comision.id_pago_servicio == 7
    assert comision.fecha_calculo == fecha_calculo
    assert db.flush_called == 1
    assert db.refresh_called == [comision]
    assert db.commit_called == 0


def test_update_comision_plataforma_estado_operativo_keeps_existing_fecha_liquidacion_when_missing():
    db = DummyDB()
    fecha_existente = datetime(2026, 6, 5, 9, 0, tzinfo=UTC)
    fecha_accion = datetime(2026, 6, 6, 11, 0, tzinfo=UTC)
    comision = SimpleNamespace(
        estado="OBSERVADA",
        observacion_estado="Revision previa",
        referencia_liquidacion="OLD-REF",
        id_usuario_ultima_accion=10,
        fecha_ultima_accion=None,
        fecha_liquidacion=fecha_existente,
        porcentaje=8,
        monto_comision=15,
        id_taller=1,
        id_pago_servicio=2,
        fecha_calculo=datetime(2026, 6, 4, 8, 0, tzinfo=UTC),
    )

    repo.update_comision_plataforma_estado_operativo(
        db,
        comision,
        estado_nuevo="CANCELADA",
        id_usuario_actor=77,
        observacion="Cancelada por revision",
        referencia="CAN-001",
        fecha_accion=fecha_accion,
    )

    assert comision.fecha_liquidacion == fecha_existente
    assert db.commit_called == 0


def test_create_historial_comision_plataforma_builds_history_without_commit():
    db = DummyDB()
    fecha_hora = datetime(2026, 6, 6, 13, 0, tzinfo=UTC)

    historial = repo.create_historial_comision_plataforma(
        db,
        id_comision=5,
        estado_anterior="PENDIENTE_LIQUIDACION",
        estado_nuevo="OBSERVADA",
        id_usuario_actor=12,
        observacion="Monto en revision",
        referencia="OBS-001",
        fecha_hora=fecha_hora,
    )

    assert historial.id_comision == 5
    assert historial.estado_anterior == "PENDIENTE_LIQUIDACION"
    assert historial.estado_nuevo == "OBSERVADA"
    assert historial.observacion == "Monto en revision"
    assert historial.referencia == "OBS-001"
    assert historial.id_usuario_actor == 12
    assert historial.fecha_hora == fecha_hora
    assert db.added == [historial]
    assert db.flush_called == 1
    assert db.refresh_called == [historial]
    assert db.commit_called == 0


def test_get_comision_plataforma_by_id_for_update_can_be_invoked_without_writing():
    db = DummyDB()
    comision = SimpleNamespace(id_comision=33)
    db.result_value = comision

    result = repo.get_comision_plataforma_by_id_for_update(db, 33)

    assert result is comision
    assert db.executed_statement is not None
    assert db.executed_statement._for_update_arg is not None
    assert db.commit_called == 0
