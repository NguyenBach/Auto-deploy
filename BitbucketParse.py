import json


class BitbucketParse:

    def __init__(self, config, header, rfile):
        self.config = config
        self.header = header
        self.rfile = rfile
        self.branch = ''
        self.name = ''
        self.owner = ''
        self.fullname = ''
        self.url = ''
        self.path = ''

    def parseRequest(self):
        length = int(self.header.getheader('content-length'))
        body = self.rfile.read(length)
        payload = json.loads(body)
        self.branch = payload['push']['changes'][0]['new']['name']
        self.name = payload['repository']['name']
        self.owner = payload['repository']['owner']['username']
        self.fullname = payload['repository']['full_name']
        self.url = payload['repository']['links']['html']['href']
        self.getLastCommit(payload)
        return self

    def getMatchingPaths(self):
        for repository in self.config['repositories']:
            if repository['url'] == self.url:
                self.path = repository['path']
            else:
                if self.fullname in repository['url']:
                    self.path = repository['path']
        return self
    def getLastCommit(self,payload):
        commits = payload['push']['changes'][0]['commits']
        self.lastCommitHash = commits[-1]['hash']