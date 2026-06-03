import os
import consul

CONSUL_HOST = os.getenv("CONSUL_HOST", "consul")
CONSUL_PORT = int(os.getenv("CONSUL_PORT", "8500"))
SERVICE_HOST = os.getenv("SERVICE_HOST", "leave-service")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8003"))

consul_client = consul.Consul(
    host=CONSUL_HOST,
    port=CONSUL_PORT
)


def register_service():

    consul_client.agent.service.register(
        name="leave-service",
        service_id="leave-service-1",
        address=SERVICE_HOST,
        port=SERVICE_PORT
    )

    print("Leave Service registered with Consul")