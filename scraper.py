from collections import deque
from enum import Enum
from itertools import islice

from github.Organization import Organization
from github.NamedUser import NamedUser
from github.Repository import Repository
from rdflib import Namespace, Graph, RDF, Literal, URIRef
from rdflib.namespace import FOAF, DC


class SeedType(Enum):
    user = 1
    repo = 2
    org = 3


github2foaf_users = Namespace("http://github2foaf.org/users#")
github2foaf_repos = Namespace("http://github2foaf.org/repos#")
github2foaf_orgs = Namespace("http://github2foaf.org/orgs#")
dbpedia_ontology = Namespace("http://dbpedia.org/ontology")
dcmi_type = Namespace("http://purl.org/dc/dcmitype")


def describe_repo_node(graph, node, node_iri):
    graph.add((node_iri, RDF.type, dcmi_type.Software))

    if node.name:
        graph.add((node_iri, dcmi_type.title, Literal(node.name)))
    if node.full_name:
        graph.add((node_iri, FOAF.name, Literal(node.full_name)))
    if node.description:
        graph.add((node_iri, DC.description, Literal(node.description)))
    if node.html_url:
        graph.add((node_iri, FOAF.isPrimaryTopicOf, Literal(node.html_url)))
    languages = node.get_languages()
    if languages:
        for lang_name, lang_id in languages.items():
            graph.add((node_iri, dbpedia_ontology.programmingLanguage, Literal(lang_name)))


def describe_userorg_node(graph, node, node_iri):
    graph.add((node_iri, RDF.type, FOAF.Person if node.type == "User" else FOAF.Organization))
    graph.add((node_iri, FOAF.nick, Literal(node.login)))
    if node.name:
        graph.add((node_iri, FOAF.name, Literal(node.name)))
    if node.avatar_url:
        graph.add((node_iri, FOAF.img, Literal(node.avatar_url)))
    if node.location:
        graph.add((node_iri, FOAF.based_near, Literal(node.location)))
    if node.email:
        graph.add((node_iri, FOAF.mbox, Literal(node.email)))
    if node.blog:
        graph.add((node_iri, FOAF.homepage, Literal(node.blog)))
    if node.html_url:
        graph.add((node_iri, FOAF.isPrimaryTopicOf, Literal(node.html_url)))


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

    graph = Graph()

    while nodes_queue and num_iterations <= max_iterations:
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
                if repo.full_name not in nodes_iris:
                    nodes_iris[repo.full_name] = github2foaf_repos[repo.full_name]
                graph.add((github2foaf_users[node.login], FOAF.maker, github2foaf_repos[repo.full_name]))

        elif isinstance(node, Organization):
            print("-- Username: {0}, iteration {1} of {2}"
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
                if repo.full_name not in nodes_iris:
                    nodes_iris[repo.full_name] = github2foaf_repos[repo.full_name]
                graph.add((github2foaf_orgs[node.name], FOAF.maker, github2foaf_repos[repo.full_name]))

        elif isinstance(node, Repository):
            print("-- Repository: {0}, iteration {1} of {2}"
                  .format(node.full_name, num_iterations, max_iterations))

            if node.full_name not in nodes_iris:
                nodes_iris[node.full_name] = github2foaf_repos[node.full_name]

            describe_repo_node(graph, node, github2foaf_repos[node.full_name])

            for contributor in islice(node.get_contributors(), 0, max_contributors):
                nodes_queue.append(contributor)
                if contributor.login not in nodes_iris:
                    nodes_iris[contributor.login] = github2foaf_users[contributor.login]
                graph.add((github2foaf_users[contributor.login], DC.contributor, github2foaf_repos[node.full_name]))

        num_iterations += 1

    graph.namespace_manager.reset()
    graph.namespace_manager.bind("foaf", FOAF)
    graph.namespace_manager.bind("dbo", dbpedia_ontology)
    graph.namespace_manager.bind("dcmit", dcmi_type)
    graph.namespace_manager.bind("g2fu", github2foaf_users)
    graph.namespace_manager.bind("g2fr", github2foaf_repos)
    graph.namespace_manager.bind("g2fo", github2foaf_orgs)

    return graph
