import os
import requests
import time
from pathlib import Path
from datetime import datetime as dtg

class Logger:
    # PURPOSE: Provide an easy-to-use format for logging capabilities
    # INPUT: Verbosity level, path for logfile
    # DOCS:
    # |__[ATTR] LEVELS
    # |_____ INFO: any general information the user should be aware of
    # |_____ STAT: status of a specific process
    # |_____ WARN: non critical errors that allow for continued execution
    # |_____ ERRO: critical errors that halt execution
    # |_____ DEBUG: messages to assist with debugging
    # |
    # |__[ATTR] VERBOSITY: {
    # |         0:no logging, 
    # |         1:log to file only,
    # |         2:log STAT, WARN, and ERRO to stdout... log all to file,
    # |         3:log all to stdout and file,
    # |         4:log only to stdout, but log everything (if fileoutput breaks)
    # |      }
    # |
    # |__[ATTR] LOGFILE: logged to ./logs/<epoch_time>.log as plaintext, newline separated
    # |
    # |__[FUNC] logToFile
    # |__[FUNC] logToSTDOUT 

    def __init__(self,verbosity=2,logpath=None):
        self.loglevels = ["INFO","STAT","WARN","ERRO","DEBUG"]
        self.verbosity = verbosity % 4
        self.logpath = logpath


    def initLogFile(self,newLogPath=None):
        # PURPOSE: Creates the log file
        # INPUT: (optional) path to log file
        # RETURN: None

        #ensure the logpath is set
        if not self.logpath:
            self.logpath = Path("logs","{}.log".format(int(time.time())))
        elif newLogPath:
            self.logpath = newLogPath

        # double check logs dir exists
        try:
            os.mkdir(Path("logs"))
        except FileExistsError:
            pass
        except Exception as e:
            self.logToSTDOUT("LOGGER","WARN","Failed to initialize logdir, continuing with ONLY stdout.{}".format(e))
            pass
        try:
            self.logfile = open(self.logpath,'w')
            self.logfile.write("Palebail log for run at {}\n".format(int(time.time())))
            self.logfile.close()
        except:
            self.logToSTDOUT("LOGGER","WARN","Failed to initialize logfile, continuing with ONLY stdout.")
            pass


    def logToFile(self,source,level,message):
        # PURPOSE: Log message to logfile
        # INPUT: Source of message, level of message, message itself
        # RETURN: True - it successfully logged to file. False - did not log to file.

        try:
            self.logfile = open(self.logpath,'a')
        except:
            self.logToSTDOUT("LOGGER","WARN","Failed to open logfile, continuing with ONLY stdout.")
            self.verbosity = 4
            return False

        try:
            self.logfile.write("[{}] {} -- {} -- {}\n".format(source,dtg.now().strftime("%Y-%m-%d %H:%M:%S"),level,message))
            return True
        except FileNotFoundError:
            self.logToSTDOUT("LOGGER","WARN","Log file no longer exists... logging will continue ONLY in stdout.")
            pass
        except:
            self.logToSTDOUT("LOGGER","WARN","Logger experienced crit fail, proceeding on stdout")
            pass
                 
        self.logfile.close()
        self.verbosity = 4
        return False


    def logToSTDOUT(self,source,level,message):
        # PURPOSE: Log message to STDOUT
        # INPUT: source and level of message, as well as the message itself
        # RETURN: None

        print("[{}] {} -- {} -- {}".format(source,dtg.now().strftime("%Y-%m-%d %H:%M:%S"),level,message))


    def log(self,source,level,message):
        # PURPOSE: Provide top-level logic for logging
        # INPUT: Source and level of message, as well as the message itself
        # RETURN: None

        if level not in self.loglevels:
            level = "INFO"

        # Verb 0
        if self.verbosity == 0:
            pass

        # Verb 1
        elif self.verbosity == 1:
            if not self.logToFile(source,level,message):
                # log to file fails, verbosity now at 4
                self.log(source,level,message)
        # Verb 2
        elif self.verbosity == 2:
            if not self.logToFile(source,level,message):
                # log to file fails, verbosity now at 4
                self.log(source,level,message)
            elif level in ["STAT","WARN","ERRO"]:
                self.logToSTDOUT(source,level,message)
        
        # Verb 3
        elif self.verbosity == 3:
            if not self.logToFile(source,level,message):
                # log to file fails, verbosity now at 4
                self.log(source,level,message)
            self.logToSTDOUT(source,level,message)

        # Verb 4
        elif self.verbosity == 4:
            self.logToSTDOUT(source,level,message)
        
        # Verb Unknown
        else:
            self.logToSTDOUT("LOGGER","WARN","Invalid verbosity level, defaulting to 2")
            self.verbosity = 2
            self.log(source,level,message)


    def cleanup(self):
        # PURPOSE: perform cleanup for logger
        # INPUT: Self
        # RETURN: None

        if self.verbosity in [1,2,3]: #log levels which include writing to file
            try:
                self.logfile.close()
            except:
                self.logToSTDOUT("LOGGER","WARN","Unable to close logfile")