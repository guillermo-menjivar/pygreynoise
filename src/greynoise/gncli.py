import csv
import json
import pydoc
import re
import time

import dict2xml
import requests

from greynoise.gnutils import GNUtils


class GNCli(object):
    banner = r"""
    _____________   ______________
     __  ____/__  | / /_  __ \__  /
     _  / __ __   |/ /_  / / /_  /
     / /_/ / _  /|  / / /_/ /_  /___
     \____/  /_/ |_/  \___\_\/_____/
    """

    # Will be loaded
    GREYNOISE_API_KEY = GNUtils.load_config()  # this is working

    # global variables #################################################################
    # For output
    contextFields = {
        "ip": "IP",
        "classification": "Classification",
        "first_seen": "First seen",
        "last_seen": "Last seen",
        "actor": "Actor",
        "tags": "Tags",
    }
    metadataFields = {
        "organization": "Organization",
        "rdns": "rDNS",
        "asn": "ASN",
        "tor": "Tor",
        "os": "OS",
        "category": "Category",
    }

    # constraints for inputre.
    flags = [
        "-f",
        "--file",
        "-o",
        "--output",
        "-q",
        "--query",
        "-t",
        "--type",
        "-v",
        "--verbose",
    ]
    flags_meta = ["-h", "--help"]
    formatTypes = ["txt", "csv", "xml", "json", "raw"]  # constraints for -o
    queryTypes = [
        "quick",
        "raw",
        "context",
        "multi",
        "bulk",
        "date",
        "actors",
    ]  # constraints for -t

    ####################################################################################

    # TODO: formatting.py - make functions, call the right one in each case Could even
    # call a text output handler function in formatting.py right from runQuery that then
    # passes control around amongst smaller functions - the stuff happening in these
    # logic branches could be functions.

    # TODO: refactor, individual functions? this is long... + name is inaccurate - not
    # all queries are IPs
    def txtIP(results, verboseOut):
        try:
            if "error" in results:
                print(" Error: %s" % results["error"])
            # quick scan fields
            elif "noise" in results:
                if results["noise"]:
                    print(" %s is classified as NOISE." % results["ip"])
                elif not results["noise"]:
                    print(" %s is classified as NOT NOISE." % results["ip"])
            # context/gnql fields - called for each result in the list when used with
            # multi-searches
            elif "seen" in results or "count" in results:
                if results["seen"] or ("count" in results and results["count"] > 0):
                    print(" " * 10 + "OVERVIEW:")
                    print(" " + "-" * 28)
                    for field in GNCli.contextFields:
                        print(" %s: %s" % (GNCli.contextFields[field], results[field]))
                    print()
                    print(" " * 10 + "METADATA:")
                    print(" " + "-" * 28)
                    # Complete location info is not always available, so concatenate
                    # whatever info there is.
                    if results["metadata"]["city"]:
                        city = "%s, " % results["metadata"]["city"]
                    else:
                        city = ""
                    if results["metadata"]["country"]:
                        country = results["metadata"]["country"]
                    else:
                        country = "Unknown Country"
                    if results["metadata"]["country_code"]:
                        country_code = " (%s)" % results["metadata"]["country_code"]
                    else:
                        country_code = ""
                    print(" Location: %s%s%s" % (city, country, country_code))
                    # the rest of the metadata can be looped thru
                    for field in GNCli.metadataFields:
                        try:
                            if results["metadata"][field]:
                                if field == "tor":  # the only non string..
                                    print("  Tor: %b" % results["metadata"][field])
                                elif results["metadata"][field]:
                                    print(
                                        " %s: %s"
                                        % (
                                            GNCli.metadataFields[field],
                                            results["metadata"][field],
                                        )
                                    )
                        except Exception:
                            continue
                    print()
                    print(" " * 10 + "RAW DATA:")
                    print(" " + "-" * 28)
                    if results["raw_data"]["scan"]:
                        if (len(results["raw_data"]["scan"]) < 20) or verboseOut:
                            for item in results["raw_data"]["scan"]:
                                try:
                                    print(
                                        " Port/Proto: %s/%s"
                                        % (item["port"], item["protocol"])
                                    )
                                except Exception:
                                    continue
                        else:
                            counter = 0
                            for item in results["raw_data"]["scan"]:
                                try:
                                    print(
                                        " Port/Proto: %s/%s"
                                        % (item["port"], item["protocol"])
                                    )
                                    counter += 1
                                    if counter == 20:
                                        break  # can make this nicer
                                except Exception:
                                    continue
                            print(
                                " Showing results 1 - 20 of %s. "
                                "Run again with -v for full output."
                                % len(results["raw_data"]["scan"])
                            )
                    if results["raw_data"]["web"]:
                        print()
                        print(" [Paths]")
                        if not results["raw_data"]["web"]["paths"]:
                            print(" None found.")
                        else:
                            if (
                                len(results["raw_data"]["web"]["paths"]) < 20
                            ) or verboseOut:
                                for path in results["raw_data"]["web"]["paths"]:
                                    try:
                                        print(" %s" % path)
                                    except Exception:
                                        continue
                            else:
                                for index in range(20):
                                    try:
                                        print(
                                            " %s"
                                            % results["raw_data"]["web"]["paths"][index]
                                        )
                                    except Exception:
                                        continue
                                print(
                                    " Showing results 1 - 20 of %s. "
                                    "Run again with -v for full output."
                                    % len(results["raw_data"]["web"]["paths"])
                                )
                    if results["raw_data"]["ja3"]:
                        print("[JA3]")
                        if not results["raw_data"]["ja3"]:
                            print("None found.")
                        else:
                            for i in results["raw_data"]["ja3"]:
                                try:
                                    print(
                                        " Port: %s Fingerprint: %s"
                                        % (i["port"], i["fingerprint"])
                                    )
                                except Exception:
                                    continue
                    print()
                else:
                    print(
                        "%s has not been seen in scans in the past 30 days."
                        % results["ip"]
                    )
        except Exception as e:
            print("Error converting output!")
            print(e)

    # -o txt
    def makeTxt(results, type, verboseOut):
        try:
            if type == "bulk" or type == "date":
                formatted = ""
                maxcount = 6  # IPs per line - TODO: allow user to set
                count = 0
                # Concatenate IPs into a string of readable columns, variable width
                for ip in results["noise_ips"]:
                    if count == 0:
                        # adds spacing to the left of the first IP printed on each line.
                        ip = "  " + ip
                    formatted = formatted + (ip + " " * (18 - len(ip)))
                    count += 1
                    if count == maxcount:
                        count = 0
                        formatted = formatted + "\n"
                # result is paginated
                return pydoc.pager(formatted)
            if type == "quick" or type == "context":
                GNCli.txtIP(results, verboseOut)
            if type == "raw" or not type:
                if "data" in results:
                    counter = 1
                    for entry in results["data"]:
                        heading = "result %i of %i" % (counter, len(results["data"]))
                        # total number of spaces needed for padding
                        spacing = 27 - len(heading)
                        # if odd number, extra space should go in front.
                        if (27 - len(heading)) % 2 != 0:
                            leading_spaces = int((spacing + 1) / 2)
                            trailing_spaces = leading_spaces - 1
                            heading = (
                                " " * (leading_spaces) + heading + " " * trailing_spaces
                            )
                        else:
                            heading = (
                                " " * int(spacing / 2)
                                + heading
                                + " " * int(spacing / 2)
                            )
                        # print title bar for each numbered result
                        # (doesnt work well in some environments)
                        print(
                            (
                                " ┌───────────────────────────┐\n"
                                " │%s│\n"
                                " └───────────────────────────┘"
                            )
                            % heading
                        )
                        print()
                        GNCli.txtIP(entry, verboseOut)
                        print()
                        print()
                        counter += 1
                else:
                    print(" No results found.")
        except Exception as e:
            print(" Error making text output!")
            print(e)

    # TODO: Clean up the lists and flatten within each cell.
    # Handling for other query types? Usage?
    def makeCSV(results, of, type):
        try:
            if type != "raw":
                print(" Output to .csv not available for this query type at this time.")
                exit()
            else:
                if "data" in results:
                    scanData = results["data"]
                else:
                    print(" No data to write.")
                    exit()
                scanCSV = open(of, "w")
                csvwriter = csv.writer(scanCSV)
                count = 0
                for o in scanData:
                    if count == 0:
                        header = o.keys()
                        csvwriter.writerow(header)
                        count += 1
                    csvwriter.writerow(o.values())
                scanCSV.close()
                print(" Output to file: %s" % of)
        except Exception as e:
            print(" Error converting to CSV!")
            print(e)

    ####################################################################################
    # Making requests
    # TODO: request.py

    # TODO: Request handler function that pares some of this insanity down

    # Handling for single-IP requests.
    # TODO: Name is inaccurate now - not all queries are IPs
    def singleIP(query, type):
        try:
            url = "https://research.api.greynoise.io/v2/"
            if type == "raw" or not type:
                r = requests.get(
                    url + "experimental/gnql",
                    params={"query": query},
                    headers={"key": GNCli.GREYNOISE_API_KEY},
                )
                return r.text.encode("utf-8")
            elif type == "quick" or type == "context":
                url += "noise/" + type + "/" + query
                r = requests.get(url, headers={"key": GNCli.GREYNOISE_API_KEY})
                r2 = json.loads(r.text)
                if "error" in r2:
                    if r2["error"] == "invalid ip":
                        print(" Please enter a valid IP address.")
                        return False
                    elif r2["error"] == "commonly spoofed ip":
                        print(" Provided IP address is commonly spoofed.")
                        return False
                    else:
                        print(" Error - %s" % r2["error"])
                        return False
                return r.text.encode("utf-8")
        except Exception as e:
            print(" Error making request for single IP!")
            print(e)

    # TODO: handling for file input... invalid/couldnt read, etc
    # TODO: log parser output directly as input for multi query.
    # Come back to this - endpoint busted
    def multiQuery(inputFile):
        try:
            if inputFile:
                ipList = GNUtils.listFile(inputFile)
                rr = {"ips": ipList}
                query = json.dumps(rr)
                r = requests.get(
                    "https://research.api.greynoise.io/v2/noise/multi/quick",
                    data=query,
                    headers={"key": GNCli.GREYNOISE_API_KEY},
                )
                return r.text.encode("utf-8")
            else:
                print("Invalid input file.")
                exit()
        except Exception as e:
            print(" Error making request!")
            print(e)

    def bulkQuery(date=False):
        rQuery = ""  # TODO: Where is rQuery coming from?
        try:
            if (
                date
            ):  # If there's an actual date given, run the date-specific bulk search
                # Restricts input to "real" dates
                matchDateFormat = re.fullmatch(
                    r"2\d{3}-((0[1-9])|(1[0-2]))-((0[1-9])|(1[0-9])|(2[0-9])|(3[0-1]))",
                    rQuery,
                )
                if not matchDateFormat:
                    print("Error: Query needs to be a date in YYYY-MM-DD format.")
                    exit()
                r = requests.get(
                    "https://research.api.greynoise.io/v2/noise/bulk/" + rQuery,
                    headers={"key": GNCli.GREYNOISE_API_KEY},
                )
            else:  # today
                r = requests.get(
                    "https://research.api.greynoise.io/v2/noise/bulk",
                    headers={"key": GNCli.GREYNOISE_API_KEY},
                )
            # enables access to fields
            r2 = json.loads(r.content.decode("utf-8"))
            # If there are no responses, and the end is reached, the log is empty
            if "noise_ips" not in r2 and "complete" in r2:
                print(" No IPs found to be generating noise for the given date.")
                return False
            return r.text.encode("utf-8")
        except Exception as e:
            print(" Error making request!")
            print(e)

    def actors():  # clarify
        try:
            r = requests.get(
                "https://research.api.greynoise.io/v2/research/actors",
                headers={"key": GNCli.GREYNOISE_API_KEY},
            )
            return r.text.encode("utf-8")
        except Exception as e:
            print(" Error making request!")
            print(e)

    # TODO: write to file with txt formatted output
    def writeToFile(contents):
        outFile = None  # TODO: Where is outFile coming from?
        if outFile:
            try:
                f = open(outFile, "w")
                f.write(str(contents))
                f.close()
                print(' Output written to file "%s".' % outFile)
            except Exception:
                print(" Error accessing output file.")

    # Ensure query is valid ~ ##########################################################
    def test_query(rQuery, queryType, outFormat):

        # If queryType is defined, but its value is not in types, it is not allowed
        if queryType and queryType not in GNCli.queryTypes:
            print(" Query type unrecognized.")
            print(
                " Accepted query types: quick, raw, context, multi, bulk, date, actors"
            )
            exit()
        # only these formats
        if outFormat and outFormat not in GNCli.formatTypes:
            print(
                " Invalid output format. "
                "Options are text, csv, xml, json, raw (default)"
            )
            exit()
        # If queryType is one of the following, rQuery must be defined
        # - the search requires a query.
        if not rQuery:
            if (
                queryType == "quick"
                or queryType == "context"
                or queryType == "raw"
                or not queryType
            ):
                print(" Please enter a query.")
                exit()
            elif queryType == "date":  # bulkdate
                print(" Please enter a date (-q YYYY-MM-DD).")
                exit()

    # Main Application Logic #####################################################
    # TODO: refactor?
    def runQuery(outFile, outFormat, queryType, rQuery, verboseOut):
        try:

            GNCli.test_query(
                rQuery, queryType, outFormat
            )  # Will lead to program exit if any issues found.

            # TODO: controller for this decision making.
            if rQuery:
                cQuery = re.sub("[/]+", "\\/", rQuery)  # Escaping backslashes
            else:
                cQuery = False
            if (
                queryType == "context"
                or queryType == "quick"
                or queryType == "raw"
                or not queryType
            ):
                result = GNCli.singleIP(cQuery, queryType)
            elif queryType == "multi":
                result = GNCli.multiQuery(cQuery)  # takes a list of ips
            elif queryType == "bulk":
                result = GNCli.bulkQuery()  # defaults to today's date
            elif queryType == "date":
                result = GNCli.bulkQuery(cQuery)  # param is a date YYYY-MM-DD
            elif queryType == "actors":
                result = GNCli.actors()
            # you can handle special cases for anything by returning False to runQuery.
            if result:
                jResult = json.loads(result.decode("utf-8"))
            else:
                jResult = False

            # TODO: formatting.py as described above - encapsulate the following
            if outFormat == "xml":
                if jResult:
                    if outFile:
                        GNCli.writeToFile(dict2xml.dict2xml(jResult))
                    else:
                        print(dict2xml.dict2xml(jResult))
            elif outFormat == "txt":
                if jResult:
                    if queryType != "quick":
                        print(GNCli.banner)
                    GNCli.makeTxt(jResult, queryType, verboseOut)
            elif outFormat == "csv":
                if outFile:
                    of = outFile
                else:  # Timestamped file name generated if none is given
                    of = "greynoise-" + time.strftime("%Y%m%d-%H%M%S") + ".csv"
                if jResult:
                    GNCli.makeCSV(jResult, of, queryType)
            elif outFormat == "json":
                if jResult:
                    print(json.dumps(jResult))
            elif not outFormat or outFormat == "raw":
                if jResult:
                    if outFile:
                        GNCli.writeToFile(jResult)
                    else:
                        print(
                            jResult
                        )  # Print raw if nothing specified # TODO: add default
        except Exception as e:
            print(" General Error! %s" % e)
            # TODO: error handling for API key