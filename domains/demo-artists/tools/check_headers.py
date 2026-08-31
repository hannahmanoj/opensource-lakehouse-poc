import csv
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "data" / "artists.csv"

with source.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    print(reader.fieldnames)
