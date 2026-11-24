# Deploying CarSense to AWS

This Terraform configuration runs the production Docker image on **ECS Fargate** behind an **Application Load Balancer** in the default VPC.

## What it creates

| Resource | Purpose |
|---|---|
| ECR repository | Stores the image. Scans on push and keeps the 10 most recent images. |
| ECS cluster, task definition and service | 1 vCPU / 2 GB tasks with Container Insights. The deployment circuit breaker rolls back failed releases. |
| Application Load Balancer | Public HTTP on port 80, health-checked on `/health`. Only the load balancer can reach the containers. |
| Autoscaling | Target tracking at 60% CPU, from `min_tasks` (default 1) to `max_tasks` (default 4). |
| CloudWatch log group | Container logs, kept for 14 days. |
| Secrets Manager | `OPENAI_API_KEY` and `DATABASE_URL`, injected at runtime and never written into the task definition. |
| RDS PostgreSQL *(optional)* | `enable_postgres = true` creates an encrypted `db.t4g.micro` catalog reachable only from the service. |

The default region is `me-central-1` (UAE).

## Capacity

A single Gunicorn worker sustained about **48 requests/s with no errors** in the [load test](../../loadtest/results.json), roughly **4 million requests per day**. One task therefore covers typical traffic many times over, and autoscaling adds tasks when CPU rises.

## Deploy

Prerequisites: Terraform 1.6+, the AWS CLI configured for your account, and Docker.

```bash
cd infra/aws
cp terraform.tfvars.example terraform.tfvars      # adjust region, scaling, Postgres
terraform init
terraform apply -target=aws_ecr_repository.app     # 1. create the registry first

# 2. push the first image
REPO=$(terraform output -raw ecr_repository_url)
aws ecr get-login-password | docker login --username AWS --password-stdin "${REPO%%/*}"
docker build -t "$REPO:latest" ../..
docker push "$REPO:latest"

terraform apply                                     # 3. create everything else
terraform output url                                # the public URL
```

If `enable_postgres = true`, load the catalog once from a machine that can reach the database (for example an ECS Exec session):

```bash
DATABASE_URL=... python scripts/postgres_uploader.py
```

## Continuous deployment

[`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml) is started manually from the Actions tab. It builds the image, pushes it to ECR tagged with the commit SHA, registers a new task definition and waits for the service to become stable. It needs:

- repository secret `AWS_DEPLOY_ROLE_ARN`: an IAM role that trusts GitHub's OIDC provider for this repository and can push to ECR and update the ECS service;
- repository variable `AWS_REGION`.

## Tear down

```bash
terraform destroy
```

The load balancer, Fargate tasks and (if enabled) RDS instance are billed while they exist.
