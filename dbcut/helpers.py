# -*- coding: utf-8 -*-
import hashlib
import logging
import re
import sys
import time
from functools import update_wrapper

import click
from sqlalchemy import event
from sqlalchemy.engine import Engine

from .compat import reraise, to_unicode

magenta = lambda x, **kwargs: click.style("%s" % x, fg="magenta", **kwargs)
yellow = lambda x, **kwargs: click.style("%s" % x, fg="yellow", **kwargs)
green = lambda x, **kwargs: click.style("%s" % x, fg="green", **kwargs)
cyan = lambda x, **kwargs: click.style("%s" % x, fg="cyan", **kwargs)
blue = lambda x, **kwargs: click.style("%s" % x, fg="blue", **kwargs)
red = lambda x, **kwargs: click.style("%s" % x, fg="red", **kwargs)


class Context(object):

    def __init__(self):
        self.debug = False
        self.verbose = False
        self.force_yes = False

    def configure_log(self):
        logging.basicConfig()
        self.logger = logging.getLogger("dbcut.cli")

        if not self.verbose:
            self.logger.setLevel(logging.INFO)
            return

        self.logger.setLevel(logging.DEBUG)

        for handler in self.logger.root.handlers:
            handler.setFormatter(AnsiColorFormatter())

        @event.listens_for(Engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement,
                                 parameters, context, executemany):
            conn.info.setdefault('query_start_time', []).append(time.time())
            self.logger.debug("Start Query: \n%s\n" % statement)

        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement,
                                parameters, context, executemany):
            total = time.time() - conn.info['query_start_time'].pop(-1)
            self.logger.debug("Query Complete!")
            self.logger.debug("Total Time: %f" % total)

    def log(self, *args, **kwargs):
        """Logs a message to stderr."""
        kwargs.setdefault("file", sys.stderr)
        prefix = kwargs.pop("prefix", "")
        for msg in args:
            message = prefix + msg
            if self.debug:
                message = message.replace('\r', '')
                kwargs['nl'] = True
            click.echo(message, **kwargs)

    def confirm(self, message, **kwargs):
        if not self.force_yes:
            if not click.confirm(message, **kwargs):
                raise click.Abort()

    def update_options(self, **kwargs):
        self.__dict__.update(kwargs)
        if self.debug and not self.verbose:
            self.verbose = True

    def handle_error(self):
        exc_type, exc_value, tb = sys.exc_info()
        if (isinstance(exc_value, (click.ClickException, click.Abort))
                or self.debug):
            reraise(exc_type, exc_value, tb.tb_next)
        else:
            sys.stderr.write(u"\nError: %s\n" % exc_value)
            sys.exit(1)


def make_pass_decorator(context_klass, ensure=True):
    def decorator(f):
        @click.pass_context
        def new_func(*args, **kwargs):
            ctx = args[0]
            if ensure:
                obj = ctx.ensure_object(context_klass)
            else:
                obj = ctx.find_object(context_klass)
            try:
                return ctx.invoke(f, obj, *args[1:], **kwargs)
            except:
                obj.handle_error()
        return update_wrapper(new_func, f)
    return decorator


re_color_codes = re.compile(r'\033\[(\d;)?\d+m')


class AnsiColorFormatter(logging.Formatter):

    LEVELS = {
        'WARNING': red(' WARN'),
        'INFO': blue(' INFO'),
        'DEBUG': blue('DEBUG'),
        'CRITICAL': magenta(' CRIT'),
        'ERROR': red('ERROR'),
    }

    def __init__(self, msgfmt=None, datefmt=None):
        logging.Formatter.__init__(self, None, '%H:%M:%S')

    def format(self, record):
        """
        Format the specified record as text.

        The record's attribute dictionary is used as the operand to a
        string formatting operation which yields the returned string.
        Before formatting the dictionary, a couple of preparatory steps
        are carried out. The message attribute of the record is computed
        using LogRecord.getMessage(). If the formatting string contains
        "%(asctime)", formatTime() is called to format the event time.
        If there is exception information, it is formatted using
        formatException() and appended to the message.
        """
        message = record.getMessage()
        asctime = self.formatTime(record, self.datefmt)
        name = yellow(record.name)

        s = '%(timestamp)s %(levelname)s %(name)s ' % {
            'timestamp': green('%s,%03d' % (asctime, record.msecs), bold=True),
            'levelname': self.LEVELS[record.levelname],
            'name': name,
        }

        if "\n" in message:
            indent_length = len(re_color_codes.sub('', s))
            message = message.replace("\n", "\n" + ' ' * indent_length)

        s += message
        return s


def merge_dicts(*dict_args):
    """Merge given dicts into a new dict."""
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


class CachedProperty(object):
    """A property that is only computed once per instance and then replaces
    itself with an ordinary attribute. Deleting the attribute resets the
    property."""
    def __init__(self, func):
        self.__name__ = func.__name__
        self.__module__ = func.__module__
        self.__doc__ = func.__doc__
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self
        obj.__dict__.setdefault("_cache", {})
        cached_value = obj._cache.get(self.__name__, None)
        if cached_value is None:
            # don't cache None value
            obj._cache[self.__name__] = self.func(obj)
        return obj._cache.get(self.__name__)

    def __delete__(self, obj):
        cache_obj = getattr(obj, "_cache", {})
        if self.__name__ in cache_obj:
            del cache_obj[self.__name__]


cached_property = CachedProperty


def get_table_name(name):
    def _join(match):
        word = match.group()
        if len(word) > 1:
            return ('_%s_%s' % (word[:-1], word[-1])).lower()
        return '_' + word.lower()
    return re.compile(r'([A-Z]+)(?=[a-z0-9])').sub(_join, name).lstrip('_')


def render_query(statement, bind=None, reindent=True):
    """Generate an SQL expression string with bound parameters rendered inline
    for the given SQLAlchemy statement.
    The function can also receive a `sqlalchemy.orm.Query` object instead of
    statement.
    """
    from sqlalchemy_utils.functions import render_statement
    raw_sql = render_statement(statement, bind)
    try:  # pragma: no cover
        import sqlparse
        return sqlparse.format(raw_sql, reindent=reindent)
    except ImportError:  # pragma: no cover
        return raw_sql


def generate_valid_index_name(index, dialect):
    table_name = index.table.name
    columns_names = '_'.join([cn.name for cn in index.columns])
    if index.unique:
        full_index_name = "%s_%s_unique_idx" % (table_name, columns_names)
    else:
        full_index_name = "%s_%s_idx" % (table_name, columns_names)
    short_index_name = "%s_%s_idx" % (table_name, short_hash(full_index_name))
    return short_index_name


def short_hash(string):
    return hashlib.sha1(to_unicode(string).encode("utf-8")).hexdigest()[:10]
