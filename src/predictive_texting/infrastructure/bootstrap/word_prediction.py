# connect to DB
# run schema SQL
# create repository
# if repo is empty seed repo
# build encoder, store, completion index
# build service
# hydrate service
# return service

from __future__ import annotations

import sqlite3
from pathlib import Path

from ...application.word_prediction.config import WordPredictionConfig

# from ..db.seed_registry import load_seed_words


def _initialise_db(db_path: Path) -> Path:
    try:
        # connect to DB, create if does not exist
        conn = sqlite3.connect(db_path)

        # initialise schema

        cursor = conn.cursor()

    except sqlite3.Error as e:
        raise Exception() from e

    return Path.home()


def _build_repository() -> None:
    return


def _seed_repository() -> None:
    return


def _build_service() -> None:
    return


def bootstrap_word_prediction_service(config: WordPredictionConfig) -> None:
    return
