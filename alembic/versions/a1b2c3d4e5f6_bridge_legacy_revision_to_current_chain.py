"""bridge legacy revision to current chain

Revision ID: a1b2c3d4e5f6
Revises: cf3b7d9f6a21
Create Date: 2026-06-05 19:20:00.000000

Esta revision no aplica cambios de esquema.
Existe para reconciliar bases ya marcadas con la revision legacy
`a1b2c3d4e5f6`, cuyo esquema observado ya contiene los cambios de
`9d4f7f1b7b34` y `cf3b7d9f6a21`.
"""

from typing import Sequence, Union


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "cf3b7d9f6a21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
