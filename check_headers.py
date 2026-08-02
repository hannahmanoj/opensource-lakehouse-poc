import csv

with open("artists.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    print(reader.fieldnames)