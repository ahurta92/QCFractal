"""remove keywordset

Revision ID: b9b7b6926b8b
Revises: c1a0b0ee712e
Create Date: 2022-05-21 09:25:14.082795

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b9b7b6926b8b"
down_revision = "c1a0b0ee712e"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("qc_specification", sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Migrate the values of the keywords
    op.execute(
        sa.text(
            """UPDATE qc_specification
           SET keywords = keywords.values
           FROM keywords
           WHERE keywords.id = keywords_id
        """
        )
    )

    op.alter_column("qc_specification", "keywords", nullable=False)
    op.drop_index("ix_qc_specification_keywords_id", table_name="qc_specification")
    op.drop_constraint("ux_qc_specification_keys", "qc_specification", type_="unique")
    op.create_unique_constraint(
        "ux_qc_specification_keys",
        "qc_specification",
        ["program", "driver", "method", "basis", "keywords", "protocols"],
    )
    op.create_index("ix_qc_specification_keywords", "qc_specification", ["keywords"], unique=False)
    op.drop_constraint("qc_specification_keywords_id_fkey", "qc_specification", type_="foreignkey")
    op.drop_column("qc_specification", "keywords_id")

    op.drop_table("keywords")
    # ### end Alembic commands ###


def downgrade():
    raise RuntimeError("Cannot downgrade")
