from xml.dom import minidom
import xml.etree.ElementTree as ET
import requests

# GLOBALS
TIMEOUT = 3

# HELPERS
def xml_prettyprint(root):
    return minidom.parseString(ET.tostring(root)).toprettyxml(indent="\t")

class Bucket:
    """
    PURPOSE: Provide an OOP structure to reference s3 buckets
    INPUT: Name of bucket
    DOCS:
    |__[ATTR] NAME
    |_____ Name of the bucket
    |__[ATTR] STATUS
    |_____ -1: Rate limit was hit and bucket was not assessed
    |_____  0: Bucket does not exist
    |_____  1: Bucket exists but access is denied
    |_____  2: Bucket exists, but all access is disabled
    |_____  3: Bucket exists and is listable
    |_____  4: Bucket exists and is readable
    |_____  5: Bucket exists and is writeable
    |_____  NOTE: Currently, the results aggregate all of the statuses, so one bucket will
    |_____        count for multiple values when being listed (except for the totals). In
    |_____        the context of the Hunter object, the status is the highest recorded level
    |_____        of access achieved.
    |__[ATTR] CONTENT
    |_____ A newline separated list of [NUM,MODIFIED,OWNER,SIZE,FILENAME] retrieved from the bucket.
    |__[ATTR] DOWNLOAD
    |_____ Boolean: True - the first file was downloadable
    |__[ATTR] WRITE
    |_____ Boolean: True - the bucket was writeable
    |_____ NOTE: This has not yet been implemented as we are attempting to find a way to reliably
    |_____       determine write capability without actually writing.
    """

    name = ""
    status = 0
    content = ""
    download = False
    write = False
    meta = ""
    headers = {
        "User-Agent":"Palebail v0.2.0"
    }
    def __init__(self,name,badchars):
        #TODO: make this a list instead of string, enumerating possible names based on
        # the original name
        self.name = name.lower()
        for elem in badchars:
            self.name = self.name.replace(elem,"") #TODO replace with more than just empty string (same TODO as above)

        self.url = "https://{}.s3.amazonaws.com/".format(self.name)
    
    def checkRateLimit(self):
        r = requests.get(self.url+"?location",timeout=TIMEOUT,headers=self.headers)
        return True if ET.fromstring(r.text)[0].text != "NoSuchBucket" else False

    def retrieveData(self,seshObj=False,params=""):
        r = requests.get(self.url+params,headers=self.headers,timeout=TIMEOUT)
        return ET.fromstring(r.text) if not seshObj else r

    def isReadable(self,testURL):
        """
        PURPOSE: Test to see if FIRST object of a bucket is downloadable
        INPUT: Bucket object, URL for testing downloadablity
        RETURN: True if contents can be downloaded / read
        """
        r = requests.get(testURL,timeout=TIMEOUT,headers=self.headers)
        if "AccessDenied" not in r.text and "NoSuchKey" not in r.text:
            return True
        else:
            return False
            self.status = 4

    def isWriteable(self,retryURL=None):
        """
        PURPOSE: Test to see if a bucket can be written to
        INPUT: bucket object
        RETURN: Boolean: True - it can be written to
        """
        endpoint = retryURL if retryURL else self.url
        r = requests.put(
            endpoint+"chonk.txt",
            headers={"Content-Type":"text/plain"},
            data="""
           .: BEWARE OF CHONKERS :.
            There are many chonkers
            on the interwebs. They
            are out to eat all the
            little innocent mice.
            Don't be a mouse! Close
            your S3 bucket so it's
            not world-writeable :)
                     /\_/\\
                    ( o.o )
                     > ^ <
            """,
            timeout=TIMEOUT,
        )
        if "TemporaryRedirect" in r.text:
            root = ET.fromstring(r.text)
            retryURL = root[2].text # redirect endpoint url
            if self.isWriteable(retryURL):
                return True
        elif r.status_code == 200:
            return True
        else:
            return False

    def assignState(self):
        xmlroot = self.retrieveData()
        if "Error" in xmlroot.tag:
            error = xmlroot[0].text
            if error == "NoSuchBucket":
                if self.checkRateLimit():
                    self.status = -1
                else:
                    self.status = 0                  

            elif error == "AccessDenied":
                self.status = 1

            elif error == "AllAccessDisabled":
                self.status = 2
            
            return False

        else:
            self.status = 3
            return True

    def enumContent(self):
        """
        PURPOSE: List and assign content to a bucket object
        INPUT: Bucket object
        RETURN: URL to test for readability
        """
        r = self.retrieveData(True)
        root = ET.fromstring(r.text)
        linefmt = "\t{}\t{}\t{}\t\t{}\t{}\n"
        files = ""
        counter = 1
        testfileURL = ""
        default = self.url
        
        for child in root:
            if child.tag.split("}")[1].lower() == "contents":
                filename = child[0].text
                if testfileURL == "":
                    testfileURL = self.url+filename if filename != "" else default
                modified = child[1].text
                try:
                    owner = child[5][1].text
                except:
                    owner = ""
                size = child[3].text
                files += linefmt.format(counter,modified,owner,size,filename)
                counter += 1

        self.content = (files if files.strip() != "\n" else None)
        testfileURL = default if testfileURL == "" else testfileURL
        return testfileURL

    def get_acl(self):
        xmlroot = self.retrieveData(params="?acl")
        return None if "Error" in xmlroot.tag else xml_prettyprint(xmlroot)

    def get_accelerate(self):
        xmlroot = self.retrieveData(params="?accelerate")
        return None if "Error" in xmlroot.tag else xml_prettyprint(xmlroot)

    def get_cors(self):
        xmlroot = self.retrieveData(params="?cors")
        return None if "Error" in xmlroot.tag else xml_prettyprint(xmlroot)

    def get_encryption(self):
        xmlroot = self.retrieveData(params="?encryption")
        return None if "Error" in xmlroot.tag else xml_prettyprint(xmlroot)

    def get_location(self):
        xmlroot = self.retrieveData(params="?location")
        return None if "Error" in xmlroot.tag else xml_prettyprint(xmlroot)

    def get_logging(self):
        xmlroot = self.retrieveData(params="?logging")
        return None if "Error" in xmlroot.tag else xml_prettyprint(xmlroot)

    def get_policy(self):
        xmlroot = self.retrieveData(params="?policy")
        return None if "Error" in xmlroot.tag else xml_prettyprint(xmlroot)

    def get_replication(self):
        xmlroot = self.retrieveData(params="?replication")
        return None if "Error" in xmlroot.tag else xml_prettyprint(xmlroot)

    def get_website(self):
        xmlroot = self.retrieveData(params="?website")
        return None if "Error" in xmlroot.tag else xml_prettyprint(xmlroot)

    def metadata(self):
        content = {
            "acl":self.get_acl(),
            "accelerate":self.get_accelerate(),
            "cors":self.get_cors(),
            "encryption":self.get_encryption(),
            "location":self.get_location(),
            "logging":self.get_logging(),
            "policy":self.get_policy(),
            "replication":self.get_replication(),
            "website":self.get_website()
        }
        output = ""
        output += "[+] ACL\n{}".format(content['acl']) if content['acl'] else ""
        output += "[+] Accelerate\n{}".format(content['accelerate']) if content['accelerate'] else ""
        output += "[+] CORS\n{}".format(content['cors']) if content['cors'] else ""
        output += "[+] Encryption\n{}".format(content['encryption']) if content['encryption'] else ""
        output += "[+] Location\n{}".format(content['location']) if content['location'] else ""
        output += "[+] Logging\n{}".format(content['logging']) if content['logging'] else ""
        output += "[+] Policy\n{}".format(content['policy']) if content['policy'] else ""
        output += "[+] Replication\n{}".format(content['replication']) if content['replication'] else ""
        output += "[+] Website\n{}".format(content['website']) if content['website'] else ""

        return output