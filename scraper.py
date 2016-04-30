from collections import deque
from rdflib import Namespace, Graph, RDF, Literal
from rdflib.namespace import FOAF

github2foaf = Namespace("http://github2foaf.org/users#")


def describe_node(graph, node, node_iri):
    graph.add((node_iri, FOAF.nick, Literal(node.login)))
    if node.name:
        graph.add((node_iri, FOAF.nick, Literal(node.name)))
    if node.avatar_url:
        graph.add((node_iri, FOAF.img, Literal(node.avatar_url)))
    if node.location:
        graph.add((node_iri, FOAF.based_near, Literal(node.location)))
    if node.email:
        graph.add((node_iri, FOAF.mbox, Literal(node.email)))
    if node.blog:
        graph.add((node_iri, FOAF.weblog, Literal(node.blog)))
    if node.html_url:
        graph.add((node_iri, FOAF.isPrimaryTopicOf, Literal(node.html_url)))
    graph.add((node_iri, RDF.type, FOAF.Person if node.type == "User" else FOAF.Organization))


def build_graph(github,
                seed_username,
                max_following=30,
                max_iterations=5):
    nodes_queue = deque([github.get_user(seed_username)])
    nodes_iris = {}
    num_iterations = 1

    graph = Graph()
    graph.bind("foaf", FOAF)
    graph.bind("g2f", github2foaf)

    while nodes_queue and num_iterations <= max_iterations:
        node = nodes_queue.popleft()
        print("-- Username: {0}, iteration {1} of {2}"
              .format(node.login, num_iterations, max_iterations))

        if node.login not in nodes_iris:
            nodes_iris[node.login] = github2foaf[node.login]

        describe_node(graph, node, github2foaf[node.login])

        if node.following != 0:
            for followed in node.get_following()[:max_following]:
                nodes_queue.append(followed)
                if followed.login not in nodes_iris:
                    nodes_iris[followed.login] = github2foaf[followed.login]
                graph.add((github2foaf[node.login], FOAF.knows, github2foaf[followed.login]))

        num_iterations += 1

    return graph
