#!/usr/bin/env python3
#####################################
############ palebail.py ############
#####################################
# PURPOSE:
#   Provide an easy-to-use command line tool to enumerate S3 contents based on a
# keyword.
# 
# CAVEAT: 
#   This tool is not to be used for malicious purposes. Although open source, we do 
# not condone using this tool to intentionally harm innocent people or organizations
# in any way, shape, or form.

# IMPORTS
import sys, time, os
from argparse import ArgumentParser

from hunter import Hunter
from logger import Logger



# GLOBALS
SILENT = False
VERBOSE = False
# Configure combinators/joining characters
COMBINATORS = ["-","","_"]
# a little lesson in RFC-1738 and RFC-2396 via StackOverflow
# https://stackoverflow.com/questions/1547899/which-characters-make-a-url-invalid
control = [chr(x) for x in range(0,0x20)]
delims = ["<",">","#","%",'"']
unwise = ["{","}","|","\\","^","[","]","`"," "]
reserved = [";","/","?",":","@","&","=","+","$",",","."]
BADCHARS = control+delims+unwise+reserved


# MAIN
def main():
    global SILENT, VERBOSE, COMBINATORS, LOGGER

    #Configure argument parser
    parser = ArgumentParser()
    parser.add_argument("-m", "--modifiers", dest="modifiers",
        help="Modifiers wordlist for common bucket names",
        default="modifiers/default.txt",
        metavar="modifiers")
    parser.add_argument("-o", "--out", dest="out",
        help="Output file (default is <timestamp>.log in ./logs/",
        default="out.txt",
        metavar="out")
    parser.add_argument("-k", "--keyword", dest="keyword",
        help="""Keyword to base the search around""",
        default="",
        metavar="keyword")
    parser.add_argument("-w", "--wordlist", dest="wordlist",
        help="""List of keywords to enumerate""",
        default="",
        metavar="wordlist")
    parser.add_argument("-t", "--threads", dest="threads",
        help="""Number of threads to use""",
        default="1",
        metavar="threads")
    parser.add_argument("-s", "--silent", dest="silent",
        help="""Silent mode - only prints Found buckets""",
        action="store_true")
    parser.add_argument("-v", "--verbose", dest="verbose",
        help="""Verbose mode, log everything to stdout and logfile""",
        action="store_true")


    args = parser.parse_args()

    if (args.keyword == "" and args.wordlist == "") or len(sys.argv) == 1:
        print(
            "Palebail must be run with at least a keyword/wordlist (-k / -w)\n"+
            "Use -h or --help for help"
        )
        sys.exit(1)

    # set globals based on user input
    SILENT = args.silent
    VERBOSE = args.verbose

    # init log file
    if args.out:
        LOGGER.initLogFile(args.out) #PATH
    if VERBOSE:
        LOGGER.verbosity = 3
    LOGGER.log("PALEBAIL","STAT","Starting up Palebail")

    hunter = Hunter(args.modifiers,args.keyword,args.wordlist,args.threads,LOGGER)

    # Main sequence and exception handling
    try:
        hunter.logger = LOGGER
        hunter.COMBINATORS = COMBINATORS
        hunter.BADCHARS = BADCHARS
        hunter.hunt()
    except KeyboardInterrupt:
        LOGGER.log("PALEBAIL","ERRO","User interrupt")
    except Exception as e:
        LOGGER.log("PALEBAIL","ERRO",e)
    finally:
        hunter.status()
        LOGGER.log("PALEBAIL","STAT","Shutting down.")
        LOGGER.cleanup()
        return 0


if __name__ == "__main__":
    LOGGER = Logger()
    main()
