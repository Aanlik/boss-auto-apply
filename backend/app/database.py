from sqlmodel import SQLModel, create_engine

engine = create_engine("sqlite:///./boss_workbench.db")


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
