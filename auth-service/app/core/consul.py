import os
import consul

CONSUL_HOST = os.getenv("CONSUL_HOST", "consul")
CONSUL_PORT = int(os.getenv("CONSUL_PORT", "8500"))
SERVICE_HOST = os.getenv("SERVICE_HOST", "auth-service")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8001"))

consul_client = consul.Consul(
    host=CONSUL_HOST,
    port=CONSUL_PORT
)

def register_service():

    consul_client.agent.service.register(
        name="auth-service",
        service_id="auth-service-1",
        address=SERVICE_HOST,
        port=SERVICE_PORT
    )

    print("Auth Service registered with Consul")