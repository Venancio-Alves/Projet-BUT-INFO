#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Vérifier les collections Qdrant pour IA"""

from qdrant_client import QdrantClient

client = QdrantClient('localhost', port=6333)
collections = client.get_collections()

print(f"📊 Collections Qdrant:")
for col in collections.collections:
    try:
        info = client.get_collection(col.name)
        print(f"  - {col.name}: {info.points_count} points")
    except:
        print(f"  - {col.name}: (impossible à récupérer)")
