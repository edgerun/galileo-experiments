# Galileo Experiments

This repository contains code that invokes the galileo shell to start experiments.
It also includes deployment files for necessary components and describes in detail which other services are 
required to start an experiment.
Further, this project aims to unify different sub-projects of `edgerun` and make deployment and experiment setup easy.
The main goals and functionalities are:

* A framework for distributed load testing experiments
* Fine-grained telemetry data collection
* HTTP Trace recording for any service
* A container orchestration adaption for ease of use

## Who is this project for?

For everyone that wants to see resource usage and application performance with easy configurable workload creation.
All components are tailored and suited to run on low performance devices (i.e., Raspberry Pi) but can run on default server VMs too.

Common questions that can be answered by performing and analyzing Galileo experiments:

* How much CPU usage does my application use?
* What is the average execution time of my application across the cluster?
* What are the differences in terms of resource usage between two nodes hosting the same application?
* What is the impact of having multiple applications running on one node?

All these questions can be easily answered and have a simple flow in common:
1. Deploy base infrastructure
2. Deploy my application
3. Start requests
4. Analyze in Jupyter Notebooks

In summary: simple profiling tasks.
But, this framework also targets full end-to-end tests to evaluate important cluster components (i.e, load balancer, scheduler and scaling).

Therefore, experiments can be done to evaluate new implementations for  the aforementioned components.


# High level overview



# Kubernetes cluster setup

![Cluster components](figures/cluster.drawio.png)

## Overview

### Main components
The cluster setup consists of the following main components:

* Kubernetes
* Galileo (for clients and experiment shell)
* Telemd
* Controller (i.e., the load balancer)
* MySQL (i.e., MariaDB)
* InfluxDB v2
* Etcd (Kubernetes requires an instance to run!)

Kubernetes is used to host the clients (galileo running in a Pod), telemetry agents (telemd), load balancer and the applications to test.
Redis is used as a pub/sub system through which all data is sent (i.e., telemetry) and recorded by the Galileo Shell (i.e., the program that prepares and executes an experiment).
The Galileo Shell persists data in MariaDB and InfluxDB.
The provided load balancer implementation uses etcd to watch for weights for the round-robin algorithm and galileo uses redis to provide the clients with routing rules (`rtbl`).



## Main interactions

The figure above depicts all components and also highlights important interactions.
Those interactions are in short:
* Client nodes send HTTP requests to the Controller (load balancer), which forwards requests to the worker nodes which host the application pods.
* Client nodes report the results of each request (i.e., trace) via Redis. 
* The Go-based load balancer implementation fetches weights and ip addresses from the etcd instance.
* The clients get the routing rules from the Redis instance (set via `rtbl` from Galileo)
* Worker nodes report resource usage (i.e., telemd) via Redis, which is saved in InfluxDB
* The Galileo Shell starts the experiments and saves metadata (i.e., the cluster hosts, misc. data) in the MariaDB


## Deployment 

This project provides deployment files for the following components:
* Galileo (for clients and experiment shell)
* Telemd
* Controller (i.e., the load balancer)

Which leaves the following components to be additionally deployed:

* Kubernetes
* MySQL (i.e., MariaDB)
* InfluxDB v2
* Etcd (Kubernetes requires an instance to run!)

Deployment files can be found in `deployment/kubernetes`.
Note, that we use Kubernetes node labels to schedule the workers (i.e., clients).
On nodes that should act as clients execute the following command:

    kubectl label node <node> node-role.kubernetes.io/client=true

The following label is used to identify nodes with hosting capabilities (i.e., workers):

    kubectl label node <node> node-role.kubernetes.io/worker=true

If you have multiple zones (i.e., clusters) in which you want to have seperate clients, adapt the `zone`  arguments (default is `main`).
You can easily group your nodes by labelling it with the following command:

    kubectl label node <node> ether.edgerun.io/zone=main

Further, `telemd` also offers support to monitor GPUs.
Therefore, you have to label your nodes accordingly:

    kubectl label node <node> telemd.edgerun.io/mode=[cpu|gpu]

See more information for GPU monitoring in the [GPU support branch](https://github.com/edgerun/telemd/tree/gpu-support). 

## Galileo Workers

The galileo workers run on each client node and is connected via Redis to receive commands and also the routing rules.
Routing rules are simple key-value pairs, whereas the key represents your service name and the value is a list of hosts 
with the respective weight.

You can easily set these in your program via `rtbl.set('service', ['127.0.0.1:8080], [1])`.


# Data storage

Galileo requires the following data components that are either deployed in the cluster or externally:

* Redis (pub/sub for telemetry and traces)
* MySQL (i.e., MariaDB) (persistent storage for experiment metadata)
* InfluxDB v2 (stores runtime data - telemetry and traces)

All connection parameters are set via environment variables.

# Extensions

The [extension repository](https://github.com/edgerun/galileo-experiments-extensions) is meant to provide examples  on how to implement and use the project to run experiments.
It will be continually updated and include new services.


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