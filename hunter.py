from bucket import Bucket
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed, thread

class Hunter:
    """
    PURPOSE: Provide object to wrap logic surrounding the requests for the hunt
    INPUT: Modifiers wordlist (prefix,suffix), keyword or wordlist of keywords
    """
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
                self.modifiers = [line.strip() for line in modsFile]
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

        # Determine number of threads
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
        """
        PURPOSE: Amazon rate-limits the requests to S3 by IP, so it must be rotated
        INPUT: None
        RETURN: None
        """
        # TODO implement IP rotation
        self.logger.log("HUNTER","WARN","rotateIP() not yet implemented!")
        pass

    def doRateLimitAvoid(self,lastBucket):
        """
        PURPOSE: Avoid rate limiting from Amazon
        INPUT: bucket objcet
        RETURN: Boolean
        """
        self.rotateIP()
        # TODO retry same bucket name
        lastBucket.status = -1
        self.metadata['rate_limits'] += 1
        self.metadata['failed_hit'] += 1
        self.logger.log("HUNTER","WARN","{} Rate limit hit".format(lastBucket.name))
        return False

    def getBucketState(self,bucket):
        """
        PURPOSE: Assign one of the statuses to a bucket object based on response
        INPUT: Bucket object
        RETURN: True - open or exists, more work to be done; False - DNE. No more work.
        """
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
        """
        PURPOSE: provide threadsafe request parsing functionality
        INPUT: Self, Bucket Name
        RETURN: None
        """
        # init Bucket object
        bucket = Bucket(cur_name,self.BADCHARS)

        # assign state of bucket and associated objects
        if self.getBucketState(bucket):
            
            testURL = bucket.enumContent()
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
        
        # if the rate limit is hit, conduct avoidance
        elif bucket.status == -1:
            if not self.doRateLimitAvoid(bucket): # NOT THREADSAFE
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
            bucket.meta = bucket.metadata()

    def recordBucket(self,bucket):
        if bucket.status <= 2:
            return # bucket DNE or disabled / denied
        self.logger.log("HUNTER","INFO","######## Record for {} ########".format(bucket.name))
        if bucket.meta:
            self.logger.log(
                "HUNTER",
                "INFO",
                "Metadata for {}...\n{}".format(bucket.name,bucket.meta)
            )

        # list the content, get a valid URL to test
        self.logger.log("HUNTER","INFO","Listing {}".format(bucket.name))
        self.logger.log("HUNTER","INFO","\n{}".format(bucket.content))

        self.logger.log("HUNTER","INFO","######## End of Record ########")

    def nameGenerator(self,keyword):
        """
        PURPOSE: modify the keyword and generate new name candidates
        INPUT: keyword
        RETURN: list of candidates from keyword seed
        """
        formatted_names = []
        for name in self.modifiers:
            if name != "":
                for char in self.COMBINATORS:
                    # format as prefix and suffix with modifier
                    formatted_names.insert(0,"{}{}{}".format(keyword, char, name))
                    formatted_names.insert(0,"{}{}{}".format(name, char, keyword))
        return formatted_names

    def hunt(self):
        """
        PURPOSE: provide threading
        INPUT: Self
        RETURN: Number of attempts
        """
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            for k in self.keywords:
                # permutate the names based on the modifiers wordlist...
                fnames = self.nameGenerator(k)
                # ... then kick off a thread for each name.
                for fname in fnames:
                    self.processes.append(executor.submit(self.parseBucket,fname))
            # everything is submitted to futures immediately, so interrupt handling
            # is done here
            try:
                for future in as_completed(self.processes):
                    future.result()
            except KeyboardInterrupt:
                executor._threads.clear()
                thread._threads_queues.clear()
                raise

                    
        self.logger.log("HUNTER","STAT","Parsing complete, compiling data...")
        for name in self.buckets.keys():
            # writing to a file/stdout was not threadsafe
            self.recordBucket(self.buckets[name])
        return self.metadata['total']

    def status(self):
        # log hunt meta results
        total = self.metadata['total']
        try:
            valid = "{:.2f}".format(100*(1 - (
                (self.metadata['open_list']+self.metadata['open_read']+self.metadata['open_write']) / \
                (self.metadata['total'] - self.metadata['failed_hit'])
                ))
            )
        except ZeroDivisionError:
            valid = "{:.2f}".format(0)
        denied = self.metadata['denied']
        disabled = self.metadata['disabled']
        listable = self.metadata['open_list']
        downloadable = self.metadata['open_read']
        writeable = self.metadata['open_write']
        ratelimits = self.metadata['rate_limits']
        self.logger.log("HUNTER","STAT","Hunt complete.")
        self.logger.log("HUNTER","INFO",f"\nResults:\n" + \
            f"\tTotal tries: {total}\n" + \
            f"\tPercent Valid: {valid}%\n" + \
            f"\tDenied: {denied}\n" + \
            f"\tDisabled: {disabled}\n" + \
            f"\tListable: {listable}\n" + \
            f"\tDownloadable: {downloadable}\n" + \
            f"\tWriteable: {writeable}\n" + \
            f"\tRate limits hit: {ratelimits}\n"
        )
        self.logger.log("HUNTER","INFO","Downloadable buckets:{}\n".format("".join(
            {("\n\t"+name if self.buckets[name].download else "") for name in self.buckets.keys()}
        )))
        self.logger.log("HUNTER","INFO","Writeable buckets:{}\n".format("".join(
            {("\n\t"+name if self.buckets[name].write else "") for name in self.buckets.keys()}
        )))
        return 0
