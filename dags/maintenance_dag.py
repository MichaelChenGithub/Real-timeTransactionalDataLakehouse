from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'data_engineer',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'lakehouse_hourly_maintenance',
    default_args=default_args,
    description='Hourly Compaction for Iceberg',
    schedule_interval='@hourly',
    start_date=datetime(2026, 1, 30),
    catchup=False,
    tags=['lakehouse'],
) as dag:

    compact_cmd = """
    docker exec lakehouse-spark spark-submit \
    /home/iceberg/local/src/maintenance/compact_cold_data.py
    """

    run_compaction = BashOperator(
        task_id='run_spark_compaction',
        bash_command=compact_cmd
    )