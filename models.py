from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    create_engine,
    ForeignKey,
    DateTime,
    text
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP")
    )

    # Relationships
    allergies = relationship("Allergy", back_populates="user", cascade="all, delete-orphan")
    diets = relationship("Diet", back_populates="user", cascade="all, delete-orphan")
    ingredients = relationship("Ingredient", back_populates="user", cascade="all, delete-orphan")


class Allergy(Base):
    __tablename__ = "allergies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    allergy_name = Column(String(255), nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="allergies")

    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class Diet(Base):
    __tablename__ = "diets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    diet_name = Column(String(255), nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="diets")

    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class Ingredient(Base):
    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingredient_name = Column(String(255), nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="ingredients")

    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


engine = create_engine("sqlite:///db.sqlite3", echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    """
    Helper for obtaining a database session in other modules.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db():
    """
    Initialize the database (create tables if they don't exist).
    """
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    init_db()