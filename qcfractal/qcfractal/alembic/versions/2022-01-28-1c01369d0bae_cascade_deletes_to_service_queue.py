"""cascade deletes to service queue

Revision ID: 1c01369d0bae
Revises: 0f6d9e6ef312
Create Date: 2022-01-28 10:44:03.394150

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "1c01369d0bae"
down_revision = "0f6d9e6ef312"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("service_queue_record_id_fkey", "service_queue", type_="foreignkey")
    op.create_foreign_key(None, "service_queue", "base_record", ["record_id"], ["id"], ondelete="cascade")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "service_queue", type_="foreignkey")
    op.create_foreign_key("service_queue_record_id_fkey", "service_queue", "base_record", ["record_id"], ["id"])
    # ### end Alembic commands ###
