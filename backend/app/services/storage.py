from pathlib import Path


def ensure_data_dir(path: str = "data") -> Path:
    data_dir = Path(path)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
