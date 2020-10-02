import cgi
import datetime
import json
import os
from urllib.parse import urlparse
from urllib.request import urlretrieve

import click


def _download_file(url):  # pragma: no cover
    tmp_path, headers = urlretrieve(url)

    try:
        _, params = cgi.parse_header(headers["Content-Disposition"])
        filename = params["filename"]
    except KeyError:
        filename = os.path.basename(urlparse(url).path)

    out_path = os.path.join(os.path.dirname(tmp_path), filename)
    os.rename(tmp_path, out_path)

    return out_path


@click.group()
def main():
    pass


@main.command(help="Run a docstore API server")
@click.option(
    "--root",
    default=".",
    help="The root of the docstore database.",
    type=click.Path(),
    show_default=True,
)
@click.option(
    "--host", default="127.0.0.1", help="The interface to bind to.", show_default=True
)
@click.option("--port", default=3391, help="The port to bind to.", show_default=True)
@click.option("--title", default="", help="The title of the app.")
@click.option("--debug", default=False, is_flag=True, help="Run in debug mode.")
@click.option("--profile", default=False, is_flag=True, help="Run a profiler.")
def serve(host, port, title, debug, root, profile):  # pragma: no cover
    from docstore.server import run_profiler, run_server

    if profile:
        run_profiler(root=root, title=title, host=host, port=port)
    else:
        run_server(root=root, title=title, host=host, port=port, debug=debug)


def _add_document(root, path, title, tags, source_url):
    tags = tags or ""
    tags = [t.strip() for t in tags.split(",") if t.strip()]

    title = title or ""

    from docstore.documents import store_new_document
    document = store_new_document(
        root=root,
        path=path,
        title=title,
        tags=tags,
        source_url=source_url,
        date_saved=datetime.datetime.now(),
    )

    print(document.id)


@main.command(help="Store a file in docstore")
@click.option(
    "--root",
    default=".",
    help="The root of the docstore database.",
    type=click.Path(),
    show_default=True,
)
@click.option("--path", help="The file to store.", type=click.Path(), required=True)
@click.option("--title", help="The title of the file.")
@click.option("--tags", help="The tags to apply to the file.")
@click.option("--source_url", help="Where was this file downloaded from?.")
def add(root, path, title, tags, source_url):
    return _add_document(
        root=root, path=path, title=title, tags=tags, source_url=source_url
    )


@main.command(help="Store a file on the web in docstore")
@click.option(
    "--root",
    default=".",
    help="The root of the docstore database.",
    type=click.Path(),
    show_default=True,
)
@click.option(
    "--url", help="URL of the file to store.", type=click.Path(), required=True
)
@click.option("--title", help="The title of the file.")
@click.option("--tags", help="The tags to apply to the file.")
@click.option("--source_url", help="Where was this file downloaded from?.")
def add_from_url(root, url, title, tags, source_url):  # pragma: no cover
    path = _download_file(url)

    return _add_document(
        root=root, path=path, title=title, tags=tags, source_url=source_url
    )


@main.command(help="Migrate a V1 docstore")
@click.option(
    "--root",
    default=".",
    help="The root of the docstore database.",
    type=click.Path(),
    show_default=True,
)
@click.option(
    "--v1_path",
    help="Path to the root of the V1 instance.",
    type=click.Path(),
    required=True,
)
def migrate(root, v1_path):  # pragma: no cover
    documents = json.load(open(os.path.join(v1_path, "documents.json")))

    for _, doc in documents.items():
        stored_file_path = os.path.join(v1_path, "files", doc["file_identifier"])

        try:
            filename_path = os.path.join(v1_path, "files", doc["filename"])
        except KeyError:
            filename_path = stored_file_path

        if os.path.exists(stored_file_path):
            os.rename(stored_file_path, filename_path)

            from docstore.documents import store_new_document
            store_new_document(
                root=root,
                path=filename_path,
                title=doc.get("title", ""),
                tags=doc["tags"],
                source_url=doc.get("user_data", {}).get("source_url", ""),
                date_created=datetime.datetime.fromisoformat(doc["date_created"]),
            )
            print(doc.get("filename", os.path.basename(doc["file_identifier"])))


@main.command(help="Delete one or more documents")
@click.option(
    "--root",
    default=".",
    help="The root of the docstore database.",
    type=click.Path(),
    show_default=True,
)
@click.argument("doc_ids", nargs=-1)
def delete(root, doc_ids):
    from docstore.documents import delete_document

    for d_id in doc_ids:
        delete_document(root=root, doc_id=d_id)
        print(d_id)


@main.command(help="Merge the files on two documents")
@click.option(
    "--root",
    default=".",
    help="The root of the docstore database.",
    type=click.Path(),
    show_default=True,
)
@click.argument("doc_ids", nargs=-1)
@click.option("--yes", is_flag=True, help="Skip confirmation prompts.")
def merge(root, doc_ids, yes):
    if len(doc_ids) == 1:
        return

    from docstore.documents import read_documents
    documents = {d.id: d for d in read_documents(root)}

    documents_to_merge = [documents[d_id] for d_id in doc_ids]

    for doc in documents_to_merge:
        click.echo(
            f'{doc.id.split("-")[0]} {click.style(doc.title, fg="yellow") or "<untitled>"}'
        )

    if not yes:  # pragma: no cover
        click.confirm(f"Merge these {len(doc_ids)} documents?", abort=True)

    # What should the title of the merged document be?
    from docstore.merging import get_title_candidates
    title_candidates = get_title_candidates(documents_to_merge)

    if len(title_candidates) == 1:
        click.echo(f"Using common title: {click.style(title_candidates[0], fg='blue')}")
        new_title = title_candidates[0]
    else:
        print("")
        click.echo(f'Guessed title: {click.style(title_candidates[0], fg="blue")}')
        if yes or click.confirm("Use title?"):
            new_title = title_candidates[0]
        else:  # pragma: no cover
            new_title = click.edit("\n".join(title_candidates)).strip()

    # What should the tags on the merged document be?
    from docstore.merging import get_union_of_tags
    all_tags = get_union_of_tags(documents_to_merge)

    print("")

    if all(doc.tags == all_tags for doc in documents_to_merge):
        click.echo(f"Using common tags: {click.style(', '.join(all_tags), fg='blue')}")
        new_tags = all_tags
    else:
        click.echo(f"Guessed tags: {click.style(', '.join(all_tags), fg='blue')}")
        if yes or click.confirm("Use tags?"):
            new_tags = all_tags
        else:  # pragma: no cover
            new_tags = click.edit("\n".join(all_tags)).strip().splitlines()

    from docstore.documents import pairwise_merge_documents

    doc1 = documents[doc_ids[0]]
    for doc2_id in doc_ids[1:]:
        doc2 = documents[doc2_id]
        pairwise_merge_documents(
            root=root, doc1=doc1, doc2=doc2, new_title=new_title, new_tags=new_tags
        )
