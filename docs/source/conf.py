import importlib
import inspect
import os
import re
import sys
from collections.abc import Set
from typing import Any

from docutils import nodes
from sphinx import addnodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.environment.collectors import EnvironmentCollector
from sphinx.transforms import SphinxContentsFilter
from sphinx.util.typing import ExtensionMetadata

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

project = "VmaxBuilder"
copyright = "2026, Jelle Bonthuis, Marian Breuer, Michiel Adriaens"
author = "Jelle Bonthuis, Marian Breuer, Michiel Adriaens; MaCSBio2"

try:
    import VmaxBuilder  # noqa: E402

    release = VmaxBuilder.__version__
except (ImportError, AttributeError):
    # fallback if running on CI before package is installed
    release = os.environ.get("VmaxBuilder_VERSION", "0.1.0")
sys.modules["VmaxBuilder"] = VmaxBuilder
version = release.split("-")[0]  # Get the version without any tags

language = "en"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
]

napoleon_custom_sections = [
    ("Requires", "params_style"),
    ("Modifies", "params_style"),
]
napoleon_use_param = False
napoleon_use_rtype = False
# set autodoc to always show private _methods
autodoc_default_options = {
    "private-members": True,
    "autodoc_class_signature": "separated",
}
autosummary_generate = True
autosummary_generate_overwrite = True
autodoc_member_order = "bysource"
autodoc_preserve_defaults = True

html_theme = "furo"
html_permalinks = False
html_last_updated_fmt = "%b %d, %Y"

html_static_path = ["_static"]
html_css_files = ["custom.css"]
templates_path = ["_templates"]

# # -- Custom Documenter to skip function headers -----------------------------
from sphinx.environment.collectors.title import TitleCollector  # noqa: E402
from sphinx.ext.autodoc import (  # noqa: E402
    ClassDocumenter,
    DataDocumenter,
    FunctionDocumenter,
)


def custom_process_doc(self: TitleCollector, app: Sphinx, doctree: nodes.document) -> None:
    """Add a title node to the document (just copy the first section title),
    and store that title in the environment.
    """
    titlenode = nodes.title()
    longtitlenode = titlenode
    # explicit title set with title directive; use this only for
    # the <title> tag in HTML output
    if "title" in doctree:
        longtitlenode = nodes.title()
        longtitlenode += nodes.Text(doctree["title"])
    # look for first section title and use that as the title
    for node in doctree.findall(nodes.section):
        visitor = SphinxContentsFilter(doctree)
        node[0].walkabout(visitor)
        titlenode += visitor.get_entry_text()  # type: ignore[no-untyped-call]
        break
    else:
        # document has no title
        # Added by Jelle Bonthuis 2025-06-17 to handle caes where no section title is found
        # but we want to not use <no title>
        desc_signatures = list(doctree.traverse(addnodes.desc_signature))
        if desc_signatures:
            for sig in desc_signatures:
                match = re.search(r'_toc_name="([^"]*)"', str(sig))
                if match:
                    value = match.group(1)
                    titlenode += nodes.Text(value)
                    break
        else:
            titlenode += nodes.Text(doctree.get("title", "<no title>"))
    app.env.titles[app.env.docname] = titlenode
    app.env.longtitles[app.env.docname] = longtitlenode


title_collector_class: Any = TitleCollector
title_collector_class.process_doc = custom_process_doc  # ty: ignore


def setup(app):
    # app.add_autodocumenter(TitleClassDocumenter, override=True)
    # app.add_autodocumenter(NoHeaderFunctionDocumenter, override=True)
    # app.add_autodocumenter(NoHeaderDataDocumenter, override=True)
    pass
