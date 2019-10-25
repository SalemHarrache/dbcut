# -*- coding: utf-8 -*-
from contextlib import contextmanager
from itertools import chain

import ujson as json
from sqlalchemy_utils.functions import (create_database, database_exists,
                                        drop_database)
from tqdm import tqdm

from ..query import parse_query


def parse_queries(ctx):
    queries = []
    session = ctx.src_db.session
    if ctx.last_only:
        raw_queries = [ctx.config["queries"][-1]]
    else:
        raw_queries = ctx.config["queries"]

    for dict_query in raw_queries:
        queries.append(parse_query(dict_query.copy(), session, ctx.config))
    return queries


@contextmanager
def db_profiling(ctx):
    if ctx.profiler:
        ctx.src_db.start_profiler()
        ctx.dest_db.start_profiler()
    yield
    if ctx.profiler:
        ctx.src_db.stop_profiler()
        ctx.dest_db.stop_profiler()
        ctx.src_db.profiler_stats()
        ctx.dest_db.profiler_stats()


def get_objects_generator(ctx, query, session):

    if ctx.no_cache:
        using_cache = False
        count = query.count()
        generator = query.objects()
    else:
        if not query.is_cached or ctx.force_refresh:
            using_cache = False
            count = query.count()

            def generator_func():
                objects = []
                for obj in query.objects():
                    objects.append(obj)
                    yield obj
                query.save_to_cache(objects=objects)

            generator = generator_func()

        else:
            using_cache = True
            count, data = query.load_from_cache()
            generator = (obj for obj in data)

    def objects_generator():
        progressbar = None

        obj = next(generator, None)
        if obj is not None:
            fetch_generator = chain([obj], generator)
        else:
            fetch_generator = generator

        yield

        if not using_cache:
            progressbar = tqdm(total=count, leave=False)

        for obj in fetch_generator:
            yield obj
            if progressbar is not None:
                progressbar.update(1)

        if progressbar is not None:
            progressbar.close()

    return objects_generator(), count, using_cache


def copy_query(ctx, query, session, query_index, number_of_queries):
    objects_generator, count, using_cache = get_objects_generator(ctx, query, session)

    ctx.log("")
    ctx.log("Query %d/%d : " % ((query_index + 1), number_of_queries), nl=False)
    ctx.log(json.dumps(query.query_dict, sort_keys=False))
    ctx.log("", quietable=True)
    ctx.log(
        query.relation_tree.render(return_value=True), tty_truncate=True, quietable=True
    )
    ctx.log(" ---> Cache key : %s" % query.cache_key, quietable=True)

    continue_operation = True
    if ctx.interactive:
        continue_operation = ctx.continue_operation("Continue ?", default=False)

    if continue_operation:
        if using_cache:
            ctx.log(" ---> Using cache ({} elements)".format(count), quietable=True)
        else:
            ctx.log(" ---> Executing query")

        next(objects_generator)

        if count:
            ctx.log(" ---> Fetching objects")
            objects_to_serialize = []
            for obj in objects_generator:
                if ctx.export_json:
                    objects_to_serialize.append(obj)
                else:
                    session.add(obj)

            if ctx.export_json:
                ctx.log(" ---> Exporting json to {}".format(query.json_file))
                query.export_to_json(objects_to_serialize)
            else:
                rows_count = len(list(session))
                ctx.log(" ---> Inserting {} rows".format(rows_count))
                session.commit()
        else:
            ctx.log(" ---> Nothing to do")
    else:
        ctx.log(" ---> Skipped")


def load_data(ctx):
    with db_profiling(ctx):
        with ctx.dest_db.no_fkc_session() as session:
            queries = parse_queries(ctx)
            number_of_queries = len(queries)
            for query_index, query in enumerate(queries):
                copy_query(ctx, query, session, query_index, number_of_queries)


def sync_schema(ctx):
    if not database_exists(ctx.dest_db.engine.url):
        create_db(ctx)
    else:
        if set(ctx.src_db.table_names) - set(ctx.dest_db.table_names):
            create_tables(ctx)

    ctx.log(" ---> Reflecting database schema from %s" % ctx.dest_db.engine.url)
    ctx.src_db.reflect(bind=ctx.dest_db.engine)
    ctx.dest_db.reflect(bind=ctx.dest_db.engine)


def create_db(ctx):
    if not database_exists(ctx.dest_db.engine.url):
        ctx.log(" ---> Creating new %s database" % ctx.dest_db.engine.url)
        create_database(ctx.dest_db.engine.url)


def create_tables(ctx, checkfirst=True):
    ctx.log(" ---> Reflecting database schema from %s" % ctx.src_db.engine.url)
    ctx.dest_db.reflect(bind=ctx.src_db.engine)
    ctx.log(" ---> Creating all tables and relations on %s" % ctx.dest_db.engine.url)
    ctx.dest_db.create_all(checkfirst=checkfirst)


def flush(ctx):
    if database_exists(ctx.dest_db.engine.url):
        ctx.confirm(
            "Removes ALL TABLES from %s" % ctx.dest_db.engine.url, default=False
        )
        ctx.log(" ---> Removing %s database" % ctx.dest_db.engine.url)
        drop_database(ctx.dest_db.engine.url)
    create_db(ctx)
    create_tables(ctx, checkfirst=False)


def load(ctx):
    sync_schema(ctx)
    load_data(ctx)
