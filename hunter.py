from bucket import Bucket
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

class Hunter:
    # PURPOSE: Provide object to wrap logic surrounding the requests for the hunt
    # INPUT: Modifiers wordlist (postfix), keyword or keyfile (prefix)

    def __init__(self,modifiers,keyword="",keyfile=None,threads="1",logger=None):
        # using self.logger in case there is a bug with using global logger
        self.logger = logger
        self.COMBINATORS = []
        self.BADCHARS = []
        self.THREADMAX = 20

        # begin session
        self.session = requests.session()

        #Open indicated files
        try:
            with open(modifiers, "r") as modsFile:
                self.bucket_names = [line.strip() for line in modsFile]
        except FileNotFoundError:
            self.logger.log("HUNTER","ERRO","Modifiers wordlist {} not found.".format(modifiers))
            raise FileNotFoundError

        if keyfile:
            try:
                with open(keyfile, "r") as keyFile:
                    self.keywords = [line.strip() for line in keyFile]
            except FileNotFoundError:
                self.logger.log("HUNTER","ERRO","Keyfile {} not found.".format(keyfile))
                raise FileNotFoundError
        else:
            self.keywords = [keyword]

        self.metadata = {
            "total":0,
            "denied":0,
            "disabled":0,
            "open_list":0,
            "open_read":0,
            "open_write":0,
            "rate_limits":0,
            "nonexist":0,
            "failed_hit":0
        }

        #Determine number of threads
        try:
            self.threads = int(threads)
            if self.threads <= 0 or self.threads > self.THREADMAX:
                raise ValueError
        except ValueError:
            self.logger.log("HUNTER","ERRO","Thread number {} is not an integer between 1 and {}".format(threads,self.THREADMAX))
            self.logger.log("HUNTER","WARN","Running single-threaded")
            self.threads = 1

        self.buckets = {}
        self.processes = []        

    def rotateIP(self):
        # PURPOSE: Amazon rate-limits the requests to S3 by IP, so it must be rotated
        # INPUT: None
        # RETURN: None

        # TODO implement IP rotation
        self.logger.log("HUNTER","WARN","rotateIP() not yet implemented!")
        pass


    def doRateLimitAvoid(self,lastBucket):
        # PURPOSE: Avoid rate limiting from Amazon
        # INPUT: bucket objcet
        # RETURN: Boolean

        self.rotateIP()
        # TODO retry same bucket name
        lastBucket.status = -1
        self.metadata['rate_limits'] += 1
        self.metadata['failed_hit'] += 1
        self.logger.log("HUNTER","WARN","{} Rate limit hit".format(lastBucket.name))
        return False


    def getBucketState(self,bucket):
        # PURPOSE: Assign one of the statuses to a bucket object based on response
        # INPUT: Bucket object
        # RETURN: True - open or exists, more work to be done; False - DNE. No more work.
        try:
            bucket.assignState()
        except requests.exceptions.ConnectionError:
            self.logger.log("HUNTER","WARN", "{} Connection Error".format(bucket.name))
        self.metadata['total'] += 1
        if bucket.status == 0:
            self.metadata['nonexist'] += 1
            self.metadata['failed_hit'] += 1
        elif bucket.status == 1:
            self.metadata['denied'] += 1
            self.metadata['failed_hit'] += 1
        elif bucket.status == 2:
            self.metadata['disabled'] += 1
            self.metadata['failed_hit'] += 1
        elif bucket.status == 3:
            self.logger.log("HUNTER","INFO","{} is open, URL: {}".format(bucket.name,bucket.url))
            self.metadata['open_list'] += 1
            return True # catch for status 3
        return False # catch for status -1,0,1,2

    def parseBucket(self,cur_name):
        # PURPOSE: provide request parsing functionality
        # INPUT: Self, Bucket Name
        # RETURN: None

        # init Bucket object
        bucket = Bucket(cur_name,self.BADCHARS)

        # assign state of bucket and associated objects
        if self.getBucketState(bucket):
            # list the content, get a valid URL to test
            self.logger.log("HUNTER","INFO","Listing {}".format(bucket.name))
            testURL = bucket.listContent()
            self.logger.log("HUNTER","INFO","\n{}".format(bucket.content))
            # then, see if the contents are readable
            if bucket.isReadable(testURL):
                bucket.status = 4
                self.metadata['open_read'] += 1
                # if so, mark for download
                bucket.download = True
            # finally, check to see if it is writeable
            if bucket.isWriteable():
                bucket.status = 5
                self.metadata['open_write'] += 1
                bucket.write = True
        
        # NOT THREADSAFE
        # if the rate limit is hit, conduct avoidance
        elif bucket.status == -1:
            if not self.doRateLimitAvoid(bucket):
                return self.metadata['total']

        # store the bucket data in memory
        if bucket.status > 0: # if the bucket exists
            self.buckets[bucket.name] = bucket
            replies = ["non-existent","denied","disabled","open","readable","writeable"]
            self.logger.log(
                "HUNTER",
                "INFO",
                "Bucket {} is {}".format(bucket.name,replies[bucket.status])
            )
            meta = bucket.metadata()
            if meta:
                self.logger.log(
                    "HUNTER",
                    "INFO",
                    "Metadata...\n{}".format(meta)
                )

    def hunt(self):
        # PURPOSE: provide threading
        # INPUT: Self
        # RETURN: Number of attempts
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            for k in self.keywords:
                for name in self.bucket_names:
                    for char in self.COMBINATORS:
                        # format bucket name attempt
                        cur_name = "{}{}{}".format(k, char, name)
                        self.processes.append(executor.submit(self.parseBucket,cur_name))

        return self.metadata['total']
    

    def status(self):
        # log hunt meta results
        self.logger.log("HUNTER","STAT","Hunt complete.")
        self.logger.log("HUNTER","INFO","\nResults:\n\tTotal tries: {}\n\tPercent Valid: {}%\n\tDenied: {}\n\tDisabled: {}\n\tListable: {}\n\tDownloadable: {}\n\tWriteable: {}\n\tRate limits hit: {}\n".format(
            self.metadata['total'],
            "{:.2f}".format(100*(1 - (self.metadata['failed_hit']/self.metadata['total']))),
            self.metadata['denied'],
            self.metadata['disabled'],
            self.metadata['open_list'],
            self.metadata['open_read'],
            self.metadata['open_write'],
            self.metadata['rate_limits']
        ))
        self.logger.log("HUNTER","INFO","Downloadable buckets:{}\n".format("".join(
            {("\n\t"+name if self.buckets[name].download else "") for name in self.buckets.keys()}
        )))
        self.logger.log("HUNTER","INFO","Writeable buckets:{}\n".format("".join(
            {("\n\t"+name if self.buckets[name].write else "") for name in self.buckets.keys()}
        )))
        return 0
