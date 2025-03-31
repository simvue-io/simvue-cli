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


def get_ip_of_url(url: str) -> str:
    """Retrieves the IP address for the given URL as a string"""
    try:
        if hostname := urllib_parser.urlparse(url).hostname:
            return socket.gethostbyname(hostname)
        else:
            raise RuntimeError

    except (socket.gaierror, RuntimeError):
        return "Unknown IP"
