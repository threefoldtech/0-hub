class RepositoriesService:
    def __init__(self, client):
        self.client = client



    def repositories_get(self, headers=None, query_params=None, content_type="application/json"):
        """
        List all repositories (users) found
        It is method for GET /repositories
        """
        uri = self.client.base_url + "/repositories"
        return self.client.get(uri, None, headers, query_params, content_type)
