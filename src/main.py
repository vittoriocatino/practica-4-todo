"""To-do API with RDS persistence and CloudWatch observability."""
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, Integer, String, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from src.database import RuntimeDatabase
from src.telemetry import CloudWatchMetrics

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=200, pattern=r"\S")
    done: bool = False


class TaskOutput(TaskInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


def get_session(request_engine, metrics):
    """Dependency factory kept injectable for isolated unit tests."""
    def session_dependency():
        started = perf_counter()
        try:
            engine = request_engine()
            # Idempotent DDL also handles first boot while RDS is still becoming ready.
            Base.metadata.create_all(engine)
            with sessionmaker(bind=engine, expire_on_commit=False)() as session:
                yield session
        except Exception as exc:
            if isinstance(exc, HTTPException):
                raise
            metrics.emit("DatabaseErrors", 1)
            log.error("Database operation failed: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Database unavailable") from exc
        else:
            metrics.emit("DatabaseErrors", 0)
        finally:
            metrics.emit("DatabaseLatency", (perf_counter() - started) * 1000, "Milliseconds")
    return session_dependency


def create_app(engine_factory=None, metrics=None):
    db = RuntimeDatabase()
    sink = metrics if metrics is not None else CloudWatchMetrics()
    engine_factory = engine_factory or db.engine
    session_dep = get_session(engine_factory, sink)

    @asynccontextmanager
    async def lifespan(app):
        sink.start()
        yield
        sink.stop()

    api = FastAPI(title="Vittorio Catino - To-Do List", lifespan=lifespan)
    api.state.metrics = sink
    api.state.session_dependency = session_dep

    @api.get("/version")
    def version():
        return {"version": os.getenv("APP_VERSION", "dev")}

    @api.get("/tasks", response_model=list[TaskOutput])
    def tasks(session=Depends(session_dep)):
        return session.scalars(select(Task).order_by(Task.id)).all()

    @api.post("/tasks", response_model=TaskOutput, status_code=201)
    def create_task(payload: TaskInput, session=Depends(session_dep)):
        task = Task(title=payload.title.strip(), done=payload.done,
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None))
        session.add(task)
        session.commit()
        session.refresh(task)
        return task

    @api.get("/health")
    def health():
        started = perf_counter()
        status = "OK"
        try:
            with engine_factory().connect() as connection:
                connection.execute(text("SELECT 1"))
            sink.emit("DatabaseErrors", 0)
        except Exception as exc:
            status = "FAIL"
            sink.emit("DatabaseErrors", 1)
            log.error("Database health failed: %s", type(exc).__name__)
        finally:
            sink.emit("DatabaseLatency", (perf_counter() - started) * 1000, "Milliseconds")
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=200 if status == "OK" else 503, content={
            "database": status, "version": os.getenv("APP_VERSION", "dev"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return api


app = create_app()
