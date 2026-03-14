"""add posts calendar/external unique

Revision ID: a4f31f0e9c7b
Revises: e493e865595a
Create Date: 2026-03-14 00:00:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "a4f31f0e9c7b"
down_revision = "e493e865595a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("posts", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_posts_calendar_external",
            ["calendar_id", "external_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("posts", schema=None) as batch_op:
        batch_op.drop_constraint("uq_posts_calendar_external", type_="unique")
