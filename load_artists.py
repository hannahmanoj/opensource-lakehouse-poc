import csv
import trino

conn = trino.dbapi.connect(
    host="localhost",
    port=8080,
    user="poc-loader",
    catalog="iceberg",
    schema="demo",
)
cur = conn.cursor()

with open("artists.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cur.execute(
            """
            INSERT INTO artists (
              artist_name, sex, country_of_origin, primary_language,
              primary_genre, artist_type, debut_year,
              total_streams_millions, lead_streams_millions,
              feature_streams_millions, solo_streams_millions,
              pct_solo_streams, collab_streams_millions, pct_collab_streams
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row["Artist Name"],
                row["Sex"],
                row["Country of Origin"],
                row["Primary Language"],
                row["Primary Genre"],
                row[" Artist Type"],
                int(row["Debut Year"]),
                float(row["Total Streams (in millions)"]),
                float(row["Lead Streams (in millions)"]),
                float(row["Feature Streams (in millions)"]),
                float(row["Solo Streams (in millions)"]),
                float(row["% of Solo Streams"]),
                float(row["Collaborative Streams (in millions)"]),
                float(row["% of Collaborative Streams"]),
            ],
        )

print("Done loading artists.csv into iceberg.demo.artists")