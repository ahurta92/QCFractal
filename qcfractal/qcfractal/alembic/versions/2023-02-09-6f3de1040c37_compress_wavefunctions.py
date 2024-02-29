"""compress wavefunctions

Revision ID: 6f3de1040c37
Revises: 1a61b3bb1ee4
Create Date: 2023-02-09 10:00:49.665770

"""

import sqlalchemy as sa
from alembic import op
from qcelemental.models.results import WavefunctionProperties
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import table, column

from qcfractal.db_socket.column_types import MsgpackExt
from qcportal.compression import compress, CompressionEnum

# revision identifiers, used by Alembic.
revision = "6f3de1040c37"
down_revision = "1a61b3bb1ee4"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.add_column("wavefunction_store", sa.Column("compression_type", sa.Enum(CompressionEnum, nullable=True)))
    op.add_column("wavefunction_store", sa.Column("compression_level", sa.Integer, nullable=True))
    op.add_column("wavefunction_store", sa.Column("data", sa.LargeBinary, nullable=True))

    op.execute(sa.text("ALTER TABLE native_file ALTER COLUMN data SET STORAGE EXTERNAL"))

    # Migrate wavefunction data
    old_wfn_table = table(
        "wavefunction_store",
        column("id", sa.Integer),
        column("record_id", sa.Integer),
        column("basis", MsgpackExt),
        column("restricted", sa.Boolean),
        column("h_core_a", MsgpackExt),
        column("h_core_b", MsgpackExt),
        column("h_effective_a", MsgpackExt),
        column("h_effective_b", MsgpackExt),
        column("scf_orbitals_a", MsgpackExt),
        column("scf_orbitals_b", MsgpackExt),
        column("scf_density_a", MsgpackExt),
        column("scf_density_b", MsgpackExt),
        column("scf_fock_a", MsgpackExt),
        column("scf_fock_b", MsgpackExt),
        column("scf_eigenvalues_a", MsgpackExt),
        column("scf_eigenvalues_b", MsgpackExt),
        column("scf_occupations_a", MsgpackExt),
        column("scf_occupations_b", MsgpackExt),
        column("orbitals_a", sa.String),
        column("orbitals_b", sa.String),
        column("density_a", sa.String),
        column("density_b", sa.String),
        column("fock_a", sa.String),
        column("fock_b", sa.String),
        column("eigenvalues_a", sa.String),
        column("eigenvalues_b", sa.String),
        column("occupations_a", sa.String),
        column("occupations_b", sa.String),
    )

    conn = op.get_bind()
    session = Session(conn)

    old_wfns = session.query(old_wfn_table).yield_per(200)
    for old_wfn in old_wfns:
        wfn_dict = dict(
            basis=old_wfn.basis,
            restricted=old_wfn.restricted,
            h_core_a=old_wfn.h_core_a,
            h_core_b=old_wfn.h_core_b,
            h_effective_a=old_wfn.h_effective_a,
            h_effective_b=old_wfn.h_effective_b,
            scf_orbitals_a=old_wfn.scf_orbitals_a,
            scf_orbitals_b=old_wfn.scf_orbitals_b,
            scf_density_a=old_wfn.scf_density_a,
            scf_density_b=old_wfn.scf_density_b,
            scf_fock_a=old_wfn.scf_fock_a,
            scf_fock_b=old_wfn.scf_fock_b,
            scf_eigenvalues_a=old_wfn.scf_eigenvalues_a,
            scf_eigenvalues_b=old_wfn.scf_eigenvalues_b,
            scf_occupations_a=old_wfn.scf_occupations_a,
            scf_occupations_b=old_wfn.scf_occupations_b,
            orbitals_a=old_wfn.orbitals_a,
            orbitals_b=old_wfn.orbitals_b,
            density_a=old_wfn.density_a,
            density_b=old_wfn.density_b,
            fock_a=old_wfn.fock_a,
            fock_b=old_wfn.fock_b,
            eigenvalues_a=old_wfn.eigenvalues_a,
            eigenvalues_b=old_wfn.eigenvalues_b,
            occupations_a=old_wfn.occupations_a,
            occupations_b=old_wfn.occupations_b,
        )

        # prune None values
        wfn_dict = {k: v for k, v in wfn_dict.items() if v is not None}
        wfn_prop = WavefunctionProperties(**wfn_dict)

        wfn_compressed, ctype, clevel = compress(wfn_prop.dict(encoding="json"), CompressionEnum.zstd)

        r = conn.execute(
            sa.text(
                """UPDATE wavefunction_store SET
                     h_core_a=NULL,
                     h_core_b=NULL,
                     h_effective_a=NULL,
                     h_effective_b=NULL,
                     scf_orbitals_a=NULL,
                     scf_orbitals_b=NULL,
                     scf_density_a=NULL,
                     scf_density_b=NULL,
                     scf_fock_a=NULL,
                     scf_fock_b=NULL,
                     scf_eigenvalues_a=NULL,
                     scf_eigenvalues_b=NULL,
                     scf_occupations_a=NULL,
                     scf_occupations_b=NULL,
                     orbitals_a=NULL,
                     orbitals_b=NULL,
                     density_a=NULL,
                     density_b=NULL,
                     fock_a=NULL,
                     fock_b=NULL,
                     eigenvalues_a=NULL,
                     eigenvalues_b=NULL,
                     occupations_a=NULL,
                     occupations_b=NULL,
                     compression_type='zstd',
                     compression_level=:clevel,
                     data=:cdata
                   WHERE id = :id"""
            ),
            parameters={"cdata": wfn_compressed, "clevel": clevel, "id": old_wfn.id},
        )

    op.drop_column("wavefunction_store", "basis")
    op.drop_column("wavefunction_store", "restricted")
    op.drop_column("wavefunction_store", "h_core_a")
    op.drop_column("wavefunction_store", "h_core_b")
    op.drop_column("wavefunction_store", "h_effective_a")
    op.drop_column("wavefunction_store", "h_effective_b")
    op.drop_column("wavefunction_store", "scf_orbitals_a")
    op.drop_column("wavefunction_store", "scf_orbitals_b")
    op.drop_column("wavefunction_store", "scf_density_a")
    op.drop_column("wavefunction_store", "scf_density_b")
    op.drop_column("wavefunction_store", "scf_fock_a")
    op.drop_column("wavefunction_store", "scf_fock_b")
    op.drop_column("wavefunction_store", "scf_eigenvalues_a")
    op.drop_column("wavefunction_store", "scf_eigenvalues_b")
    op.drop_column("wavefunction_store", "scf_occupations_a")
    op.drop_column("wavefunction_store", "scf_occupations_b")
    op.drop_column("wavefunction_store", "orbitals_a")
    op.drop_column("wavefunction_store", "orbitals_b")
    op.drop_column("wavefunction_store", "density_a")
    op.drop_column("wavefunction_store", "density_b")
    op.drop_column("wavefunction_store", "fock_a")
    op.drop_column("wavefunction_store", "fock_b")
    op.drop_column("wavefunction_store", "eigenvalues_a")
    op.drop_column("wavefunction_store", "eigenvalues_b")
    op.drop_column("wavefunction_store", "occupations_a")
    op.drop_column("wavefunction_store", "occupations_b")

    op.alter_column("wavefunction_store", "compression_type", nullable=False)
    op.alter_column("wavefunction_store", "compression_level", nullable=False)
    op.alter_column("wavefunction_store", "data", nullable=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    raise RuntimeError("Cannot downgrade")
    # ### end Alembic commands ###
