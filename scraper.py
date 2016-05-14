import time
import validators
from collections import deque
from enum import Enum
from itertools import islice

from github.NamedUser import NamedUser
from github.Organization import Organization
from github.Repository import Repository
from rdflib import Namespace, Graph, RDF, Literal, URIRef
from rdflib.namespace import XSD


class SeedType(Enum):
    user = 1
    repo = 2
    org = 3


github2foaf_users = Namespace("http://uniba.it/github2owl/users/")
github2foaf_repos = Namespace("http://uniba.it/github2owl/repos/")
github2foaf_orgs = Namespace("http://uniba.it/github2owl/orgs/")
schema = Namespace("http://schema.org/")


def describe_user_node(graph, node, node_iri):
    graph.add((node_iri, RDF.type, schema.Person))
    graph.add((node_iri, schema.alternateName, Literal(node.login, datatype=XSD.string)))
    if node.name:
        graph.add((node_iri, schema.name, Literal(node.name, datatype=XSD.string)))
    if node.avatar_url:
        graph.add((node_iri, schema.image, URIRef(node.avatar_url)))
    if node.location:
        graph.add((node_iri, schema.workLocation, Literal(node.location, datatype=XSD.string)))
    if node.email:
        sanitized_email = sanitize(node.email)
        if validators.email(sanitized_email):
            graph.add((node_iri, schema.email, URIRef("mailto:{0}".format(sanitized_email))))
    if node.html_url:
        sanitized_url = sanitize(node.html_url)
        if validators.url(node.html_url):
            graph.add((node_iri, schema.url, URIRef(sanitized_url)))


def describe_org_node(graph, node, node_iri):
    graph.add((node_iri, RDF.type, schema.Organization))
    if node.name:
        graph.add((node_iri, schema.name, Literal(node.name, datatype=XSD.string)))
    if node.avatar_url:
        graph.add((node_iri, schema.logo, URIRef(node.avatar_url)))
    if node.location:
        graph.add((node_iri, schema.location, Literal(node.location, datatype=XSD.string)))
    if node.email:
        sanitized_email = sanitize(node.email)
        if validators.email(sanitized_email):
            graph.add((node_iri, schema.email, URIRef("mailto:{0}".format(sanitized_email))))
    if node.html_url:
        sanitized_url = sanitize(node.html_url)
        if validators.url(node.html_url):
            graph.add((node_iri, schema.url, URIRef(sanitized_url)))


def sanitize(text):
    return text.replace(" ", "")


def describe_repo_node(graph, node, node_iri):
    graph.add((node_iri, RDF.type, schema.SoftwareSourceCode))
    if node.html_url:
        graph.add((node_iri, schema.codeRepository, URIRef(node.html_url)))
    if node.name:
        graph.add((node_iri, schema.alternateName, Literal(node.name, datatype=XSD.string)))
    if node.full_name:
        graph.add((node_iri, schema.name, Literal(node.full_name, datatype=XSD.string)))
    if node.description:
        graph.add((node_iri, schema.description, Literal(node.description, datatype=XSD.string)))
    languages = node.get_languages()
    if languages:
        for lang_name, lang_id in languages.items():
            graph.add((node_iri, schema.programmingLanguage, Literal(lang_name, datatype=XSD.string)))


def get_seed_node(github, seed_name, seed_type):
    if seed_type == SeedType.user:
        return github.get_user(seed_name)
    if seed_type == SeedType.repo:
        return github.get_repo(seed_name)
    if seed_type == SeedType.team:
        return github.get_team(seed_name)


def pause_requests(github, margin=500, sleep_time=5400):
    remaining_requests = github.rate_limiting[0]
    print("-- Remaining requests {0}".format(remaining_requests))
    if remaining_requests <= margin:
        print("-- Sleeping...")
        time.sleep(sleep_time)


def build_graph(github,
                seed_name,
                seed_type,
                max_following=30,
                max_contributors=30,
                max_members=30,
                max_repos=30,
                max_iterations=5):
    nodes_queue = deque([get_seed_node(github, seed_name, seed_type)])
    nodes_iris = {}
    num_iterations = 1
    graph = Graph(identifier=URIRef("http://uniba.it/github2owl/"))
    graph.namespace_manager.reset()

    graph.bind("g2fu", github2foaf_users)
    graph.bind("g2fr", github2foaf_repos)
    graph.bind("g2fo", github2foaf_orgs)
    graph.bind("schema", schema)

    while nodes_queue and num_iterations <= max_iterations:
        node = nodes_queue.popleft()
        try:
            pause_requests(github)
            if isinstance(node, NamedUser):
                print("-- Username: {0}, iteration {1} of {2}"
                      .format(node.login, num_iterations, max_iterations))

                if node.login not in nodes_iris:
                    nodes_iris[node.login] = github2foaf_users[node.login]

                describe_user_node(graph, node, github2foaf_users[node.login])

                for followed in islice(node.get_following(), 0, max_following):
                    nodes_queue.append(followed)
                    if followed.login not in nodes_iris:
                        nodes_iris[followed.login] = github2foaf_users[followed.login]
                    graph.add((github2foaf_users[node.login], schema.follows, github2foaf_users[followed.login]))

                pause_requests(github)

                for repo in islice(node.get_repos(), 0, max_repos):
                    nodes_queue.append(repo)
                    repo_name = repo.full_name.replace("/", "-")
                    if repo_name not in nodes_iris:
                        nodes_iris[repo_name] = github2foaf_repos[repo_name]
                    graph.add((github2foaf_users[node.login], schema.creator, github2foaf_repos[repo_name]))

            elif isinstance(node, Organization):
                print("-- Organization: {0}, iteration {1} of {2}"
                      .format(node.name, num_iterations, max_iterations))

                if node.name not in nodes_iris:
                    nodes_iris[node.name] = github2foaf_orgs[node.name]

                describe_org_node(graph, node, github2foaf_orgs[node.name])

                for member in islice(node.get_members(), 0, max_members):
                    nodes_queue.append(member)
                    if member.login not in nodes_iris:
                        nodes_iris[member.login] = github2foaf_users[member.login]
                    graph.add((github2foaf_users[member.login], schema.memberOf, github2foaf_orgs[node.name]))

                pause_requests(github)

                for repo in islice(node.get_repos(), 0, max_repos):
                    nodes_queue.append(repo)
                    repo_name = repo.full_name.replace("/", "-")
                    if repo_name not in nodes_iris:
                        nodes_iris[repo_name] = github2foaf_repos[repo_name]
                    graph.add((github2foaf_orgs[node.name], schema.creator, github2foaf_repos[repo_name]))

            elif isinstance(node, Repository):
                print("-- Repository: {0}, iteration {1} of {2}"
                      .format(node.full_name, num_iterations, max_iterations))
                repo_name = node.full_name.replace("/", "-")
                if repo_name not in nodes_iris:
                    nodes_iris[repo_name] = github2foaf_repos[repo_name]

                describe_repo_node(graph, node, github2foaf_repos[repo_name])

                for contributor in islice(node.get_contributors(), 0, max_contributors):
                    nodes_queue.append(contributor)
                    if contributor.login not in nodes_iris:
                        nodes_iris[contributor.login] = github2foaf_users[contributor.login]
                    graph.add((github2foaf_users[contributor.login], schema.contributor, github2foaf_repos[repo_name]))

            num_iterations += 1
        except Exception:
            print("Skipped blocked repository.")

    queue_elements = 1
    queue_size = len(nodes_queue)

    while nodes_queue:
        node = nodes_queue.popleft()
        try:
            pause_requests(github)

            if isinstance(node, NamedUser):
                print("-- Username: {0}, node {1} of {2}"
                      .format(node.login, queue_elements, queue_size))

                if node.login not in nodes_iris:
                    nodes_iris[node.login] = github2foaf_users[node.login]

                describe_user_node(graph, node, github2foaf_users[node.login])

                for followed in islice(node.get_following(), 0, max_following):
                    if followed.login in nodes_iris:
                        graph.add((github2foaf_users[node.login], schema.follows, github2foaf_users[followed.login]))

                pause_requests(github)

                for repo in islice(node.get_repos(), 0, max_repos):
                    repo_name = repo.full_name.replace("/", "-")
                    if repo_name in nodes_iris:
                        graph.add((github2foaf_users[node.login], schema.creator, github2foaf_repos[repo_name]))

            elif isinstance(node, Organization):
                print("-- Organization: {0}, node {1} of {2}"
                      .format(node.name, queue_elements, queue_size))

                if node.name not in nodes_iris:
                    nodes_iris[node.name] = github2foaf_orgs[node.name]

                describe_org_node(graph, node, github2foaf_orgs[node.name])

                for member in islice(node.get_members(), 0, max_members):
                    if member.login in nodes_iris:
                        graph.add((github2foaf_users[member.login], schema.memberOf, github2foaf_orgs[node.name]))

                pause_requests(github)

                for repo in islice(node.get_repos(), 0, max_repos):
                    repo_name = repo.full_name.replace("/", "-")
                    if repo_name in nodes_iris:
                        graph.add((github2foaf_orgs[node.name], schema.creator, github2foaf_repos[repo_name]))

            elif isinstance(node, Repository):
                print("-- Repository: {0}, node {1} of {2}"
                      .format(node.full_name, queue_elements, queue_size))
                repo_name = node.full_name.replace("/", "-")
                if repo_name not in nodes_iris:
                    nodes_iris[repo_name] = github2foaf_repos[repo_name]

                describe_repo_node(graph, node, github2foaf_repos[repo_name])

                for contributor in islice(node.get_contributors(), 0, max_contributors):
                    if contributor.login in nodes_iris:
                        graph.add(
                            (github2foaf_users[contributor.login], schema.contributor, github2foaf_repos[repo_name]))

            queue_elements += 1

        except Exception:
            print("Skipped repository")

    return graph
