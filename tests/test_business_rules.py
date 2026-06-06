from pathlib import Path
import re

from app.modules.gestion_incidentes_atencion.models import SolicitudTaller
from app.modules.gestion_incidentes_atencion.schemas import AsignacionIncidenteRequest


def test_id_unidad_movil_is_optional_in_schema():
    payload = AsignacionIncidenteRequest(id_tecnico=1, id_unidad_movil=None)

    assert payload.id_unidad_movil is None


def test_no_hardcoded_finalizado_state_id_in_business_logic():
    root = Path(__file__).resolve().parents[1] / "app" / "modules"
    offending = []
    pattern = re.compile(r"id_estado_servicio_actual\s*==\s*7\b")

    for path in root.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if pattern.search(content):
            offending.append(str(path))

    assert offending == []


def test_solicitud_taller_has_unique_constraint_for_incidente_y_taller():
    constraint_names = {
        getattr(constraint, "name", None)
        for constraint in SolicitudTaller.__table__.constraints
    }

    assert "uq_solicitud_taller_incidente_taller" in constraint_names
