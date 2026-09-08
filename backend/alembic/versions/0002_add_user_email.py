"""Add the optional, unique email login identifier to existing users."""

revision = '0002_add_user_email'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    from alembic import op
    from sqlalchemy import Column, String, inspect

    bind = op.get_bind()
    columns = {column['name'] for column in inspect(bind).get_columns('users')}
    if 'email' not in columns:
        op.add_column('users', Column('email', String(length=254), nullable=True))
    indexes = {index['name'] for index in inspect(bind).get_indexes('users')}
    if 'ix_users_email' not in indexes:
        op.create_index('ix_users_email', 'users', ['email'], unique=True)


def downgrade():
    # SQLite cannot safely drop a column in place. Leave it intact rather than
    # risking user data in a development downgrade.
    pass
