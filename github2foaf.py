from datetime import datetime
import sys

from github import Github

from scraper import build_graph, SeedType

if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Invalid number of parameters!")

    # github2foaf
    # fanizzi2016
    # mnielsen

    graph_filename = sys.argv[1]
    github_username = sys.argv[2]
    github_password = sys.argv[3]
    seed_name = sys.argv[4]
    seed_type = SeedType[sys.argv[5]]

    github = Github(github_username, github_password)

    print("Number of remaining requests:", github.rate_limiting[0])
    print("Limit of requests:", github.rate_limiting[1])
    rate_limiting_resettime = github.rate_limiting_resettime
    print("Time to requests limit reset:",
          datetime.fromtimestamp(rate_limiting_resettime)
          .strftime('%Y-%m-%d %H:%M:%S'))

    graph = build_graph(github, seed_name, seed_type,
                        max_following=50,
                        max_contributors=50,
                        max_members=50,
                        max_repos=50,
                        max_orgs=50,
                        max_iterations=1500)

    print("Number of remaining requests:", github.rate_limiting[0])
    print("Limit of requests:", github.rate_limiting[1])
    rate_limiting_resettime = github.rate_limiting_resettime
    print("Time to requests limit reset:",
          datetime.fromtimestamp(rate_limiting_resettime)
          .strftime('%Y-%m-%d %H:%M:%S'))

    graph.serialize(destination=graph_filename, base="", format="pretty-xml")
