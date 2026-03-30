from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Oracle connection
    oracle_host: str = "oracle-db"
    oracle_port: int = 1521
    oracle_service: str = "FREEPDB1"
    oracle_user: str = "demo"
    oracle_password: str = "DemoPass1"
    oracle_system_password: str = "OraclePass1"
    oracle_pool_min: int = 2
    oracle_pool_max: int = 10
    oracle_pool_increment: int = 1

    # OpenTelemetry
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"
    otel_service_name: str = "oracle-otel-showcase"
    otel_service_version: str = "1.0.0"

    # Workload
    workload_interval_seconds: float = 2.0
    vector_dimensions: int = 1536
    vector_count_seed: int = 100

    # Report
    prometheus_url: str = "http://prometheus:9090"
    tempo_url: str = "http://tempo:3200"
    report_output_dir: str = "/reports"
    report_lookback_minutes: int = 30


settings = Settings()
