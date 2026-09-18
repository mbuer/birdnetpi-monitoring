import os

import psycopg


MODEL_SUFFIX = "_species_v1"


def connect():
    return psycopg.connect(
        host=os.environ.get("BIRDNET_DB_HOST", "127.0.0.1"),
        dbname=os.environ.get("BIRDNET_DB_NAME", "birdnet"),
        user=os.environ.get("BIRDNET_DB_USER", "birdnet"),
        password=os.environ["BIRDNET_DB_PASSWORD"],
    )


def score_species_predictions():
    conn = connect()

    query = """
    WITH ready AS (
        SELECT
            p.id,
            s.present AS actual_present
        FROM bird_species_predictions p
        JOIN bird_species_hourly s
          ON s.station_id = p.station_id
         AND s.species = p.species
         AND s.hour_local = p.predicted_hour
        WHERE p.actual_present IS NULL

          -- Match the explicit species-model suffix without relying on
          -- SQL LIKE wildcards for underscores.
          AND RIGHT(p.model, LENGTH(%s)) = %s

          -- The forecast must have existed before the target hour began.
          -- This prevents late/manual rows from being scored as genuine
          -- forward predictions.
          AND p.prediction_created_at <
              (
                  p.predicted_hour
                  AT TIME ZONE 'America/Los_Angeles'
              )

          -- Target hour must be completely finished, plus the same
          -- ten-minute ingestion grace used by the prediction cycle.
          AND NOW() >= (
              p.predicted_hour
              + interval '1 hour 10 minutes'
          ) AT TIME ZONE 'America/Los_Angeles'
    )
    UPDATE bird_species_predictions p
    SET
        actual_present = ready.actual_present,
        correct = (
            p.predicted_present = ready.actual_present
        ),
        scored_at = NOW()
    FROM ready
    WHERE p.id = ready.id
    RETURNING
        p.species,
        p.predicted_hour,
        p.model,
        p.predicted_present,
        p.actual_present,
        p.correct;
    """

    try:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (MODEL_SUFFIX, MODEL_SUFFIX),
            )
            rows = cur.fetchall()

        conn.commit()
        return rows

    finally:
        conn.close()


def main():
    rows = score_species_predictions()

    if not rows:
        print("No species predictions ready to score.")
        return

    print()
    print("Scored species predictions")
    print("==========================")
    print()

    for row in rows:
        species = row[0]
        predicted_hour = row[1]
        model = row[2]
        predicted = row[3]
        actual = row[4]
        correct = row[5]

        print(
            f"{species:<18} "
            f"{predicted_hour} "
            f"{model:<32} "
            f"pred={predicted} "
            f"actual={actual} "
            f"correct={correct}"
        )


if __name__ == "__main__":
    main()
