"""Base model enhancements"""

import itertools
from operator import itemgetter
from odoo.addons.udes_common import tools
from odoo import models

# TODO pull this out of edi and into a stand-alone module so we don't need the
# error flag


def add_if_not_exists(cls):
    """Patch class to add a new method"""

    def wrapper(func):
        # pylint: disable=missing-docstring
        if not hasattr(cls, func.__name__):
            setattr(cls, func.__name__, func)
        return func

    return wrapper


@add_if_not_exists(models.BaseModel)
def sliced(self, size=models.PREFETCH_MAX):
    """Return the recordset ``self`` split into slices of a specified size"""
    return tools.sliced(self, size=size, concat=lambda s: self.browse(x.id for x in s))


@add_if_not_exists(models.BaseModel)
def batched(self, size=models.PREFETCH_MAX):
    """Return the recordset ``self`` split into batches of a specified size"""
    return tools.batched(self, size=size)


@add_if_not_exists(models.BaseModel)
def groupby(self, key, sort=True):
    """Return the recordset ``self`` grouped by ``key``

    The recordset will automatically be sorted using ``key`` as the
    sorting key, unless ``sort`` is explicitly set to ``False``.

    ``key`` is permitted to produce a singleton recordset object, in
    which case the sort order will be well-defined but arbitrary.  If
    a non-arbitrary ordering is required, then use :meth:`~.sorted` to
    sort the recordset first, then pass to :meth:`~.groupby` with
    ``sort=False``.
    """

    recs = self
    if isinstance(key, str):
        key = itemgetter(key)
    if sort:
        if recs and isinstance(key(next(iter(recs))), models.BaseModel):
            recs = recs.sorted(key=lambda x: key(x).ids)
        else:
            recs = recs.sorted(key=key)
    return ((k, self.browse(x.id for x in v)) for k, v in itertools.groupby(recs, key=key))


@add_if_not_exists(models.BaseModel)
def statistics(self, cache=False):
    """Gather profiling statistics for an operation"""
    return tools.Statistics(self.env, cache=cache)


@add_if_not_exists(models.BaseModel)
def trace(self, filter=None, max=None):
    """Trace database queries"""
    return tools.QueryTracer(self.env.cr, filter=filter, max=max)
