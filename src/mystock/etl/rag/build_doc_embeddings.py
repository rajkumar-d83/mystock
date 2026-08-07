"""Builds the RAG store that grounds natural-language-to-SQL: embeds warehouse
documentation (docs/*.md) and schema metadata (metadata.tables/columns descriptions)
into metadata.doc_embeddings using a local model (sentence-transformers,
all-MiniLM-L6-v2, 384 dims — no cloud API key needed, see MYSTOCK_PRODUCT_SPEC.md §11).

The MCP server's search_docs() tool embeds a query with the same model and does a
cosine-similarity search against this table to retrieve relevant context before
generating SQL.

Chunking: markdown docs are split on level-2 headers (## ...), each section as one
chunk (further split on paragraph boundaries if still too long). Table/column metadata
becomes one short chunk per row — tables always included (existence + layer is useful
minimum context), columns only when they have a real description (an undescribed
column adds nothing beyond what describe_table() already shows directly).

Idempotent — clears and rebuilds each source_type on every run, since re-embedding a
small doc corpus is cheap and avoids stale-chunk bookkeeping.

Usage:
    python -m mystock.etl.rag.build_doc_embeddings
"""
import re
from pathlib import Path

import psycopg2.extras
from sentence_transformers import SentenceTransformer

from mystock.db import get_conn

DOCS_DIR = Path(__file__).resolve().parents[4] / "docs"
MODEL_NAME = "all-MiniLM-L6-v2"
MAX_CHUNK_CHARS = 1500


def split_markdown(text):
    """Splits on level-2 headers (## ...); further splits any resulting section over
    MAX_CHUNK_CHARS on paragraph boundaries."""
    sections = re.split(r"\n(?=## )", text)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= MAX_CHUNK_CHARS:
            chunks.append(section)
            continue
        heading_match = re.match(r"(##[^\n]*)\n", section)
        heading = heading_match.group(1) if heading_match else ""
        paragraphs = section.split("\n\n")
        buf = heading
        for para in paragraphs:
            if len(buf) + len(para) > MAX_CHUNK_CHARS and buf.strip() != heading.strip():
                chunks.append(buf.strip())
                buf = heading + "\n" + para
            else:
                buf += "\n\n" + para
        if buf.strip():
            chunks.append(buf.strip())
    return chunks


def load_markdown_chunks():
    chunks = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        text = path.read_text()
        for chunk in split_markdown(text):
            chunks.append((str(path.relative_to(DOCS_DIR.parent)), chunk))
    return chunks


def load_table_metadata_chunks(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT schema_name, table_name, layer, description FROM metadata.tables")
        rows = cur.fetchall()
    chunks = []
    for schema, table, layer, description in rows:
        ref = f"{schema}.{table}"
        text = f"Table {ref} (layer: {layer}). {description or 'No description on file.'}"
        chunks.append((ref, text))
    return chunks


def load_column_metadata_chunks(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT schema_name, table_name, column_name, data_type, is_nullable, description
               FROM metadata.columns WHERE description IS NOT NULL"""
        )
        rows = cur.fetchall()
    chunks = []
    for schema, table, col, dtype, nullable, description in rows:
        ref = f"{schema}.{table}.{col}"
        nullability = "nullable" if nullable else "not null"
        text = f"Column {ref} ({dtype}, {nullability}): {description}"
        chunks.append((ref, text))
    return chunks


def main():
    print(f"Loading embedding model {MODEL_NAME}...", flush=True)
    model = SentenceTransformer(MODEL_NAME)

    conn = get_conn()
    sources = {
        "markdown_doc": load_markdown_chunks(),
        "table_metadata": load_table_metadata_chunks(conn),
        "column_metadata": load_column_metadata_chunks(conn),
    }

    with conn.cursor() as cur:
        for source_type, chunks in sources.items():
            cur.execute("DELETE FROM metadata.doc_embeddings WHERE source_type = %s", (source_type,))
            if not chunks:
                continue
            texts = [text for _, text in chunks]
            embeddings = model.encode(texts, show_progress_bar=False)
            values = [
                (source_type, ref, text, emb.tolist())
                for (ref, text), emb in zip(chunks, embeddings)
            ]
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO metadata.doc_embeddings (source_type, source_ref, chunk_text, embedding)
                   VALUES %s""",
                values,
                template="(%s, %s, %s, %s::vector)",
            )
            print(f"{source_type}: {len(values)} chunks embedded", flush=True)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
