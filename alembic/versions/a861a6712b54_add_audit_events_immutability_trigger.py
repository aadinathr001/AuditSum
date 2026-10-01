"""add audit_events immutability trigger

Revision ID: a861a6712b54
Revises: 87d5012388b3
Create Date: 2026-09-30 23:45:48.292105

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a861a6712b54'
down_revision: Union[str, Sequence[str], None] = '87d5012388b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION audit_events_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'audit_events is append-only (% blocked)', TG_OP;
        END $$;
    """)
    op.execute("""
        CREATE TRIGGER audit_no_update_delete
          BEFORE UPDATE OR DELETE ON audit_events
          FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_no_update_delete ON audit_events;")
    op.execute("DROP FUNCTION IF EXISTS audit_events_immutable();")