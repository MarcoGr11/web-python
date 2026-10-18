import socket

# Inside a container this is the container ID, unique per replica.
HOSTNAME = socket.gethostname()


def served_by_middleware(get_response):
    """Tag every response with the replica that produced it (load-balancer demo)."""

    def middleware(request):
        response = get_response(request)
        response["X-Served-By"] = HOSTNAME
        return response

    return middleware
