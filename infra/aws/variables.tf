variable "region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "me-central-1" # UAE
}

variable "image_tag" {
  description = "Tag of the image in ECR to run (the deploy workflow passes the git commit SHA)"
  type        = string
  default     = "latest"
}

variable "container_port" {
  description = "Port Gunicorn listens on inside the container"
  type        = number
  default     = 5000
}

variable "task_cpu" {
  description = "Fargate CPU units per task (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "Fargate memory per task in MiB (the embedding model needs about 1 GB)"
  type        = number
  default     = 2048
}

variable "min_tasks" {
  description = "Minimum running tasks"
  type        = number
  default     = 1
}

variable "max_tasks" {
  description = "Maximum tasks the CPU autoscaler may add"
  type        = number
  default     = 4
}

variable "openai_api_key" {
  description = "Optional OpenAI key for LLM query extraction; stored in Secrets Manager. Leave empty for rules-only parsing."
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_model" {
  description = "OpenAI model used when a key is configured"
  type        = string
  default     = "gpt-4o-mini"
}

variable "enable_postgres" {
  description = "Create an RDS PostgreSQL catalog and pass DATABASE_URL to the service"
  type        = bool
  default     = false
}
