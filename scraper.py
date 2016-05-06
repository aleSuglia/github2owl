import time
from collections import deque
from enum import Enum
from itertools import islice

from github import GithubException
from github.NamedUser import NamedUser
from github.Organization import Organization
from github.Repository import Repository
from rdflib import Namespace, Graph, RDF, Literal, URIRef
from rdflib.namespace import FOAF, DC, XSD


class SeedType(Enum):
    user = 1
    repo = 2
    org = 3


github2foaf_users = Namespace("http://github2foaf.org/users/")
github2foaf_repos = Namespace("http://github2foaf.org/repos/")
github2foaf_orgs = Namespace("http://github2foaf.org/orgs/")
doap = Namespace("http://http://usefulinc.com/ns/doap#")
dcmi_type = Namespace("http://purl.org/dc/dcmitype/")


def describe_repo_node(graph, node, node_iri):
    graph.add((node_iri, RDF.type, dcmi_type.Software))

    if node.name:
        graph.add((node_iri, dcmi_type.title, Literal(node.name, datatype=XSD.string)))
    if node.full_name:
        graph.add((node_iri, FOAF.name, Literal(node.full_name, datatype=XSD.string)))
    if node.description:
        graph.add((node_iri, DC.description, Literal(node.description, datatype=XSD.string)))
    if node.html_url:
        graph.add((node_iri, FOAF.isPrimaryTopicOf, URIRef(node.html_url)))
    languages = node.get_languages()
    if languages:
        for lang_name, lang_id in languages.items():
            graph.add((node_iri, doap["programming-language"], Literal(lang_name, datatype=XSD.string)))


def describe_userorg_node(graph, node, node_iri):
    graph.add((node_iri, RDF.type, FOAF.Person if node.type == "User" else FOAF.Organization))
    graph.add((node_iri, FOAF.nick, Literal(node.login, datatype=XSD.string)))
    if node.name:
        graph.add((node_iri, FOAF.name, Literal(node.name, datatype=XSD.string)))
    if node.avatar_url:
        graph.add((node_iri, FOAF.img, URIRef(node.avatar_url)))
    if node.location:
        graph.add((node_iri, FOAF.based_near, Literal(node.location, datatype=XSD.string)))
    if node.email:
        graph.add((node_iri, FOAF.mbox, URIRef("mailto:{0}".format(node.email))))
    if node.blog:
        graph.add((node_iri, FOAF.homepage, URIRef(node.blog)))
    if node.html_url:
        graph.add((node_iri, FOAF.isPrimaryTopicOf, URIRef(node.html_url)))


def get_seed_node(github, seed_name, seed_type):
    if seed_type == SeedType.user:
        return github.get_user(seed_name)
    if seed_type == SeedType.repo:
        return github.get_repo(seed_name)
    if seed_type == SeedType.team:
        return github.get_team(seed_name)


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
    graph = Graph(identifier=URIRef("http://github2foaf.org/"))
    graph.namespace_manager.reset()

    graph.namespace_manager.bind("g2fu", "http://github2foaf.org/users/")
    graph.namespace_manager.bind("g2fr", "http://github2foaf.org/repos/")
    graph.namespace_manager.bind("g2fo", "http://github2foaf.org/orgs/")
    graph.namespace_manager.bind("foaf", "http://xmlns.com/foaf/0.1/")
    graph.namespace_manager.bind("doap", "http://http://usefulinc.com/ns/doap#")
    graph.namespace_manager.bind("dcmit", "http://purl.org/dc/dcmitype/")

    while nodes_queue and num_iterations <= max_iterations:
        try:
            remaining_requests = github.rate_limiting[0]
            print("-- Remaining requests {0}".format(remaining_requests))
            if remaining_requests <= 100:
                time.sleep(3600)
            node = nodes_queue.popleft()

            if isinstance(node, NamedUser):
                print("-- Username: {0}, iteration {1} of {2}"
                      .format(node.login, num_iterations, max_iterations))

                if node.login not in nodes_iris:
                    nodes_iris[node.login] = github2foaf_users[node.login]

                describe_userorg_node(graph, node, github2foaf_users[node.login])

                for followed in islice(node.get_following(), 0, max_following):
                    nodes_queue.append(followed)
                    if followed.login not in nodes_iris:
                        nodes_iris[followed.login] = github2foaf_users[followed.login]
                    graph.add((github2foaf_users[node.login], FOAF.knows, github2foaf_users[followed.login]))

                for repo in islice(node.get_repos(), 0, max_repos):
                    nodes_queue.append(repo)
                    repo_name = repo.full_name.replace("/", "-")
                    if repo_name not in nodes_iris:
                        nodes_iris[repo_name] = github2foaf_repos[repo_name]
                    graph.add((github2foaf_users[node.login], FOAF.maker, github2foaf_repos[repo_name]))

            elif isinstance(node, Organization):
                print("-- Organization: {0}, iteration {1} of {2}"
                      .format(node.name, num_iterations, max_iterations))

                if node.name not in nodes_iris:
                    nodes_iris[node.name] = github2foaf_orgs[node.name]

                describe_userorg_node(graph, node, github2foaf_orgs[node.name])

                for member in islice(node.get_members(), 0, max_members):
                    nodes_queue.append(member)
                    if member.login not in nodes_iris:
                        nodes_iris[member.login] = github2foaf_users[member.login]
                    graph.add((github2foaf_users[member.login], FOAF.member, github2foaf_orgs[node.name]))

                for repo in islice(node.get_repos(), 0, max_repos):
                    nodes_queue.append(repo)
                    repo_name = repo.full_name.replace("/", "-")
                    if repo_name not in nodes_iris:
                        nodes_iris[repo_name] = github2foaf_repos[repo_name]
                    graph.add((github2foaf_orgs[node.name], FOAF.maker, github2foaf_repos[repo_name]))

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
                    graph.add((github2foaf_users[contributor.login], DC.contributor, github2foaf_repos[repo_name]))

            num_iterations += 1
        except GithubException:
            print("Skipped blocked repository.")

    queue_elements = 1
    queue_size = len(nodes_queue)

    while nodes_queue:
        node = nodes_queue.popleft()

        if isinstance(node, NamedUser):
            print("-- Username: {0}, node {1} of {2}"
                  .format(node.login, queue_elements, queue_size))

            if node.login not in nodes_iris:
                nodes_iris[node.login] = github2foaf_users[node.login]

            describe_userorg_node(graph, node, github2foaf_users[node.login])

            for followed in islice(node.get_following(), 0, max_following):
                nodes_queue.append(followed)
                if followed.login in nodes_iris:
                    graph.add((github2foaf_users[node.login], FOAF.knows, github2foaf_users[followed.login]))

            for repo in islice(node.get_repos(), 0, max_repos):
                nodes_queue.append(repo)
                repo_name = repo.full_name.replace("/", "-")
                if repo_name in nodes_iris:
                    graph.add((github2foaf_users[node.login], FOAF.maker, github2foaf_repos[repo_name]))

        elif isinstance(node, Organization):
            print("-- Organization: {0}, node {1} of {2}"
                  .format(node.name, queue_elements, queue_size))

            if node.name not in nodes_iris:
                nodes_iris[node.name] = github2foaf_orgs[node.name]

            describe_userorg_node(graph, node, github2foaf_orgs[node.name])

            for member in islice(node.get_members(), 0, max_members):
                nodes_queue.append(member)
                if member.login in nodes_iris:
                    graph.add((github2foaf_users[member.login], FOAF.member, github2foaf_orgs[node.name]))

            for repo in islice(node.get_repos(), 0, max_repos):
                nodes_queue.append(repo)
                repo_name = repo.full_name.replace("/", "-")
                if repo_name in nodes_iris:
                    graph.add((github2foaf_orgs[node.name], FOAF.maker, github2foaf_repos[repo_name]))

        elif isinstance(node, Repository):
            print("-- Repository: {0}, node {1} of {2}"
                  .format(node.full_name, queue_elements, queue_size))
            repo_name = node.full_name.replace("/", "-")
            if repo_name not in nodes_iris:
                nodes_iris[repo_name] = github2foaf_repos[repo_name]

            describe_repo_node(graph, node, github2foaf_repos[repo_name])

            for contributor in islice(node.get_contributors(), 0, max_contributors):
                nodes_queue.append(contributor)
                if contributor.login in nodes_iris:
                    graph.add((github2foaf_users[contributor.login], DC.contributor, github2foaf_repos[repo_name]))

        queue_elements += 1

    return graph
