"""Add Document and Question models

Revision ID: 812fc0ad70ea
Revises: 9288637c4647
Create Date: 2024-10-21 21:52:25.628110

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '812fc0ad70ea'
down_revision = '9288637c4647'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=256), nullable=False),
    sa.Column('filepath', sa.String(length=512), nullable=False),
    sa.Column('upload_date', sa.DateTime(), nullable=True),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('questions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('question_text', sa.Text(), nullable=False),
    sa.Column('options', sa.JSON(), nullable=False),
    sa.Column('correct_answer', sa.String(length=256), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('questions')
    op.drop_table('documents')
    # ### end Alembic commands ###
