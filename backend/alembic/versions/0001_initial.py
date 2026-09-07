revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    from alembic import op
    from app.core.database import Base
    from app.models import models  # noqa: F401
    Base.metadata.create_all(bind=op.get_bind())
def downgrade():
    from alembic import op
    from app.core.database import Base
    from app.models import models  # noqa: F401
    Base.metadata.drop_all(bind=op.get_bind())

