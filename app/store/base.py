# A hacky workaround to name forgein keys.
#
# Using `TableBase` is prefered over `sqlmodel.SQLModel` to explicitly avoid
# forgetting to specify the naming conventions.
#
# Related issue on the SQLModel repository:
# https://github.com/fastapi/sqlmodel/issues/85

from sqlalchemy import MetaData
from sqlmodel import SQLModel

# Let SQLAlchemy generate constraint names to support downgrading forgeign keys
# Also see: https://alembic.sqlalchemy.org/en/latest/naming.html
SQLModel.metadata.naming_convention = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
).naming_convention

TableBase = SQLModel
