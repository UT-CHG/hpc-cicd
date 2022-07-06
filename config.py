import json

with open("server_config.json") as fp:
    server_config = json.load(fp)

# TODO - see if there's a way to not hardcode this

base_job_config = {
  "name": "pyopatra-test",
  "appId": "pyopatra-0.0.1",
  "archive": False,
  "batchQueue": "skx-normal",
  "processorsPerNode": 32,
  "nodeCount": 1,
  "inputs": {},
  "parameters": {},
  "notifications": [
    {
        "event": "*",
        "persistent": True,
        "url": f"http://{server_config['ip']}:{server_config['webhook_port']}"
    }
  ]
}
