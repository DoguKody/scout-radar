from airflow.decorators import dag, task
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from datetime import datetime

@dag(
    dag_id="manual_ingestion_test_20250502",
    schedule_interval=None,
    start_date=datetime(2025, 5, 3),
    catchup=False,
    tags=["test", "manual_ingest"],
)
def manual_ingest_test():

    @task()
    def read_manual_csv():
        hook = GCSHook(gcp_conn_id="google_cloud_default")
        bucket = "scoutradar-manual"
        object_name = "TEST-Manual Pipeline Input_20250502.csv"

        raw_bytes = hook.download(bucket_name=bucket, object_name=object_name)
        raw_text = raw_bytes.decode("utf-8")
        row_count = max(0, raw_text.count("\n") - 1)
        print(f"✅ Read {row_count} data rows from GCS://{bucket}/{object_name}")
        return raw_text

    # trigger the task inside the DAG
    raw_csv = read_manual_csv()


manual_ingestion_test_dag = manual_ingest_test()