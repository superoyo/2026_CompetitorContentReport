import functools, http.server, socketserver
D = "/Users/parndoungjai/Desktop/claude jun 18"
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=D)
with socketserver.TCPServer(("127.0.0.1", 8736), H) as s:
    print("serving", D, "on 8736", flush=True)
    s.serve_forever()
