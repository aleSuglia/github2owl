import socket
import time
from collections import deque
from enum import Enum
from itertools import islice

import validators
from github import Github
from github.GithubException import GithubException
from github.NamedUser import NamedUser
from github.Organization import Organization
from github.Repository import Repository
from rdflib import Namespace, Graph, RDF, Literal, URIRef
from rdflib.namespace import XSD


class SeedType(Enum):
    """
    Class which represents the type of the seed node.
    """
    user = 1
    repo = 2
    org = 3


github2owl_users = Namespace("http://github2owl.org/users/")
github2owl_repos = Namespace("http://github2owl.org/repos/")
github2owl_orgs = Namespace("http://github2owl.org/orgs/")
schema = Namespace("http://schema.org/")


def sanitize(text):
    """
    Removes spaces from the given text.

    :param text: Text to be fixed
    :return: Fixed text
    """
    return text.replace(" ", "")


def describe_user_node(graph, node, node_iri):
    """
    Generates the RDF representation of the given user node and adds it to the graph.

    :param graph: RDF graph
    :param node: User node to be described
    :param node_iri: Identifier associated to the given node
    """
    graph.add((node_iri, RDF.type, schema.Person))
    graph.add((node_iri, schema.alternateName, Literal(node.login, datatype=schema.Text)))
    if node.name:
        graph.add((node_iri, schema.name, Literal(node.name, datatype=schema.Text)))
    if node.avatar_url:
        graph.add((node_iri, schema.image, Literal(node.avatar_url, datatype=schema.URL)))
    if node.email:
        sanitized_email = sanitize(node.email)
        if validators.email(sanitized_email):
            email = "mailto:{0}".format(sanitized_email)
            graph.add((node_iri, schema.email, Literal(email, datatype=schema.Text)))
    if node.html_url:
        sanitized_url = sanitize(node.html_url)
        if validators.url(node.html_url):
            graph.add((node_iri, schema.url, Literal(sanitized_url, datatype=schema.URL)))


def describe_org_node(graph, node, node_iri):
    """
    Generates the RDF representation of the given organization node and adds it to the graph.

    :param graph: RDF graph
    :param node: Organization node to be described
    :param node_iri: Identifier associated to the given node
    """
    graph.add((node_iri, RDF.type, schema.Organization))
    graph.add((node_iri, schema.alternateName, Literal(node.login, datatype=schema.Text)))
    if node.name:
        graph.add((node_iri, schema.name, Literal(node.name, datatype=schema.Text)))
    if node.avatar_url:
        graph.add((node_iri, schema.image, Literal(node.avatar_url, datatype=schema.URL)))
    if node.location:
        graph.add((node_iri, schema.location, Literal(node.location, datatype=schema.Text)))
    if node.email:
        sanitized_email = sanitize(node.email)
        if validators.email(sanitized_email):
            email = "mailto:{0}".format(sanitized_email)
            graph.add((node_iri, schema.email, Literal(email, datatype=schema.Text)))
    if node.html_url:
        sanitized_url = sanitize(node.html_url)
        if validators.url(node.html_url):
            graph.add((node_iri, schema.url, Literal(sanitized_url, datatype=schema.URL)))


def describe_repo_node(graph, node, node_iri):
    """
    Generates the RDF representation of the given repository node and adds it to the graph.

    :param graph: RDF graph
    :param node: Repository node to be described
    :param node_iri: Identifier associated to the given node
    """
    graph.add((node_iri, RDF.type, schema.SoftwareSourceCode))
    if node.html_url:
        graph.add((node_iri, schema.codeRepository, Literal(node.html_url, datatype=schema.URL)))
    if node.name:
        graph.add((node_iri, schema.alternateName, Literal(node.name, datatype=schema.Text)))
    if node.full_name:
        graph.add((node_iri, schema.name, Literal(node.full_name, datatype=schema.Text)))
    if node.description:
        graph.add((node_iri, schema.description, Literal(node.description, datatype=schema.Text)))
    languages = node.get_languages()
    if languages:
        for lang_name, lang_id in languages.items():
            graph.add((node_iri, schema.programmingLanguage, Literal(lang_name, datatype=schema.Text)))


def get_seed_node(github, seed_name, seed_type):
    """
    Returns the node associated to the given seed name and seed type.

    :param github: Client of the GitHub API
    :param seed_name: GitHub nickname to be used as seed
    :param seed_type: Type of the node to be used as seed
    :return: Node associated to the given seed name and seed type
    """
    if seed_type == SeedType.user:
        return github.get_user(seed_name)
    if seed_type == SeedType.repo:
        return github.get_repo(seed_name)
    if seed_type == SeedType.team:
        return github.get_team(seed_name)


def pause_requests(github, github_username, github_password, margin=500, sleep_time=350):
    """
    Pause requests to respect GitHub API limits.
    Recreates a GitHub client when limits have been reset.

    :param github: Client of the GitHub API
    :param github_username: Username of the GitHub API account
    :param github_password: Password of the GitHub API account
    :param margin: Minimum number of the remaining requests
    :param sleep_time: Number of seconds to wait
    """
    remaining_requests = github.rate_limiting[0]
    print("-- Remaining requests {0}".format(remaining_requests))
    while github.rate_limiting[0] <= margin:
        print("-- Sleeping...")
        time.sleep(sleep_time)
        github = Github(github_username, github_password)


def build_graph(github,
                github_username,
                github_password,
                seed_name,
                seed_type,
                max_following=30,
                max_contributors=30,
                max_members=30,
                max_repos=30,
                max_orgs=30,
                max_iterations=5):
    """
    Builds the RDF graph scraped using the GitHub API.

    :param github: Client of the GitHub API
    :param github_username: Username of the GitHub API account
    :param github_password: Password of the GitHub API account
    :param seed_name: GitHub nickname to be used as seed
    :param seed_type: Type of the node to be used as seed
    :param max_following: Maximum number of following relations
    :param max_contributors: Maximum number of contributors
    :param max_members: Maximum number of organization members
    :param max_repos: Maximum number of repositories
    :param max_orgs: Maximum number of organizations
    :param max_iterations: Maximum number of iterations for the scraping procedure
    :return: RDF graph of the dataset
    """
    nodes_queue = deque([get_seed_node(github, seed_name, seed_type)])
    visited_nodes = set()
    nodes_iris = {}
    num_iterations = 1
    graph = Graph(identifier=URIRef("http://github2owl.org/"))

    graph.bind("g2fu", github2owl_users)
    graph.bind("g2fr", github2owl_repos)
    graph.bind("g2fo", github2owl_orgs)
    graph.bind("schema", schema)

    while nodes_queue and num_iterations <= max_iterations:
        node = nodes_queue.popleft()
        try:
            pause_requests(github, github_username, github_password)

            if isinstance(node, NamedUser):
                print("-- Username: {0}, iteration {1} of {2}"
                      .format(node.login, num_iterations, max_iterations))

                if node.login not in nodes_iris:
                    nodes_iris[node.login] = github2owl_users[node.login]

                describe_user_node(graph, node, nodes_iris[node.login])

                for followed in islice(node.get_following(), 0, max_following):
                    if followed.login not in visited_nodes:
                        nodes_queue.append(followed.login)
                    if followed.login not in nodes_iris:
                        nodes_iris[followed.login] = github2owl_users[followed.login]
                    graph.add((github2owl_users[node.login], schema.follows, nodes_iris[followed.login]))

                pause_requests(github, github_username, github_password)

                for repo in islice(node.get_repos(), 0, max_repos):
                    repo_name = repo.full_name.replace("/", "-")
                    if repo_name not in visited_nodes:
                        nodes_queue.append(repo)
                    if repo_name not in nodes_iris:
                        nodes_iris[repo_name] = github2owl_repos[repo_name]
                    graph.add((github2owl_users[node.login], schema.creator, nodes_iris[repo_name]))

                pause_requests(github, github_username, github_password)

                for orgs in islice(node.get_orgs(), 0, max_orgs):
                    org_name = orgs.login
                    if org_name not in visited_nodes:
                        nodes_queue.append(orgs)
                    if org_name not in nodes_iris:
                        nodes_iris[org_name] = github2owl_orgs[org_name]
                    graph.add((github2owl_users[node.login], schema.memberOf, nodes_iris[org_name]))
                visited_nodes.add(node.login)

            elif isinstance(node, Organization):
                org_name = node.login

                print("-- Organization: {0}, iteration {1} of {2}"
                      .format(org_name, num_iterations, max_iterations))

                if org_name not in nodes_iris:
                    nodes_iris[org_name] = github2owl_orgs[org_name]

                describe_org_node(graph, node, github2owl_orgs[org_name])

                for member in islice(node.get_members(), 0, max_members):
                    if member.login not in visited_nodes:
                        nodes_queue.append(member)
                    if member.login not in nodes_iris:
                        nodes_iris[member.login] = github2owl_users[member.login]
                    graph.add((github2owl_orgs[org_name], schema.member, nodes_iris[member.login]))

                pause_requests(github, github_username, github_password)

                for repo in islice(node.get_repos(), 0, max_repos):
                    repo_name = repo.full_name.replace("/", "-")
                    if repo_name not in visited_nodes:
                        nodes_queue.append(repo)
                    if repo_name not in nodes_iris:
                        nodes_iris[repo_name] = github2owl_repos[repo_name]
                    graph.add((github2owl_orgs[org_name], schema.creator, nodes_iris[repo_name]))
                visited_nodes.add(node.login)

            elif isinstance(node, Repository):
                print("-- Repository: {0}, iteration {1} of {2}"
                      .format(node.full_name, num_iterations, max_iterations))
                repo_name = node.full_name.replace("/", "-")
                if repo_name not in nodes_iris:
                    nodes_iris[repo_name] = github2owl_repos[repo_name]

                describe_repo_node(graph, node, github2owl_repos[repo_name])

                for contributor in islice(node.get_contributors(), 0, max_contributors):
                    if contributor.login not in visited_nodes:
                        nodes_queue.append(contributor)
                    if contributor.login not in nodes_iris:
                        if isinstance(contributor, NamedUser):
                            nodes_iris[contributor.login] = github2owl_users[contributor.login]
                        else:
                            nodes_iris[contributor.login] = github2owl_orgs[contributor.login]
                    graph.add((github2owl_repos[repo_name], schema.contributor, nodes_iris[contributor.login]))

                pause_requests(github, github_username, github_password)

                repo_creator = node.owner
                if repo_creator.login not in visited_nodes:
                    nodes_queue.append(repo_creator)
                if repo_creator.login not in nodes_iris:
                    if isinstance(contributor, NamedUser):
                        nodes_iris[contributor.login] = github2owl_users[contributor.login]
                    else:
                        nodes_iris[contributor.login] = github2owl_orgs[contributor.login]
                graph.add((github2owl_repos[repo_name], schema.creator, nodes_iris[repo_creator.login]))

                visited_nodes.add(repo_name)

            num_iterations += 1

        except GithubException:
            print("Skipped blocked repository.")
        except (socket.error, socket.gaierror):
            print("Connection error! Reconnecting...")
            github = Github(github_username, github_password)

    queue_elements = 1
    queue_size = len(nodes_queue)

    while nodes_queue:
        node = nodes_queue.popleft()
        try:
            pause_requests(github, github_username, github_password)

            if isinstance(node, NamedUser):
                print("-- Username: {0}, node {1} of {2}"
                      .format(node.login, queue_elements, queue_size))

                if node.login not in nodes_iris:
                    nodes_iris[node.login] = github2owl_users[node.login]

                describe_user_node(graph, node, github2owl_users[node.login])

                for followed in islice(node.get_following(), 0, max_following):
                    if followed.login in nodes_iris:
                        graph.add((nodes_iris[node.login], schema.follows, nodes_iris[followed.login]))

                pause_requests(github, github_username, github_password)

                for repo in islice(node.get_repos(), 0, max_repos):
                    repo_name = repo.full_name.replace("/", "-")
                    if repo_name in nodes_iris:
                        graph.add((nodes_iris[node.login], schema.creator, nodes_iris[repo_name]))

                pause_requests(github, github_username, github_password)

                for org in islice(node.get_orgs(), 0, max_orgs):
                    org_name = org.login
                    if org_name in nodes_iris:
                        graph.add((nodes_iris[node.login], schema.memberOf, nodes_iris[org_name]))

            elif isinstance(node, Organization):
                org_name = node.login

                print("-- Organization: {0}, iteration {1} of {2}"
                      .format(org_name, num_iterations, max_iterations))

                if org_name not in nodes_iris:
                    nodes_iris[org_name] = github2owl_orgs[org_name]

                describe_org_node(graph, node, github2owl_orgs[org_name])

                for member in islice(node.get_members(), 0, max_members):
                    if member.login in nodes_iris:
                        graph.add((nodes_iris[org_name], schema.member, nodes_iris[member.login]))

                pause_requests(github, github_username, github_password)

                for repo in islice(node.get_repos(), 0, max_repos):
                    repo_name = repo.full_name.replace("/", "-")
                    if repo_name in nodes_iris:
                        graph.add((nodes_iris[org_name], schema.creator, nodes_iris[repo_name]))

            elif isinstance(node, Repository):
                print("-- Repository: {0}, node {1} of {2}"
                      .format(node.full_name, queue_elements, queue_size))
                repo_name = node.full_name.replace("/", "-")
                if repo_name not in nodes_iris:
                    nodes_iris[repo_name] = github2owl_repos[repo_name]

                describe_repo_node(graph, node, github2owl_repos[repo_name])

            queue_elements += 1

        except GithubException:
            print("Skipped repository")
        except (socket.error, socket.gaierror):
            print("Connection error! Reconnecting...")
            github = Github(github_username, github_password)
    return graph
