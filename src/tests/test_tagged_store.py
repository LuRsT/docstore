# -*- encoding: utf-8

import pytest

from tagged_store import TaggedDocument, TaggedDocumentStore


def test_tagged_document_equality():
    d1 = TaggedDocument({"id": "1"})
    assert d1 == d1
    assert d1 == {"id": "1", "date_created": d1.date_created}


def test_tagged_document_inequality():
    d1 = TaggedDocument({"id": "1"})
    d2 = TaggedDocument({"id": "2"})
    assert d1 != d2


def test_tagged_document_inequality_with_other_types():
    d1 = TaggedDocument({"id": "1"})
    assert d1 != 2


def test_inconsistent_id_is_valuerror():
    with pytest.raises(ValueError, match=r"^IDs must match:"):
        TaggedDocument({"id": "1"}, doc_id="2")


def test_removes_id_field_if_present():
    d = TaggedDocument({"id": "1", "color": "red"}, doc_id="1")
    assert "id" not in d.data


def test_cant_put_tagged_document_in_set():
    d1 = TaggedDocument({"id": "1"})
    with pytest.raises(TypeError, match=r"^unhashable type:"):
        set([d1])


@pytest.mark.parametrize('data, query, expected_result', [
    ({"id": "1"}, [], True),
    ({"id": "2"}, ["foo"], False),
    ({"id": "3"}, ["foo", "bar"], False),
    ({"id": "4", "tags": []}, [], True),
    ({"id": "5", "tags": ["foo"]}, [], True),
    ({"id": "6", "tags": ["foo"]}, ["foo"], True),
    ({"id": "7", "tags": ["foo"]}, ["foo", "bar"], False),
    ({"id": "8", "tags": ["foo"]}, ["bar"], False),
])
def test_can_match_tag_query(data, query, expected_result):
    doc = TaggedDocument(data)
    assert doc.matches_tag_query(query) == expected_result


def test_can_read_values():
    doc = TaggedDocument({"x": "xray"})
    assert doc["x"] == "xray"
    with pytest.raises(KeyError, match="y"):
        doc["y"]


def test_can_set_values():
    doc = TaggedDocument({"id": "1"})
    doc["foo"] = "bar"
    assert doc.data["foo"] == "bar"


def test_can_delete_value():
    doc = TaggedDocument({"foo": "bar"})
    del doc["foo"]
    with pytest.raises(KeyError, match="foo"):
        doc["foo"]


def test_doc_has_length():
    doc = TaggedDocument(data={})
    assert len(doc) == 1  # Created date
    doc["foo"] = "bar"
    doc["bar"] = "baz"
    assert len(doc) == 3


def test_can_iterate_over_doc():
    doc = TaggedDocument(data={})
    assert list(iter(doc)) == list(iter(doc.data))


def test_root_path_properties(tmpdir):
    store = TaggedDocumentStore(root=tmpdir)
    assert store.db_path == tmpdir.join("documents.json")
    assert store.files_dir == tmpdir.join("files")
    assert store.thumbnails_dir == tmpdir.join("thumbnails")


def test_gets_empty_documents_on_startup(store):
    assert store.documents == {}


def test_can_store_a_document(store):
    doc = {"tags": ["foo", "bar"]}
    store.index_document(doc_id="1", doc=doc)
    assert doc in store.documents.values()


def test_documents_are_saved_to_disk(store):
    doc = {"tags": ["foo", "bar"]}
    store.index_document(doc_id="1", doc=doc)

    new_store = TaggedDocumentStore(root=store.root)
    assert store.documents == new_store.documents


def test_can_search_documents(store):
    doc1 = {"tags": ["foo", "bar"]}
    doc2 = {"tags": ["foo", "baz"]}
    doc3 = {"tags": []}

    store.index_document(doc_id="1", doc=doc1)
    store.index_document(doc_id="2", doc=doc2)
    store.index_document(doc_id="3", doc=doc3)

    assert store.search_documents(query=["foo"]) == [doc1, doc2]
    assert store.search_documents(query=["baz"]) == [doc2]
    assert store.search_documents(query=[]) == [doc1, doc2, doc3]


def test_can_update_document_by_id(store):
    doc = {"color": "blue"}
    stored_doc = store.index_document(doc_id="1", doc=doc)

    doc_new = {"color": "yellow"}
    store.index_document(doc_id="1", doc=doc_new)

    assert len(store.documents) == 1
    assert doc not in store.documents.values()
    assert doc_new in store.documents.values()


def test_creates_necessary_directories(tmpdir):
    store = TaggedDocumentStore(root=tmpdir)
    assert store.files_dir.exists()
    assert store.thumbnails_dir.exists()


def test_persists_id(tmpdir):
    store = TaggedDocumentStore(root=tmpdir)

    doc_id = "1"
    doc = {"name": "lexie"}

    store.index_document(doc_id=doc_id, doc=doc)

    new_store = TaggedDocumentStore(root=tmpdir)
    assert new_store.documents == {doc_id: doc}
