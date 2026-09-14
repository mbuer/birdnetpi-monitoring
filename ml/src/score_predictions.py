import os

import psycopg


def get_connection():
    return psycopg.connect(
        host=os.environ.get("BIRDNET_DB_HOST", "127.0.0.1"),
        dbname=os.environ.get("BIRDNET_DB_NAME", "birdnet"),
        user=os.environ.get("BIRDNET_DB_USER", "birdnet"),
        password=os.environ["BIRDNET_DB_PASSWORD"],
    )


def score_predictions():
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE bird_activity_predictions AS p
                SET
                    actual_activity = h.activity_index,
                    absolute_error = ABS(
                        p.predicted_activity - h.activity_index
                    ),
                    scored_at = NOW()
                FROM bird_activity_hourly AS h
                WHERE
                    p.predicted_hour = h.hour_local
                    AND p.actual_activity IS NULL
                RETURNING
                    p.id,
                    p.predicted_hour,
                    p.model,
                    p.predicted_activity,
                    p.actual_activity,
                    p.absolute_error;
                """
            )

            rows = cur.fetchall()

        conn.commit()

        return rows

    finally:
        conn.close()


if __name__ == "__main__":
    rows = score_predictions()

    if not rows:
        print("No predictions ready to score.")
    else:
        print()
        print("Scored predictions")
        print("==================")
        print()

        for row in rows:
            (
                prediction_id,
                predicted_hour,
                model,
                predicted_activity,
                actual_activity,
                absolute_error,
            ) = row

            print(f"Prediction ID:    {prediction_id}")
            print(f"Hour:             {predicted_hour}")
            print(f"Model:            {model}")
            print(f"Predicted:        {predicted_activity:.1f}")
            print(f"Actual:           {actual_activity:.1f}")
            print(f"Absolute error:   {absolute_error:.1f}")
            print()
