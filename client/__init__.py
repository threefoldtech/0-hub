import requests



from .client import Client as APIClient


class Client:
    def __init__(self, base_uri=""):
        self.api = APIClient(base_uri)
        