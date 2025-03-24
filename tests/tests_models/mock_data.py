"""Python file to store the mocke responses for testing"""
# Since error response will be a string and it won't be parsed in json so this error will come.
MOCK_ERROR_CRT_SVC = {"error": "string indices must be integers"} # since func only read json

# This response will come from configMap
MOCK_CRITICAL_SERVICES_RESPONSE = {
   "coredns": {
        "namespace": "kube-system",
        "type": "Deployment"
   },
   "kube-proxy": {
       "namespace": "kube-system",
       "type": "DaemonSet"
   }
}

# Sample file to update in config map(though the test case won't update the config map)
MOCK_CRITICAL_SERVICES_UPDATE_FILE = """{
   "critical-services": {
      "xyz": {
         "namespace": "abc",
         "type": "Deployment"
      },
      "kube-proxy": {
         "namespace": "kube-system",
         "type": "DaemonSet"
      }
   }
}"""

# Mock file to test existing services in the configmap
MOCK_ALREADY_EXISTING_FILE = """{
   "critical-services": {
      "kube-proxy": {
         "namespace": "kube-system",
         "type": "DaemonSet"
      }
   }
}"""

# Mock Kubernetes response
MOCK_K8S_RESPONSE = {
    "x3002":{
       "masters":[
          {
             "name":"ncn-m003",
             "status":"Ready"
          }
       ],
       "workers":[
          {
             "name":"ncn-w003",
             "status":"Ready"
          }
       ]
    }
 }

# Mock Ceph response
MOCK_CEPH_RESPONSE = {
    "x3002":[
       {
          "name":"ncn-s005",
          "status":"Ready",
          "osds": [{"name": "osd.0", "status": "down"}, {"name": "osd.5", "status": "down"}]
       }
    ]
 }

# Mock error response
MOCK_ERROR_RESPONSE = {"error": "Failed to fetch data"}
