class FlistService:
    def __init__(self, client):
        self.client = client



    def flist_memerge_post(self, target, data, headers=None, query_params=None, content_type="application/json"):
        """
        Merge multiple flist together
        It is method for POST /flist/me/merge/{target}
        """
        uri = self.client.base_url + "/flist/me/merge/" + target
        return self.client.post(uri, data, headers, query_params, content_type)


    def flist_meupload_post(self, data, headers=None, query_params=None, content_type="application/json"):
        """
        Upload a .tar.gz file and insert it to the hub
        It is method for POST /flist/me/upload
        """
        uri = self.client.base_url + "/flist/me/upload"
        return self.client.post(uri, data, headers, query_params, content_type)


    def flist_meflistlinklinkname_get(self, flist, linkname, headers=None, query_params=None, content_type="application/json"):
        """
        Create a flist link (symlink) updatable
        It is method for GET /flist/me/{flist}/link/{linkname}
        """
        uri = self.client.base_url + "/flist/me/"+flist+"/link/"+linkname
        return self.client.get(uri, None, headers, query_params, content_type)


    def flist_meflistrenametarget_get(self, flist, target, headers=None, query_params=None, content_type="application/json"):
        """
        Rename one of your flist
        It is method for GET /flist/me/{flist}/rename/{target}
        """
        uri = self.client.base_url + "/flist/me/"+flist+"/rename/"+target
        return self.client.get(uri, None, headers, query_params, content_type)

    def flist_meflistpromote_get(self, srepo, sfile, dfile, headers=None, query_params=None, content_type="application/json"):
        """
        Promote one flist to your local repository
        It is method for GET /flist/me/promote/{sourcerepo}/{sourcefile}/{localtarget}
        """
        uri = self.client.base_url + "/flist/me/promote/" + srepo + "/" + sfile + "/" + dfile
        return self.client.get(uri, None, headers, query_params, content_type)

    def flist_meflist_delete(self, flist, headers=None, query_params=None, content_type="application/json"):
        """
        Delete one of your flist
        It is method for DELETE /flist/me/{flist}
        """
        uri = self.client.base_url + "/flist/me/"+flist
        return self.client.delete(uri, None, headers, query_params, content_type)


    def flist_meflist_get(self, flist, headers=None, query_params=None, content_type="application/json"):
        """
        See '/flist/{user}/{flist}' GET endpoint
        It is method for GET /flist/me/{flist}
        """
        uri = self.client.base_url + "/flist/me/"+flist
        return self.client.get(uri, None, headers, query_params, content_type)


    def flist_byUsernameflist_get(self, username, flist, headers=None, query_params=None, content_type="application/json"):
        """
        Get information about a specific flist
        It is method for GET /flist/{username}/{flist}
        """
        uri = self.client.base_url + "/flist/"+username+"/"+flist
        return self.client.get(uri, None, headers, query_params, content_type)


    def flist_byUsername_get(self, username, headers=None, query_params=None, content_type="application/json"):
        """
        Get available flist for a specific user
        It is method for GET /flist/{username}
        """
        uri = self.client.base_url + "/flist/"+username
        return self.client.get(uri, None, headers, query_params, content_type)


    def flist_get(self, headers=None, query_params=None, content_type="application/json"):
        """
        List all flist found, sorted alphabetically
        It is method for GET /flist
        """
        uri = self.client.base_url + "/flist"
        return self.client.get(uri, None, headers, query_params, content_type)
