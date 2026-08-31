FROM docker:27-cli AS docker_cli

FROM apache/airflow:2.9.3

USER root
COPY --from=docker_cli /usr/local/bin/docker /usr/local/bin/docker
USER airflow
