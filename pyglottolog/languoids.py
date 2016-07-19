# coding: utf8
from __future__ import unicode_literals
import os
import re
from itertools import takewhile
from collections import defaultdict, OrderedDict
import io

from enum import Enum
from six import text_type
from clldutils.misc import slug
from clldutils import jsonlib
from clldutils.path import Path, walk
from clldutils.inifile import INI

from pyglottolog.util import languoids_path, parse_conjunctions


TREE = languoids_path('tree')
ID_REGEX = '([a-z0-9]{4}[0-9]{4}|NOCODE(_[A-Za-z0-9\-]+)?)'


class Level(Enum):
    family = 'family'
    language = 'language'
    dialect = 'dialect'


class Languoid(object):
    section_core = 'core'
    id_pattern = re.compile(ID_REGEX + '$')

    def __init__(self, cfg, lineage=None, directory=None):
        """

        :param cfg:
        :param lineage: list of ancestors, given as (id, name) pairs.
        """
        lineage = lineage or []
        assert all(
            [self.id_pattern.match(id) and Level(level) for name, id, level in lineage])
        self.lineage = [(name, id, Level(level)) for name, id, level in lineage]
        self.cfg = cfg
        self.dir = directory or TREE.joinpath(*[id for name, id, _ in self.lineage])

    @classmethod
    def from_dir(cls, directory, **kw):
        for p in directory.iterdir():
            if p.is_file():
                assert p.suffix == '.ini'
                return cls.from_ini(p, **kw)

    @classmethod
    def from_ini(cls, ini, nodes={}):
        if not isinstance(ini, Path):
            ini = Path(ini)

        directory = ini.parent
        cfg = INI(interpolation=None)
        cfg.read(ini.as_posix(), encoding='utf8')

        lineage = []
        for parent in directory.parents:
            id_ = parent.name
            assert id_ != directory.name
            if not cls.id_pattern.match(id_):
                # we ignore leading non-languoid-dir path components.
                break

            if id_ not in nodes:
                l = Languoid.from_dir(parent, nodes=nodes)
                nodes[id_] = (l.name, l.id, l.level)
            lineage.append(nodes[id_])

        res = cls(cfg, list(reversed(lineage)), directory=directory)
        nodes[res.id] = (res.name, res.id, res.level)
        return res

    @classmethod
    def from_name_id_level(cls, name, id, level, **kw):
        cfg = INI(interpolation=None)
        cfg.read_dict(dict(core=dict(name=name, glottocode=id)))
        res = cls(cfg, [])
        res.level = Level(level)
        for k, v in kw.items():
            setattr(res, k, v)
        return res

    @classmethod
    def from_lff(cls, path, name_and_codes, level):
        assert isinstance(level, Level)
        lname, codes = name_and_codes.split('[', 1)
        lname = lname.strip()
        glottocode, isocode = codes[:-1].split('][')

        lineage = []
        if path:
            for i, comp in enumerate(path.split('], ')):
                if comp.endswith(']'):
                    comp = comp[:-1]
                name, id_ = comp.split(' [', 1)
                _level = Level.family
                if level == Level.dialect:
                    _level = Level.language if i == 0 else Level.dialect
                lineage.append((name, id_, _level))

        cfg = INI(interpolation=None)
        cfg.read_dict(dict(core=dict(name=lname, glottocode=glottocode)))
        res = cls(cfg, lineage)
        res.level = level
        if isocode:
            res.iso = isocode
        return res

    @property
    def children(self):
        return [Languoid.from_dir(d) for d in self.dir.iterdir() if d.is_dir()]

    @property
    def ancestors(self):
        res = []
        for parent in self.dir.parents:
            id_ = parent.name
            if self.id_pattern.match(id_):
                res.append(Languoid.from_dir(parent))
            else:
                # we ignore leading non-languoid-dir path components.
                break
        return list(reversed(res))

    @property
    def parent(self):
        ancestors = self.ancestors
        return ancestors[-1] if ancestors else None

    @property
    def family(self):
        ancestors = self.ancestors
        return ancestors[0] if ancestors else None

    def _set(self, key, value):
        self.cfg.set(self.section_core, key, value)

    def _get(self, key, type_=None):
        res = self.cfg.get(self.section_core, key, fallback=None)
        if type_ and res:
            return type_(res)
        return res

    @property
    def macroareas(self):
        return self.cfg.getlist(self.section_core, 'macroareas')

    @macroareas.setter
    def macroareas(self, value):
        assert isinstance(value, (list, tuple))
        self._set('macroareas', value)

    @property
    def name(self):
        return self._get('name')

    @name.setter
    def name(self, value):
        self._set('name', value)

    @property
    def id(self):
        return self._get('glottocode')

    @id.setter
    def id(self, value):
        self._set('glottocode', value)

    @property
    def glottocode(self):
        return self._get('glottocode')

    @glottocode.setter
    def glottocode(self, value):
        self._set('glottocode', value)

    @property
    def latitude(self):
        return self._get('latitude', float)

    @latitude.setter
    def latitude(self, value):
        self._set('latitude', value)

    @property
    def longitude(self):
        return self._get('longitude', float)

    @longitude.setter
    def longitude(self, value):
        self._set('longitude', value)

    @property
    def hid(self):
        return self._get('hid')

    @property
    def level(self):
        return self._get('level', Level)

    @level.setter
    def level(self, value):
        self._set('level', Level(value).value)

    @property
    def iso(self):
        return self._get('iso639-3')

    @iso.setter
    def iso(self, value):
        self._set('iso639-3', value)

    @property
    def iso_code(self):
        return self._get('iso639-3')

    @iso_code.setter
    def iso_code(self, value):
        self._set('iso639-3', value)

    @property
    def classification_status(self):
        return self._get('classification_status')

    @classification_status.setter
    def classification_status(self, value):
        self._set('classification_status', value)

    def fname(self, suffix=''):
        return '%s%s' % (self.id, suffix)

    def write_info(self, outdir=None):
        outdir = outdir or self.id
        if not isinstance(outdir, Path):
            outdir = Path(outdir)
        if not outdir.exists():
            outdir.mkdir()
        fname = outdir.joinpath(self.fname('.ini'))
        self.cfg.write(fname)
        if os.linesep == '\n':
            with fname.open(encoding='utf8') as fp:
                text = fp.read()
            with fname.open('w', encoding='utf8') as fp:
                fp.write(text.replace('\n', '\r\n'))
        return fname

    def lff_group(self):
        if self.level == Level.dialect:
            lineage = reversed(
                list(takewhile(lambda x: x[2] != Level.family, reversed(self.lineage))))
        else:
            lineage = self.lineage
        if not self.lineage:
            return '%s [-isolate-]' % self.name
        res = ', '.join('%s [%s]' % (name, id) for name, id, level in lineage)
        return res or 'ERROR [-unclassified-]'

    def lff_language(self):
        res = '    %s [%s][%s]' % (self.name, self.id, self.iso or '')
        if self.classification_status:
            res = '%s %s' % (res, self.classification_status)
        return res


def find_languoid(tree=TREE, glottocode=None, **kw):
    for fname in walk(tree, mode='dirs', followlinks=True):
        if fname.name == glottocode:
            return Languoid.from_dir(fname)


def walk_tree(tree=TREE, **kw):
    for fname in walk(tree, mode='files', followlinks=True):
        if fname.suffix == '.ini':
            yield Languoid.from_ini(fname, **kw)


def make_index(level):
    fname = dict(language='languages', family='families', dialect='dialects')[level]
    links = defaultdict(dict)
    for lang in walk_tree():
        if lang.level == level:
            label = '{0.name} [{0.id}]'.format(lang)
            if lang.iso:
                label += '[%s]' % lang.iso
            links[slug(lang.name)[0]][label] = \
                lang.dir.joinpath(lang.fname('.ini')).relative_to(languoids_path())

    with languoids_path(fname + '.md').open('w', encoding='utf8') as fp:
        fp.write('## %s\n\n' % fname.capitalize())
        fp.write(' '.join(
            '[-%s-](%s_%s.md)' % (i.upper(), fname, i) for i in sorted(links.keys())))
        fp.write('\n')

    for i, langs in links.items():
        with languoids_path('%s_%s.md' % (fname, i)).open('w', encoding='utf8') as fp:
            for label in sorted(langs.keys()):
                fp.write('- [%s](%s)\n' % (label, langs[label]))


#
# The following two functions are necessary to make the compilation of the monster bib
# compatible with the new way of storing languoid data.
#
def macro_area_from_hid(tree=TREE):
    res = {}
    for lang in walk_tree(tree):
        if lang.hid:
            macroareas = lang.cfg.getlist('core', 'macroareas')
            res[lang.hid] = macroareas[0] if macroareas else ''
    return res


def load_triggers(tree=TREE, type_='lgcode'):
    res = {}
    for lang in walk_tree(tree):
        if lang.hid and lang.cfg.has_option('triggers', type_):
            triggers = lang.cfg.getlist('triggers', type_)
            if not triggers:
                continue
            res[(type_, '%s [%s]' % (lang.name, lang.hid))] = [
                parse_conjunctions(t) for t in triggers]
    return res


def glottocode_for_name(name, dry_run=False, repos=None):
    alpha = slug(text_type(name))[:4]
    assert alpha
    while len(alpha) < 4:
        alpha += alpha[-1]

    gc_store = languoids_path('glottocodes.json', **{'data_dir': repos} if repos else {})
    glottocodes = jsonlib.load(gc_store)
    glottocodes[alpha] = num = glottocodes.get(alpha, 1233) + 1
    if not dry_run:
        # Store the updated dictionary of glottocodes back.
        ordered = OrderedDict()
        for k in sorted(glottocodes.keys()):
            ordered[k] = glottocodes[k]
        jsonlib.dump(ordered, gc_store, indent=4)
    return '%s%s' % (alpha, num)
