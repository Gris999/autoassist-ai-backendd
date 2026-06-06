"""add pendiente_asignacion service state

Revision ID: b3c4d5e6f7a8
Revises: a6b8c9d0e1f2
Create Date: 2026-06-05 19:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a6b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO estado_servicio (nombre, descripcion, orden_flujo, estado)
        SELECT
            'PENDIENTE_ASIGNACION',
            'Taller acepto y falta asignar recursos',
            4,
            TRUE
        WHERE NOT EXISTS (
            SELECT 1
            FROM estado_servicio
            WHERE nombre = 'PENDIENTE_ASIGNACION'
        );
        """
    )

    op.execute(
        """
        UPDATE estado_servicio
        SET
            orden_flujo = CASE nombre
                WHEN 'BUSCANDO_TALLER' THEN 3
                WHEN 'PENDIENTE_ASIGNACION' THEN 4
                WHEN 'ASIGNADO' THEN 5
                WHEN 'EN_CAMINO' THEN 6
                WHEN 'EN_ATENCION' THEN 7
                WHEN 'FINALIZADO' THEN 8
                WHEN 'CANCELADO' THEN 9
                ELSE orden_flujo
            END,
            descripcion = CASE nombre
                WHEN 'PENDIENTE_ASIGNACION' THEN 'Taller acepto y falta asignar recursos'
                WHEN 'ASIGNADO' THEN 'Servicio con tecnico y unidad movil ya asignados'
                ELSE descripcion
            END
        WHERE nombre IN (
            'BUSCANDO_TALLER',
            'PENDIENTE_ASIGNACION',
            'ASIGNADO',
            'EN_CAMINO',
            'EN_ATENCION',
            'FINALIZADO',
            'CANCELADO'
        );
        """
    )
    op.execute(
        """
        UPDATE historial_incidente
        SET detalle = REPLACE(
            detalle,
            'acepto la solicitud de atencion.',
            'acepto la solicitud y el incidente quedo pendiente de asignacion de recursos.'
        )
        WHERE detalle LIKE '%acepto la solicitud de atencion.%';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        WITH ids AS (
            SELECT
                MAX(CASE WHEN nombre = 'PENDIENTE_ASIGNACION' THEN id_estado_servicio END) AS pendiente_id,
                MAX(CASE WHEN nombre = 'ASIGNADO' THEN id_estado_servicio END) AS asignado_id
            FROM estado_servicio
        )
        UPDATE incidente
        SET id_estado_servicio_actual = ids.asignado_id
        FROM ids
        WHERE ids.pendiente_id IS NOT NULL
          AND incidente.id_estado_servicio_actual = ids.pendiente_id;
        """
    )
    op.execute(
        """
        WITH ids AS (
            SELECT
                MAX(CASE WHEN nombre = 'PENDIENTE_ASIGNACION' THEN id_estado_servicio END) AS pendiente_id,
                MAX(CASE WHEN nombre = 'ASIGNADO' THEN id_estado_servicio END) AS asignado_id
            FROM estado_servicio
        )
        UPDATE historial_incidente
        SET id_estado_anterior = ids.asignado_id
        FROM ids
        WHERE ids.pendiente_id IS NOT NULL
          AND historial_incidente.id_estado_anterior = ids.pendiente_id;
        """
    )
    op.execute(
        """
        WITH ids AS (
            SELECT
                MAX(CASE WHEN nombre = 'PENDIENTE_ASIGNACION' THEN id_estado_servicio END) AS pendiente_id,
                MAX(CASE WHEN nombre = 'ASIGNADO' THEN id_estado_servicio END) AS asignado_id
            FROM estado_servicio
        )
        UPDATE historial_incidente
        SET id_estado_nuevo = ids.asignado_id
        FROM ids
        WHERE ids.pendiente_id IS NOT NULL
          AND historial_incidente.id_estado_nuevo = ids.pendiente_id;
        """
    )
    op.execute(
        """
        DELETE FROM estado_servicio
        WHERE nombre = 'PENDIENTE_ASIGNACION';
        """
    )
    op.execute(
        """
        UPDATE estado_servicio
        SET
            orden_flujo = CASE nombre
                WHEN 'BUSCANDO_TALLER' THEN 3
                WHEN 'ASIGNADO' THEN 4
                WHEN 'EN_CAMINO' THEN 5
                WHEN 'EN_ATENCION' THEN 6
                WHEN 'FINALIZADO' THEN 7
                WHEN 'CANCELADO' THEN 8
                ELSE orden_flujo
            END,
            descripcion = CASE nombre
                WHEN 'ASIGNADO' THEN 'Servicio asignado a un taller/tecnico'
                ELSE descripcion
            END
        WHERE nombre IN (
            'BUSCANDO_TALLER',
            'ASIGNADO',
            'EN_CAMINO',
            'EN_ATENCION',
            'FINALIZADO',
            'CANCELADO'
        );
        """
    )
    op.execute(
        """
        UPDATE historial_incidente
        SET detalle = REPLACE(
            detalle,
            'acepto la solicitud y el incidente quedo pendiente de asignacion de recursos.',
            'acepto la solicitud de atencion.'
        )
        WHERE detalle LIKE '%acepto la solicitud y el incidente quedo pendiente de asignacion de recursos.%';
        """
    )
