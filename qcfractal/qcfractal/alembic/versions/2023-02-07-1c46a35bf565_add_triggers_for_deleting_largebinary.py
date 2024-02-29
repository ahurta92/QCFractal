"""add triggers for deleting largebinary

Revision ID: 1c46a35bf565
Revises: 63115797e6da
Create Date: 2023-02-07 12:09:40.908204

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1c46a35bf565"
down_revision = "63115797e6da"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute(
        sa.text(
            """
    CREATE OR REPLACE FUNCTION qca_service_subtask_delete_lb()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
    BEGIN
      DELETE FROM largebinary_store
      WHERE largebinary_store.id = OLD.function_kwargs_lb_id OR largebinary_store.id = OLD.results_lb_id;
      RETURN OLD;
    END
    $function$ ;
    """
        )
    )

    op.execute(
        sa.text(
            """
    CREATE OR REPLACE FUNCTION qca_task_queue_delete_lb()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
    BEGIN
      DELETE FROM largebinary_store WHERE largebinary_store.id = OLD.function_kwargs_lb_id;
      RETURN OLD;
    END
    $function$ ;
    """
        )
    )

    op.execute(
        sa.text(
            """
    CREATE TRIGGER qca_service_subtask_delete_lb_tr
    AFTER DELETE ON service_subtask_record
    FOR EACH ROW EXECUTE FUNCTION qca_service_subtask_delete_lb();
    """
        )
    )

    op.execute(
        sa.text(
            """
    CREATE TRIGGER qca_task_queue_delete_lb_tr
    AFTER DELETE ON task_queue
    FOR EACH ROW EXECUTE FUNCTION qca_task_queue_delete_lb();
    """
        )
    )

    op.execute(
        sa.text(
            """
    CREATE FUNCTION qca_largebinary_base_delete() RETURNS TRIGGER AS
    $_$
    BEGIN
      DELETE FROM largebinary_store WHERE largebinary_store.id = OLD.id;
      RETURN OLD;
    END
    $_$ LANGUAGE 'plpgsql';
    """
        )
    )

    # Delete orphan largebinary
    op.execute(
        sa.text(
            """
        WITH anon_1 AS
        (SELECT service_subtask_record.function_kwargs_lb_id AS ref_col FROM service_subtask_record UNION
         SELECT service_subtask_record.results_lb_id AS ref_col FROM service_subtask_record UNION
         SELECT task_queue.function_kwargs_lb_id AS ref_col FROM task_queue)
        DELETE FROM largebinary_store
        WHERE largebinary_store.id NOT IN (SELECT ref_col FROM anon_1 WHERE ref_col IS NOT NULL)
        """
        )
    )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    raise RuntimeError("CANNOT DOWNGRADE")
    # ### end Alembic commands ###
