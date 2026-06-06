"""add operational fields to comision_plataforma and history

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-06-06 18:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "comision_plataforma",
        sa.Column("fecha_liquidacion", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "comision_plataforma",
        sa.Column("observacion_estado", sa.Text(), nullable=True),
    )
    op.add_column(
        "comision_plataforma",
        sa.Column("referencia_liquidacion", sa.String(length=150), nullable=True),
    )
    op.add_column(
        "comision_plataforma",
        sa.Column("id_usuario_ultima_accion", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "comision_plataforma",
        sa.Column("fecha_ultima_accion", sa.DateTime(), nullable=True),
    )
    op.create_foreign_key(
        "fk_comision_plataforma_usuario_ultima_accion",
        "comision_plataforma",
        "usuario",
        ["id_usuario_ultima_accion"],
        ["id_usuario"],
    )
    op.create_index(
        "ix_comision_plataforma_estado",
        "comision_plataforma",
        ["estado"],
        unique=False,
    )
    op.create_index(
        "ix_comision_plataforma_id_taller_estado",
        "comision_plataforma",
        ["id_taller", "estado"],
        unique=False,
    )

    op.create_table(
        "historial_comision_plataforma",
        sa.Column(
            "id_historial_comision",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("id_comision", sa.BigInteger(), nullable=False),
        sa.Column("estado_anterior", sa.String(length=50), nullable=True),
        sa.Column("estado_nuevo", sa.String(length=50), nullable=False),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.Column("referencia", sa.String(length=150), nullable=True),
        sa.Column("id_usuario_actor", sa.BigInteger(), nullable=False),
        sa.Column("fecha_hora", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_comision"],
            ["comision_plataforma.id_comision"],
            name="fk_historial_comision_plataforma_comision",
        ),
        sa.ForeignKeyConstraint(
            ["id_usuario_actor"],
            ["usuario.id_usuario"],
            name="fk_historial_comision_plataforma_usuario_actor",
        ),
        sa.PrimaryKeyConstraint(
            "id_historial_comision",
            name="pk_historial_comision_plataforma",
        ),
    )
    op.create_index(
        "ix_historial_comision_id_comision_fecha_hora",
        "historial_comision_plataforma",
        ["id_comision", "fecha_hora"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_historial_comision_id_comision_fecha_hora",
        table_name="historial_comision_plataforma",
    )
    op.drop_table("historial_comision_plataforma")

    op.drop_index(
        "ix_comision_plataforma_id_taller_estado",
        table_name="comision_plataforma",
    )
    op.drop_index(
        "ix_comision_plataforma_estado",
        table_name="comision_plataforma",
    )
    op.drop_constraint(
        "fk_comision_plataforma_usuario_ultima_accion",
        "comision_plataforma",
        type_="foreignkey",
    )
    op.drop_column("comision_plataforma", "fecha_ultima_accion")
    op.drop_column("comision_plataforma", "id_usuario_ultima_accion")
    op.drop_column("comision_plataforma", "referencia_liquidacion")
    op.drop_column("comision_plataforma", "observacion_estado")
    op.drop_column("comision_plataforma", "fecha_liquidacion")
