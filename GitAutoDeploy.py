#!/usr/bin/env python

import json, urlparse, sys, os, signal
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from subprocess import call
from BitbucketParse import BitbucketParse


class GitAutoDeploy(BaseHTTPRequestHandler):
    CONFIG_FILEPATH = './GitAutoDeploy.conf.json'
    config = None
    quiet = False
    daemon = False

    @classmethod
    def getConfig(myClass):
        if myClass.config is None:
            try:
                configString = open(myClass.CONFIG_FILEPATH).read()
            except:
                sys.exit('Could not load ' + myClass.CONFIG_FILEPATH + ' file')

            try:
                myClass.config = json.loads(configString)
            except:
                sys.exit(myClass.CONFIG_FILEPATH + ' file is not valid json')

            for repository in myClass.config['repositories']:
                if (not os.path.isdir(repository['path'])):
                    sys.exit('Directory ' + repository['path'] + ' not found')
                # Check for a repository with a local or a remote GIT_WORK_DIR
                if not os.path.isdir(os.path.join(repository['path'], '.git')) \
                        and not os.path.isdir(os.path.join(repository['path'], 'objects')):
                    sys.exit('Directory ' + repository['path'] + ' is not a Git repository')

        return myClass.config

    def do_POST(self):
        config = self.getConfig()
        if self.getEvent(config) != 1:
            self.respond(304)
            return
        self.respond(204)
        if self.server == 'bitbucket':
            self.bitbucketRequest(config)
        repo = self.getRepository(self.fullname)
        if repo is None:
            print "Not found repository"
            return
        deployBranch = repo['deploy-branch']
        if self.branch == deployBranch:
            self.fetch(self.path)
            self.deploy(self.path)
            file = open(self.name + "_" + self.branch + ".txt", "w+")
            file.write(str(self.lastCommitHash))

    def do_GET(self):
        self.respond(200)
        self.wfile("hello")

    def getEvent(self):
        event = self.headers.getheader('X-Event-Key')
        if event is None:
            event = self.headers.getheader('X-GitHub-Event')
            self.server = 'github'
        else:
            self.server = 'bitbucket'
        if 'push' not in event:
            print('Not a push request')
            return 304
        else:
            return 1

    def getRepository(self, config, name):
        for repository in config['repositories']:
            if repository['full-name'] == name:
                return repository
            else:
                return None

    def bitbucketRequest(self, config):
        bitbucket = BitbucketParse(config, self.headers, self.rfile)
        bitbucket.parseRequest()
        bitbucket.getMatchingPaths()
        self.branch = bitbucket.branch
        self.name = bitbucket.name
        self.owner = bitbucket.owner
        self.fullname = bitbucket.fullname
        self.url = bitbucket.url
        self.path = bitbucket.path
        self.lastCommitHash = bitbucket.lastCommitHash

    def respond(self, code):
        self.send_response(code)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

    def fetch(self, path):
        if (not self.quiet):
            print "\nPost push request received"
            print 'Updating ' + path
        call(['cd "' + path + '" && git pull origin ' + self.branch], shell=True)
        print 'Completed'

    def deploy(self, path):
        config = self.getConfig()
        for repository in config['repositories']:
            if repository['path'] == path:
                if 'deploy' in repository:
                    branch = None
                    if 'deploy-branch' in repository:
                        branch = repository['deploy-branch']

                    if branch is None or branch == self.branch:
                        if not self.quiet:
                            print 'Executing deploy command'
                        call(['cd "' + path + '" && ' + repository['deploy']], shell=True)

                    elif not self.quiet:
                        print 'Push to different branch (%s != %s), not deploying' % (branch, self.branch)
                break

    def reset(self, path, name, branch):
        filename = name + "_" + branch + ".txt"
        file = open(filename, 'r')
        lastCommitHash = file.read()
        call(['cd "' + path + '" && git reset --hard ' + lastCommitHash], shell=True)


def main():
    try:
        server = None
        for arg in sys.argv:
            if (arg == '-d' or arg == '--daemon-mode'):
                GitAutoDeploy.daemon = True
                GitAutoDeploy.quiet = True
            if (arg == '-q' or arg == '--quiet'):
                GitAutoDeploy.quiet = True
            if (arg == '-s' or arg == '--stop'):
                file = open("pid.txt", "r")
                pid = file.read()
                if (not pid.isdigit()):
                    return
                else:
                    os.kill(int(pid), signal.SIGKILL)
                    print 'Stop Auto deploy'
                    return
        if (GitAutoDeploy.daemon):
            file = open("pid.txt", "w+")
            pid = os.fork()
            if (pid != 0):
                file.write(str(pid))
                sys.exit()
            os.setsid()

        if (not GitAutoDeploy.quiet):
            print 'Github Autodeploy Service  started'
        else:
            print 'Github Autodeploy Service started in daemon mode'

        server = HTTPServer(('', GitAutoDeploy.getConfig()['port']), GitAutoDeploy)
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit) as e:
        if (e):  # wtf, why is this creating a new line?
            print >> sys.stderr, e

        if (not server is None):
            server.socket.close()

        if (not GitAutoDeploy.quiet):
            print 'Goodbye'


if __name__ == '__main__':
    main()
