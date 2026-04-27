"""add push notifications

Revision ID: cf3b7d9f6a21
Revises: 9d4f7f1b7b34
Create Date: 2026-04-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cf3b7d9f6a21"
down_revision: Union[str, Sequence[str], None] = "9d4f7f1b7b34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notificacion",
        sa.Column("push_estado", sa.String(length=50), nullable=False, server_default="PENDIENTE"),
    )
    op.add_column("notificacion", sa.Column("push_error", sa.Text(), nullable=True))
    op.add_column("notificacion", sa.Column("fecha_envio_push", sa.DateTime(), nullable=True))
    op.create_table(
        "dispositivo_push_usuario",
        sa.Column(
            "id_dispositivo_push",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("id_usuario", sa.BigInteger(), nullable=False),
        sa.Column("token_push", sa.String(length=500), nullable=False),
        sa.Column("plataforma", sa.String(length=30), nullable=False),
        sa.Column("proveedor", sa.String(length=30), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("fecha_registro", sa.DateTime(), nullable=False),
        sa.Column("fecha_actualizacion", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["id_usuario"], ["usuario.id_usuario"]),
        sa.PrimaryKeyConstraint("id_dispositivo_push"),
        sa.UniqueConstraint("token_push"),
    )
    op.alter_column("notificacion", "push_estado", server_default=None)


def downgrade() -> None:
    op.drop_table("dispositivo_push_usuario")
    op.drop_column("notificacion", "fecha_envio_push")
    op.drop_column("notificacion", "push_error")
    op.drop_column("notificacion", "push_estado")
