output "url" {
  description = "Public URL of the load balancer"
  value       = "http://${aws_lb.app.dns_name}"
}

output "ecr_repository_url" {
  description = "Push images here; the deploy workflow does this automatically"
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster" {
  value = aws_ecs_cluster.app.name
}

output "ecs_service" {
  value = aws_ecs_service.app.name
}

output "database_endpoint" {
  description = "RDS endpoint when enable_postgres = true"
  value       = var.enable_postgres ? aws_db_instance.catalog[0].endpoint : null
}
