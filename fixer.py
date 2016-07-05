import sys

import rdflib
from rdflib import Namespace, Literal

schema = Namespace("http://schema.org/")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Invalid number of parameters!")

    ontology_filename = sys.argv[1]
    fixed_ontology_filename = sys.argv[2]

    print("-- Loading ontology: " + ontology_filename)

    g = rdflib.Graph()
    g.load(ontology_filename)

    print("-- Fixing ontology")

    fixed_g = rdflib.Graph()

    for s, p, o in g:
        if str(p) == "http://schema.org/workLocation":
            continue
        elif str(p) == "http://schema.org/contributor" and ("users/" in str(s) or "orgs/" in str(s)):
            continue
        elif str(p) == "http://schema.org/creator" and ("users/" in str(s) or "orgs/" in str(s)):
            fixed_g.add((o, p, s))
        elif str(p) == "http://schema.org/codeRepository":
            o = Literal(str(o), datatype=schema.URL)
            fixed_g.add((s, p, o))
        elif str(p) == "http://schema.org/alternateName":
            o = Literal(str(o), datatype=schema.Text)
            fixed_g.add((s, p, o))
        elif str(p) == "http://schema.org/name":
            o = Literal(str(o), datatype=schema.Text)
            fixed_g.add((s, p, o))
        elif str(p) == "http://schema.org/image":
            o = Literal(str(o), datatype=schema.URL)
            fixed_g.add((s, p, o))
        elif str(p) == "http://schema.org/email":
            o = Literal(str(o), datatype=schema.Text)
            fixed_g.add((s, p, o))
        elif str(p) == "http://schema.org/url":
            o = Literal(str(o), datatype=schema.URL)
            fixed_g.add((s, p, o))
        elif str(p) == "http://schema.org/location":
            o = Literal(str(o), datatype=schema.Text)
            fixed_g.add((s, p, o))
        elif str(p) == "http://schema.org/description":
            o = Literal(str(o), datatype=schema.Text)
            fixed_g.add((s, p, o))
        elif str(p) == "http://schema.org/programmingLanguage":
            o = Literal(str(o), datatype=schema.Text)
            fixed_g.add((s, p, o))
        else:
            fixed_g.add((s, p, o))

    fixed_g.serialize(destination=fixed_ontology_filename, base="", format="pretty-xml")
