import sys
import math

# ---- Given: the HTTP plumbing. Read it, then leave it alone. ----

class Request:
    def __init__(self, now, method, target, headers):
        self.now = now          # simulated clock, seconds since the epoch (a float)
        self.method = method    # "GET", "POST", ...
        self.target = target    # the request target as sent, query string included
        self.headers = headers  # lower-case header name -> value, surrounding spaces trimmed


def header(req: Request, name: str) -> str:
    """Value of a request header (pass the name in lower case), or "" if it is absent."""
    return req.headers.get(name, "")


REASONS = {200: "OK", 429: "Too Many Requests"}
out = []


def status_line(code: int):
    out.append("HTTP/1.1 %d %s\r\n" % (code, REASONS[code]))


def add_header(name: str, value: str):
    out.append("%s: %s\r\n" % (name, value))


def add_header_int(name: str, value: str):
    out.append("%s: %d\r\n" % (name, value))


def end_head():
    out.append("Content-Length: 0\r\n\r\n")


budget = {"login": 5, "api": 5}  # class -> limit per window
WINDOW = 60     # window length in seconds

logs = {}       # [client, route] -> [log of timestamps]


def handle(req: Request):
    client = header(req, "x-api-key") or "anonymous"
    path = req.target.split("?", 1)[0]
    route = "login" if req.method == "POST" and path == "/login" else "api"
    limit = budget[route]

    log = logs.setdefault((client, route), [])
    while log and log[0] <= req.now - WINDOW:
        log.pop(0)

    if len(log) >= limit:
        status_line(429)
        add_header_int("Retry-After", math.ceil(log[0] + WINDOW - req.now))
    else:
        log.append(req.now)
        status_line(200)

    add_header_int("X-RateLimit-Limit", limit)
    add_header_int("X-RateLimit-Remaining", limit - len(log))
    add_header_int("X-RateLimit-Reset", math.ceil(log[0] + WINDOW))
    end_head()

def directive(line, now):
    pass


def main():
    data = sys.stdin.buffer.read().decode("utf-8", "replace")
    pos = 0
    now = 0.0
    while pos < len(data):
        if data[pos] == "@":
            eol = data.find("\n", pos)
            if eol < 0:
                eol = len(data)
            line = data[pos:eol].strip()
            parts = line.split()
            if len(parts) == 2 and parts[0] == "@now":
                now = float(parts[1])
            else:
                directive(line, now)
            pos = eol + 1
            continue
        end = data.find("\r\n\r\n", pos)
        if end < 0:
            break  # an unfinished request head gets no reply
        lines = data[pos:end].split("\r\n")
        pos = end + 4
        first = lines[0].split(" ")
        method = first[0]
        target = first[1] if len(first) > 1 else ""
        headers = {}
        for text in lines[1:]:
            colon = text.find(":")
            if colon <= 0:
                continue
            name = text[:colon].lower()
            value = text[colon + 1:].strip(" \t")
            headers[name] = headers[name] + ", " + value if name in headers else value
        handle(Request(now, method, target, headers))
    sys.stdout.write("".join(out))




main()