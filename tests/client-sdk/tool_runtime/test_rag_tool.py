# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

import random

import pytest

from llama_stack_client.types.tool_runtime import DocumentParam


@pytest.fixture(scope="function")
def empty_vector_db_registry(llama_stack_client):
    vector_dbs = [
        vector_db.identifier for vector_db in llama_stack_client.vector_dbs.list()
    ]
    for vector_db_id in vector_dbs:
        llama_stack_client.vector_dbs.unregister(vector_db_id=vector_db_id)


@pytest.fixture(scope="function")
def single_entry_vector_db_registry(llama_stack_client, empty_vector_db_registry):
    vector_db_id = f"test_vector_db_{random.randint(1000, 9999)}"
    llama_stack_client.vector_dbs.register(
        vector_db_id=vector_db_id,
        embedding_model="all-MiniLM-L6-v2",
        embedding_dimension=384,
        provider_id="faiss",
    )
    vector_dbs = [
        vector_db.identifier for vector_db in llama_stack_client.vector_dbs.list()
    ]
    return vector_dbs


@pytest.fixture(scope="session")
def sample_documents():
    return [
        DocumentParam(
            document_id="test-doc-1",
            content="Python is a high-level programming language.",
            metadata={"category": "programming", "difficulty": "beginner"},
        ),
        DocumentParam(
            document_id="test-doc-2",
            content="Machine learning is a subset of artificial intelligence.",
            metadata={"category": "AI", "difficulty": "advanced"},
        ),
        DocumentParam(
            document_id="test-doc-3",
            content="Data structures are fundamental to computer science.",
            metadata={"category": "computer science", "difficulty": "intermediate"},
        ),
        DocumentParam(
            document_id="test-doc-4",
            content="Neural networks are inspired by biological neural networks.",
            metadata={"category": "AI", "difficulty": "advanced"},
        ),
    ]


def assert_valid_response(response):
    assert len(response.chunks) > 0
    assert len(response.scores) > 0
    assert len(response.chunks) == len(response.scores)
    for chunk in response.chunks:
        assert isinstance(chunk.content, str)


def test_vector_db_insert_inline_and_query(
    llama_stack_client, single_entry_vector_db_registry, sample_documents
):
    vector_db_id = single_entry_vector_db_registry[0]
    llama_stack_client.tool_runtime.rag_tool.insert_documents(
        documents=sample_documents,
        chunk_size_in_tokens=512,
        vector_db_id=vector_db_id,
    )

    # Query with a direct match
    query1 = "programming language"
    response1 = llama_stack_client.vector_io.query(
        vector_db_id=vector_db_id,
        query=query1,
    )
    assert_valid_response(response1)
    assert any("Python" in chunk.content for chunk in response1.chunks)

    # Query with semantic similarity
    query2 = "AI and brain-inspired computing"
    response2 = llama_stack_client.vector_io.query(
        vector_db_id=vector_db_id,
        query=query2,
    )
    assert_valid_response(response2)
    assert any("neural networks" in chunk.content.lower() for chunk in response2.chunks)

    # Query with limit on number of results (max_chunks=2)
    query3 = "computer"
    response3 = llama_stack_client.vector_io.query(
        vector_db_id=vector_db_id,
        query=query3,
        params={"max_chunks": 2},
    )
    assert_valid_response(response3)
    assert len(response3.chunks) <= 2

    # Query with threshold on similarity score
    query4 = "computer"
    response4 = llama_stack_client.vector_io.query(
        vector_db_id=vector_db_id,
        query=query4,
        params={"score_threshold": 0.01},
    )
    assert_valid_response(response4)
    assert all(score >= 0.01 for score in response4.scores)


def test_vector_db_insert_from_url_and_query(
    llama_stack_client, empty_vector_db_registry
):
    providers = [p for p in llama_stack_client.providers.list() if p.api == "vector_io"]
    assert len(providers) > 0

    vector_db_id = "test_vector_db"

    llama_stack_client.vector_dbs.register(
        vector_db_id=vector_db_id,
        embedding_model="all-MiniLM-L6-v2",
        embedding_dimension=384,
        provider_id="faiss",
    )

    # list to check memory bank is successfully registered
    available_vector_dbs = [
        vector_db.identifier for vector_db in llama_stack_client.vector_dbs.list()
    ]
    assert vector_db_id in available_vector_dbs

    # URLs of documents to insert
    # TODO: Move to test/memory/resources then update the url to
    # https://raw.githubusercontent.com/meta-llama/llama-stack/main/tests/memory/resources/{url}
    urls = [
        "memory_optimizations.rst",
        "chat.rst",
        "llama3.rst",
    ]
    documents = [
        DocumentParam(
            document_id=f"num-{i}",
            content=f"https://raw.githubusercontent.com/pytorch/torchtune/main/docs/source/tutorials/{url}",
            mime_type="text/plain",
            metadata={},
        )
        for i, url in enumerate(urls)
    ]

    llama_stack_client.tool_runtime.rag_tool.insert_documents(
        documents=documents,
        vector_db_id=vector_db_id,
        chunk_size_in_tokens=512,
    )

    # Query for the name of method
    response1 = llama_stack_client.vector_io.query(
        vector_db_id=vector_db_id,
        query="What's the name of the fine-tunning method used?",
    )
    assert_valid_response(response1)
    assert any("lora" in chunk.content.lower() for chunk in response1.chunks)

    # Query for the name of model
    response2 = llama_stack_client.vector_io.query(
        vector_db_id=vector_db_id,
        query="Which Llama model is mentioned?",
    )
    assert_valid_response(response2)
    assert any("llama2" in chunk.content.lower() for chunk in response2.chunks)
