# coding: utf8
"""
Main command line interface of the pyglottolog package.

Like programs such as git, this cli splits its functionality into sub-commands
(see e.g. https://docs.python.org/2/library/argparse.html#sub-commands).
The rationale behind this is that while a lot of different tasks may be triggered using
this cli, most of them require common configuration.

The basic invocation looks like

    glottolog [OPTIONS] <command> [args]

"""
from __future__ import unicode_literals
import sys

from clldutils.clilib import ArgumentParser, ParserError
from clldutils.path import copytree, rmtree

from pyglottolog.monster import main as compile_monster
from pyglottolog.languoids import make_index, glottocode_for_name, Languoid, find_languoid
from pyglottolog import lff


def monster(args):
    """Compile the monster bibfile from the BibTeX files listed in references/BIBFILES.ini

    glottolog monster
    """
    compile_monster()


def index(args):
    """Create an index page listing and linking to all languoids of a specified level.

    glottolog index (family|language|dialect|all)
    """
    for level in ['family', 'language', 'dialect']:
        if args.args[0] in [level, 'all']:
            make_index(level)


def check_tree(args):
    pass


def recode(args):
    """Assign a new glottocode to an existing languoid.

    glottolog recode <code>
    """
    lang = find_languoid(glottocode=args.args[0])
    if not lang:
        raise ParserError('languoid not found')
    gc = glottocode_for_name(lang.name)
    lang.id = gc
    new_dir = lang.dir.parent.joinpath(gc)
    copytree(lang.dir, new_dir)
    lang.write_info(new_dir)
    rmtree(lang.dir)
    print("%s -> %s" % (args.args[0], gc))


def new_languoid(args):
    """Create a new languoid directory for a languoid specified by name and level.

    glottolog new_languoid <name> <level>
    """
    assert args.args[1] in ['family', 'language', 'dialect']
    lang = Languoid.from_name_id_level(
        args.args[0],
        glottocode_for_name(args.args[0]),
        args.args[1],
        **dict(prop.split('=') for prop in args.args[2:]))
    #
    # FIXME: how to specify parent? Just mv there?
    #
    print("Info written to %s" % lang.write_info())


def tree2lff(args):
    """Create lff.txt and dff.txt from the current languoid tree.

    glottolog tree2lff
    """
    lff.tree2lff()


def lff2tree(args):
    """Recreate tree from lff.txt and dff.txt

    glottolog lff2tree [test]
    """
    lff.lff2tree()
    if args.args and args.args[0] == 'test':
        print("""
You can run

    diff -rbB build/tree/ languoids/tree/

to inspect the changes in the directory tree.
""")
    else:
        print("""
Run

    git status

to inspect changes in the directory tree.
You can run

    diff -rbB build/tree/ languoids/tree/

to inspect the changes in detail.

- To discard changes run

    git checkout languoids/tree

- To commit and push changes, run

    git add languoids/tree/...

  for any newly created nodes listed under

# Untracked files:
#   (use "git add <file>..." to include in what will be committed)
#
#	languoids/tree/...

  followed by

    git commit -a -m"reason for change of classification"
    git push origin
""")


def main():
    parser = ArgumentParser(
        'pyglottolog', monster, index, tree2lff, lff2tree, new_languoid, recode)
    sys.exit(parser.main())
