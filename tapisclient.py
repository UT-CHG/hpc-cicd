import requests
import json
import time
import os

"""
A custom API client for the TAPIS v2 api.

The tapis-cli package offers incomplete coverage of the API endpoints, and is cumbersome to use
for scripting. Consequently, we have to deal directly with the API.
"""

base_url = "https://api.tacc.utexas.edu/"

class TapisClient:

    REQ_FIELDS = ["username", "password", "clientName", "storage_system"]

    OPT_FIELDS = ["api_key", "api_secret"]

    CACHEDIR = os.getenv("HOME") + "/.tapisclient"

    def __init__(self, configfile):
        """Initialize the client
        """

        self.configfile = configfile
        with open(configfile, "r") as fp:
            config = d = json.load(fp)
            # TACC username and password must be specified
            for k in self.REQ_FIELDS:
                if k not in d:
                    raise ValueError(f"Configfile {configfile} missing required field '{k}'!")

                setattr(self, k, d[k])

            for k in self.OPT_FIELDS:
                 setattr(self, k, d.get(k, None))

        if self.api_key is None:
            # get api token
            res = requests.post(base_url+"/clients/v2",
                {'clientName': 'pyopatra-test-runner'},
                auth = (self.username, self.password))
            print(res.json())
            res = res.json()['result']
            print(res)
            self.api_key, self.api_secret = res["consumerKey"], res["consumerSecret"]
            self.save_config()

        self.init_tokens()

    def save_config(self):
        with open(self.configfile, "w") as fp:
            config = {k: getattr(self, k) for k in self.REQ_FIELDS+self.OPT_FIELDS}
            json.dump(config, fp)

    def init_tokens(self):
        # Try to initialize from a cache
        if self._init_tokens_from_cache():
            return

        if self.refresh_token is None:
            self.get_new_tokens()
            return

        res = requests.post(base_url+"/token",{
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
            "scope": "PRODUCTION"
            },
            auth=(self.api_key, self.api_secret)
        )

        res = res.json()
        print(res)
        if res.get("error") == "invalid_grant":
            self.get_new_tokens()
            return

        self.access_token, self.refresh_token = res["access_token"], res["refresh_token"]
        self._save_tokens(self.refresh_token, self.access_token, res["expires_in"])

    def get_new_tokens(self):

        res = requests.post(base_url+"/token", {
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
            "scope": "PRODUCTION"
            },
            auth=(self.api_key, self.api_secret)
        )

        res = res.json()
        self.access_token, self.refresh_token = res["access_token"], res["refresh_token"]
        self._save_tokens(self.refresh_token, self.access_token, res["expires_in"])

    def get_cache_fname(self):
        return self.CACHEDIR+"/"+self.api_key+"-tokens.json"

    def _init_tokens_from_cache(self):
        fname = self.get_cache_fname()
        if os.path.exists(fname):
            with open(fname, "r") as fp: tokens = json.load(fp)
            self.refresh_token = tokens["refresh"]
            if tokens["expiration_timestamp"] > int(time.time()):
                self.access_token = tokens["access"]
                return True
        else:
            self.refresh_token = None

        return False

    def _save_tokens(self, refresh, access, expires_in):
        # take off a minute so that we refresh a little before the token expires
        expiration_timestamp = int(time.time()) + expires_in - 60

        if not os.path.exists(self.CACHEDIR): os.mkdir(self.CACHEDIR)
        with open(self.get_cache_fname(), "w") as fp:
            json.dump({
                "access": access,
                "refresh": refresh,
                "expiration_timestamp": expiration_timestamp},
            fp)

    def submit_job(self, config):
        res = requests.post(base_url+'jobs/v2', json=config,
            headers=self._get_json_headers())

        return res.json()

    def mkdir(self, dirname):
        """Make a directory on a storage system
        """

        res = requests.put(base_url+f'files/v2/media/system/{self.storage_system}',
            headers=self._get_json_headers(),
            json = {'action': 'mkdir', 'path': dirname} )

        return self.check_for_error(res)

    def upload(self, local_path, remote_path):

        res = requests.post(base_url+f'files/v2/media/system/{self.storage_system}/{remote_path}',
            headers=self._get_auth_header(),
            files={'fileToUpload': open(local_path, 'rb')}
            )

        return self.check_for_error(res)

    def check_for_error(self, res):
        res = res.json()
        if res.get('status') == 'error':
            raise Exception("Error in API result ", res)
        return res

    def _get_auth_header(self):
        return {
            "Authorization": "Bearer " + self.access_token        
        }

    def _get_json_headers(self):
        return {
            'Content-type':'application/json', 
            'Accept':'application/json',
            **self._get_auth_header()
        }

if __name__ == "__main__":

    c = TapisClient(configfile="tapisconfig.json")
