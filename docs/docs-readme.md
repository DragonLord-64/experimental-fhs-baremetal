# Documentation Notes

## What to Document
Any role that is developed should be documented, with the tasks it executes, along with any variables it will use. These can be placed under the `docs/src/roles` directory and will be automatically added. 

Playbooks can also be added under the `docs/src/playbooks` section.

Anything else can be added to the `docs/src/guide` section, and manually added to `index.rst`.

## Formatting
Use either [Markdown](https://daringfireball.net/projects/markdown/syntax) (.md) or [reStructuredText](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html) (.rst) files, which will be parsed by Sphinx in the pipeline to create the docs webpages.

Be sure to only use one level one heading (`#` or `=======`) in the documentation, as the Sphinx will end up parsing the heading tree incorrectly otherwise.