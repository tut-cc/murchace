from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column
from sqlalchemy.schema import MetaData


class Base(MappedAsDataclass, DeclarativeBase):
    id: Mapped[int | None] = mapped_column(kw_only=True, default=None, primary_key=True)


# Let SQLAlchemy generate constraint names to support downgrading forgeign keys
# Also see: https://alembic.sqlalchemy.org/en/latest/naming.html
Base.metadata.naming_convention = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
).naming_convention
