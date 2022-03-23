# Galileo Client

This repo contains code that invokes the galileo shell to start experiments.

Environment variables
=====================

The following table shows all environment variables to be set.
For ease of use a `.env` is included which includes all variables (under `bin/.env`).

| Variable                       | Default               | Description                                                                                        |
|--------------------------------|-----------------------|----------------------------------------------------------------------------------------------------|
| galileo_expdb_driver           | mixed                 | Uses a SQL database to store experiment metadata and InfluxDB to store runtime data (i.e., traces) | 
| galileo_logging_level          | DEBUG                 | Logger level (DEBUG, INFO, WARN, ERROR)                                                            | 
| galileo_expdb_mysql_host       | localhost             | MySQL host                                                                                         |
| galileo_expdb_mysql_port       | 3307                  | MySQL port                                                                                         |
| galileo_expdb_mysql_db         | db                    | MySQL database                                                                                     |
| galileo_expdb_mysql_user       | user                  | MySQL user                                                                                         |
| galileo_expdb_mysql_password   | password              | MySQL password                                                                                     |
| galileo_expdb_influxdb_url     | http://localhost:8086 | InfluxDB url                                                                                       |
| galileo_expdb_influxdb_token   | auth-token            | InfluxDB authentication token                                                                      |
| galileo_expdb_influxdb_timeout | 10000                 | InfluxDB timeout in ms                                                                             |
| galileo_expdb_influxdb_org     | org                   | InfluxDB organization name                                                                         |
| galileo_expdb_influxdb_org_id  | org-id                | InfluxDB organization ID                                                                           |
| galileo_redis_host             | localhost             | Redis host                                                                                         |
| galileo_redis_password         | **optional**          | Redis port                                                                                         |
| KUBECONFIG                     | **not set**           | Path to the kubeconfig                                                                             |