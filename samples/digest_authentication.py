from webpie import WPApp, WPHandler                       
import time, secrets

import re, hashlib, base64, time

def digest_client(url, username, password):
    from requests.auth import HTTPDigestAuth
    response = requests.get(url, auth=HTTPDigestAuth(username, password))
    return response.status_code, response.content
    
def digest_password(realm, user, password):
    combined = (user + ":" + realm + ":" + password).encode("utf-8")
    return hashlib.md5(combined).hexdigest()

def digest_server(realm, env, get_password):
    #
    # Server side authentication function
    # env is WSGI evironment
    # get_password is a function: password = get_password(realm, username)
    # 

    def md5sum(data):
        from hashlib import md5
        m = md5()
        if isinstance(data, str):
            data = data.encode("utf-8")
        m.update(data)
        return m.hexdigest()

    auth_header = env.get("HTTP_AUTHORIZATION","")
    #print "auth_header:", auth_header
    matches = re.compile('Digest \s+ (.*)', re.I + re.X).match(auth_header)
    
    if not matches:
        # need "Authorization" header
        #nonce = base64.b64encode(str(int(time.time())).encode("utf-8")).decode("utf-8")
        nonce = secrets.token_urlsafe()
        header = 'Digest realm="%s", nonce="%s", algorithm=MD5, qop="auth"' % (realm, nonce)
        return False, header        
    
    
    vals = re.compile(', \s*', re.I + re.X).split(matches.group(1))

    dict = {}

    pat = re.compile('(\S+?) \s* = \s* ("?) (.*) \\2', re.X)
    for val in vals:
        ms = pat.match(val)
        if ms:
            dict[ms.group(1)] = ms.group(3)

    user = dict['username']
    truth_digest = get_password(realm, user)        # as hex
    if truth_digest == None:
        # unknown user
        return False, None

    #a1 = md5sum('%s:%s:%s' % (user, realm, cfg_password))        
    a2 = md5sum('%s:%s' % (env['REQUEST_METHOD'], dict["uri"]))
    myresp = md5sum('%s:%s:%s:%s:%s:%s' % (truth_digest, dict['nonce'], dict['nc'], dict['cnonce'], dict['qop'], a2))
    if myresp == dict['response']:
        # success
        return True, user
    else:
        # password did not match
	    #print "signature mismatch"
        return False, None

class Handler(WPHandler):
    
    Realm = "realm"
    Password = "hello"
    
    def get_digest(self, realm, user):
        return digest_password(realm, user, self.Password)        
    
    def auth(self, request, relpath, **args):

        if request.method.upper() == "OPTIONS":
            return 204, "", {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET",
                "Access-Control-Allow-Headers": "WWW-Authenticate,Authorization,Access-Control-Allow-Origin",
                "Access-Control-Expose-Headers": "WWW-Authenticate,Content-Length",
                "Access-Control-Max-Age": "1728000"
            }

        authenticated, response = digest_server(self.Realm, request.environ, self.get_digest)
        if authenticated:
            return "OK", { "Access-Control-Allow-Origin": "*"}
        elif response:
            return 401, "", {"WWW-Authenticate": response, 
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET",
                "Access-Control-Allow-Headers": "WWW-Authenticate,Authorization",
                "Access-Control-Expose-Headers": "WWW-Authenticate,Content-Length",
                "Access-Control-Max-Age": "1728000",

            }
        else:
            return 403, "Authentication failed"

WPApp(Handler).run_server(8443, logging=True, debug=True)        
