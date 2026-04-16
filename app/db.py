from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def ensure_runtime_schema() -> None:
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "reservations" not in table_names:
        return

    reservation_columns = {column["name"] for column in inspector.get_columns("reservations")}
    statements: list[tuple[str, str]] = []

    if "cancel_token" not in reservation_columns:
        statements.append((
            "reservation_cancel_token",
            "ALTER TABLE reservations ADD COLUMN cancel_token VARCHAR(80) DEFAULT '' NOT NULL",
        ))
    if "cancellation_reason" not in reservation_columns:
        statements.append((
            "reservation_cancellation_reason",
            "ALTER TABLE reservations ADD COLUMN cancellation_reason VARCHAR(120) DEFAULT '' NOT NULL",
        ))
    if "cancellation_message" not in reservation_columns:
        statements.append((
            "reservation_cancellation_message",
            "ALTER TABLE reservations ADD COLUMN cancellation_message VARCHAR(1000) DEFAULT '' NOT NULL",
        ))
    if "cancelled_at_utc" not in reservation_columns:
        statements.append((
            "reservation_cancelled_at_utc",
            "ALTER TABLE reservations ADD COLUMN cancelled_at_utc TIMESTAMP NULL",
        ))
    if "google_event_id" not in reservation_columns:
        statements.append((
            "reservation_google_event_id",
            "ALTER TABLE reservations ADD COLUMN google_event_id VARCHAR(190) DEFAULT '' NOT NULL",
        ))
    if "google_event_calendar_id" not in reservation_columns:
        statements.append((
            "reservation_google_event_calendar_id",
            "ALTER TABLE reservations ADD COLUMN google_event_calendar_id VARCHAR(190) DEFAULT '' NOT NULL",
        ))

    if len(statements) == 0:
        return

    with engine.begin() as connection:
        for _, statement in statements:
            connection.execute(text(statement))

    inspector = inspect(engine)
    reservation_indexes = {index["name"] for index in inspector.get_indexes("reservations")}
    with engine.begin() as connection:
        if "ix_reservations_cancel_token" not in reservation_indexes:
            connection.execute(text("CREATE INDEX ix_reservations_cancel_token ON reservations (cancel_token)"))
        if "ix_reservations_cancelled_at_utc" not in reservation_indexes:
            connection.execute(text("CREATE INDEX ix_reservations_cancelled_at_utc ON reservations (cancelled_at_utc)"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
