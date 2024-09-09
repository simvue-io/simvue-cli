"""
Server Metadata
===============

Functions which retrieve additional information on the Simvue
server not provided by the RestAPI
"""
__author__ = "Kristian Zarebski"
__date__ = "2024-09-09"

import socket
import urllib.parse as urllib_parser

from simvue.factory.proxy import Simvue

def get_ip_of_url(url: str) -> str:
    """Retrieves the IP address for the given URL as a string"""
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

