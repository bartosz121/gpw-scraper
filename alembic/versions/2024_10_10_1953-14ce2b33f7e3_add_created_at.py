"""Add created at

Revision ID: 14ce2b33f7e3
Revises: 4de9c1afb476
Create Date: 2024-10-10 19:53:46.357026

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "14ce2b33f7e3"
down_revision: Union[str, None] = "4de9c1afb476"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "espi_ebi", sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )

    op.execute("UPDATE espi_ebi SET created_at = date WHERE created_at IS NULL;")

    op.alter_column("espi_ebi", "created_at", nullable=False)


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("espi_ebi", "created_at")
    # ### end Alembic commands ###