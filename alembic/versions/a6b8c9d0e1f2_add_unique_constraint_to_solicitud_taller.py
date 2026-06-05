"""add unique constraint to solicitud_taller

Revision ID: a6b8c9d0e1f2
Revises: a1b2c3d4e5f6
Create Date: 2026-06-05 16:45:00.000000

Regla de deduplicacion aplicada antes del constraint:
1. conservar estado_solicitud='ACEPTADA' sobre 'PENDIENTE';
2. si empatan, conservar la fila con fecha_respuesta/fecha_envio mas reciente;
3. si aun empatan, conservar el mayor id_solicitud_taller.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a6b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id_solicitud_taller,
                ROW_NUMBER() OVER (
                    PARTITION BY id_incidente, id_taller
                    ORDER BY
                        CASE
                            WHEN estado_solicitud = 'ACEPTADA' THEN 0
                            WHEN estado_solicitud = 'PENDIENTE' THEN 1
                            ELSE 2
                        END,
                        COALESCE(fecha_respuesta, fecha_envio) DESC,
                        id_solicitud_taller DESC
                ) AS rn
            FROM solicitud_taller
        )
        DELETE FROM solicitud_taller
        WHERE id_solicitud_taller IN (
            SELECT id_solicitud_taller
            FROM ranked
            WHERE rn > 1
        );
        """
    )
    op.create_unique_constraint(
        "uq_solicitud_taller_incidente_taller",
        "solicitud_taller",
        ["id_incidente", "id_taller"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_solicitud_taller_incidente_taller",
        "solicitud_taller",
        type_="unique",
    )
