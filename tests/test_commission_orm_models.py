from app.modules.seguimiento_monitoreo_servicio.models import (
    ComisionPlataforma,
    HistorialComisionPlataforma,
)


def test_commission_orm_matches_operational_fields():
    assert ComisionPlataforma.__tablename__ == "comision_plataforma"
    assert HistorialComisionPlataforma.__tablename__ == "historial_comision_plataforma"

    commission_columns = ComisionPlataforma.__table__.columns
    history_columns = HistorialComisionPlataforma.__table__.columns

    for column_name in (
        "fecha_liquidacion",
        "observacion_estado",
        "referencia_liquidacion",
        "id_usuario_ultima_accion",
        "fecha_ultima_accion",
    ):
        assert column_name in commission_columns

    for column_name in (
        "id_historial_comision",
        "id_comision",
        "estado_anterior",
        "estado_nuevo",
        "observacion",
        "referencia",
        "id_usuario_actor",
        "fecha_hora",
    ):
        assert column_name in history_columns

    commission_fk_targets = {
        f"{fk.column.table.name}.{fk.column.name}"
        for fk in ComisionPlataforma.__table__.foreign_keys
        if fk.parent.name == "id_usuario_ultima_accion"
    }
    assert "usuario.id_usuario" in commission_fk_targets

    history_fk_targets = {
        (fk.parent.name, f"{fk.column.table.name}.{fk.column.name}")
        for fk in HistorialComisionPlataforma.__table__.foreign_keys
    }
    assert ("id_comision", "comision_plataforma.id_comision") in history_fk_targets
    assert ("id_usuario_actor", "usuario.id_usuario") in history_fk_targets

    assert "historial" in ComisionPlataforma.__mapper__.relationships
    assert "comision" in HistorialComisionPlataforma.__mapper__.relationships
