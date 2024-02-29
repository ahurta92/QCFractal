"""optimization dataset

Revision ID: bf4b379a6ce4
Revises: 4485daecc21b
Create Date: 2022-02-18 10:31:50.528949

"""
import json
import os
import sys

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import table, column

sys.path.insert(1, os.path.dirname(os.path.abspath(__file__)))
from migration_helpers.v0_50_helpers import get_empty_keywords_id, add_opt_spec, add_qc_spec

# revision identifiers, used by Alembic.
revision = "bf4b379a6ce4"
down_revision = "4485daecc21b"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "optimization_dataset",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["collection.id"], ondelete="cascade"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "optimization_dataset_entry",
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("initial_molecule_id", sa.Integer(), nullable=False),
        sa.Column("additional_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["optimization_dataset.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(
            ["initial_molecule_id"],
            ["molecule.id"],
        ),
        sa.PrimaryKeyConstraint("dataset_id", "name"),
    )
    op.create_index(
        "ix_optimization_dataset_entry_dataset_id", "optimization_dataset_entry", ["dataset_id"], unique=False
    )
    op.create_index(
        "ix_optimization_dataset_entry_initial_molecule_id",
        "optimization_dataset_entry",
        ["initial_molecule_id"],
        unique=False,
    )
    op.create_index("ix_optimization_dataset_entry_name", "optimization_dataset_entry", ["name"], unique=False)
    op.create_table(
        "optimization_dataset_specification",
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("specification_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["optimization_dataset.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(
            ["specification_id"],
            ["optimization_specification.id"],
        ),
        sa.PrimaryKeyConstraint("dataset_id", "name"),
    )
    op.create_index(
        "ix_optimization_dataset_specification_dataset_id",
        "optimization_dataset_specification",
        ["dataset_id"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_dataset_specification_name", "optimization_dataset_specification", ["name"], unique=False
    )
    op.create_index(
        "ix_optimization_dataset_specification_specification_id",
        "optimization_dataset_specification",
        ["specification_id"],
        unique=False,
    )
    op.create_table(
        "optimization_dataset_record",
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("entry_name", sa.String(), nullable=False),
        sa.Column("specification_name", sa.String(), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id", "entry_name"],
            ["optimization_dataset_entry.dataset_id", "optimization_dataset_entry.name"],
            onupdate="cascade",
            ondelete="cascade",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id", "specification_name"],
            ["optimization_dataset_specification.dataset_id", "optimization_dataset_specification.name"],
            onupdate="cascade",
            ondelete="cascade",
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["optimization_dataset.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(
            ["record_id"],
            ["optimization_record.id"],
        ),
        sa.PrimaryKeyConstraint("dataset_id", "entry_name", "specification_name"),
        sa.UniqueConstraint(
            "dataset_id", "entry_name", "specification_name", name="ux_optimization_dataset_record_unique"
        ),
    )
    op.create_index(
        "ix_optimization_dataset_record_record_id", "optimization_dataset_record", ["record_id"], unique=False
    )

    # Add default tag/priority to base collection class
    op.add_column("collection", sa.Column("default_tag", sa.String(), nullable=True))
    op.add_column("collection", sa.Column("default_priority", sa.Integer(), nullable=True))

    op.execute(sa.text("UPDATE collection SET default_tag = '*' where default_tag IS NULL"))
    op.execute(sa.text("UPDATE collection SET default_priority = 1 where default_priority IS NULL"))

    op.alter_column("collection", "default_tag", nullable=False)
    op.alter_column("collection", "default_priority", nullable=False)

    ######################
    # MIGRATION
    ######################
    conn = op.get_bind()

    # For all collections
    conn.execute(
        sa.text(
            """UPDATE collection
        SET provenance = NULL
        WHERE provenance::jsonb = 'null'::jsonb
        """
        )
    )

    # Just for optimization
    op.execute(
        sa.text("UPDATE collection SET collection_type = 'optimization' where collection = 'optimizationdataset'")
    )
    op.execute(sa.text("UPDATE collection SET collection = 'optimization' where collection = 'optimizationdataset'"))

    # Temporary ORM
    collection_table = table(
        "collection",
        column("id", sa.Integer),
        column("collection", sa.String),
        column("extra", sa.JSON),
    )

    session = Session(conn)
    collections = session.query(collection_table).where(collection_table.c.collection == "optimization").all()
    for col in collections:
        ext = col.extra
        col_specs = ext.pop("specs")
        col_record = ext.pop("records")

        # Add the dataset to the separate optimziation dataset table
        conn.execute(sa.text("INSERT INTO optimization_dataset (id) VALUES (:colid)"), parameters={"colid": col.id})

        # Specifications
        # Empty keywords
        empty_kw_id = get_empty_keywords_id(conn)

        #########################
        # SPECIFICATIONS
        #########################
        for spec_name, spec in col_specs.items():
            # Protocols for qc_spec were always ignored. So set them with the default
            opt_spec = spec["optimization_spec"]
            qc_spec = spec["qc_spec"]
            qc_spec["driver"] = "deferred"

            if qc_spec.get("keywords", None) is None:
                qc_spec["keywords"] = empty_kw_id

            qc_spec_id = add_qc_spec(
                conn,
                qc_spec["program"],
                qc_spec["driver"],
                qc_spec["method"],
                qc_spec["basis"],
                qc_spec["keywords"],
                {},
            )

            # Optimization spec
            if opt_spec.get("protocols", None) is None:
                opt_spec["protocols"] = {}
            if opt_spec.get("keywords", None) is None:
                opt_spec["keywords"] = {}

            opt_spec_id = add_opt_spec(
                conn, qc_spec_id, opt_spec["program"], opt_spec["keywords"], opt_spec["protocols"]
            )

            # Now add to the dataset spec
            conn.execute(
                sa.text(
                    """
                       INSERT INTO optimization_dataset_specification (dataset_id, name, description, specification_id)
                       VALUES (:col_id, :spec_name, :spec_desc, :opt_spec_id)
                    """
                ),
                parameters=dict(
                    col_id=col.id, spec_name=spec["name"], spec_desc=spec["description"], opt_spec_id=opt_spec_id
                ),
            )

        ####################
        # ENTRIES/RECORDS
        ####################
        conn.execute(
            sa.text(
                """
                   INSERT INTO optimization_dataset_entry (dataset_id, name, initial_molecule_id, additional_keywords, attributes)
                   SELECT :col_id, j.key, m.id, (j.value->>'additional_keywords')::jsonb, (j.value->>'attributes')::jsonb
                   FROM collection, json_each(extra->'records') AS j
                   INNER JOIN molecule m ON m.id = (j.value->>'initial_molecule')::integer
                   WHERE collection.id = :col_id
                """
            ),
            parameters=dict(col_id=col.id),
        )

        for ent_name, ent in col_record.items():
            for spec_name, record_id in ent["object_map"].items():
                conn.execute(
                    sa.text(
                        """
                           INSERT INTO optimization_dataset_record (dataset_id, entry_name, specification_name, record_id)
                           SELECT :col_id, :ent_name, :spec_name, r.id
                           FROM optimization_record r
                           WHERE r.id = :record_id
                           """
                    ),
                    parameters=dict(
                        col_id=col.id,
                        ent_name=ent_name,
                        spec_name=spec_name,
                        record_id=record_id,
                    ),
                )

        # Update the collection extra, with the removed fields
        ext.pop("history", None)
        conn.execute(
            sa.text("UPDATE collection SET extra = (:extra)::json WHERE id = :col_id"),
            parameters=dict(
                col_id=col.id,
                extra=json.dumps(ext),
            ),
        )

    # ### end Alembic commands ###


def downgrade():
    raise RuntimeError("Cannot downgrade")
