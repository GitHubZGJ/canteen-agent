"""forecast_result dish_id

Revision ID: 5e6deec0363d
Revises: a0257ec18a4d
Create Date: 2026-11-08 18:24:02.080443
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5e6deec0363d'
down_revision: Union[str, None] = 'a0257ec18a4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('forecast_result', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dish_id', sa.Integer(), nullable=False))
        batch_op.create_index(batch_op.f('ix_forecast_result_dish_id'), ['dish_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_forecast_result_dish_id_dish', 'dish', ['dish_id'], ['id']
        )


def downgrade() -> None:
    with op.batch_alter_table('forecast_result', schema=None) as batch_op:
        batch_op.drop_constraint('fk_forecast_result_dish_id_dish', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_forecast_result_dish_id'))
        batch_op.drop_column('dish_id')