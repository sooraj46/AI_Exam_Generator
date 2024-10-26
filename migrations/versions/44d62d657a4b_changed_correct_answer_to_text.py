"""Changed correct_answer to Text

Revision ID: 44d62d657a4b
Revises: a07eed0ec5f8
Create Date: 2024-10-22 22:01:09.791434

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '44d62d657a4b'
down_revision = 'a07eed0ec5f8'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column('correct_answer',
               existing_type=sa.VARCHAR(length=256),
               type_=sa.Text(),
               existing_nullable=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column('correct_answer',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=256),
               existing_nullable=False)

    # ### end Alembic commands ###
