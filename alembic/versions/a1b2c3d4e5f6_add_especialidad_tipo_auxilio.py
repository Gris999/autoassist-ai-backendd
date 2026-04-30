"""add especialidad tipo auxilio relation

Revision ID: a1b2c3d4e5f6
Revises: cf3b7d9f6a21
Create Date: 2026-04-30 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "cf3b7d9f6a21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "especialidad_tipo_auxilio",
        sa.Column(
            "id_especialidad_tipo_auxilio",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("id_especialidad", sa.BigInteger(), nullable=False),
        sa.Column("id_tipo_auxilio", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["id_especialidad"], ["especialidad.id_especialidad"]),
        sa.ForeignKeyConstraint(["id_tipo_auxilio"], ["tipo_auxilio.id_tipo_auxilio"]),
        sa.PrimaryKeyConstraint("id_especialidad_tipo_auxilio"),
        sa.UniqueConstraint(
            "id_especialidad",
            "id_tipo_auxilio",
            name="uq_especialidad_tipo_auxilio",
        ),
    )

    # Seed de compatibilidades iniciales (si existen esos nombres de catalogo).
    op.execute(
        """
        INSERT INTO especialidad_tipo_auxilio (id_especialidad, id_tipo_auxilio)
        SELECT e.id_especialidad, t.id_tipo_auxilio
        FROM especialidad e
        JOIN tipo_auxilio t ON t.nombre = 'AUXILIO_ELECTRICO'
        WHERE e.nombre = 'ELECTRICIDAD_AUTOMOTRIZ'
          AND NOT EXISTS (
            SELECT 1
            FROM especialidad_tipo_auxilio eta
            WHERE eta.id_especialidad = e.id_especialidad
              AND eta.id_tipo_auxilio = t.id_tipo_auxilio
          )
        """
    )
    op.execute(
        """
        INSERT INTO especialidad_tipo_auxilio (id_especialidad, id_tipo_auxilio)
        SELECT e.id_especialidad, t.id_tipo_auxilio
        FROM especialidad e
        JOIN tipo_auxilio t ON t.nombre = 'CAMBIO_DE_LLANTA'
        WHERE e.nombre = 'LLANTAS_Y_NEUMATICOS'
          AND NOT EXISTS (
            SELECT 1
            FROM especialidad_tipo_auxilio eta
            WHERE eta.id_especialidad = e.id_especialidad
              AND eta.id_tipo_auxilio = t.id_tipo_auxilio
          )
        """
    )
    op.execute(
        """
        INSERT INTO especialidad_tipo_auxilio (id_especialidad, id_tipo_auxilio)
        SELECT e.id_especialidad, t.id_tipo_auxilio
        FROM especialidad e
        JOIN tipo_auxilio t ON t.nombre = 'REMOLQUE'
        WHERE e.nombre = 'GRUA_Y_REMOLQUE'
          AND NOT EXISTS (
            SELECT 1
            FROM especialidad_tipo_auxilio eta
            WHERE eta.id_especialidad = e.id_especialidad
              AND eta.id_tipo_auxilio = t.id_tipo_auxilio
          )
        """
    )
    op.execute(
        """
        INSERT INTO especialidad_tipo_auxilio (id_especialidad, id_tipo_auxilio)
        SELECT e.id_especialidad, t.id_tipo_auxilio
        FROM especialidad e
        JOIN tipo_auxilio t ON t.nombre IN ('AUXILIO_MECANICO_BASICO', 'SUMINISTRO_COMBUSTIBLE')
        WHERE e.nombre = 'MECANICA_GENERAL'
          AND NOT EXISTS (
            SELECT 1
            FROM especialidad_tipo_auxilio eta
            WHERE eta.id_especialidad = e.id_especialidad
              AND eta.id_tipo_auxilio = t.id_tipo_auxilio
          )
        """
    )


def downgrade() -> None:
    op.drop_table("especialidad_tipo_auxilio")

