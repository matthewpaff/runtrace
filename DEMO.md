# Runtrace walkthrough

Run `python server.py` from this repository. No packages are required.

1. Start the workbench and open the baseline synthetic run. Inspect its six checks and recorded events.
2. Reset the replay cursor, play, pause, and inspect a tool result. Replay changes the view; it executes no external tools.
3. Generate a timeout or rate-limit scenario. Compare the withheld delivery and missing evidence with the baseline.
4. Generate a duplicate scenario. Distinct successful effect receipts under one request are flagged; a retry referring to the same receipt is not a duplicate effect.
5. Lower the declared step or cost budget and generate another run. Inspect which check flags the supplied values.
6. Import sample-trace.json. Imported traces are validated synthetic recordings; pass rates and costs are fixture results, not model benchmarks or bills.

## Review evidence

Run `python -m unittest discover -s tests -v`. Tests include a real loopback HTTP server with an isolated temporary database, malformed request handling, cross-site write denial, and the main application path. The GitHub workflow checks Python 3.11 and 3.13 on Linux and Windows; a configured workflow is not evidence that a run has passed.

The interface has been reviewed from source and HTTP responses. An automated visual browser check was unavailable in the development session. These local servers are development demonstrations. See README.md for limits.
