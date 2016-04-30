from datetime import datetime
import sys

from github import Github

from scraper import build_graph

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Invalid number of parameters!")

    graph_filename = sys.argv[1]

    github = Github("github2foaf", "fanizzi2016")

    print("Number of remaining requests:", github.rate_limiting[0])
    print("Limit of requests:", github.rate_limiting[1])
    rate_limiting_resettime = github.rate_limiting_resettime
    print("Time to requests limit reset:",
          datetime.fromtimestamp(rate_limiting_resettime)
          .strftime('%Y-%m-%d %H:%M:%S'))

    graph = build_graph(github, "mnielsen")

    print("Number of remaining requests:", github.rate_limiting[0])
    print("Limit of requests:", github.rate_limiting[1])
    rate_limiting_resettime = github.rate_limiting_resettime
    print("Time to requests limit reset:",
          datetime.fromtimestamp(rate_limiting_resettime)
          .strftime('%Y-%m-%d %H:%M:%S'))

    graph.serialize(destination=graph_filename, format="xml")
