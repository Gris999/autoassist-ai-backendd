import inspect
from types import SimpleNamespace

import pytest

from app.modules.gestion_incidentes_atencion import service as incident_service


class DummyDB:
    def rollback(self):
        return None


def test_pendiente_asignacion_is_not_visible_to_tecnico():
    assert (
        incident_service.ESTADO_INCIDENTE_PENDIENTE_ASIGNACION
        not in incident_service.ESTADOS_CONSULTABLES_TECNICO
    )


def test_validar_incidente_aceptado_para_taller_requires_pendiente_asignacion(monkeypatch):
    incidente = SimpleNamespace(
        estado_servicio_actual=SimpleNamespace(nombre="PENDIENTE_ASIGNACION")
    )
    solicitud = SimpleNamespace(id_taller=9)

    monkeypatch.setattr(incident_service, "get_incidente_by_id", lambda db, incident_id: incidente)
    monkeypatch.setattr(
        incident_service,
        "get_solicitud_aceptada_by_incidente_id",
        lambda db, incident_id: solicitud,
    )
    monkeypatch.setattr(
        incident_service,
        "get_asignacion_servicio_by_incidente_id",
        lambda db, incident_id: None,
    )

    result = incident_service._validar_incidente_aceptado_para_taller(
        None,
        id_incidente=1,
        id_taller=9,
    )

    assert result is incidente


def test_asignacion_exige_pendiente_asignacion(monkeypatch):
    db = DummyDB()
    incidente = SimpleNamespace(
        estado_servicio_actual=SimpleNamespace(nombre="BUSCANDO_TALLER")
    )

    monkeypatch.setattr(
        incident_service,
        "_get_taller_actor_service",
        lambda db, current_user: SimpleNamespace(id_taller=3),
    )
    monkeypatch.setattr(
        incident_service,
        "get_incidente_by_id_for_update",
        lambda db, incident_id: incidente,
    )
    monkeypatch.setattr(
        incident_service,
        "get_solicitud_aceptada_by_incidente_and_taller_id",
        lambda db, id_incidente, id_taller: SimpleNamespace(id_taller=id_taller),
    )

    payload = incident_service.AsignacionIncidenteRequest(id_tecnico=1, id_unidad_movil=None)

    with pytest.raises(ValueError, match="estado apto para asignacion"):
        incident_service.asignar_tecnico_unidad_incidente_service(
            db,
            SimpleNamespace(id_usuario=1),
            1,
            payload,
        )


def test_aceptacion_usa_pendiente_asignacion_en_el_servicio():
    source = inspect.getsource(incident_service.responder_solicitud_atencion_service)

    assert "ESTADO_INCIDENTE_PENDIENTE_ASIGNACION" in source
    assert "id_estado_servicio_actual=estado_pendiente_asignacion.id_estado_servicio" in source


def test_asignado_se_aplica_despues_de_crear_asignacion_servicio():
    source = inspect.getsource(incident_service.asignar_tecnico_unidad_incidente_service)

    assert source.index("create_asignacion_servicio(") < source.index(
        "update_incidente_estado_servicio_actual("
    )
