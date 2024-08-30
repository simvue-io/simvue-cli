import socket
import urllib.parse as urllib_parser

def get_ip_of_url(url: str) -> str:
    try:
        # Extract the hostname from the URL if necessary
        hostname = urllib_parser.urlparse(url).hostname

        if not hostname:
            raise RuntimeError

        # Get the IP address of the hostname
        ip_address = socket.gethostbyname(hostname)
        return ip_address
    except (socket.gaierror, RuntimeError):
        return "Unknown IP"

