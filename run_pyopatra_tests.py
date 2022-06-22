from tapisclient import TapisClient
from multiprocessing.connection import Listener
from fire import Fire
import os
import yaml
from datetime import datetime

"""
Entry script to run HPC tests via CI/CD
"""

# TODO - see if there's a way to not hardcode this

base_job_config = {
  "name": "pyopatra-test",
  "appId": "pyopatra-0.0.1",
  "archive": False,
  "batchQueue": "skx-normal", #if multiple jobs are needed, this will need to be switched to skx
  "processorsPerNode": 32,
  "nodeCount": 1,
  "inputs": {},
  "parameters": {},
  "notifications": [
    {
        "event": "*",
        "persistent": True,
        "url": "http://129.114.17.65:8000"
    }
  ]
}

class TestCase:
    DEFAULT_CONFIG = {
        "nodeCount": 1,
        "processorsPerNode": 32,
        "maxRunTime": "00:30:00"
    }
    
    def __init__(self, dirname):
        # There has to be a run.py file to count
        if not os.path.exists(dirname+"/run.py"):
            self.is_valid = False
            return

        config = None
        for ending in [".yml", ".yaml"]:
            path = dirname+"/config"+ending
            if os.path.exists(path):
                with open(path, "r") as fp:
                    config = yaml.load(fp)
                break

        self.name = os.path.basename(dirname)

        if config is None:
            print(f"Warning: Missing config file for test '{self.name}'! Using defaults.")
            config = self.DEFAULT_CONFIG

        self.is_valid = True
        self.config = config
        self.dirname = dirname
        self.remote_dir = None

    def make_zip_file(self):
        """Zip the test assets and return a path to the zipfile
        """

        path = self.dirname + "/testcase.zip"
        if os.path.exists(path): os.remove(path)
        os.system(f"cd {self.dirname} && zip -r testcase.zip *")
        self.zipfile = path
        return path

    def get_job_config(self, storage_system):
        # a shallow copy is ok here
        config = {**base_job_config}
        config.update(self.config)
        config["name"] = "pyopatra-test-"+self.name
        config["inputs"] = {"test_assets": f"agave://{storage_system}/{self.remote_dir}/testcase.zip"}
        print(config)
        return config

    def get_remote_dir(self):
        if self.remote_dir is None:
            self.remote_dir = f"tapis_job_assets/{self.name}-" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        return self.remote_dir 

def main(testsdir,
    tapisconfig="config.json",
    storage_system="bpachev.stampede2.storage" #TODO - don't hardcocde this
    ):
    # iterate over tests
    # currently each directory in the tests directory describes a single test
    tests = []
    for dirname in next(os.walk(testsdir))[1]:
        path = testsdir+"/"+dirname
        testcase = TestCase(path)
        if not testcase.is_valid:
            # not a valid testcase
            continue

        tests.append(testcase)

    print(f"Found {len(tests)} tests. Uploading assets. . .")

    t = TapisClient(tapisconfig)
    
    for test in tests:
        zipfile = test.make_zip_file()
        remote_dir = test.get_remote_dir()
        t.mkdir(remote_dir, storage_system)
        t.upload(zipfile, remote_dir, storage_system)
        # TODO - check for errors with the upload operations

    print("Uploaded test assets. Submitting jobs. . .")
    jobs = {}
    for test in tests:
        j = t.submit_job(test.get_job_config(storage_system))
        jobs[j['result']['id']] = j['result']

    print(f"Submitted {len(jobs)} jobs. Monitoring status. . .")
    # TODO - don't hardcode the port here
    listener = Listener(('localhost', 9001), authkey=b'speakfriendandenter')
    conn = listener.accept()
    completed = {}
    failed = {}
    while True:
        try:
            msg = conn.recv()
        except EOFError:
            conn.close()
            conn = listener.accept()
            continue

        print("Recieved status update: ", msg)
        if msg['status'] in ['FINISHED', 'FAILED', 'STOPPED']:
            job_id = msg['id']
            completed[job_id] = msg
            if msg['status'] in ['FAILED', 'STOPPED']:
                failed[job_id] = msg
            print(f"Job {job_id} completed.")

        if len(completed) == len(jobs):
            print("All jobs complete.")
            break

    if len(failed):
        raise RuntimeError("Jobs Failed!", failed)

if __name__ == "__main__":
    Fire(main, name="run-pyopatra-tests")
